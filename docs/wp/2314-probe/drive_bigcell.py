"""WP-2314 measurement driver: WP-2317 probe 1 run as ``bigcell-structural``.

A measurement scaffold, not package code.  It runs the probe at 40 atoms,
P2₁2₁2₁, 2θ ≤ 90°, ``mccusker_structural``, and prints a digest of the
result's 296 values and esds, so two arms can be compared bit for bit.

    RIETX_TELEMETRY=0 [PYTHONPATH=<main snapshot>/src] .venv/bin/python \
        docs/wp/2314-probe/drive_bigcell.py ARM PROBE MODE

    ARM     a label for the log
    PROBE   path to probe1_bigcell.py (the snapshot's own, for main)
    MODE    time     unprofiled wall (the probe prints it) and the digest
            verify   also hashes every Jacobian of the fit in order and counts
                     ``_orbit_terms`` calls per Jacobian
            profile  the probe's cProfile split

The "main" arm is a ``git archive`` of ``origin/main`` (``src`` and
``docs/wp/2317-probe``) unpacked to a scratch directory and put first on
``PYTHONPATH``; never ``python -I``, which ignores it.  Check the printed
``rietx`` path.  Interleave the arms (main, branch, main, …), three ``time``
runs each, under the machine's suite lock.  Readings: the WP-2314 file's
handover log.
"""
import hashlib
import os
import runpy
import sys

arm, probe, mode = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["PLAN"] = "mccusker_structural"
os.environ["PROFILE"] = "1" if mode == "profile" else "0"

import rietx  # noqa: E402

print(f"arm {arm}  rietx {rietx.__file__}")
jac_digest = hashlib.sha256()
jac_calls = [0]
orbit_per_jac: list[int] = []
if mode == "verify":
    from rietx.crystallography import structure_factor as SF
    from rietx.optimize import least_squares as LS
    calls = [0]
    real_terms = SF._orbit_terms

    def counting(*a, **k):
        calls[0] += 1
        return real_terms(*a, **k)

    SF._orbit_terms = counting
    real_make = LS._make_jacobian

    def make(*a, **k):
        inner = real_make(*a, **k)

        def jacobian(theta):
            calls[0] = 0
            J = inner(theta)
            orbit_per_jac.append(calls[0])
            jac_calls[0] += 1
            jac_digest.update(J.tobytes())
            return J
        return jacobian

    LS._make_jacobian = make

sys.argv = [probe, "rietveld", "P 21 21 21", "90", "40"]
g = runpy.run_path(probe, run_name="__main__")
res = g["res"]
h = hashlib.sha256()
for p in res.parameters:
    h.update(p.path.encode())
    h.update(float(p.value).hex().encode())
    h.update(("none" if p.stderr is None else float(p.stderr).hex()).encode())
print(f"result digest {h.hexdigest()[:16]}  rwp {res.statistics.rwp!r}  "
      f"n_params {len(res.parameters)}")
if mode == "verify":
    import numpy as np
    o = np.array(orbit_per_jac)
    print(f"jacobians {jac_calls[0]}  digest {jac_digest.hexdigest()[:16]}  "
          f"_orbit_terms per jacobian min {o.min()} median {int(np.median(o))} "
          f"max {o.max()}  total {o.sum()}")
