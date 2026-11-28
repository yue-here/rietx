"""WP-2316 task 1: why Le Bail lands at three times Pawley's Rwp on probe 1.

A measurement scaffold, not package code.  The pattern is WP-2317 probe 1's
(``docs/wp/2317-probe/probe1_bigcell.py``), rebuilt here with the same seeds:
12 × 36 × 4 Å, P2₁2₁2₁, invented atoms, Cu Kα doublet + FCJ, Poisson counts on
a flat 900-count background, the start 500 ppm high on the cell with generic
widths.  Nothing it prints is a structural claim.

    RIETX_TELEMETRY=0 .venv/bin/python -I docs/wp/2316-probe/diag_gap.py STEP OUT

    STEP  fits     Pawley and Le Bail from probe 1's start (mccusker_default)
          cross    the partition at each answer's fixed parameters, from flat
                   and from the other answer's intensities
          swap     Le Bail started from Pawley's answer, and Pawley from Le Bail's
          compare  the two answers' values, background, banded Rwp and per-hkl
                   intensities side by side
          seeded   Le Bail (and Pawley) with the background seeded first, the
                   skill's rule (SKILL.md §2 rule 5)
          truth    the generating model's Rwp, and the partition at its parameters
          degenerate  the b = 3a coincidences, and the partition at truth and
                   Pawley's answer with the cell split and restored
          plots    obs/calc/diff PNGs of every fit
    OUT   a directory for the saved answers, logs and PNGs

    TTMAX=90 NATOMS=10   probe 1's arguments (2θ ≤ 90°, 899 reflections)
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable

step, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
SG = "P 21 21 21"
TTMAX = float(os.environ.get("TTMAX", "90"))
NATOMS = int(os.environ.get("NATOMS", "10"))
CELL = (12.0, 36.0, 4.0, 90.0, 90.0, 90.0)
TT = np.arange(5.0, TTMAX, 0.02)
SPECIES = ["Mo", "O", "O", "O", "C", "N"]
MIN_SEP = 1.5


def p(v, **kw):
    return rx.Parameter(value=v, **kw)


def _positions(seed=0):
    """Probe 1's rejection sampler, unchanged (every image ≥ MIN_SEP apart)."""
    import gemmi
    ops = list(gemmi.SpaceGroup(SG).operations())
    G = np.diag(np.array(CELL[:3]) ** 2)
    r = np.random.default_rng(seed)
    images, out = [], []
    while len(out) < NATOMS:
        x = r.uniform(0.0, 1.0, 3)
        imgs = np.array([np.mod(op.apply_to_xyz(list(x)), 1.0) for op in ops])
        cand = np.vstack(images + [imgs]) if images else imgs
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
    atoms = [rx.Atom(label=f"A{i}", species=SPECIES[i % len(SPECIES)],
                     x=p(xyz[0]), y=p(xyz[1]), z=p(xyz[2]),
                     biso=p(1.0, min=0.0, max=25.0))
             for i, xyz in enumerate(POSITIONS)]
    return rx.Phase(name="big", space_group=SG,
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
    ins.source.dispersion = None
    ins.geometry.axial_sl.value = 0.03 if truth else 0.02
    ins.geometry.axial_hl.value = 0.03 if truth else 0.02
    ins.profile.w.value = 0.006 if truth else 0.010
    ins.profile.x.value = 0.02 if truth else 0.01
    if truth:
        ins.background.coefficients[0].value = 900.0
    return ins


def data():
    truth = rx.Structure(phases=[phase(0.0)])
    blank = rx.PatternData(two_theta=TT.tolist(), intensity=np.ones_like(TT).tolist())
    m = compile_model(truth, instrument(True), blank)
    tab = ParameterTable(truth, instrument(True))
    y = np.asarray(m.evaluate(tab.decode(tab.x0())))
    bkg = np.asarray(m.background(tab.decode(tab.x0())))
    counts = np.random.default_rng(1).poisson(np.clip(y, 1.0, None)).astype(float)
    return rx.PatternData(two_theta=TT.tolist(), intensity=counts.tolist()), y, bkg


DATA, Y_TRUE, BKG_TRUE = data()
YO = np.asarray(DATA.intensity)
W = 1.0 / np.maximum(YO, 1.0)            # the Poisson fallback the fit uses (no esd column)


def rwp(yc, mask=None):
    m = np.ones_like(YO, bool) if mask is None else mask
    return float(np.sqrt((W[m] * (YO[m] - yc[m]) ** 2).sum() / (W[m] * YO[m] ** 2).sum()))


def keyed(model):
    cp = model.phases[0]
    return {tuple(int(v) for v in h): float(i)
            for h, i in zip(cp.reflections.hkl, cp.hkl_intensity, strict=True)}


def save(tag, ref, res, wall):
    (OUT / f"{tag}.result.json").write_text(res.model_dump_json())
    (OUT / f"{tag}.structure.json").write_text(ref.structure.model_dump_json())
    (OUT / f"{tag}.instrument.json").write_text(ref.instrument.model_dump_json())
    inten = keyed(ref._model)
    (OUT / f"{tag}.intensities.json").write_text(
        json.dumps([[list(k), v] for k, v in inten.items()]))
    rows = {"tag": tag, "wall_s": wall, "rwp": res.statistics.rwp,
            "stages": [[s.name, s.rwp, s.n_iterations] for s in res.stages],
            "codes": sorted({d.code for d in res.diagnostics}),
            "values": {q.path: q.value for q in res.parameters}}
    (OUT / f"{tag}.summary.json").write_text(json.dumps(rows, indent=1))
    print(json.dumps({k: rows[k] for k in ("tag", "wall_s", "rwp", "stages", "codes")}))


def fit(tag, mode, structure, ins):
    ref = rx.Refinement(structure, ins)
    t0 = time.perf_counter()
    res = ref.fit(DATA, mode=mode, plan="mccusker_default")
    save(tag, ref, res, time.perf_counter() - t0)


def load(tag):
    s = rx.Structure.model_validate_json((OUT / f"{tag}.structure.json").read_text())
    i = rx.Instrument.model_validate_json((OUT / f"{tag}.instrument.json").read_text())
    inten = {tuple(k): v for k, v in json.loads((OUT / f"{tag}.intensities.json").read_text())}
    return s, i, inten


def partition_at(s, ins, seed, label):
    """Settle a Le Bail partition at fixed parameters (the fit's tolerance and
    cap) and report Rwp of what it lands on."""
    m = compile_model(s, ins, DATA, mode="lebail")
    vals = ParameterTable(s, ins).decode(ParameterTable(s, ins).x0())
    cp = m.phases[0]
    if seed is not None:
        keys = [tuple(int(v) for v in h) for h in cp.reflections.hkl]
        cp.hkl_intensity = np.array([seed.get(k, 1e-10) for k in keys])
    before = rwp(np.asarray(m.evaluate(vals)))
    t0 = time.perf_counter()
    run, settled = m.lebail_update(vals, n_cycles=25000, tol=1e-7)
    after = rwp(np.asarray(m.evaluate(vals)))
    floor = int((cp.hkl_intensity <= 1e-9).sum())
    print(f"{label:<46} Rwp seed {before:.4f} -> settled {after:.4f}  cycles {run} "
          f"settled {settled}  at floor {floor}/{cp.hkl_intensity.size}  "
          f"{time.perf_counter() - t0:.1f} s")
    return m, vals


if step == "fits":
    fit("pawley", "pawley", rx.Structure(phases=[phase(5e-4)]), instrument(False))
    fit("lebail", "lebail", rx.Structure(phases=[phase(5e-4)]), instrument(False))
elif step == "cross":
    sp, ip, Ip = load("pawley")
    sl, il, Il = load("lebail")
    partition_at(sp, ip, Ip, "Pawley's params, Pawley's intensities")
    partition_at(sp, ip, None, "Pawley's params, flat intensities")
    partition_at(sl, il, Il, "Le Bail's params, Le Bail's intensities")
    partition_at(sl, il, Ip, "Le Bail's params, Pawley's intensities")
    # Pawley's cell and profile with Le Bail's background, and the converse
    sx = sp.model_copy(deep=True)
    ix = ip.model_copy(deep=True)
    ix.background = il.background.model_copy(deep=True)
    partition_at(sx, ix, Ip, "Pawley's params + Le Bail's background")
    ix2 = il.model_copy(deep=True)
    ix2.background = ip.background.model_copy(deep=True)
    partition_at(sl, ix2, Il, "Le Bail's params + Pawley's background")
elif step == "swap":
    sp, ip, _ = load("pawley")
    sl, il, _ = load("lebail")
    fit("lebail_from_pawley", "lebail", sp, ip)
    fit("pawley_from_lebail", "pawley", sl, il)
elif step == "seeded":
    # the skill's SKILL.md §2 rule 5: seed the background before a Le Bail run
    for kind in ("chebyshev", "pspline"):
        ins = instrument(False)
        ins.background = rx.auto_background(DATA, kind=kind, seed=True).background
        print(f"seeded {kind}: {type(ins.background).__name__}")
        fit(f"lebail_seeded_{kind}", "lebail", rx.Structure(phases=[phase(5e-4)]), ins)
        if kind == "chebyshev":
            fit(f"pawley_seeded_{kind}", "pawley", rx.Structure(phases=[phase(5e-4)]),
                ins.model_copy(deep=True))
elif step == "degenerate":
    # the invented cell has b = 3a exactly, so (h, k, l) and (k/3, 3h, l) share
    # a d-spacing; a refined cell breaks that by parts in 1e4
    from rietx.crystallography.symmetry import generate_reflections
    rs = generate_reflections(SG, CELL, 1.5406, TTMAX)
    d = np.sort(np.asarray(rs.d))
    tied = np.diff(d) < 1e-9
    sharing = np.zeros(d.size, bool)
    sharing[:-1] |= tied
    sharing[1:] |= tied
    print(f"reflections {d.size}; sharing a d-spacing to 1e-9 Å with a neighbour: "
          f"{int(sharing.sum())} ({int(tied.sum())} coincident adjacent pairs)")

    def with_cell(s, a=None, b=None):
        s = s.model_copy(deep=True)
        if a is not None:
            s.phases[0].cell.a.value = a
        if b is not None:
            s.phases[0].cell.b.value = b
        return s
    st = rx.Structure(phases=[phase(0.0)])
    partition_at(st, instrument(True), None, "truth (b = 3a exactly)")
    partition_at(with_cell(st, b=36.0 * (1 + 2e-4)), instrument(True), None,
                 "truth, b × (1 + 2e-4)")
    sp, ip, _ = load("pawley")
    a = sp.phases[0].cell.a.value
    print(f"Pawley's b/a − 3 = {sp.phases[0].cell.b.value / a - 3:+.2e}")
    partition_at(sp, ip, None, "Pawley's params, flat")
    partition_at(with_cell(sp, b=3 * a), ip, None, "Pawley's params with b = 3a, flat")
elif step == "truth":
    # the generating model's own Rwp, and the partition at the truth's parameters
    st = rx.Structure(phases=[phase(0.0)])
    print(f"truth model Rwp {rwp(Y_TRUE):.4f}")
    partition_at(st, instrument(True), None, "truth params, flat intensities")
elif step == "compare":
    # the two answers side by side: every refined value, the background curve,
    # Rwp by 2θ band, and the per-hkl intensities matched by hkl
    A = {t: json.loads((OUT / f"{t}.summary.json").read_text()) for t in ("pawley", "lebail")}
    for path in sorted(set(A["pawley"]["values"]) | set(A["lebail"]["values"])):
        if path.startswith("phases.0.atoms"):
            continue
        a, b = A["pawley"]["values"].get(path), A["lebail"]["values"].get(path)
        print(f"{path:<40} pawley {a!s:>24}  lebail {b!s:>24}")
    R = {t: rx.RefinementResult.model_validate_json((OUT / f"{t}.result.json").read_text())
         for t in ("pawley", "lebail")}
    bands = [(5, 20), (20, 35), (35, 50), (50, 65), (65, 80), (80, 90)]
    for t, r in R.items():
        yc, yb = np.asarray(r.y_calc), np.asarray(r.y_background)
        cells = "  ".join(f"{lo}-{hi}: {rwp(yc, (TT >= lo) & (TT < hi)):.4f}" for lo, hi in bands)
        print(f"{t:<8} Rwp {rwp(yc):.4f} by band  {cells}")
        print(f"{t:<8} background − truth: mean {np.mean(yb - BKG_TRUE):+.1f}  "
              f"min {np.min(yb - BKG_TRUE):+.1f}  max {np.max(yb - BKG_TRUE):+.1f} counts")
    _, _, Ip = load("pawley")
    _, _, Il = load("lebail")
    keys = sorted(set(Ip) & set(Il))
    a = np.array([Ip[k] for k in keys])
    b = np.array([Il[k] for k in keys])
    big = a > np.percentile(a, 50)
    print(f"matched {len(keys)} hkl (pawley {len(Ip)}, lebail {len(Il)});  "
          f"Σ lebail/Σ pawley {b.sum() / a.sum():.4f};  "
          f"median |ln(lb/pw)| over the stronger half {np.median(np.abs(np.log(b[big] / a[big]))):.3f};  "
          f"lebail at floor {(b <= 1e-9).sum()}, pawley ≤ 0 {(a <= 0).sum()}")
elif step == "plots":
    from rietx.viz.plots import plot_result
    for f in sorted(OUT.glob("*.result.json")):
        res = rx.RefinementResult.model_validate_json(f.read_text())
        tag = f.name.split(".")[0]
        plot_result(res, path=OUT / f"{tag}_fit.png")
        plot_result(res, path=OUT / f"{tag}_zoom.png", two_theta_limits=(40.0, 46.0))
        print(tag, "plotted")
else:
    sys.exit(f"unknown STEP {step!r}; see the module docstring")
