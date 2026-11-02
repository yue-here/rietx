"""How many continuations each 150 K `solve_magnetic` trial takes, and what each one
gains, at 1e-14 nudges of the nuclear reference's w (2026-11-02).

usage: python cr2wo6_150k_continuations.py <repo root> k [k ...]
"""
import sys

sys.path.insert(0, sys.argv[1])
import rietx as rx  # noqa: E402
import rietx.strategy.magnetic as mag  # noqa: E402
from tests.test_acceptance_magnetic import DATA, NUCLEAR_STAGES, _fit, _instrument, _trirutile  # noqa: E402

LOG = []
_refit = rx.Refinement.fit


def fit(self, *a, **kw):
    res = _refit(self, *a, **kw)
    LOG.append([(s.name, s.status, s.n_iterations, round(s.cost_initial, 4), round(s.cost_final, 4))
                for s in res.stages])
    return res


_trial = mag._fit


def traced(*a, **kw):
    LOG.clear()
    ref, result = _trial(*a, **kw)
    print(f"  trial: {len(LOG) - 1} continuations, {result.status}, Rwp {result.statistics.rwp:.7f}")
    for i, call in enumerate(LOG):
        print(f"    fit {i}: {call if i == 0 else call[-1]}")
    return ref, result


rx.Refinement.fit = fit
mag._fit = traced
d150 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_150K.dat")
ref150, _ = _fit(_trirutile(), _instrument(), d150, NUCLEAR_STAGES, closing_window_tol=None)
for k in [float(x) for x in sys.argv[2:]]:
    ins = ref150.instrument
    w0 = ins.profile.w.value
    ins.profile.w.value = w0 * (1 + k * 1e-14)
    print(f"k = {k:g}", flush=True)
    s = rx.solve_magnetic(ref150, d150, sites=["Cr1"], ion="Cr3+")
    ins.profile.w.value = w0
    print("  ", s.verdict, [(t.class_index, t.fit_status) for t in s.trials if t.status == "refined"],
          flush=True)
