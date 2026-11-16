"""C12 on brucite (``tests/test_acceptance_stephens.py``), WP-2018 task 3.

The pair: ``ParameterTable.seed_stephens`` puts an all-zero Stephens block on
the isotropic ray when its stage frees it, and skips a block the caller set
nonzero; ``least_squares.strain_cone_inequalities`` builds the σ²(M) ≥ 0 rows
against the stage's starting point and drops a phase's rows when that start
is already outside the cone.  So a caller's block that starts outside is the
one case where the LM driver fits the strain block with no cone at all.

The protocol is the test module's LM fit: ``_plan(texture=True,
stephens=True)`` (strain seed 800 ppm in ``sample_broadening``,
``intermediate_ftol`` 1e-6, no closing stage), brucite textured, the
``qarr_instrument``.  Arms (the block each starts from; driver):

  zero        the test's start: an all-zero block, seeded at 800 ppm (LM)
  ray         the caller hands in ``StephensStrain.isotropic(800)``, nonzero,
              so the seed skips it; inside the cone (LM).  The skip's control:
              the same start the seed would have written
  out         the caller hands in the 800 ppm ray with s004 negated, outside
              the cone on the (00l) side; the seed skips it and the rows drop
              (LM, shipped)
  out_seeded  ``out`` with ``seed_stephens`` patched to overwrite a nonzero
              block too, so the stage starts on the ray: without the skip (LM)
  out_trf     ``out`` under ``solver="trf"``, which builds no rows anywhere
  zero_trf    ``zero`` under TRF: the test module's unconstrained fit, the
              positive arm for the guard (it must fire here)
  trf_then_lm ``zero_trf``'s fitted structure and instrument refitted under the
              default LM driver with the same plan: what a caller does on
              reading the guard's suggestion ("refit with the default LM
              driver"), carrying the TRF block, which is outside the cone
  trf_then_lm_seeded
              ``trf_then_lm`` with the skip removed, as ``out_seeded``

Each record carries, per LM solve, whether the strain rows were built or
dropped and why (``cone``), how many of the stage's reflections start and
end with σ²(M) < 0, and the guard's codes.  Two start counts:
``n_negative_at_start`` is the strict σ²(M) < 0, and ``n_violated_at_start``
the drop test itself (``LinearInequality.violated``, which allows ``_ON_FACE``
of the block's largest |σ²(M)|), so a block can be built with a few rows
strictly negative on its face.

usage (repo root): python docs/wp/2018-measure/stephens_start.py [arm ...]
"""
from __future__ import annotations

import importlib
import os
import sys

from common import OUT, emit, patched, provenance, record

os.environ.setdefault("RIETX_TELEMETRY", "0")

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.crystallography.stephens import S_NAMES  # noqa: E402
from rietx.schemas.structure import StephensStrain  # noqa: E402
from tests.test_acceptance_qpa_roundrobin import DATA, brucite_phase, qarr_instrument, seed_scales  # noqa: E402
from tests.test_acceptance_stephens import _plan  # noqa: E402

refine_module = importlib.import_module("rietx.refine")
ls_module = importlib.import_module("rietx.optimize.least_squares")
lm_module = importlib.import_module("rietx.optimize.lm")
vector_module = importlib.import_module("rietx.params.vector")

ARMS = ("zero", "ray", "out", "out_seeded", "out_trf", "zero_trf", "trf_then_lm",
        "trf_then_lm_seeded")
SEED_PPM = 800.0
DOFS = [f"phases.0.microstrain.dof.{k}" for k in range(4)]


def _block(start: str, cell) -> StephensStrain:
    if start == "zero":
        return StephensStrain.from_values([0.0] * 15)
    s = list(StephensStrain.isotropic(SEED_PPM, cell, vary=False).values())
    if start == "out":
        s[S_NAMES.index("s004")] *= -1.0
    return StephensStrain.from_values(s)


