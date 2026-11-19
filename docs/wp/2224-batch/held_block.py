"""WP-2224, after the generality review: a block present from the start, held
at its identity value by the first fit, then freed by a longer plan.

The model swap in ``swap.py`` goes through ``edit`` and so runs the staged
plan.  Here nothing is written between the fits: the brucite model carries a
March-Dollase (001) block at r = 1 from the start, the first fit's plan never
frees it, and the second fit's plan adds a ``po`` stage.  The default sends that
second fit down the one-stage path.  Compared with ``refit="stages"`` from the
same answer.  Closing stage off, as in ``swap.py``.

  held_block.py

Run with RIETX_TELEMETRY=0.
"""
import warnings

from rietx.refine import Refinement
from rietx.schemas.structure import PreferredOrientation
from rietx.strategy.staged import Stage
from rietx.viz import compare

warnings.simplefilter("ignore")
DATA = compare.default_data_dir()
std = next(s for s in compare.STANDARDS if s.key == "brucite")


def plan(po):
    p = std.build(DATA).plan
    p.closing_window_tol = None
    if po:
        p.stages.append(Stage("po", ["phases.*.preferred_orientation.r"]))
    return p


inputs = std.build(DATA)
inputs.structure.phases[0].preferred_orientation = PreferredOrientation(axis=(0, 0, 1))
kw = dict(two_theta_limits=inputs.two_theta_limits)
ref = Refinement(inputs.structure, inputs.instrument)
first = ref.fit(inputs.data, plan=plan(False), **kw)
print("first", first.status, f"rwp={first.statistics.rwp:.5f}")
arms = {}
for arm in ("single", "stages"):
    ref.checkout(first.node_id)
    res = ref.fit(inputs.data, plan=plan(True), refit=arm, **kw)
    arms[arm] = res
    print(arm, [s.name for s in res.stages], res.status,
          f"rwp={res.statistics.rwp:.5f}",
          "evals", sum(s.n_iterations for s in res.stages))
st = {p.path: p for p in arms["stages"].parameters}
gaps = sorted(((abs(p.value - st[p.path].value) / st[p.path].stderr, p.path)
               for p in arms["single"].parameters
               if p.path in st and st[p.path].stderr), reverse=True)
for g, path in gaps[:5]:
    print(f"  {path}: {g:.2f} esd of the staged esd")
