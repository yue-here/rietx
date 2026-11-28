"""Does the 1e-12 nudge change which atoms the bigcell fixture ties (co_sited rounds to 1e-4)?"""
import os
import sys

os.environ["RIETX_TELEMETRY"] = "0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run2  # noqa: E402

run2._setup()
import numpy as np  # noqa: E402
import single  # noqa: E402
from test_large_cell_refinement import co_sited  # noqa: E402

for seed in [None, 0, 1, 2, 3, 4, 6, 10]:
    s, i, d, plan, kw, prep = single.FIXTURES["bigcell"]()
    if seed is not None:
        rng = np.random.default_rng(seed)
        single.nudge(s, rng)
        single.nudge(i, rng)
    ph = s.phases[0]
    pairs = co_sited(ph)
    a23, a27 = ph.atoms[23], ph.atoms[27]
    print(seed, len(pairs), [p for p in pairs if 27 in p or 23 in p],
          f"O23 ({a23.x.value!r}, {a23.y.value!r}) O27 ({a27.x.value!r}, {a27.y.value!r})",
          a23.label if hasattr(a23, "label") else "", a27.label if hasattr(a27, "label") else "")
