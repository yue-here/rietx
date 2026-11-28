"""WP-2315 Angle 0, 3rd session: is a blockwise G·E⁻¹ the dense product's
bytes under the BLAS this numpy links?

G = [I[has_lo]; −I[has_hi]; T] as in ``lm._solve_constrained_step``.  Form (a)
is the withdrawn ``lm._rows_in_z``: box rows sliced from E⁻¹, T read on its
nonzero columns only.  Form (b) slices the box rows and multiplies T's rows
whole.  Prints, per shape, how many elements differ in the box rows and in
T's rows, then the largest difference over |T|·|E⁻¹| in units of ε.

Run it with each BLAS's interpreter and ``-I``.  On an arm64 Mac an x86_64
numpy under Rosetta gives x86_64 OpenBLAS kernels:
``uv venv --python cpython-3.12-macos-x86_64-none <dir>`` then
``uv pip install --python <dir>/bin/python --python-platform x86_64-apple-darwin numpy``.
"""
import numpy as np

cfg = np.show_config(mode="dicts")["Build Dependencies"]["blas"]
print("blas:", cfg["name"], cfg.get("openblas configuration", ""))


def dense(E, lo, hi, T):
    eye = np.eye(len(E))
    return np.vstack([eye[lo], -eye[hi], T]) @ E


def form_a(E, lo, hi, T):
    cols = np.flatnonzero(np.any(T != 0.0, axis=0))
    return np.vstack([E[lo] + 0.0, -E[hi] + 0.0, T[:, cols] @ E[cols]])


def form_b(E, lo, hi, T):
    return np.vstack([E[lo] + 0.0, -E[hi] + 0.0, T @ E])


worst = {"a": 0.0, "b": 0.0}
for seed in range(8):
    rng = np.random.default_rng(seed)
    n, m = 300 + 97 * (seed % 4), 500
    E = rng.standard_normal((n, n)) * 10.0 ** rng.uniform(-3, 3, n)
    E[rng.random((n, n)) < 0.02] = 0.0
    E[rng.random((n, n)) < 0.02] = -0.0
    lo, hi = rng.random(n) < 0.8, rng.random(n) < 0.2
    T = np.zeros((m, n))
    cols = np.sort(rng.choice(20 if seed % 2 == 0 else n, 7, replace=False))
    T[:, cols] = rng.standard_normal((m, 7)) * 10.0 ** rng.uniform(-6, 6, 7)
    ref = dense(E, lo, hi, T)
    nb = int(lo.sum() + hi.sum())
    bound = np.abs(T) @ np.abs(E)
    for name, f in (("a", form_a), ("b", form_b)):
        got = f(E, lo, hi, T)
        diff = got != ref
        rel = np.abs(got[nb:] - ref[nb:]) / np.where(bound > 0, bound, 1.0)
        worst[name] = max(worst[name], float(rel.max()))
        print(f"seed {seed} form {name}: equal={got.tobytes() == ref.tobytes()} "
              f"box rows differing={int(diff[:nb].sum())} "
              f"T rows differing={int(diff[nb:].sum())}")
eps = np.finfo(float).eps
print("largest |diff| / (|T|·|E⁻¹|), in ε:", {k: round(v / eps, 2) for k, v in worst.items()})
