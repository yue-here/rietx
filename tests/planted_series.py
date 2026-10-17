"""A seeded in-situ series with planted events, and its null twin (issue #141).

A cooling ramp of a generic cubic perovskite ABO₃ (Pm-3m, a ≈ 3.95 Å), forward
modelled with rietx's own :func:`~rietx.model.forward.compile_model` and given
Poisson counting noise, with four events planted at known pattern indices:

``background``
    the background's constant term steps up by :attr:`PlantedSeries.background_factor`
    from this pattern on (a furnace window changed, a shield moved).
``bad``
    one blank frame: every Bragg scale zero, the background and its noise
    alone (the sample out of the beam; issue #481's case).
``second_phase``
    an unmodelled rock-salt phase (Fm-3m, a ≈ 4.21 Å) appears here, its
    scale growing linearly to :attr:`PlantedSeries.second_phase_scale` on the
    last pattern.
``transition``
    the perovskite turns tetragonal (P4/mmm) from this pattern on, c/a jumping
    to 1 + :attr:`PlantedSeries.tetragonality` at constant volume: a
    first-order transition with a visible peak split.

The **null** series (:func:`null_series`) is the same ramp, cell, seeds and
noise model with no event planted.  The fit model is fixed and high-symmetry
(:func:`cubic_model`): the cubic perovskite alone, which is what an operator
starts a ramp with before anything is known.

Synthetic, generic structures only.  Every number here is chosen for the
fixture: a capillary at λ = 0.4139 Å (the wavelength of the LaB6 series in
``tests/test_sequential.py``), 3-20° in 0.006° steps.

Why here: ``tests/`` already holds the package's forward-modelled fixtures
(``_synthetic_silicon.py``, ``_synthetic_crsbr.py``) and the runnable
scoreboard (``python -m tests.indexing_gallery``), it is outside the
wheel, and the fast suite imports it to regenerate a short series rather
than vendoring patterns (#141, 13 Oct).  A full-length run with its
``to_table()``::

    .venv/bin/python -m tests.planted_series --length 248 --seed 0 --out DIR
    .venv/bin/python -m tests.planted_series --null --length 248 --out DIR

writes ``DIR/table.csv`` (:meth:`~rietx.SeriesResult.to_table` over
:data:`TABLE_PATHS`) and ``DIR/signals.json`` (what was planted where, and
which of the result's own signals marks each event, :func:`surfaced`);
``--json`` adds the whole ``SeriesResult``, ``--patterns`` every pattern as a
two-column ``.xy``.  ``tests/data/planted_series/`` holds that output for the
default 248-pattern series and its null; the patterns are not vendored.
"""

from __future__ import annotations

import argparse
import functools
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.model import compiled
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase, Structure

WAVELENGTH = 0.4139
TT_MIN, TT_MAX, TT_STEP = 3.0, 20.0, 0.006
#: the true instrument: zero shift (°), Caglioti W (deg²) and the
#: Lorentzian X, Y (°), a ~0.035° line.  Y is off its floor at 0 so a fit
#: freeing it is not answering at a bound; the goniometer radius is declared
#: so a capillary fit has no unavailable correction to report on every pattern
TRUE_ZERO = 0.006
TRUE_W = 1.0e-3
TRUE_X, TRUE_Y = 2.0e-3, 4.0e-3
GONIOMETER_RADIUS_MM = 500.0
#: the true background's Chebyshev coefficients (counts)
TRUE_BKG = (300.0, -60.0, 20.0)
#: the perovskite's scale; its strongest line is ~2e4 counts over the background
TRUE_SCALE = 2.0e-4
#: the cubic cell edge at T_REF and its linear expansion coefficient (1/K)
A_REF, T_REF, ALPHA = 3.950, 400.0, 1.2e-5
#: the rock-salt phase's cell edge
A_SECOND = 4.210
#: the event kinds, in the order :func:`default_events` places them
EVENTS = ("background", "bad", "second_phase", "transition")
#: where each event falls by default, as a fraction of the length
_EVENT_FRACTIONS = {"background": 0.20, "bad": 0.35,
                    "second_phase": 0.50, "transition": 0.75}


