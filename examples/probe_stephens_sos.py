"""WP-1946: can the Stephens block refine as a sum of squares?

Run: ``.venv/bin/python examples/probe_stephens_sos.py [--classes]
[--forms a,b] [--out DIR]``

The idea under test: write σ²(hkl) = ‖Lᵀv‖², v = (h², k², l², kl, hl, hk),
so σ² cannot be negative for any hkl, and refine L instead of S_HKL.

**Symmetry (``--classes``).**  Let ρ(g) act on v by h → Rᵀh and R̄ be the
Reynolds operator on the fifteen quartic coefficients, the average of the
monomial action over the Laue group (``stephens._invariance_rows`` + 1).
The map is S(L) = R̄·π(L·Lᵀ), π taking a Gram matrix to its quartic.  Its image
is the class's non-negative cone exactly, for every class, with no per-class
proof: each π(L·Lᵀ)∘g is non-negative, so their average is, and it is
invariant; conversely an invariant non-negative quartic p is a sum of three
squares (Hilbert, 1888), p = π(L·Lᵀ) for some 6×3 L, and R̄·p = p.  The
table checks the rest numerically per class: the Jacobian of S(L) has rank m
(the allowed dimension) at a random L, and the image lies in the allowed span
and is non-negative.  It also counts the directions in L that move nothing:
15 − m for a lower-trapezoidal L, and c − m for a Gram matrix restricted to
the c-dimensional invariant (commuting) family.  Only the triclinic class has
none.

**Brucite (``--forms``).**  The round-robin brucite fit of
``probe_driver_grid.py --fits brucite_aniso``, five starts 1e-14 apart under
LM, with the strain cone's linear rows switched off.  The fifteen
``microstrain.s*`` slots carry the form's parameters instead of S_HKL
(identity strain basis), the width law maps them to S first, and the seed
writes the form's own exact representation of the isotropic ray S = ε²·[M²].
Patched internals, so each form runs in its own subprocess.

* ``hilbert_axis``: lower-trapezoidal 6×3 L, seeded from
  (x²+y²+z²)² = (x²+y²−z²)² + (2xz)² + (2yz)², x = Cᵀh, G* = C·Cᵀ, z along c*.
* ``hilbert_turned``: the same identity in a turned orthonormal frame, so no
  slot of the seed is zero.
* ``trigonal``: four parameters for -3m1, p = (a·r² + b·z²)² + |c·E₁ + d·E₂|²
  with r² = x²+y², E₁ = (x²−y², −2xy), E₂ = (xz, yz), seeded at
  (a, b, c, d) = ε·(1, −1, 0, 2).  ``--classes`` also checks that it reaches
  200 random members of the -3m1 cone.

Measured 2026-11-17 (macOS arm64, ``[dev]``, ``src`` at ``7b761b54d``), against
the default LM with its cone rows, χ²_red 7.888123976, spread 8.1e-4
(``probe_driver_grid.py --fits brucite_aniso --arms lm``, same day):

==============  =========================  ======  ===============================
form            χ²_red                     spread  stages at max_iter (of 9)
==============  =========================  ======  ===============================
hilbert_axis    9.548343980-9.548343992    1.3e-9  none; the slots never move
hilbert_turned  7.910398294-7.911857845    1.8e-4  2 (sample_broadening, biso)
trigonal        7.903062730-8.126564772    2.8e-2  0 or 1 (biso)
==============  =========================  ======  ===============================

``hilbert_axis`` never leaves its seed, and its strain stage ends
``no_descent``.  Five of its fifteen columns have no true derivative there
(the group average cancels it) and read as rounding noise, about 1e-8 of the
others; the step's column equilibration promotes them to full directions, so
every trial step fails.  The other two refine, and every start of every form
ends with ``FLAT_DIRECTION`` and ``HIGH_CORRELATION``.  Under ``trigonal`` c
and d go to 0, or towards it in the starts still moving at max_iter: brucite's
best non-negative quartic is the rank-one (a·r² + b·z²)² with a ≈ 73,
b ≈ −2026, which vanishes on the real cone |z|/r = √(−a/b) ≈ 0.19.  That is
the boundary of the cone.  There the form's c and d columns vanish, which is
the cone's edge seen again through the parametrisation.

Licensing: Hilbert (1888) and the Reynolds operator are textbook; no program
was read or run beyond rietx.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "examples"))

from rietx.crystallography import stephens as st  # noqa: E402
from rietx.crystallography.lattice import reciprocal_metric_tensor  # noqa: E402
from rietx.crystallography.symmetry import as_group, rotation_matrices  # noqa: E402

STARTS = (0, 1, 2, 3, 4)
FORMS = ("hilbert_axis", "hilbert_turned", "trigonal")
#: the turned frame's Euler angles (z-y-z, radians); any generic choice serves
TURN = (0.3, 0.7, 1.1)
#: one representative group per Laue class
CLASSES = {"-1": "P -1", "2/m": "P 1 2/m 1", "mmm": "P m m m", "4/m": "P 4/m",
           "4/mmm": "P 4/m m m", "-3": "P -3", "-3m1": "P -3 m 1",
           "-31m": "P -3 1 m", "6/m": "P 6/m", "6/mmm": "P 6/m m m",
           "m-3": "P m -3", "m-3m": "P m -3 m"}
#: v's exponents: (h², k², l², kl, hl, hk)
QUAD = ((2, 0, 0), (0, 2, 0), (0, 0, 2), (0, 1, 1), (1, 0, 1), (1, 1, 0))

#: π: vec(Q) (36) → the fifteen quartic coefficients of vᵀQv
PI = np.zeros((15, 36))
for _a, _ea in enumerate(QUAD):
    for _b, _eb in enumerate(QUAD):
        PI[st._S_INDEX[(_ea[0] + _eb[0], _ea[1] + _eb[1], _ea[2] + _eb[2])],
           6 * _a + _b] += 1.0


# ------------------------------------------------------------- the algebra
def _rotations(space_group) -> list[np.ndarray]:
    out, seen = [], set()
    for r in np.asarray(rotation_matrices(as_group(space_group)), dtype=np.float64):
        key = tuple(np.rint(r).astype(np.int64).ravel().tolist())
        if key not in seen:
            seen.add(key)
            out.append(np.rint(r))
    return out


def reynolds(space_group) -> np.ndarray:
    """(15, 15) group average of the monomial action; R̄·s is invariant."""
    rots = _rotations(space_group)
    acc = np.zeros((15, 15))
    for r in rots:
        rows = st._invariance_rows(np.rint(r.T).astype(np.int64))
        acc += np.array([[float(x) for x in row] for row in rows]) + np.eye(15)
    return acc / len(rots)


def sym_to_v(a: np.ndarray) -> np.ndarray:
    """hᵀAh as coefficients on v."""
    return np.array([a[0, 0], a[1, 1], a[2, 2],
                     2 * a[1, 2], 2 * a[0, 2], 2 * a[0, 1]])


def frame(cell, turn=None):
    """xx(i, j): x_i·x_j as coefficients on v, x = Cᵀh orthonormal, M = |x|²."""
    c = np.linalg.cholesky(np.asarray(reciprocal_metric_tensor(*cell),
                                      dtype=np.float64))
    if turn is not None:
        def rz(t):
            return np.array([[np.cos(t), -np.sin(t), 0], [np.sin(t), np.cos(t), 0],
                             [0, 0, 1.0]])

        def ry(t):
            return np.array([[np.cos(t), 0, np.sin(t)], [0, 1.0, 0],
                             [-np.sin(t), 0, np.cos(t)]])

        c = c @ (rz(turn[0]) @ ry(turn[1]) @ rz(turn[2])).T

    def xx(i, j):
        a = np.outer(c[:, i], c[:, j])
        return sym_to_v(0.5 * (a + a.T))
    return xx


def trapezoid(x: np.ndarray) -> np.ndarray:
    """Fifteen slots → the lower-trapezoidal 6×3 L."""
    ell = np.zeros((6, 3))
    i = 0
    for j in range(3):
        ell[j:, j] = x[i:i + 6 - j]
        i += 6 - j
    return ell


def hilbert_seed(cell, microstrain: float, turn=None) -> np.ndarray:
    """ε²M² = ε²[(x²+y²−z²)² + (2xz)² + (2yz)²], as trapezoid slots."""
    xx = frame(cell, turn)
    ell = microstrain * np.column_stack([xx(0, 0) + xx(1, 1) - xx(2, 2),
                                         2 * xx(0, 2), 2 * xx(1, 2)])
    _, r = np.linalg.qr(ell.T)              # Lᵀ = U·R, so L = Rᵀ·Uᵀ
    return np.concatenate([r.T[j:, j] for j in range(3)])


def trigonal_ell(t, cell) -> np.ndarray:
    """L of p = (a·r² + b·z²)² + |c·E₁ + d·E₂|²."""
    a, b, c, d = t
    xx = frame(cell)
    e1 = (xx(0, 0) - xx(1, 1), -2 * xx(0, 1))
    e2 = (xx(0, 2), xx(1, 2))
    return np.column_stack([a * (xx(0, 0) + xx(1, 1)) + b * xx(2, 2),
                            c * e1[0] + d * e2[0], c * e1[1] + d * e2[1]])


def s_of(ell: np.ndarray, rbar: np.ndarray) -> np.ndarray:
    return rbar @ (PI @ (ell @ ell.T).ravel())


# ------------------------------------------------------------- --classes
def _v(h: np.ndarray) -> np.ndarray:
    return np.column_stack([h[:, 0] ** 2, h[:, 1] ** 2, h[:, 2] ** 2,
                            h[:, 1] * h[:, 2], h[:, 0] * h[:, 2], h[:, 0] * h[:, 1]])


def classes() -> str:
    rng = np.random.default_rng(1946)
    pts = rng.normal(size=(40, 3))
    iu = np.triu_indices(6)
    lines = ["| Laue class | m | c | flat, trapezoid L | flat, invariant Gram | "
             "rank J | off span | min σ² |", "|---|---|---|---|---|---|---|---|"]
    for name, sg in CLASSES.items():
        basis = st.stephens_basis(sg).astype(np.float64)
        m = len(basis)
        rbar = reynolds(sg)
        # T_g: v(Rᵀh) = T_g·v(h); the invariant Gram matrices are its commutant
        ts = [np.linalg.lstsq(_v(pts), _v(pts @ r), rcond=None)[0].T
              for r in _rotations(sg)]
        units = []
        for a, b in zip(*iu, strict=True):
            q = np.zeros((6, 6))
            q[a, b] = q[b, a] = 1.0
            units.append(q)
        eqs = np.vstack([np.array([(t.T @ q @ t - q)[iu] for q in units]).T
                         for t in ts])
        c = 21 - np.linalg.matrix_rank(eqs, tol=1e-9)
        x = rng.normal(size=15)
        jac = np.array([(s_of(trapezoid(x + 1e-6 * e), rbar)
                         - s_of(trapezoid(x - 1e-6 * e), rbar)) / 2e-6
                        for e in np.eye(15)]).T
        rank = np.linalg.matrix_rank(jac, tol=1e-6 * np.abs(jac).max())
        s = s_of(trapezoid(x), rbar)
        coef = np.linalg.lstsq(basis.T, s, rcond=None)[0]
        off = np.abs(basis.T @ coef - s).max() / np.abs(s).max()
        hkl = rng.normal(size=(2000, 3))
        low = min(float((st.monomial_matrix(hkl)
                         @ s_of(trapezoid(rng.normal(size=15)), rbar)).min())
                  for _ in range(50))
        lines.append(f"| {name} | {m} | {c} | {15 - m} | {c - m} | {rank} | "
                     f"{off:.0e} | {low:.1e} |")
    return "\n".join(lines) + "\n\n" + _trigonal_reach()


def _trigonal_reach() -> str:
    from scipy.optimize import least_squares

    cell = (3.1475, 3.1475, 4.7743, 90.0, 90.0, 120.0)
    rbar = reynolds("P -3 m 1")
    rng = np.random.default_rng(7)
    worst = 0.0
    for _ in range(200):
        target = s_of(trapezoid(30.0 * rng.normal(size=15)), rbar)
        fits = [least_squares(lambda t, g=target: s_of(trigonal_ell(t, cell), rbar) - g,
                              30.0 * rng.normal(size=4), xtol=1e-15, ftol=1e-15,
                              gtol=1e-15) for _ in range(6)]
        best = min(f.cost for f in fits)
        worst = max(worst, float(np.sqrt(2 * best) / np.linalg.norm(target)))
    return (f"trigonal form on 200 random -3m1 cone members: worst relative "
            f"miss {worst:.1e}")


# ------------------------------------------------------------- --forms
def _install(form: str) -> None:
    """Patch the table, the width law, the cone rows and the seed."""
    import rietx.model.forward as fw
    import rietx.optimize.least_squares as ls
    import rietx.params.vector as pv

    n = 4 if form == "trigonal" else 15
    rbar = reynolds("P -3 m 1")
    state: dict = {}
    turn = TURN if form == "hilbert_turned" else None

    def to_s(x):
        x = np.asarray(x, dtype=np.float64)
        if form == "trigonal":
            return (s_of(trigonal_ell(x[:4], state["cell"]), rbar)
                    if "cell" in state else np.zeros(15))
        return s_of(trapezoid(x), rbar)

    pv.strain_basis = lambda rot: np.eye(15, dtype=np.int64)[:n]
    ls.strain_cone_inequalities = lambda *a, **k: []
    width = st.strain_width_deg
    fw.strain_width_deg = lambda mono, s, d: width(mono, to_s(s), d)
    collect = pv.ParameterTable._collect_microstrain

    def collect_cell(self, base, sg, phase):
        collect(self, base, sg, phase)
        state.setdefault("cells", {})[base] = phase.cell.lengths_angles()
    pv.ParameterTable._collect_microstrain = collect_cell

    def seed(self, paths, microstrain):
        if microstrain <= 0.0:
            return []
        bases = {p.rpartition(".microstrain.dof.")[0] for p in paths
                 if ".microstrain.dof." in p}
        seeded = []
        for base in bases:
            rows = [self._paths[f"{base}.microstrain.dof.{k}"] for k in range(n)]
            if any(self.entries[i].value != 0.0 for i in rows):
                continue
            cell = state["cells"][base]
            if form == "trigonal":
                state["cell"] = cell
                x = float(microstrain) * np.array([1.0, -1.0, 0.0, 2.0])
            else:
                x = hilbert_seed(cell, float(microstrain), turn)
            state["seed"] = [float(v) for v in x]
            for k, i in enumerate(rows):
                self.entries[i].value = float(x[k])
                seeded.append(self.entries[i].path)
        if seeded:
            self._rebuild()
        return seeded
    pv.ParameterTable.seed_stephens = seed
    state["to_s"] = to_s
    _install.state = state


def run_cell(form: str, out: Path) -> None:
    import probe_driver_grid as grid

    _install(form)
    calls: list[dict] = []
    grid._install_solver("lm", calls)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for k in STARTS:
            calls.clear()
            row: dict = {"form": form, "k": k}
            try:
                res = grid.FITS["brucite_aniso"](1.0 + k * 1e-14)
                slots = [q.value for q in res.parameters
                         if ".microstrain.dof." in q.path]
                seed = np.asarray(_install.state["seed"])
                moved = float(np.abs(np.asarray(slots) - seed).max()
                              / np.abs(seed).max())
                row.update(chi2=res.statistics.chi2, rwp=res.statistics.rwp,
                           slots=slots, moved=moved, s=_install.state["to_s"](slots).tolist(),
                           codes=sorted({d.code for d in res.diagnostics}))
            except Exception:  # recorded, never fatal to the cell
                row["error"] = traceback.format_exc()[-2000:]
            row["calls"] = [[c["stage"], c["status"], c["nfev"]] for c in calls]
            fh.write(json.dumps(row) + "\n")
            fh.flush()


def table(out: Path, forms: list[str]) -> str:
    lines = ["| form | χ²_red | spread | moved from seed | max_iter stages | codes |",
             "|---|---|---|---|---|---|"]
    for form in forms:
        path = out / f"{form}.jsonl"
        rows = ([json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
                if path.exists() else [])
        chi = [r["chi2"] for r in rows if "chi2" in r]
        if not rows or len(chi) < len(rows):
            lines.append(f"| {form} | error or missing | | | | |")
            continue
        moved = [r["moved"] for r in rows]
        stopped = [sum(c[1] == "max_iter" for c in r["calls"]) for r in rows]
        codes = sorted({c for r in rows for c in r["codes"]}
                       & {"FLAT_DIRECTION", "HIGH_CORRELATION"})
        lines.append(f"| {form} | {min(chi):.9f}-{max(chi):.9f} | "
                     f"{(max(chi) - min(chi)) / min(chi):.1e} | {min(moved):.0e}-{max(moved):.0e} | "
                     f"{min(stopped)}-{max(stopped)} | {', '.join(codes) or '—'} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--classes", action="store_true")
    p.add_argument("--forms", default="")
    p.add_argument("--out", type=Path, default=Path("stephens_sos"))
    p.add_argument("--cell", nargs=2, metavar=("FORM", "PATH"), help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if a.cell:
        run_cell(a.cell[0], Path(a.cell[1]))
        return 0
    if a.classes:
        print(classes())
    if a.forms:
        from rietx._about import COMPILED_THREADS_ENV, TELEMETRY_ENV

        forms = a.forms.split(",")
        a.out.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, MPLBACKEND="Agg",
                   **{TELEMETRY_ENV: "0", COMPILED_THREADS_ENV: "1"})
        for form in forms:
            path = (a.out / f"{form}.jsonl").resolve()
            rc = subprocess.call([sys.executable, __file__, "--cell", form, str(path)],
                                 cwd=ROOT, env=env)
            print(f"{form}: rc={rc}", flush=True)
        print(table(a.out, forms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
