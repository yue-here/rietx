"""The pattern at parameter values nobody has applied (WP-2125).

``POST /api/preview`` serves the Interactive tab's sliders: the calculated
pattern, its background, each phase's contribution and the reflection ticks
at values the person is dragging, with the Rwp there. **Nothing is written.**
The project directory, the history and the refinement's models stay as they
were; the values pass through the working table and the table is put back.

A compiled model freezes its reflection list, its point windows and its FCJ
node counts (root CLAUDE.md, frozen-per-stage discreteness), so an evaluation
at new values on it is exact only while those still describe the new values.
Each answer therefore picks one of three evaluations, cheapest first, and
says which in the header's ``evaluated``:

- ``recompiled`` when any reflection's drawn position moves by
  ``REFLECTION_MARGIN_DEG`` or more, since the frozen list may then miss a
  reflection pushed into range. A compile at the new values (13-18 ms on the
  examples).
- ``rewindowed`` when a window sized at the new values, its movement slack
  removed, reaches outside the frozen one, or a node count grows. Through
  ``forward.rewindow`` (0.6-3.1 ms), which is the compile's own sizing rule
  and reproduced a fresh compile to 1e-13 σ in every case measured.
- ``frozen`` otherwise: the cached compile, evaluated as it stands.

No threshold here is new: each branch is a compile rule asked at the new
values. The WP's measurements show why all three exist. A frozen window costs
at most a few hundredths of an esd across the position sliders, because its
0.3° slack covers them; the width sliders cost up to 0.26 σ; and an axial
term switched on from zero has no quadrature nodes in the frozen model, so a
frozen answer there was wrong by 516-834 σ.

The compile is cached per working state, keyed on the history head, the mode,
the 2θ limits and the excluded regions, so any verb that moves the model or
the protocol invalidates it. In Le Bail and Pawley mode the head's extracted
intensities are restored into it, as ``refine.replay`` does, and stay fixed
while a slider moves.
"""

from __future__ import annotations

import copy
import math
import threading
import weakref
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..model import forward
from ..model.forward import REFLECTION_MARGIN_DEG, CompiledModel, compile_model
from ..optimize.statistics import compute_statistics
from ..params.vector import ParameterTable
from ..viz.packed import Packed
from .session import GuiError


@dataclass
class _Base:
    """One working state's table and compile, and what the checks compare against."""

    key: tuple
    table: ParameterTable
    stored: list[float]
    values: dict[str, float]
    model: CompiledModel
    #: per phase, every reflection's drawn position at the base values
    positions: list[np.ndarray]
    #: per phase, the node counts ``window_sizing`` gives at the base values
    fcj_n: list[np.ndarray]
    lebail: list | None
    lock: threading.Lock = field(default_factory=threading.Lock)


#: one base per open ``Project``; a closed project takes its entry with it
_CACHE: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_CACHE_LOCK = threading.Lock()


def _key(project) -> tuple:
    r = project.refinement
    return (r._head_id, project.doc.mode,
            None if project.doc.two_theta_limits is None
            else tuple(project.doc.two_theta_limits),
            tuple(map(tuple, project.data.excluded_regions)))


def _compile(project, structure, instrument, lebail) -> CompiledModel:
    model = compile_model(structure, instrument, project.data,
                          mode=project.doc.mode,
                          two_theta_limits=project.doc.two_theta_limits)
    if lebail is not None:
        from ..refine import _restore_lebail

        _restore_lebail(lebail, model)
    return model


def _positions(model: CompiledModel, values: dict[str, float]) -> list[np.ndarray]:
    return [np.array(model.reflection_positions(ip, values)[0], dtype=np.float64)
            for ip in range(len(model.phases))]


def _base(project) -> _Base:
    key = _key(project)
    with _CACHE_LOCK:
        base = _CACHE.get(project)
        if base is not None and base.key == key:
            return base
    r = project.refinement
    table = r._working_table()
    lebail = None
    if project.doc.mode in ("lebail", "pawley") and r.history is not None \
            and r._head_id is not None:
        lebail = list(r.history[r._head_id].state.reflections)
    model = _compile(project, r.structure, r.instrument, lebail)
    values = table.decode(table.x0())
    base = _Base(key=key, table=table, stored=[e.value for e in table.entries],
                 values=values, model=model, positions=_positions(model, values),
                 fcj_n=[fcj for _, fcj, _ in forward.window_sizing(model, values)],
                 lebail=lebail)
    with _CACHE_LOCK:
        _CACHE[project] = base
    return base


def _edits(body: Any) -> dict[str, float]:
    values = body.get("values") if isinstance(body, dict) else None
    if not isinstance(values, dict):
        raise GuiError("'values' maps dot-path → number")
    out = {}
    for path, value in values.items():
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            raise GuiError(f"{path!r}: {value!r} is not a finite number",
                           where=[path])
        out[path] = float(value)
    return out