def default_events(length: int) -> dict[str, int]:
    """Each event's pattern index on a series of ``length`` patterns.

    Background step, then the blank frame, then the second phase, then the
    transition last, so the first three each land where the cubic model still
    describes the pattern.
    """
    return {k: int(round(f * length)) for k, f in _EVENT_FRACTIONS.items()}


@dataclass
class PlantedSeries:
    """A generated series: its patterns, coordinate, labels and planted truth."""

    patterns: list[rx.PatternData]
    temperature: list[float]
    labels: list[str]
    #: event kind → index of the first pattern it affects (absent: not planted)
    events: dict[str, int]
    seed: int
    background_factor: float
    second_phase_scale: float
    tetragonality: float
    #: the true cell per pattern, (a, c): equal while cubic
    cell: list[tuple[float, float]] = field(default_factory=list)


def _perovskite(a: float, c: float | None = None) -> Phase:
    """ABO₃ on the ideal positions; tetragonal P4/mmm when ``c`` differs."""
    if c is None:
        return Phase(
            name="ABO3", space_group="P m -3 m", cell=Cell.cubic(a, vary=True),
            atoms=[_atom("A", "Sr", 0.0, 0.0, 0.0, 0.6),
                   _atom("B", "Ti", 0.5, 0.5, 0.5, 0.4),
                   _atom("O", "O", 0.5, 0.5, 0.0, 0.8)])
    cell = Cell.cubic(a, vary=True)
    cell.c.value = c
    return Phase(
        name="ABO3", space_group="P 4/m m m", cell=cell,
        atoms=[_atom("A", "Sr", 0.0, 0.0, 0.0, 0.6),
               _atom("B", "Ti", 0.5, 0.5, 0.5, 0.4),
               _atom("O1", "O", 0.5, 0.5, 0.0, 0.8),
               _atom("O2", "O", 0.5, 0.0, 0.5, 0.8)])


def _rock_salt(a: float) -> Phase:
    return Phase(name="MO", space_group="F m -3 m", cell=Cell.cubic(a),
                 atoms=[_atom("M", "Mg", 0.0, 0.0, 0.0, 0.5),
                        _atom("O", "O", 0.5, 0.5, 0.5, 0.6)])


def _atom(label, species, x, y, z, biso) -> Atom:
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                biso=Parameter(value=biso))


def _instrument(background: tuple[float, ...]) -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(
        wavelength=WAVELENGTH, goniometer_radius_mm=GONIOMETER_RADIUS_MM)
    ins.source.dispersion = rx.Dispersion()       # declared: the default, on
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W
    ins.profile.x.value, ins.profile.y.value = TRUE_X, TRUE_Y
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=float(v)) for v in background])
    return ins


def cell_at(t: float) -> float:
    """The cubic cell edge at temperature ``t`` (K)."""
    return A_REF * (1.0 + ALPHA * (t - T_REF))


def _pattern(phases: list[Phase], background: tuple[float, ...],
             rng: np.random.Generator) -> rx.PatternData:
    """One pattern: the forward model over the grid, then Poisson counts."""
    tt = np.arange(TT_MIN, TT_MAX, TT_STEP)
    ins = _instrument(background)
    structure = Structure(phases=phases)
    grid = rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = np.asarray(model.evaluate(table.decode(table.x0())))
    counts = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=np.asarray(model.tt).tolist(),
                          intensity=counts.tolist())


def numpy_path(fn):
    """Run ``fn`` with the compiled kernel tier off: the fixture's declared path.

    The committed output and the tests' pinned index lists are fit outcomes, and
    the kernels' ``exp`` is the platform's (``tests/CLAUDE.md`` § Quoting
    numbers): a path inherited from the machine passes on darwin/arm64 and can
    fail on the Linux nightly.  The numpy builder is the bit-identity oracle, so
    both the generator and the refit say ``set_enabled(False)`` and restore the
    caller's setting.
    """
    @functools.wraps(fn)
    def run(*args, **kw):
        was = compiled.set_enabled(False)
        try:
            return fn(*args, **kw)
        finally:
            compiled.set_enabled(was)
    return run


