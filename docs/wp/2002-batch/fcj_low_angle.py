"""Check reader M's low-angle FCJ claim: shipped node count against 512 nodes.

Lab Bragg-Brentano, S/L = H/L = 0.025, FWHM 0.07 deg, eta 0.4.  Error is the
largest absolute difference over the profile, in units of the reference peak
maximum.  Also prints the node count the shipped rule picks and the count it
would pick uncapped.
"""
import numpy as np

import rietx.model.profiles.fcj as f
from rietx.model.profiles.fcj import fcj_extent_deg, fcj_node_count, fcj_offsets_weights
from rietx.model.profiles.pseudovoigt import pseudo_voigt


def composite(x, tt, fwhm, eta, sl, hl, n):
    phi, w = fcj_offsets_weights(tt, sl, hl, n)
    return (w[:, None] * pseudo_voigt(x[None, :] - np.asarray(phi)[:, None], fwhm, eta)).sum(0)


sl = hl = 0.025
fwhm, eta = 0.07, 0.4
for tt in (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0):
    n = fcj_node_count(tt, fwhm, sl, hl)
    ext = float(fcj_extent_deg(np.array(tt), sl, hl))
    uncapped = int(np.ceil(4.0 + f.NODES_PER_FWHM * ext / fwhm))
    x = np.arange(tt - ext - 6 * fwhm - 1, tt + ext + 6 * fwhm + 1, fwhm / 40)
    ref = composite(x, tt, fwhm, eta, sl, hl, 512)
    got = composite(x, tt, fwhm, eta, sl, hl, n)
    err = np.max(np.abs(got - ref)) / ref.max()
    got2 = composite(x, tt, fwhm, eta, sl, hl, max(n, min(uncapped, 512)))
    err2 = np.max(np.abs(got2 - ref)) / ref.max()
    print(f"2theta {tt:5.1f}  extent/FWHM {ext / fwhm:7.1f}  nodes {n:3d}  uncapped {uncapped:4d}"
          f"  err/peak {err:.1e}  uncapped err/peak {err2:.1e}")
