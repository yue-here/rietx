# WPEM benchmark — `pxrdref` against arXiv 2602.16372

Benchmark of `pxrdref` (structural Rietveld + agentic refinement) against
**WPEM** / PyXplore on the datasets published with *"AI-Driven Structure
Refinement of X-ray Diffraction"* (Cao et al., arXiv:2602.16372).

The findings are in **[REPORT.md](REPORT.md)**. This file is the how-to-run.

## Layout

```
fetch_cifs.py     retrieve every structural model from COD (WPEM ships none)
insitu_io.py      read the operando .xlsx series without a spreadsheet dep
bench.py          shared harness: comparable statistics, plans, fixed-point loop
run_<case>.py     one script per benchmark case
summarize.py      collect results/*.json into the REPORT.md tables
data/             downloaded WPEM CASES patterns and reference outputs (not committed)
cifs/             structures retrieved from COD (not committed)
results/<case>.json   machine-readable result per case
output/*.png      obs/calc/diff plots and zooms (gitignored)
logs/             run logs
```

## Reproduce

```sh
# 1. fetch the data (WPEM CASES) and the structures (COD)
.venv/bin/python studies/wpem_bench/fetch_data.py
.venv/bin/python studies/wpem_bench/fetch_cifs.py

# 2. run the cases — from inside studies/wpem_bench (the scripts import bench.py)
cd studies/wpem_bench
../../.venv/bin/python run_pbso4.py
../../.venv/bin/python run_tb2bacoo5.py
../../.venv/bin/python run_nacl_li2co3.py
../../.venv/bin/python run_ti15nb.py
../../.venv/bin/python run_egypt.py
../../.venv/bin/python run_mnru.py
../../.venv/bin/python run_insitu.py

# 3. tables
../../.venv/bin/python summarize.py
```

Run them one at a time: several of these hold the full Jacobian for a
6000-point, multi-phase model, and four concurrently was enough to get one
OOM-killed on a 26 GB machine.

## The one thing to know before reading any number

WPEM's published fits contain **no atomic structure**. Every case notebook
passes only `Lattice_constants`, and `WPEM.XRDfit` gives each of the (383, 131,
…) reflections its own free `(γ, σ, Δ, w)`. It is a whole-pattern
*decomposition* — the Le Bail/Pawley family — not a Rietveld refinement, and
its parameter count scales with the reflection list.

Its agreement factors are nonetheless directly comparable, which is worth
stating precisely because it is not obvious. From
`PyXplore/EMBraggOpt/EMBraggSolver.py`:

```python
p_error.append(float(abs(y[j] - i_obser[j])))
wp_error.append((p_error[j] ** 2) / max(float(i_obser[j]), 1))
Rp.append(p_error_sum / obs * 100)
Rwp.append(np.sqrt(wp_error_sum / obs) * 100)
```

with `obs = sum(i_obser)` and `i_obser` the **raw** pattern. Substituting
Poisson weights w = 1/max(y,1) into the textbook definition gives
Σ w·y² = Σ y, so this is exactly the conventional Rietveld Rwp/Rp — the same
numbers `pxrdref`'s `Statistics` reports, on the same raw profile with the
background modelled rather than subtracted.
