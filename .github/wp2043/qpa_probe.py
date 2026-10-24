"""WP-2043, temporary: the QPA guide's first fit and its esds, on the platform that runs it.

The fit is `examples/guides/qpa.py`'s first, copied so that 1.9.0, which has no
such guide, runs the same model. Fields a version lacks print as None.
"""

import json
import os
import platform
import sys

import numpy as np
import scipy

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "11BM_NAC.fxye")


def site(label, species, xyz, biso):
    x, y, z = (rx.Parameter(value=v) for v in xyz)
    return rx.Atom(label=label, species=species, x=x, y=y, z=z,
                   biso=rx.Parameter(value=biso, min=0.0, max=25.0))


def nac_and_fluorite():
    structure = rx.Structure.from_cif(examples_dir() / "cod_1000236.cif")
    structure.phases[0].name = "NAC"
    structure.phases.append(rx.Phase(
        name="CaF2", space_group="F m -3 m", cell=rx.Cell.cubic(5.4631),
        atoms=[site("Ca", "Ca2+", (0, 0, 0), 0.6), site("F", "F1-", (0.25, 0.25, 0.25), 0.9)]))
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    return rx.Refinement(structure, instrument)


result = nac_and_fluorite().fit(data, plan="mccusker_structural", two_theta_limits=(2, 24))
try:
    from rietx.optimize import lapack
    retries = lapack.retries()
except ImportError:
    retries = None

out = {
    "rietx": rx.__version__, "platform": platform.platform(), "machine": platform.machine(),
    "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
    "compiled_env": os.environ.get("RIETX_COMPILED", "default"),
    "lapack_retries_total": retries,
    "rwp": result.statistics.rwp,
    "esd_inflation": getattr(result.statistics, "esd_inflation", None),
    "qpa": [[r.name, r.weight_fraction, r.weight_fraction_stderr] for r in result.qpa.phases],
    "stages": [{k: getattr(s, k, None) for k in
                ("name", "status", "n_iterations", "cost_final", "n_lapack_fallbacks",
                 "held", "collapsed", "cell_reset", "released")} for s in result.stages],
    "parameters": [{"path": p.path, "value": p.value, "stderr": p.stderr,
                    "stderr_uncorrected": getattr(p, "stderr_uncorrected", None),
                    "at_bound": p.at_bound} for p in result.parameters],
    "diagnostics": sorted({d.code for d in result.diagnostics}),
}
for name, w, e in out["qpa"]:
    print(f"{name:<5} {100 * w:6.2f} ± {100 * e:.2f} wt%")
print("esd_inflation", out["esd_inflation"], "lapack retries", retries)
for p in out["parameters"]:
    if p["path"].startswith("phases.1.") or p["path"].endswith(".scale"):
        print(p)
with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=1, default=str)
