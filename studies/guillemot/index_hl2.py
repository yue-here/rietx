"""A small pair-seeded autoindexer, used only for HL2-1 (the one pattern in the
collection with no accompanying .inp, no formula and no sample metadata).

Method: for a two-parameter metric (cubic / tetragonal / hexagonal in Q =
A*M + C*l^2 form) every pair of observed Q values plus a pair of trial hkl
indices determines (A, C) exactly.  Enumerate those, keep positive solutions,
and score each candidate by how much of the observed *intensity* it indexes.
Degenerate seeds are cheap, so a coarse enumeration covers the space
exhaustively rather than heuristically.
"""
from __future__ import annotations

import itertools

import numpy as np
from common import EX
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import find_peaks

import pxrdref as pr

LAM = 1.540596


def peak_list(path, *, lo=5.0, hi=90.0, prom_frac=0.010):
    d = pr.read_pattern(path).crop(lo, hi)
    tt, y = d.tt(), d.y()
    bkg = uniform_filter1d(minimum_filter1d(y, 201), 201)
    net = y - bkg
    pk, props = find_peaks(net, prominence=net.max() * prom_frac, distance=5)
    # parabolic refinement of each maximum
    pos = []
    for i in pk:
        y0, y1, y2 = net[i - 1], net[i], net[i + 1]
        denom = y0 - 2 * y1 + y2
        shift = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
        step = tt[i + 1] - tt[i]
        pos.append(tt[i] + shift * step)
    return (np.asarray(pos), np.asarray(props["prominences"]),
            tt, y, net, bkg)


def q_of(tt_deg, lam=LAM, zero=0.0):
    d = lam / (2 * np.sin(np.radians((tt_deg - zero) / 2)))
    return 1.0 / d**2


#: (M, l) generators.  M is the in-plane invariant: h^2+hk+k^2 (hexagonal),
#: h^2+k^2 (tetragonal), h^2+k^2 (cubic uses M+l^2 directly).
def m_values(system, mmax=16):
    out = set()
    for h in range(0, 5):
        for k in range(0, 5):
            m = h * h + h * k + k * k if system == "hex" else h * h + k * k
            if 0 < m <= mmax:
                out.add(m)
    return sorted(out)


def candidates(q, weights, system, *, mmax=16, lmax=8, tol=0.004, n_seed=9):
    """Every (A, C) determined by two seed peaks and two trial (M, l) labels."""
    Ms = m_values(system, mmax)
    labels = [(m, ll) for m in [0] + Ms for ll in range(0, lmax + 1)
              if (m, ll) != (0, 0)]
    seeds = np.argsort(weights)[::-1][:n_seed]
    found = {}
    for i, j in itertools.combinations(sorted(seeds.tolist()), 2):
        for (m1, l1), (m2, l2) in itertools.product(labels, repeat=2):
            det = m1 * (l2 * l2) - m2 * (l1 * l1)
            if det == 0:
                continue
            A = (q[i] * l2 * l2 - q[j] * l1 * l1) / det
            C = (m1 * q[j] - m2 * q[i]) / det
            if A <= 1e-6 or C <= 1e-6 or A > 0.25 or C > 0.25:
                continue
            key = (round(A, 5), round(C, 5))
            if key in found:
                continue
            found[key] = score(q, weights, A, C, Ms, lmax, tol)
    return found


def score(q, weights, A, C, Ms, lmax, tol):
    grid = np.array(sorted({A * m + C * ll * ll
                            for m in [0] + list(Ms) for ll in range(lmax + 1)}
                           - {0.0}))
    if grid.size == 0:
        return 0.0, 0
    diff = np.abs(q[:, None] - grid[None, :]).min(axis=1)
    ok = diff < tol * q                       # relative tolerance in Q
    return float(weights[ok].sum() / weights.sum()), int(ok.sum())


def report(name, path, system_list=("cubic", "tet", "hex"), top=6):
    pos, prom, *_ = peak_list(path)
    q = q_of(pos)
    print(f"\n===== {name}: {len(pos)} peaks =====")
    for system in system_list:
        if system == "cubic":
            # one parameter: Q = A*(h^2+k^2+l^2)
            best = []
            Ns = sorted({h * h + k * k + ll * ll
                         for h in range(6) for k in range(6) for ll in range(6)}
                        - {0})
            for i in np.argsort(prom)[::-1][:9]:
                for n in Ns:
                    A = q[i] / n
                    if A <= 1e-6:
                        continue
                    grid = np.array([A * m for m in Ns])
                    diff = np.abs(q[:, None] - grid[None, :]).min(axis=1)
                    ok = diff < 0.004 * q
                    best.append((prom[ok].sum() / prom.sum(), int(ok.sum()),
                                 1 / np.sqrt(A), None))
            best = sorted({(round(b[2], 4),): b for b in best}.values(),
                          reverse=True)[:top]
            for f, n, a, _ in best:
                print(f"  cubic   a={a:8.4f}          indexes {f:5.1%} of "
                      f"intensity, {n:2d}/{len(q)} peaks")
        else:
            found = candidates(q, prom, "hex" if system == "hex" else "tet")
            best = sorted(found.items(), key=lambda kv: -kv[1][0])[:top]
            for (A, C), (f, n) in best:
                a = np.sqrt(4 / (3 * A)) if system == "hex" else 1 / np.sqrt(A)
                c = 1 / np.sqrt(C)
                print(f"  {system:7s} a={a:8.4f} c={c:8.4f}  indexes {f:5.1%} "
                      f"of intensity, {n:2d}/{len(q)} peaks")


if __name__ == "__main__":
    report("HL2-1", EX / "HL2-1" / "HL2-1_2.xy")
    # sanity: the same machinery on a pattern whose answer is known
    report("MnSb_34 (control)", EX / "MnSb_34_impure" / "MnSb_34.xy")