def values_at(project, base: _Base, edits: dict[str, float]
              ) -> tuple[dict[str, float], dict[str, float]]:
    """The decoded values with ``edits`` applied, and every row they moved.

    The refusal is ``set_values``' own (``Refinement._refuse_value_edits``),
    so the preview and the apply cannot disagree. The table is put back
    before returning, ties included.
    """
    table = base.table
    try:
        by_path = project.refinement._refuse_value_edits(table, edits)
    except ValueError as exc:
        raise GuiError(str(exc), where=sorted(edits)) from None
    try:
        for path, value in edits.items():
            by_path[path].value = value
        table.refresh_ties()
        values = table.decode(table.x0())
        moved = dict(edits)
        for e, old in zip(table.entries, base.stored):
            if e.tie is not None and e.value != old:
                moved[e.path] = e.value
    finally:
        for e, old in zip(table.entries, base.stored):
            e.value = old
        table.refresh_ties()
    return values, moved


def _choose(base: _Base, values: dict[str, float]) -> str:
    """``frozen``, ``rewindowed`` or ``recompiled``, cheapest test first."""
    model = base.model
    for old, new in zip(base.positions, _positions(model, values)):
        ok = np.isfinite(old) & np.isfinite(new)
        if (np.abs(new[ok] - old[ok]) >= REFLECTION_MARGIN_DEG).any() \
                or (np.isfinite(old) != np.isfinite(new)).any():
            return "recompiled"
    tt = np.asarray(model.tt, dtype=np.float64)
    sized = forward.window_sizing(model, values)
    for ip, (cp, (_, fcj_n, halves)) in enumerate(zip(model.phases, sized)):
        # a node count grows against the larger of the compile's and the
        # sizing rule's own count at the base values, so the ~1 % between the
        # compile's width estimate and the drawn width cannot flip a count at
        # the values the compile was built for
        if (fcj_n > np.maximum(cp.fcj_n, base.fcj_n[ip])).any():
            return "rewindowed"
        for il, (pos, *_rest) in enumerate(model.phase_peaks(ip, values)):
            pos = np.asarray(pos, dtype=np.float64)
            core = halves[il] - model.window_slack_deg
            valid = np.isfinite(pos) & np.isfinite(core)
            i0, i1 = forward._window_bounds(tt, pos, np.where(valid, core, 0.0), valid)
            live = i1 > i0
            frozen = cp.win[il]
            if ((i0[live] < frozen[live, 0]) | (i1[live] > frozen[live, 1])).any():
                return "rewindowed"
    return "frozen"


def _recompile(project, base: _Base, edits: dict[str, float]) -> CompiledModel:
    r = project.refinement
    structure = r.structure.model_copy(deep=True)
    instrument = r.instrument.model_copy(deep=True)
    table = base.table
    by_path = {e.path: e for e in table.entries}
    try:
        for path, value in edits.items():
            by_path[path].value = value
        table.refresh_ties()
        table.apply_to_models(structure, instrument)
    finally:
        for e, old in zip(table.entries, base.stored):
            e.value = old
        table.refresh_ties()
    return _compile(project, structure, instrument,
                    None if base.lebail is None else copy.deepcopy(base.lebail))


def evaluate(project, body: Any) -> Packed:
    """The packed answer to ``POST /api/preview``; the module docstring has the contract."""
    from ..refine import _tick_rows

    edits = _edits(body)
    base = _base(project)
    with base.lock:
        values, moved = values_at(project, base, edits)
        evaluated = _choose(base, values)
        if evaluated == "recompiled":
            model = _recompile(project, base, edits)
        elif evaluated == "rewindowed":
            model = forward.rewindow(base.model, values)
        else:
            model = base.model
        y_calc, y_bkg, parts = model.evaluate_parts(values)
        y_calc = np.asarray(y_calc, dtype=np.float64)
        stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                   len(base.table.free_paths))
        # without the support, which evaluates every reflection's window and
        # cost more than the curve itself on the fluorapatite example
        ticks, tick_hkl, _support = _tick_rows(model, project.refinement.structure,
                                               values, support=False)
    arrays = {"two_theta": np.asarray(model.tt, dtype=np.float64),
              "y_calc": y_calc,
              "y_background": np.asarray(y_bkg, dtype=np.float64)}
    for ip, part in enumerate(parts):
        arrays[f"phase_{ip}"] = np.asarray(part, dtype=np.float64)
    header = {"evaluated": evaluated, "head": base.key[0], "rwp": stats.rwp,
              "values": moved,
              "phases": [ph.name for ph in project.refinement.structure.phases],
              "ticks": ticks, "tick_hkl": tick_hkl}
    return Packed(header, arrays)