def _cone_spy(log, stage):
    """``strain_cone_inequalities`` that records what it built and why."""
    real = ls_module.strain_cone_inequalities

    def spy(model, table, x0):
        out = real(model, table, x0)
        cp = model.phases[0]
        rec = {"stage": stage[0], "built": bool(out)}
        if cp.strain_monomials is not None and "phases.0.microstrain.s004" in table._paths:
            C, d = table.constraint_block()
            rows = [table._paths[f"phases.0.microstrain.{n}"] for n in S_NAMES]
            mono = np.asarray(cp.strain_monomials, dtype=np.float64)
            T = mono @ C.toarray()[rows, :]
            c = mono @ d[rows]
            sig = T @ x0 + c
            drop = lm_module.LinearInequality(T=T, c=c).violated(x0)
            rec.update(free=bool(np.any(T)), n_refl=int(len(sig)),
                       n_negative_at_start=int((sig < 0).sum()),
                       n_violated_at_start=int(drop.sum()),
                       min_over_max=float(sig.min() / max(abs(sig).max(), 1e-300)))
        log.append(rec)
        return out

    return spy


def _stage_tag(stage):
    real = refine_module.run_least_squares

    def solve(model, table, **kwargs):
        stage[0] = kwargs.get("stage")
        return real(model, table, **kwargs)

    return solve


def _overwriting_seed():
    """``seed_stephens`` that seeds a nonzero block too (the skip removed)."""
    real = vector_module.ParameterTable.seed_stephens

    def seed(self, paths, microstrain):
        for path in paths:
            if ".microstrain.dof." in path:
                self.entries[self._paths[path]].value = 0.0
        return real(self, paths, microstrain)

    return seed


def _sigma2_end(ref):
    from rietx.crystallography.stephens import sigma2_m
    block = ref.fitted_structure.phases[0].microstrain
    s = np.array([getattr(block, n).value for n in S_NAMES])
    sig = np.asarray(sigma2_m(ref._model.phases[0].strain_monomials, s))
    return {"n_refl": int(len(sig)), "n_negative": int((sig < 0).sum()),
            "min_over_max": float(sig.min() / abs(sig).max()),
            "s": {n: float(v) for n, v in zip(S_NAMES, s) if v}}


def fit(arm: str):
    data = rx.read_pattern(DATA / "brucite.prn")
    if arm.startswith("trf_then_lm"):
        first, _, _ = fit("zero_trf")
        structure, ins = first.fitted_structure, first.fitted_instrument
        solver, phase = None, structure.phases[0]
    else:
        start = arm.split("_")[0]
        solver = "trf" if arm.endswith("_trf") else None
        phase = brucite_phase(textured=True)
        phase.microstrain = _block(start, phase.cell)
        structure = rx.Structure(phases=[phase])
        ins = qarr_instrument()
        seed_scales(structure, ins, data)
    kw = {"history": False} if solver is None else {"history": False, "solver": solver}
    ref = rx.Refinement(structure, ins, **kw)
    stage, cone = [None], []
    seed = (_overwriting_seed() if arm.endswith("_seeded")
            else vector_module.ParameterTable.seed_stephens)
    with patched(ls_module, "strain_cone_inequalities", _cone_spy(cone, stage)), \
            patched(refine_module, "run_least_squares", _stage_tag(stage)), \
            patched(vector_module.ParameterTable, "seed_stephens", seed):
        result = ref.fit(data, plan=_plan(texture=True, stephens=True))
    rec = record(result, DOFS + ["phases.0.scale", "phases.0.preferred_orientation.r",
                                  "phases.0.cell.a", "phases.0.cell.c"])
    rec["cone"] = cone
    rec["seeded"] = [{"stage": s.name, "seeded": dict(s.seeded or {})}
                     for s in result.stages if s.seeded]
    rec["sigma2_end"] = _sigma2_end(ref)
    rec["start_s"] = {n: v for n, v in zip(S_NAMES, phase.microstrain.values()) if v}
    rec["guard"] = [{"message": d.message, "suggestion": d.suggestion}
                    for d in result.diagnostics
                    if d.code in ("STEPHENS_STRAIN_NOT_POSITIVE", "CONSTRAINT_ACTIVE")]
    return ref, result, rec


def main(arms):
    emit({"provenance": provenance(), "seed_ppm": SEED_PPM})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            _, result, rec = fit(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rec["arm"] = arm
        emit(rec)
        result.plot(path=str(OUT / f"c12_{arm}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)
