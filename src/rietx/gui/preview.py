"""The pattern at parameter values nobody has applied (WP-2125).

``POST /api/preview`` serves the Interactive tab's sliders: the calculated
pattern, its background, each phase's contribution, the three residuals the
curves route sends and the reflection ticks at values the person is dragging,
with the Rwp there. **Nothing is written.**
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
  examples). Also when a magnetic phase's second frozen family (WP-1343)
  would grow or appear, since ``rewindow`` keeps that family's windows.
- ``rewindowed`` when a window sized at the new values, its movement slack
  removed, reaches outside the frozen one, or a node count grows. Through
  ``forward.rewindow`` (0.6-3.1 ms), which is the compile's own sizing rule
  and reproduced a fresh compile to 1e-13 σ in every case measured.
- ``frozen`` otherwise: the cached compile, evaluated as it stands.

The window and node branches are the compile's own sizing rule asked at the
new values. The recompile trigger is looser than a fresh compile's list: a
reflection that started just past ``REFLECTION_MARGIN_DEG`` and moved inward by
less than it is missing (WP-2125 § The tier of each rule). The WP's measurements show why all three exist. A frozen window costs
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

import math
import threading
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..model import forward
from ..model.forward import REFLECTION_MARGIN_DEG, CompiledModel, compile_model, orbit_split_of
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
    #: the same for the magnetic family, ``None`` for a phase without one
    fcj_n_mag: list[np.ndarray | None]
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


def _compile(project, structure, instrument, lebail,
             orbit_split: list | None = None) -> CompiledModel:
    model = compile_model(structure, instrument, project.data,
                          mode=project.doc.mode,
                          two_theta_limits=project.doc.two_theta_limits,
                          orbit_split=orbit_split)
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
                 fcj_n_mag=[None if s is None else s[1] for s in
                            forward.window_sizing(model, values, component=1)],
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


@contextmanager
def _edited(project, base: _Base, edits: dict[str, float]) -> Iterator[None]:
    """``base.table`` with ``edits`` applied and its ties and derived rows
    refreshed, put back on exit.

    The refusal is ``set_values``' own (``Refinement._refuse_value_edits``),
    so the preview and the apply cannot disagree.
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
        yield
    finally:
        for e, old in zip(table.entries, base.stored):
            e.value = old
        table.refresh_ties()


def _moved(base: _Base, edits: dict[str, float]) -> dict[str, float]:
    """Every row the edits moved: the edits, and each tied or derived row
    (a user formula, a rigid body's atoms) that follows them."""
    moved = dict(edits)
    for e, old in zip(base.table.entries, base.stored):
        if e.value != old:
            moved[e.path] = e.value
    return moved


def _outgrown(model: CompiledModel, values: dict[str, float], component: int,
              base_fcj: list[np.ndarray | None]) -> bool:
    """Whether one frozen family's windows or node counts are too small at ``values``."""
    tt = np.asarray(model.tt, dtype=np.float64)
    sized = forward.window_sizing(model, values, component=component)
    for ip, (cp, family) in enumerate(zip(model.phases, sized)):
        if family is None:
            continue
        _, fcj_n, halves = family
        win, frozen_fcj = ((cp.win, cp.fcj_n) if component == 0
                           else (cp.win_mag, cp.fcj_n_mag))
        # a node count grows against the larger of the compile's and the
        # sizing rule's own count at the base values, so the ~1 % between the
        # compile's width estimate and the drawn width cannot flip a count at
        # the values the compile was built for
        if (fcj_n > np.maximum(frozen_fcj, base_fcj[ip])).any():
            return True
        for il, (pos, *_rest) in enumerate(
                model.phase_peaks(ip, values, component=component)):
            pos = np.asarray(pos, dtype=np.float64)
            core = halves[il] - model.window_slack_deg
            valid = np.isfinite(pos) & np.isfinite(core)
            i0, i1 = forward._window_bounds(tt, pos, np.where(valid, core, 0.0), valid)
            live = i1 > i0
            if ((i0[live] < win[il][live, 0]) | (i1[live] > win[il][live, 1])).any():
                return True
    return False


