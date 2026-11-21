"""How far a fine-tuning nudge moves the preview's Rwp, against the offset.

Run from the repository root: ``.venv/bin/python docs/wp/2226-measure/nudge.py``.
"""
import os
import sys
import tempfile

import numpy as np

os.environ["RIETX_TELEMETRY"] = "0"
sys.path.insert(0, "docs/wp/2226-measure")
sys.argv = ["x", tempfile.mkdtemp()]
from measure import fitted, set_tol  # noqa: E402

from rietx.gui import preview  # noqa: E402

for name in ("fap", "nac"):
    p = fitted(name)
    fit = p.refinement.result_.statistics.rwp
    set_tol(p, None)
    v = preview._base(p).values
    fwhm = float(np.median(preview._base(p).model.phase_peaks(0, v)[0][1]))
    nudges = {"scale x1.01": {"phases.0.scale": v["phases.0.scale"] * 1.01},
              "zero +0.1 FWHM": {"instrument.zero_shift": v["instrument.zero_shift"] + 0.1 * fwhm}}
    for arm, tol in (("status quo", None), ("A", 0.02)):
        set_tol(p, tol)
        for label, edits in nudges.items():
            rwp = preview.evaluate(p, {"values": edits}).header["rwp"]
            print(name, arm, label, f"preview {100 * rwp:.3f} %  last fit {100 * fit:.3f} %"
                  f"  shown change {100 * (rwp - fit):+.3f} points")
