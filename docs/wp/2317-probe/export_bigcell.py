"""Write the bench's bigcell patterns and start models for the GSAS-II driver.

    .venv/bin/python docs/wp/2317-probe/export_bigcell.py WORKTREE WORKDIR

A measurement scaffold for ``gsas2_bigcell.py`` (WP-2317, cross-code timing).
xye: 2θ, counts, σ = √max(y, 1) (rietx's Poisson fallback, the weight its fit uses).
json: the start model in rietx units.

``bigcell-lebail`` exports its seeded 16-term background since 1d6677887.
The WP's GSAS-II Le Bail row ran from probe 1's unseeded six zeros, which
this script wrote at 896991fde.

Since the bench's cases moved to Nb₁₈W₁₆O₉₃ (COD 2107344, P b a m, mixed
sites), this script refuses them: the driver writes probe 1's space group
at full occupancy. The GSAS-II readings in the WP are probe 1's.
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

W, OUT = sys.argv[1], Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("bench_refinement",
                                              f"{W}/examples/bench_refinement.py")
bench = importlib.util.module_from_spec(spec)
sys.modules["bench_refinement"] = bench
spec.loader.exec_module(bench)

for key in ("bigcell-structural", "bigcell-pawley", "bigcell-pawley-120", "bigcell-lebail"):
    setup = {c.key: c for c in bench.CASES}[key].build()
    tt = np.asarray(setup.data.two_theta)
    y = np.asarray(setup.data.intensity)
    sig = np.asarray(setup.data.sig())
    assert np.allclose(sig, np.sqrt(np.maximum(y, 1.0)))
    np.savetxt(OUT / f"{key}.xye", np.column_stack([tt, y, sig]), fmt="%.6f %.1f %.6f")
    ph = setup.structure.phases[0]
    if ph.space_group != "P 21 21 21" or any(a.occ.value != 1.0 for a in ph.atoms):
        sys.exit(f"{key}: the bench's phase is {ph.space_group!r} with partial "
                 "sites, and gsas2_bigcell.py writes probe 1's P 21 21 21 at full "
                 "occupancy. Export from a checkout before the COD swap "
                 "(8ac51004f), or teach the driver the space group and occupancy.")
    ins = setup.instrument
    start = {
        "mode": setup.mode,
        "plan": [s.name for s in setup.plan.stages],
        "cell": [ph.cell.a.value, ph.cell.b.value, ph.cell.c.value],
        "atoms": [(a.label, a.species, a.x.value, a.y.value, a.z.value, a.biso.value)
                  for a in ph.atoms],
        "lor_size": ph.lor_size.value, "lor_strain": ph.lor_strain.value,
        "u": ins.profile.u.value, "v": ins.profile.v.value, "w": ins.profile.w.value,
        "x": ins.profile.x.value, "y": ins.profile.y.value,
        "axial_sl": ins.geometry.axial_sl.value, "axial_hl": ins.geometry.axial_hl.value,
        "zero": ins.zero_shift.value,
        "bkg": [c.value for c in ins.background.coefficients],
        "lines": [(ln.wavelength.value, ln.weight.value) for ln in ins.source.lines],
        "npoints": len(tt), "tt_min": float(tt[0]), "tt_max": float(tt[-1]),
    }
    (OUT / f"{key}.json").write_text(json.dumps(start, indent=1), encoding="utf-8")
    print(key, len(tt), start["cell"], len(start["atoms"]), "atoms", flush=True)