def _choose(base: _Base, values: dict[str, float]) -> str:
    """``frozen``, ``rewindowed`` or ``recompiled``, cheapest test first."""
    model = base.model
    for old, new in zip(base.positions, _positions(model, values)):
        ok = np.isfinite(old) & np.isfinite(new)
        if (np.abs(new[ok] - old[ok]) >= REFLECTION_MARGIN_DEG).any() \
                or (np.isfinite(old) != np.isfinite(new)).any():
            return "recompiled"
    for ip, cp in enumerate(model.phases):
        # a magnetic width moved off zero: the compile builds the second
        # family only where one is nonzero (WP-1343), and this one has none
        if (model.mode == "rietveld" and cp.magnetic is not None
                and not model.mag_split(ip)
                and (values.get(f"phases.{ip}.magnetic_lor_size", 0.0) != 0.0
                     or values.get(f"phases.{ip}.magnetic_lor_strain", 0.0) != 0.0)):
            return "recompiled"
    # ``rewindow`` keeps the magnetic family's windows, so only a compile
    # can grow them
    if _outgrown(model, values, 1, base.fcj_n_mag):
        return "recompiled"
    if _outgrown(model, values, 0, base.fcj_n):
        return "rewindowed"
    return "frozen"


def _recompile(project, base: _Base) -> CompiledModel:
    """A compile at the values ``base.table`` holds, inside :func:`_edited`.

    The base compile's orbit split, moment frames and σ ride along, as
    ``Refinement._final_compile`` carries the solve's: a site the edit moves
    onto a mirror keeps its multiplicity, a moment DOF is read in the frame
    the other two paths read it in, and the Rwp of every path divides by one σ
    (a measured background's scale widens σ at compile, WP-1309).
    """
    r = project.refinement
    structure = r.structure.model_copy(deep=True)
    instrument = r.instrument.model_copy(deep=True)
    base.table.apply_to_models(structure, instrument)
    model = _compile(project, structure, instrument, base.lebail,
                     orbit_split=orbit_split_of(base.model))
    base.table.push_moment_frames(model)
    model.sigma = base.model.sigma
    return model


def evaluate(project, body: Any) -> Packed:
    """The packed answer to ``POST /api/preview``; the module docstring has the contract."""
    from ..refine import _tick_rows

    edits = _edits(body)
    base = _base(project)
    with base.lock:
        with _edited(project, base, edits):
            values = base.table.decode(base.table.x0())
            moved = _moved(base, edits)
            evaluated = _choose(base, values)
            if evaluated == "recompiled":
                try:
                    model = _recompile(project, base)
                except ValueError as exc:
                    # a multi-source tie pushed past its bounds, which
                    # ``set_values`` refuses at its write-back in this sentence
                    raise GuiError(str(exc), where=sorted(edits)) from None
        if evaluated == "rewindowed":
            model = forward.rewindow(base.model, values)
        elif evaluated == "frozen":
            model = base.model
        y_calc, y_bkg, parts = model.evaluate_parts(values)
        y_calc = np.asarray(y_calc, dtype=np.float64)
        stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                   len(base.table.free_paths))
        # without the support, which evaluates every reflection's window and
        # cost more than the curve itself on the fluorapatite example
        ticks, tick_hkl, _support = _tick_rows(model, project.refinement.structure,
                                               values, support=False)
    # The three residuals the curves route sends (``viz.packed.curve_arrays``),
    # so the residual pane under a preview draws the server's numbers. Δ/σ
    # divides by the compile's own σ, the one the Rwp above is taken over, and
    # the Σχ² is accumulated over every channel here, so a client drawing a
    # subset of the channels still reads exact values (WP-2128).
    raw = np.asarray(model.y_obs, dtype=np.float64) - y_calc
    delta = raw / np.asarray(model.sigma, dtype=np.float64)
    arrays = {"two_theta": np.asarray(model.tt, dtype=np.float64),
              "y_calc": y_calc,
              "y_background": np.asarray(y_bkg, dtype=np.float64),
              "delta": delta, "delta_raw": raw,
              "cumulative_chi2": np.cumsum(delta**2)}
    for ip, part in enumerate(parts):
        arrays[f"phase_{ip}"] = np.asarray(part, dtype=np.float64)
    header = {"evaluated": evaluated, "head": base.key[0], "rwp": stats.rwp,
              "values": moved,
              "phases": [ph.name for ph in project.refinement.structure.phases],
              "ticks": ticks, "tick_hkl": tick_hkl}
    return Packed(header, arrays)