@numpy_path
def generate(length: int = 248, *, seed: int = 0,
             events: dict[str, int] | None = None,
             t_start: float = 900.0, t_end: float = 400.0,
             background_factor: float = 1.5,
             second_phase_scale: float = 0.6 * TRUE_SCALE,
             tetragonality: float = 0.005) -> PlantedSeries:
    """A cooling ramp of ``length`` patterns with ``events`` planted.

    ``events`` maps each kind of :data:`EVENTS` to the index of the first
    pattern it affects; ``None`` places all four (:func:`default_events`), and
    an empty dict plants none (:func:`null_series`).  The temperature falls
    linearly from ``t_start`` to ``t_end`` whatever the length, so a short
    series is the long one sampled coarsely.  Pattern ``k``'s noise is drawn
    from ``default_rng([seed, k])``, so the null and the planted series share
    every draw where their expected counts agree.
    """
    if length < 2:
        raise ValueError(f"a series needs at least two patterns, not {length}")
    events = default_events(length) if events is None else dict(events)
    unknown = set(events) - set(EVENTS)
    if unknown:
        raise ValueError(f"unknown event kinds {sorted(unknown)}; "
                         f"the kinds are {list(EVENTS)}")
    bad = [k for k, i in events.items() if not 0 < i < length]
    if bad:
        raise ValueError(f"events {bad} fall outside patterns 1..{length - 1}")

    temperature = np.linspace(t_start, t_end, length).tolist()
    patterns, cells = [], []
    for k, t in enumerate(temperature):
        a = cell_at(t)
        if k >= events.get("transition", length):
            # constant volume: a²c = a_cubic³
            at = a / (1.0 + tetragonality) ** (1.0 / 3.0)
            ct = at * (1.0 + tetragonality)
            main = _perovskite(at, ct)
            cells.append((at, ct))
        else:
            main = _perovskite(a)
            cells.append((a, a))
        main.scale.value = TRUE_SCALE
        phases = [main]
        onset = events.get("second_phase", length)
        if k >= onset:
            grow = (k - onset + 1) / (length - onset)
            second = _rock_salt(A_SECOND * (1.0 + ALPHA * (t - T_REF)))
            second.scale.value = second_phase_scale * grow
            phases.append(second)
        background = list(TRUE_BKG)
        if k >= events.get("background", length):
            background[0] *= background_factor
        if k == events.get("bad"):
            for phase in phases:      # the sample out of the beam
                phase.scale.value = 0.0
        rng = np.random.default_rng([seed, k])
        patterns.append(_pattern(phases, tuple(background), rng))

    labels = [f"T{k:03d}" for k in range(length)]
    return PlantedSeries(patterns=patterns, temperature=temperature,
                         labels=labels, events=events, seed=seed,
                         background_factor=background_factor,
                         second_phase_scale=second_phase_scale,
                         tetragonality=tetragonality, cell=cells)


def null_series(length: int = 248, *, seed: int = 0, **kw) -> PlantedSeries:
    """The negative arm: the same ramp and noise with no event planted."""
    return generate(length, seed=seed, events={}, **kw)


def cubic_model(start_t: float = 900.0) -> tuple[Structure, rx.Instrument]:
    """The fixed fit model: the cubic perovskite alone, started 0.1 % off.

    Zero shift at 0, the width 1.5× too broad, a 4-term flat background —
    what an operator would start the ramp's first pattern from.
    """
    phase = _perovskite(cell_at(start_t) * 1.001)
    phase.scale.value = TRUE_SCALE * 1.5
    ins = _instrument((0.0,))
    ins.zero_shift.value = 0.0
    ins.profile.w.value = TRUE_W * 1.5
    ins.profile.x.value, ins.profile.y.value = TRUE_X * 1.5, TRUE_Y * 1.5
    ins.background = BackgroundChebyshev.with_terms(4)
    return Structure(phases=[phase]), ins


