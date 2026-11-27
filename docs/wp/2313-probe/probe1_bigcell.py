"""WP-2313 probe 1: where a 12 x 36 x 4 Å cell spends its time.

A measurement scaffold, not package code.  The cell, the space group and the
atoms are **invented** for a performance question: the atoms are drawn at a
fixed seed inside (0.05, 0.45) on general positions, the pattern is the truth
model Poisson-sampled, and the fit starts 500 ppm high on the cell with
generic widths.  Nothing it prints is a structural claim, and Rwp is an
identity check only.

    RIETX_TELEMETRY=0 .venv/bin/python -I docs/wp/2313-probe/probe1_bigcell.py \
        MODE SG TTMAX NATOMS

    MODE    rietveld | lebail | pawley
    SG      a space-group symbol, e.g. "P 21 21 21"
    TTMAX   2θ upper limit (deg), Cu Kα doublet, 0.02° steps from 5°
    NATOMS  general-position atoms in the asymmetric unit

    PLAN=mccusker_structural  the plan (default mccusker_default)
    REPORT=1                  also time ``Refinement.report()``
    PROFILE=0                 no cProfile (the profiled wall is inflated by
                              the profiler's per-call charge; quote the
                              unprofiled wall as the timing)

Run 2026-11-26/27 (linux x86_64, 4 cores, Python 3.12.3, numpy 2.5.5,
``[dev]`` venv, compiled tier on, rietx 1.13.0.dev0 at 4e099d68) — readings in
the WP-2313 file, Context.  The start carries the truth's atoms (the same
``POSITIONS``); only the cell, the widths and the background start off.
``MIN_SEP`` (Å, default 1.5) sets the closest approach of any two images.
"""
import os
import sys
import time
import cProfile
import pstats

import numpy as np
import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.crystallography.symmetry import generate_reflections

mode, sg, ttmax, natoms = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
PLAN = os.environ.get("PLAN", "mccusker_default")
PROFILE = os.environ.get("PROFILE", "1") != "0"
cell = (12.0, 36.0, 4.0, 90.0, 90.0, 90.0)
TT = np.arange(5.0, ttmax, 0.02)


def p(v, **kw):
    return rx.Parameter(value=v, **kw)


species = ["Mo", "O", "O", "O", "C", "N"]
MIN_SEP = float(os.environ.get("MIN_SEP", "1.5"))     # Å, between any two images


def _positions(seed: int = 0) -> list[tuple[float, float, float]]:
    """Asymmetric-unit sites drawn over the whole cell, every symmetry image of
    every site at least ``MIN_SEP`` from every other (rejection sampling).

    The first version drew inside (0.05, 0.45)³, a 1/15.6 sub-box: at 40 atoms
    65 % of nearest neighbours sat under 1 Å, a non-physical model (WP-2313
    review, S3).
    """
    import gemmi
    ops = list(gemmi.SpaceGroup(sg).operations())
    G = np.diag(np.array(cell[:3]) ** 2)              # orthogonal cells only
    r = np.random.default_rng(seed)
    images: list[np.ndarray] = []
    out: list[tuple[float, float, float]] = []
    tries = 0
    while len(out) < natoms:
        tries += 1
        if tries > 200_000:
            raise RuntimeError(f"cannot place {natoms} atoms {MIN_SEP} Å apart")
        x = r.uniform(0.0, 1.0, 3)
        imgs = np.array([np.mod(op.apply_to_xyz(list(x)), 1.0) for op in ops])
        cand = np.vstack(images + [imgs]) if images else imgs
        # every pair among the new images and against the placed ones, minimum image
        d = imgs[:, None, :] - cand[None, :, :]
        d -= np.round(d)
        dist = np.sqrt(np.einsum("ijk,kl,ijl->ij", d, G, d))
        n_new = len(imgs)
        dist[np.arange(n_new), len(cand) - n_new + np.arange(n_new)] = np.inf
        if np.all(dist >= MIN_SEP):
            images.append(imgs)
            out.append(tuple(float(v) for v in x))
    return out


POSITIONS = _positions()


def phase(drift):
    f = 1 + drift
    atoms = [rx.Atom(label=f"A{i}", species=species[i % len(species)],
                     x=p(xyz[0]), y=p(xyz[1]), z=p(xyz[2]),
                     biso=p(1.0, min=0.0, max=25.0))
             for i, xyz in enumerate(POSITIONS)]
    return rx.Phase(name="big", space_group=sg,
                    cell=rx.Cell(a=p(12.0 * f, min=1.0), b=p(36.0 * f, min=1.0),
                                 c=p(4.0 * f, min=1.0), alpha=p(90.0), beta=p(90.0),
                                 gamma=p(90.0)),
                    atoms=atoms, scale=p(1e-4, min=0.0),
                    lor_size=p(0.03, min=0.0), lor_strain=p(0.0, min=0.0))


def instrument(truth):
    from rietx.schemas.instrument import BackgroundChebyshev
    ins = rx.Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=250.0,
                                       monochromator_two_theta=26.6)
    ins.background = BackgroundChebyshev.with_terms(6)
    ins.source.dispersion = None    # declared, so a default move cannot move the timing
    ins.geometry.axial_sl.value = 0.03 if truth else 0.02
    ins.geometry.axial_hl.value = 0.03 if truth else 0.02
    ins.profile.w.value = 0.006 if truth else 0.010
    ins.profile.x.value = 0.02 if truth else 0.01
    if truth:
        ins.background.coefficients[0].value = 900.0
    return ins


rs = generate_reflections(sg, cell, 1.5406, ttmax)
print(f"SG {sg}  2theta<= {ttmax}  points {len(TT)}  unique reflections "
      f"{len(rs.hkl)}  atoms {natoms}  plan {PLAN}")

truth = rx.Structure(phases=[phase(0.0)])
blank = rx.PatternData(two_theta=TT.tolist(), intensity=np.ones_like(TT).tolist())
m = compile_model(truth, instrument(True), blank)
tab = ParameterTable(truth, instrument(True))
vals = tab.decode(tab.x0())
y = np.asarray(m.evaluate(vals))
t0 = time.perf_counter()
for _ in range(5):
    m.evaluate(vals)
print(f"one forward evaluation (warm): {(time.perf_counter() - t0) / 5 * 1e3:.0f} ms")
counts = np.random.default_rng(1).poisson(np.clip(y, 1.0, None)).astype(float)
data = rx.PatternData(two_theta=TT.tolist(), intensity=counts.tolist())

start = rx.Structure(phases=[phase(5e-4)])
ref = rx.Refinement(start, instrument(False))
pr = cProfile.Profile() if PROFILE else None
t0 = time.perf_counter()
if pr:
    pr.enable()
res = ref.fit(data, mode=mode, plan=PLAN)
if pr:
    pr.disable()
wall = time.perf_counter() - t0
print(f"fit mode={mode}: wall {wall:.1f} s{' (profiled)' if pr else ''}  "
      f"Rwp {res.statistics.rwp:.4f}")
for st in res.stages:
    print(f"  stage {st.name:<22} n_iter {st.n_iterations:>4}  "
          f"n_freed {len(st.freed)}  status {st.status}")
if pr:
    pstats.Stats(pr).sort_stats("cumulative").print_stats(28)
if os.environ.get("REPORT"):
    t0 = time.perf_counter()
    ref.report()
    print(f"report(): {time.perf_counter() - t0:.1f} s")
