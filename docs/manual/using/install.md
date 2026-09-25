# Installation

`rietx` needs Python 3.11 or newer and installs from PyPI. Install it into a
virtual environment: `numba` carries an upper bound on `numpy`, which is easier
to satisfy per project than across one shared environment.

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
was built from. [](quickstart.md) is the first refinement.

## Requirements

| Requirement | Purpose |
|---|---|
| Python ≥ 3.11 | |
| `numpy` ≥ 1.26 | the fp64 arrays the core computes in |
| `scipy` ≥ 1.11 | the trust-region least-squares solver |
| `pydantic` ≥ 2.6 | the schemas: validation, defaults, JSON round-trip |
| `gemmi` ≥ 0.6.5 | CIF reading, space groups, symmetry operations |
| `spglib` ≥ 2.4 | site symmetry, Wyckoff positions, cell reduction |
| `numba` ≥ 0.63 | compiles the peak kernels ({ref}`the-compiled-kernels`) |

Those six are the whole install, and nothing in that list is optional or
lazily imported. It reads patterns and CIFs, applies every correction, runs the
staged refinement machinery, builds the report, indexes an unknown cell, and
keeps projects and history.

## Optional extras

No extra changes a refined number. Name one in brackets to install it, quoting
the argument because `zsh` reads bare brackets as a glob:

```sh
pip install "rietx[viz]"           # one extra
pip install "rietx[viz,jax]"       # several, comma-separated, no spaces
uv pip install -e ".[dev]"         # from a source checkout
```

| Extra | Installs | Purpose |
|---|---|---|
| `viz` | matplotlib | Plots. `RefinementResult.plot` and the report figures need it. The interactive page `viz.html.write_html` writes does not. |
| `gui` | nothing | Empty, and kept so an existing `rietx[gui]` install line still works. The refinement GUI, `rietx gui`, runs on a base install. Its built front end is committed inside the package with every library it draws with. |
| `jax` | jax | The `backend="jax"` Jacobian (`jacfwd`, chunked). |
| `torch` | torch | Experimental. `backend="torch"` (CPU fp64) and `backend="torch-mps"` (Apple GPU, necessarily fp32). About 500 MB, and slower than numpy on this hardware. It buys an independent opinion in the Jacobian-agreement matrix, and the forward model as a differentiable layer. It does not buy speed. |
| `docs` | sphinx, myst-parser, sphinxcontrib-bibtex, sphinx-design, furo | Builds this manual. |
| `dev` | the `docs` and `viz` extras, pytest, pytest-xdist, hypothesis, ruff | The test suite. |

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

The first process on a machine pays a 0.6 s compile, and every later one pays
0.12 s to load the result from `~/.rietx/numba-cache` (or from
`$RIETX_STATE_DIR` if that is set). Most of even that overlaps with other work:
the compile starts on a background thread when the model is compiled, and runs
while the file is read and the parameter table is built.

Turn the kernels off with `RIETX_COMPILED=0`, which needs no reinstall. Every
kernel has the numpy expression it replaces standing behind it, so refinements
run correctly, only slower. Use it on a machine where the compiler misbehaves,
or for a run that has to reproduce another one exactly.

```sh
RIETX_COMPILED=0 python my_refinement.py
```

For a smaller install, leave `numba` out altogether and take the numpy path
permanently. It is 157 MB of the install, 137 MB of that `llvmlite`, against a
124 MB baseline:

```sh
pip install --no-deps rietx
pip install numpy scipy pydantic gemmi spglib
```

`capabilities().features` answers the two questions separately, because they can
disagree: `compiled_kernels` is whether `numba` imports here, and
`compiled_kernels_active` is whether the next refinement will use it.

```python
from rietx import capabilities

caps = capabilities()
caps.features["compiled_kernels"]
caps.features["compiled_kernels_active"]
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
that produced it can never disagree about it.

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

`zsh: no matches found: rietx[viz]`. `zsh` expanded the brackets as a glob.
Quote the argument: `pip install "rietx[viz]"`.

`rietx.__version__` reads `0.0.0+dev`. No distribution of that name is
installed, and what you imported is a source checkout sitting on `sys.path`
ahead of its own install. Install it (`uv pip install -e .`) before refining
anything: that string is stamped into the provenance of every result, every
history tree and every project file the session writes.

`pip` cannot find a version of `numba` for your `numpy`. `numba` carries an
upper bound on `numpy` (`numpy<2.6` as of `numba` 0.63), so a very new numpy has
to wait for a `numba` that admits it. Either pin numpy below the ceiling in this
environment, or install without `numba` as above and run the numpy path.

## Validation and accuracy claims

[`docs/VALIDATION.md`](https://github.com/yue-here/rietx/blob/main/docs/VALIDATION.md)
tabulates every real-data assertion in the repository and says what each
tolerance is referenced to. It is generated from the suite, so it is the
accuracy claim, and nothing in this manual restates it.

It opens with the rule to read it under: judge a correction by what it changed,
never by ΔRwp. Of the eight corrections in v0.5, two provably cannot move Rwp,
one moves it the wrong way when it is right, and the two largest accuracy wins
are invisible in it.