@numpy_path
def refine(series: PlantedSeries, **kw) -> rx.SeriesResult:
    """``refine_sequential`` with the fixed cubic model, the fixture's protocol.

    ``mccusker_default`` on the first pattern, ``refit="single"`` after it,
    forward, reseed on: the defaults, so the fixture measures what a plain
    call carries, on the numpy path (:func:`numpy_path`).  ``kw`` goes to :func:`rietx.refine_sequential`.
    """
    structure, ins = cubic_model(series.temperature[0])
    kw.setdefault("plan", "mccusker_default")
    return rx.refine_sequential(series.patterns, structure, ins,
                                x=series.temperature, x_label="T (K)",
                                labels=series.labels, **kw)


#: the paths the committed table carries: the cell, the scale, the zero, the
#: Gaussian width and the background's constant, each with its esd
TABLE_PATHS = ("phases.0.cell.a", "phases.0.scale", "instrument.zero_shift",
               "instrument.profile.w", "instrument.background.c0")


def signals(result: rx.SeriesResult) -> dict:
    """What the result itself says, in its own vocabulary, compactly.

    Read off the :class:`~rietx.SeriesResult` and nothing else (WP-1317's one
    vocabulary): the entries above the Rwp fence (``SEQUENTIAL_RWP_OUTLIER``),
    the flagged steps (``SeriesResult.discontinuities``, one per
    ``SEQUENTIAL_DISCONTINUITY``), the reseeded entries
    (``SEQUENTIAL_RESEED``), the quarantined ones (``SEQUENTIAL_UNRECOVERED``),
    the entries carrying ``PHASE_UNCONSTRAINED``, and every series-level code
    with its ``where``.
    """
    return {
        "above_fence": [e.index for e in result.entries if e.above_fence],
        "steps": [[s.path, *s.indices] for s in result.discontinuities or []],
        "reseeded": [e.index for e in result.entries if e.reseeded],
        "unrecovered": [e.index for e in result.entries
                        if e.status == "diverged"],
        "phase_unconstrained": [
            e.index for e in result.entries
            if any(d.code == "PHASE_UNCONSTRAINED" for d in e.diagnostics)],
        "codes": sorted({(d.code, ",".join(d.where or []))
                         for d in result.diagnostics}),
    }


def _run_onsets(indices: list[int]) -> list[int]:
    """The first index of each run of consecutive indices."""
    have = set(indices)
    return [i for i in sorted(have) if i - 1 not in have]


