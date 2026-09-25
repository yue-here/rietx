# rietx

[![CI](https://github.com/yue-here/rietx/actions/workflows/ci.yml/badge.svg)](https://github.com/yue-here/rietx/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/rietx)](https://pypi.org/project/rietx/)

**`rietx`** is an open-source Rietveld refinement and pattern analysis Python module with a streamlined API designed for those who want to drive refinements from code.

## Installation

```sh
pip install rietx            # Python >= 3.11; numpy/scipy core, compiled kernels on
pip install "rietx[viz]"     # + matplotlib figures
```

## Example refinement

Condensed from [`examples/nac_11bm.py`](https://github.com/yue-here/rietx/blob/main/examples/nac_11bm.py),
which fits APS 11-BM synchrotron data on Na₂Ca₃Al₂F₁₄ with a CaF₂ impurity.

```python
import rietx as rx

data = rx.read_pattern("11BM_NAC.fxye")              # esd column read from file
structure = rx.Structure.from_cif("cod_1000236.cif")
instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)

ref = rx.Refinement(structure, instrument)

# structure-free Le Bail first: cell + profile + background
lebail = ref.fit(data, mode="lebail", two_theta_limits=(2, 24))

# then Rietveld under the staged turn-on order of McCusker et al. (1999)
result = ref.fit(data, plan="mccusker_default", two_theta_limits=(2, 24))

report = rx.build_report(result)                     # numbers, not pixels
result.plot(path="fit.png")                          # obs/calc/diff/ticks
```

Output of the full script (trimmed at the `…`):

```text
Le Bail:  status=converged  Rwp=0.1435  GoF=5.44  a=10.251214 A
Rietveld: status=converged  Rwp=0.0933  GoF=3.54
          a = 10.251216 +/- 0.000046 A (COD reference 10.257(1); high-accuracy powder ~10.2497-10.2506)
          [warning] BOUND_HIT: phases.1.atoms.0.biso refined to its bound
          [info] CAPILLARY_OFFSET_UNAVAILABLE: this capillary geometry declares no goniometer radius, …

FitReport: Rwp=0.0933 GoF=3.54; 53 regions, top 15 shown (74% of χ²); 53 unmatched observed peak(s); …
  region  14.22- 14.54 deg  localRwp=0.154  chi2share=13.6%  max|d/sig|=49.5
  …

Refinement history (every stage is a restorable checkpoint):
t5544a638  13 nodes  data=11BM_NAC.fxye
 n0000  root                   —
└─  n0001  stage:bkg              Rwp 3.1772
   …
                                 └─ *n0012  stage:biso             Rwp 0.0933
```

## Current features

- Multi-phase Rietveld, Le Bail and Pawley
- X-ray and constant-wavelength [neutron](https://rietx.org/using/data.html#a-neutron-source) data
- Preset [staged plans](https://rietx.org/using/concepts.html#refinement-plans)
- Extensively documented [forward model](https://rietx.org/forward-model.html)
- [Multiple solvers](https://rietx.org/estimation.html#solvers)
- Optional [JAX & torch differentiable backends](https://rietx.org/using/install.html#optional-extras) 
- [Readers](https://rietx.org/using/files.html) for many standard formats including
  `.xy`/`.xye`, GSAS raw, pdCIF, `.chi`, Rigaku `.ras`/`.rasx`, Bruker
  `.uxd`/`.brml`/`.raw`, PANalytical `.xrdml`/`.udf` and Philips `.rd`/`.sd`
- [Another program's refinement, read in](https://rietx.org/using/files.html#refinement-files-another-program-wrote):
  `read_project_model` opens a TOPAS `.inp` or a FullProf `.pcr` by content,
  refine flags included
- The [`FitReport`](https://rietx.org/using/report.html), an output bundle designed for agentic consumption. 
- A git-style branchable [refinement history](https://rietx.org/using/history.html)
- [Sequential refinements](https://rietx.org/using/series.html)
- [Indexing](https://rietx.org/using/indexing.html), and
  [peaks fitted on their own](https://rietx.org/using/indexing.html#fitting-peaks-you-name)
  at positions you name, with no structure at all
- [Declared extra peaks and humps](https://rietx.org/using/model.html#declared-extra-peaks):
  a sample holder or an unidentified line stays in the fit instead of being
  excluded along with the sample peaks underneath it
- [Extensive agentic surface](https://rietx.org/using/agents.html)
- [PowderLine recipe interchange](https://rietx.org/using/recipe.html): read a
  pipeline's recipe, write its four tables back
- [GUI mode](https://rietx.org/using/gui-quickstart.html) `rietx gui`

## Validation

Validation suites are run in CI against real data. Details here: [docs/VALIDATION.md](https://github.com/yue-here/rietx/blob/main/docs/VALIDATION.md)

## Documentation

- HTML manual: https://rietx.org/manual.html (https://rietx.org/ is the project page)
- Driving instructions for agents: the [agent skill](https://rietx.org/skill/rietx/SKILL.md)
  (`rietx skill --install` puts it where your harness looks)

## Development

```sh
git clone https://github.com/yue-here/rietx && cd rietx
uv venv --python 3.12 && uv pip install -e ".[dev]"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # ~1-3 min
.venv/bin/python -m pytest -n auto --dist loadgroup                 # + real-data acceptance, ~15-30 min
.venv/bin/python -m ruff check src tests examples
```

`--dist loadgroup` is required to keep shared expensive fixtures on one
worker. For the test ladder and style see
[CONTRIBUTING.md](https://github.com/yue-here/rietx/blob/main/CONTRIBUTING.md), and [AGENTS.md](https://github.com/yue-here/rietx/blob/main/AGENTS.md) if your
contributor is an agent.

## License and credits

MIT. Algorithms are independently implemented from the published literature, with sources cited in the manual. A full list of sources is also provided in
[ATTRIBUTION.md](https://github.com/yue-here/rietx/blob/main/ATTRIBUTION.md).
and test-data provenance is listed in
[tests/data/README.md](https://github.com/yue-here/rietx/blob/main/tests/data/README.md).
CIF and symmetry handling uses
[gemmi](https://github.com/project-gemmi/gemmi). To cite the package, use
[CITATION.cff](https://github.com/yue-here/rietx/blob/main/CITATION.cff).