def second_phase_tolerance(length: int, onset: int) -> int:
    """How many patterns after its onset a growing phase may first be seen.

    A tenth of the patterns it grows over, rounded up: the phase grows
    linearly from nothing, so the fence can only see it once its share has
    grown, and on a longer series that takes more patterns.
    """
    return -(-(length - onset) // 10)


def surfaced(result: rx.SeriesResult, kind: str, index: int) -> str | None:
    """The signal by which ``result`` marks the event ``kind`` planted at
    ``index``, or ``None`` when it marks none.

    One rule per kind, each read from :func:`signals`:

    ``background``
        a flagged step on ``instrument.background.c0`` between ``index - 1``
        and ``index``;
    ``bad``
        the frame alone above the Rwp fence, neither neighbour with it (a
        frame inside a run is the run's), or a flagged step on
        ``phases.0.scale`` into or out of it;
    ``second_phase``
        a run of patterns above the fence beginning within
        :func:`second_phase_tolerance` of ``index``;
    ``transition``
        a run above the fence beginning at ``index`` or the one after it, or a
        flagged step on a ``phases.0.cell`` length between ``index - 1`` and
        ``index``.

    A reseed is not a marker of its own: it fires through any run above the
    fence wherever the ladder's first rung is cut short, on the event's
    neighbours as readily as on the event.
    """
    sig = signals(result)
    onsets = _run_onsets(sig["above_fence"])
    if kind == "background":
        for path, i, j in sig["steps"]:
            if path == "instrument.background.c0" and (i, j) == (index - 1, index):
                return f"SEQUENTIAL_DISCONTINUITY {path} ({i}, {j})"
        return None
    if kind == "bad":
        above = set(sig["above_fence"])
        if index in above and not {index - 1, index + 1} & above:
            return f"SEQUENTIAL_RWP_OUTLIER {index}"
        for path, i, j in sig["steps"]:
            if path == "phases.0.scale" and index in (i, j):
                return f"SEQUENTIAL_DISCONTINUITY {path} ({i}, {j})"
        return None
    if kind == "second_phase":
        n = len(result.entries)
        tol = second_phase_tolerance(n, index)
        for k in onsets:
            if index <= k <= index + tol:
                return f"SEQUENTIAL_RWP_OUTLIER run from {k}"
        return None
    if kind == "transition":
        for k in onsets:
            if index <= k <= index + 1:
                return f"SEQUENTIAL_RWP_OUTLIER run from {k}"
        for path, i, j in sig["steps"]:
            if path.startswith("phases.0.cell.") and (i, j) == (index - 1, index):
                return f"SEQUENTIAL_DISCONTINUITY {path} ({i}, {j})"
        return None
    raise ValueError(f"unknown event kind {kind!r}; the kinds are {list(EVENTS)}")


def write_outputs(series: PlantedSeries, result: rx.SeriesResult,
                  out: Path) -> None:
    """``table.csv`` (``to_table`` over :data:`TABLE_PATHS`, six significant
    figures) and ``signals.json`` (what was planted, :func:`signals`, and
    which signal marks each event)."""
    import csv

    header, rows = result.to_table(paths=list(TABLE_PATHS))
    with (out / "table.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow(["" if v is None else f"{v:.6g}" if isinstance(v, float)
                        else v for v in row])
    record = {
        "length": len(series.patterns), "seed": series.seed,
        "events": series.events,
        "surfaced": {k: surfaced(result, k, i) for k, i in series.events.items()},
        "signals": signals(result),
    }
    (out / "signals.json").write_text(json.dumps(record, indent=1) + "\n",
                                     encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m tests.planted_series",
        description="Generate the planted-events series (or its null), "
                    "refine it and write its to_table() and signals.")
    p.add_argument("--length", type=int, default=248)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--null", action="store_true",
                   help="plant no event (the negative arm)")
    for kind in EVENTS:
        p.add_argument(f"--{kind.replace('_', '-')}", type=int, default=None,
                       metavar="INDEX", help=f"index of the {kind} event")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--patterns", action="store_true",
                   help="also write every pattern as a two-column .xy")
    p.add_argument("--json", action="store_true",
                   help="also write the whole SeriesResult as series.json")
    args = p.parse_args(argv)

    events: dict[str, int] | None
    if args.null:
        events = {}
    else:
        events = default_events(args.length)
        for kind in EVENTS:
            given = getattr(args, kind)
            if given is not None:
                events[kind] = given
    series = generate(args.length, seed=args.seed, events=events)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.patterns:
        for label, pattern in zip(series.labels, series.patterns, strict=True):
            np.savetxt(args.out / f"{label}.xy",
                       np.column_stack([pattern.two_theta, pattern.intensity]),
                       fmt="%.4f %.0f")
    t0 = time.perf_counter()
    result = refine(series)
    wall = time.perf_counter() - t0
    write_outputs(series, result, args.out)
    if args.json:
        (args.out / "series.json").write_text(result.model_dump_json(),
                                             encoding="utf-8", newline="\n")
    print(f"{len(series.patterns)} patterns refined in {wall:.1f} s")
    for kind, index in series.events.items():
        print(f"{kind} at {index}: {surfaced(result, kind, index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
