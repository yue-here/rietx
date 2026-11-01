"""WP-2003 task 2, the measurement half: the reseed fence on, status-only and off.

What it measures.  :data:`rietx.sequential.RESEED_FACTOR` sets the Rwp fence of
:meth:`rietx.SequentialRefinement.fit`: a warm fit above ``reseed_factor`` × the
median Rwp of the accepted patterns climbs the rung ladder (``_ladder``), and a
kept fit above it is an outlier (``SEQUENTIAL_RWP_OUTLIER``) whose steps the
discontinuity scan drops.  Each chain family is run under three arms, every
other setting at the family's own protocol:

``on``
    the default, ``reseed=True, reseed_factor=RESEED_FACTOR`` (1.25).
``status``
    ``reseed=True, reseed_factor=float("inf")``: the ladder escalates only on a
    diverged or raised rung, never on Rwp.  ``fit`` does not validate the
    factor, so ``inf`` is accepted as given; every ``rwp_fence`` is then
    ``inf`` and no entry is ever ``above_fence``.
``off``
    ``reseed=False``: no fence- or status-driven escalation.  Not "no ladder":
    a first rung WP-1127's budget truncated still escalates one rung
    (``forced`` in ``SequentialRefinement._chain`` bypasses ``reseed``).  The
    fence is still *recorded* (the field is written whatever ``reseed``
    says), so its codes still fire.
``status_maxiter``
    as ``status``, and the ladder also escalates while its best attempt so
    far ended ``max_iter`` (added the second session, 2026-10-24: cpd-1b's bad
    warm rung ended ``max_iter``, which ``status`` keeps).  The fence is asked
    about the best attempt, not the last rung, so a warm ``max_iter`` that a
    worse later rung does not displace keeps escalating to the last rung.
    ``fit`` has no such switch, so the arm wraps
    :func:`rietx.sequential._reseed_needed` for its own run alone.
``status_runaway``
    as ``status``, and the ladder also escalates while its best attempt so
    far carries a ``CELL_RUNAWAY`` diagnostic, from any of its stages (batch.md
    C1, option (iii); added the third session, 2026-10-25).  The same wrapper
    as ``status_maxiter``, asked about ``RefinementResult.diagnostics``
    instead of ``.status``; ``_reseed_needed`` has one call site, in
    ``SequentialRefinement._chain``, looked up as a module global at call
    time, so the wrapper reaches the forward and the backward pass.

Two arms put the first-rung bound aside (WP-1127, ``first_rung_factor``,
default :data:`rietx.sequential.FIRST_RUNG_FACTOR`), each to be read against
the arm it differs from by that alone (clashes.md X1, X2):

``on_nobound``
    as ``on``, with ``first_rung_factor=None``.
``off_nobound``
    as ``off``, with ``first_rung_factor=None``: the one arm with no
    escalation of any kind, since ``reseed=False`` declines the fence and the
    status, and with no bound no first rung is truncated, so ``forced`` never
    fires.

and one reference arm, ``ref``: every pattern fitted cold and alone, as
``SequentialRefinement(...).fit([pattern])`` from the chain's own initial
models, which is exactly what the chain's cold rung computes.  The CPD families
add ``ref_seeded``, the acceptance suite's independent protocol
(``seed_scales`` on each mixture, the ``sample1_results`` fits), and its
weighed composition; the synthetic families add their simulated truth.

The families (:data:`FAMILIES`), each at its own test's or example's protocol:
``cpd`` (IUCr CPD sample 1a-1h, ``chained_all``), ``cpd-noclose`` (the same
with ``plan.closing_window_tol = None``, a declared variant), ``cpd-ftolnone``
(the same with ``plan.intermediate_ftol = None``, closing stage on: clashes.md
X13's open arm, a declared variant), ``planted`` and
``planted-null`` (``tests/planted_series.py``, 248 patterns), ``trigger``
(``examples/bench_refinement.py``'s ``_trigger_series``), ``cr2wo6`` (the
HB-2A 4 K/150 K pair of ``tests/test_magnetic_series.py``) and
``tut05-jump``/``tut05-broken`` (tutorial 05's two edited LaB6 ramps).

Per pattern it records index, label, status, the rung kept, ``rungs_tried``,
``reseeded``, ``rwp_warm``, the kept Rwp, ``rwp_fence``, ``SeriesEntry.n_iterations``
(residual evaluations over every returned rung, scipy's ``nfev`` convention),
the kept fit's own evaluations, the solver calls' ``nfev``/``njev`` counted at
``rietx.optimize.lm.minimize`` and scipy's ``least_squares`` (the scaffold of
``examples/bench_refinement.py``, extended to the LM driver that scaffold does
not see), the wall clock between ``on_result`` calls, the entry's codes, the
series-level codes naming it, and every refined value with its esd.  A
pattern every rung of which raised has no entry and no ``on_result`` call, so
its cost lands in the next row, which names it in ``charged_failures``.

Stored values carry 12 significant figures and esds 4, far below every
comparison's resolution; ``values_sha`` hashes the full-precision values and
esds, so two rows with equal hashes are bit-identical.

Comparisons (``--table``).  Of a row against a baseline row, per pattern: the
worst ``|Δ| / esd_baseline`` over the refined paths both carry, and over the
weight fractions, the baseline being ``on`` for an arm against ``on`` and the
reference for an arm against a reference (the row's own esd only where the
baseline has none); against truth, ``|Δ| / esd`` with the arm's own esd.  Not
the larger of the two esds and not a combined σ: both fits saw the same
counts, so their esds are not independent, and a fit that lands far off
carries inflated esds that would shrink the very difference asked about
(:func:`worst` has the measured case).  A path with no esd in either row is
compared on its own (moved past 1e-6 relative), and the family's anchored
coordinate DOFs (``ParameterTable.anchored_dof_paths``, recorded per run) are
left out: such a DOF is a displacement from where its own fit began, so the
absolute coordinate rows are compared instead.  ``--annotate`` adds that
list to a JSON written before the field existed.  An arm that differs from
another by one switch is also compared against that one (:data:`PAIRED`), and
a declared variant family against its base family arm by arm
(:data:`VARIANT_OF`), with the base's esd.

How to run (from the repository root; ``[dev]`` extras suffice)::

    .venv/bin/python docs/wp/2003-batch/measure_reseed.py --family cpd --arm all
    .venv/bin/python docs/wp/2003-batch/measure_reseed.py --family planted --arm on
    .venv/bin/python docs/wp/2003-batch/measure_reseed.py --table > tables.md

    .venv/bin/python docs/wp/2003-batch/measure_reseed.py --annotate

``--family`` is one of :data:`FAMILIES` or ``all``; ``--arm`` one of
:data:`ARMS`, ``ref``, ``ref_seeded`` (CPD only) or ``all``; ``--out`` the JSON
directory (default ``docs/wp/2003-batch/reseed``); ``--first N`` cuts a family
to its first N patterns (the patterns are those of the full family, so a cut
chain is the full chain's prefix).  A chain arm prints one progress line per
finished pattern.  Telemetry is off (``RIETX_TELEMETRY=0``) so no run
directory is written.  Wall clock is context only, never the comparison; on a
loaded machine set ``OPENBLAS_NUM_THREADS=1`` for every arm of a family alike
(the closing stage's quadrature calls ``leggauss``, which contended BLAS
threads slowed ~400× here), and the JSON records the setting.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")

ROOT = Path(__file__).resolve().parents[3]
for sub in ("", "tests", "examples"):
    sys.path.insert(0, str(ROOT / sub) if sub else str(ROOT))


import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.sequential import RESEED_FACTOR  # noqa: E402

OUT = Path(__file__).resolve().parent / "reseed"

#: the chain arms (module docstring), as ``SequentialRefinement.fit`` kwargs
ARMS = {
    "on": {"reseed": True, "reseed_factor": RESEED_FACTOR},
    "status": {"reseed": True, "reseed_factor": float("inf")},
    "off": {"reseed": False},
    "status_maxiter": {"reseed": True, "reseed_factor": float("inf")},
    "status_runaway": {"reseed": True, "reseed_factor": float("inf")},
    "on_nobound": {"reseed": True, "reseed_factor": RESEED_FACTOR,
                   "first_rung_factor": None},
    "off_nobound": {"reseed": False, "first_rung_factor": None},
}
#: arms whose rule ``fit`` cannot express, so ``_reseed_needed`` is wrapped:
#: the best attempt so far also escalates on a ``status`` in the first tuple
#: or a diagnostic ``code`` in the second
ESCALATE_ON: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "status_maxiter": (("max_iter",), ()),
    "status_runaway": ((), ("CELL_RUNAWAY",)),
}
#: an arm → the arm it differs from by one switch, which ``--table`` also
#: compares it against (every arm is compared against ``on`` besides)
PAIRED = {"status_maxiter": "status", "status_runaway": "status",
          "off_nobound": "off"}
REFERENCE_ARMS = ("ref", "ref_seeded")
#: a between-arm difference counted as "the accepted values differ"
DIFFER_ESD = 0.1


@contextmanager
def _escalating(statuses=(), codes=()):
    """Make ``_reseed_needed`` also reject a best-so-far attempt whose status
    is in *statuses* or that carries a diagnostic whose code is in *codes*,
    for the ``with`` block alone.

    ``RefinementResult.diagnostics`` holds every stage's ``CELL_RUNAWAY``
    (``Refinement.fit`` appends each stage's as it runs), so a code asks
    about the whole rung, its closing stage included.
    """
    if not statuses and not codes:
        yield
        return
    import rietx.sequential as seq
    original = seq._reseed_needed

    def wrapped(result, accepted_rwp, factor):
        return (result.status in statuses
                or any(d.code in codes for d in result.diagnostics)
                or original(result, accepted_rwp, factor))

    seq._reseed_needed = wrapped
    try:
        yield
    finally:
        seq._reseed_needed = original


# -- families ---------------------------------------------------------------

@dataclass
class Family:
    """One chain family at its own protocol."""

    name: str
    title: str
    protocol: str
    patterns: list
    start: Callable[[], tuple]          # the chain's initial models, fresh copies
    fit_kw: dict
    labels: list[str] | None = None
    x: list[float] | None = None
    x_label: str = "index"
    numpy_path: bool = False
    #: the paths the markdown shows values for
    key_paths: list[str] = field(default_factory=list)
    #: pattern index → {path: true value}; synthetic families only
    truth: Callable[[int], dict[str, float]] | None = None
    #: pattern index → {phase name: weighed wt %}; CPD only
    weighed: list[dict[str, float]] | None = None
    #: CPD only: pattern index → the acceptance suite's per-mixture start
    seeded_start: Callable[[int], tuple] | None = None
    events: dict[str, int] = field(default_factory=dict)


def _cpd(closing: bool = True, ftol_none: bool = False) -> Family:
    """The CPD chain; ``closing=False`` is the declared variant with
    ``plan.closing_window_tol = None``, the bit-identical way back from
    WP-2002's closing stage, and the one change from the protocol.
    ``ftol_none=True`` is the declared variant with ``plan.intermediate_ftol
    = None`` (WP-1123's way back), closing stage on: clashes.md X13's open
    arm.  Since WP-2045 the last declared stage converges at the solver's
    tolerance whatever the plan says, so a collapsed warm rung (one stage) is
    unchanged by it, and the variant reaches the cold fit of 1a and any
    ``warm_staged`` or ``cold`` rung."""
    from tests.test_acceptance_qpa_roundrobin import (
        DATA,
        SAMPLE1,
        WEIGHED,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
        zincite_phase,
    )

    if not DATA.exists():
        raise FileNotFoundError("IUCr QPA round-robin dataset not present")
    patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1]

    def phases():
        return [corundum_phase(), zincite_phase(), fluorite_phase()]

    def start():
        # tests/test_acceptance_sequential.py::chained_all, line for line
        structure = rx.Structure(phases=phases())
        ins = qarr_instrument()
        seed_scales(structure, ins, patterns[0])
        return structure, ins

    def seeded_start(k):
        # conftest.sample1_results / test_acceptance_qpa_roundrobin._fit
        structure = rx.Structure(phases=phases())
        ins = qarr_instrument()
        seed_scales(structure, ins, patterns[k])
        return structure, ins

    plan = qpa_plan()
    if not closing:
        plan.closing_window_tol = None
    if ftol_none:
        plan.intermediate_ftol = None
    name, title, change = "cpd", "IUCr CPD sample-1 chain 1a-1h (real, lab Cu Kα)", ""
    if not closing:
        name, title = "cpd-noclose", title + ", closing stage off (declared variant)"
        change = "; the one change: plan.closing_window_tol = None"
    if ftol_none:
        name = "cpd-ftolnone" if closing else name + "-ftolnone"
        title += (", intermediate_ftol = None, closing stage "
                  + ("on" if closing else "off") + " (declared variant)")
        change = (change + ", and plan.intermediate_ftol = None" if change else
                  "; the one change: plan.intermediate_ftol = None (qpa_plan "
                  "names 1e-6)")
    return Family(
        name=name, title=title,
        protocol=("tests/test_acceptance_sequential.py chained_all: "
                  "SequentialRefinement(structure, qarr_instrument()) with "
                  "seed_scales on 1a, carry=('*',), plan=qpa_plan(), "
                  "refit='single', dispersion declined, compiled tier default"
                  + change),
        patterns=patterns, start=start, fit_kw={"plan": plan},
        labels=list(SAMPLE1),
        key_paths=["phases.0.cell.a", "phases.0.cell.c", "phases.1.cell.a",
                   "phases.2.cell.a", "instrument.zero_shift",
                   "instrument.geometry.sample_displacement"],
        weighed=[{k: v for k, v in WEIGHED[s].items()} for s in SAMPLE1],
        seeded_start=seeded_start)


def _planted(null: bool = False) -> Family:
    from tests.planted_series import (
        TRUE_BKG,
        TRUE_SCALE,
        TRUE_W,
        TRUE_X,
        TRUE_Y,
        TRUE_ZERO,
        cell_at,
        cubic_model,
        generate,
        null_series,
    )

    series = null_series(248, seed=0) if null else generate(248, seed=0)
    events = dict(series.events)

    def start():
        return cubic_model(series.temperature[0])

    def truth(k):
        t = series.temperature[k]
        out = {"instrument.zero_shift": TRUE_ZERO,
               "instrument.profile.w": TRUE_W,
               "instrument.profile.x": TRUE_X,
               "instrument.profile.y": TRUE_Y,
               "instrument.background.c1": TRUE_BKG[1],
               "instrument.background.c2": TRUE_BKG[2],
               "instrument.background.c3": 0.0,
               "phases.0.atoms.0.biso": 0.6, "phases.0.atoms.1.biso": 0.4,
               "phases.0.atoms.2.biso": 0.8}
        c0 = TRUE_BKG[0]
        if k >= events.get("background", 10**9):
            c0 *= series.background_factor
        out["instrument.background.c0"] = c0
        out["phases.0.scale"] = 0.0 if k == events.get("bad") else TRUE_SCALE
        # a cubic edge exists only while the perovskite is cubic; after the
        # transition the fixed cubic model has no true value to be held to
        if k < events.get("transition", 10**9):
            out["phases.0.cell.a"] = cell_at(t)
        return out

    name = "planted-null" if null else "planted"
    what = ("its null twin (same ramp, no event)" if null else
            "events: background step 50, blank frame 87, unmodelled phase "
            "from 124, cubic → tetragonal 186")
    return Family(
        name=name,
        title=f"planted perovskite cooling ramp, 248 patterns (synthetic), {what}",
        protocol=("tests/planted_series.py refine(): cubic_model(T0), "
                  "plan='mccusker_default', refit='single', forward, "
                  "x=T (K), carry=('*',), compiled tier OFF (numpy_path)"),
        patterns=series.patterns, start=start,
        fit_kw={"plan": "mccusker_default"},
        labels=list(series.labels), x=list(series.temperature),
        x_label="T (K)", numpy_path=True,
        key_paths=["phases.0.cell.a", "phases.0.scale", "instrument.zero_shift",
                   "instrument.profile.w", "instrument.background.c0"],
        truth=truth, events=events)


def _planted_null() -> Family:
    return _planted(null=True)


def _trigger() -> Family:
    import bench_refinement as bench

    from rietx.params.vector import ParameterTable

    setup = bench._trigger_series()
    drifts = [i * 100e-6 for i in range(len(setup.patterns))]

    def start():
        return (setup.structure.model_copy(deep=True),
                setup.instrument.model_copy(deep=True))

    def truth(k):
        table = ParameterTable(rx.Structure(phases=bench._trigger_phases(drifts[k])),
                               bench._trigger_instrument(truth=True))
        return {e.path: e.value for e in table.entries}

    return Family(
        name="trigger",
        title=("simulated trigger series: ten ZrMo₂O₈-shaped 4 165-point "
               "patterns, four phases, 100 ppm/step cell ramp (synthetic)"),
        protocol=("examples/bench_refinement.py _trigger_series(): "
                  "refine_sequential(plan=qpa_plan(), refit='single', "
                  "first_rung_factor=FIRST_RUNG_FACTOR), carry=('*',), "
                  "dispersion declined, compiled tier default"),
        patterns=list(setup.patterns), start=start,
        fit_kw={"plan": setup.plan, "refit": setup.refit,
                "first_rung_factor": setup.first_rung_factor},
        key_paths=["phases.0.cell.a", "phases.1.cell.a", "phases.1.cell.c",
                   "phases.2.cell.b", "phases.3.cell.b", "phases.0.scale",
                   "instrument.zero_shift"],
        truth=truth)


def _cr2wo6() -> Family:
    from tests.test_acceptance_magnetic import (
        DATA,
        MAGNETIC_STAGES,
        NUCLEAR_STAGES,
        _fit,
        _instrument,
        _plan,
        _trirutile,
        _with_moment,
    )

    d4 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_4K.dat")
    d150 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_150K.dat")
    # conftest.cr2wo6_nuclear, line for line: 150 K from the trirutile start,
    # 4 K from 150 K, the declared stages alone (closing_window_tol=None)
    ref150, _ = _fit(_trirutile(), _instrument(), d150, NUCLEAR_STAGES,
                     closing_window_tol=None)
    ref4, _ = _fit(ref150.structure.model_copy(deep=True),
                   ref150.instrument.model_copy(deep=True), d4, NUCLEAR_STAGES,
                   closing_window_tol=None)
    structure = _with_moment(ref4.structure, (2.0, 0.0, 0.0))
    instrument = ref4.instrument.model_copy(deep=True)

    def start():
        return structure.model_copy(deep=True), instrument.model_copy(deep=True)

    return Family(
        name="cr2wo6",
        title=("Cr₂WO₆ HB-2A pair, 4 K then 150 K (real, constant-wavelength "
               "neutron, λ 2.4067 Å)"),
        protocol=("tests/test_magnetic_series.py::test_the_cr2wo6_pair_as_a_"
                  "series_gives_the_single_pattern_verdicts: start = the 4 K "
                  "nuclear fit of conftest.cr2wo6_nuclear with a 2 μB Cr "
                  "moment (58.395), refine_sequential(plan=_plan(MAGNETIC_"
                  "STAGES), x=[4, 150]), carry=('*',), refit='single', "
                  "compiled tier OFF for the series (the nuclear setup fits "
                  "run on the default path, as the fixture's do)"),
        patterns=[d4, d150], start=start,
        fit_kw={"plan": _plan(MAGNETIC_STAGES)},
        labels=["4K", "150K"], x=[4.0, 150.0], x_label="T (K)",
        numpy_path=True,
        key_paths=["phases.0.atoms.1.moment.dof0", "phases.0.cell.a",
                   "phases.0.cell.c", "phases.0.scale", "instrument.zero_shift"])


def _tut05(jump: float, name: str) -> Family:
    """``examples/tutorials/05_sequential_fits.py``'s jump/broken series.

    Reproduced statement for statement, the round trip through ``.xy`` files
    included (the tutorial fits what it read back), with the 700 K pattern
    re-simulated at ``jump`` × its true cell.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        return _tut05_in(jump, name, Path(tmp))


def _tut05_in(jump: float, name: str, work: Path) -> Family:
    """:func:`_tut05` in ``work``, which holds files only until they are read."""
    cif = work / "LaB6.cif"
    cif.write_text(
        "data_LaB6\n_space_group_name_H-M_alt 'P m -3 m'\n"
        "_cell_length_a 4.1566\n_cell_length_b 4.1566\n_cell_length_c 4.1566\n"
        "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
        "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
        "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
        "La1 La 0 0 0 0.4\n"
        "B1  B  0.1996 0.5 0.5 0.4\n", encoding="utf-8")
    lab6 = rx.Structure.from_cif(cif)
    temperatures = [300, 400, 500, 600, 700, 800, 900]
    a0, expansion = 4.1566, 5e-6
    true_a = [a0 * (1 + expansion * (t - 300)) for t in temperatures]
    true_ins = rx.Instrument.debye_scherrer(wavelength=0.4139)
    true_ins.zero_shift.value = 0.008
    true_ins.profile.w.value = 2.5e-4
    true_ins.background = rx.BackgroundChebyshev.with_terms(3)
    for coef, v in zip(true_ins.background.coefficients, (40.0, -6.0, 1.5),
                       strict=True):
        coef.value = v
    two_theta = np.arange(3.0, 24.0, 0.005)

    def simulate(a, seed):
        specimen = lab6.model_copy(deep=True)
        for edge in "abc":
            getattr(specimen.phases[0].cell, edge).value = a
        specimen.phases[0].scale.value = 5e-4
        y = rx.Refinement(specimen, true_ins).predict(two_theta)
        counts = np.random.default_rng(seed).poisson(np.maximum(y, 1.0))
        return rx.PatternData(two_theta=two_theta, intensity=counts.astype(float))

    folder = work / "ramp"
    folder.mkdir()
    for scan, a in enumerate(true_a, start=8):
        p = simulate(a, seed=11 + scan - 8)
        np.savetxt(folder / f"scan{scan}.xy",
                   np.column_stack([p.two_theta, p.intensity]),
                   fmt="%.4f %.0f", encoding="utf-8")
    files = sorted(folder.glob("*.xy"), key=lambda p: int(p.stem[4:]))
    loaded = [rx.read_pattern(p) for p in files]
    loaded[4] = simulate(true_a[4] * jump, seed=15)
    cells = list(true_a)
    cells[4] = true_a[4] * jump

    def start():
        structure = lab6.model_copy(deep=True)
        for edge in "abc":
            getattr(structure.phases[0].cell, edge).value = a0 * 1.001
        ins = rx.Instrument.debye_scherrer(wavelength=0.4139)
        ins.profile.w.value = 2.5e-4 * 1.5
        ins.background = rx.BackgroundChebyshev.with_terms(3)
        return structure, ins

    def truth(k):
        return {"phases.0.cell.a": cells[k], "phases.0.scale": 5e-4,
                "instrument.zero_shift": 0.008, "instrument.profile.w": 2.5e-4,
                "instrument.background.c0": 40.0, "instrument.background.c1": -6.0,
                "instrument.background.c2": 1.5,
                "phases.0.atoms.0.biso": 0.4, "phases.0.atoms.1.biso": 0.4}

    return Family(
        name=name,
        title=(f"tutorial 05's LaB6 ramp, 7 patterns 300-900 K (synthetic), the "
               f"700 K cell × {jump:g}"),
        protocol=("examples/tutorials/05_sequential_fits.py series_jump / "
                  "series_broken: refine_sequential(plan='mccusker_default', "
                  "x=T, labels=scans), carry=('*',), refit='single', compiled "
                  "tier default"),
        patterns=loaded, start=start, fit_kw={"plan": "mccusker_default"},
        labels=[p.stem for p in files], x=[float(t) for t in temperatures],
        x_label="T (K)",
        key_paths=["phases.0.cell.a", "phases.0.scale", "instrument.zero_shift",
                   "instrument.profile.w", "instrument.background.c0"],
        truth=truth, events={"jump": 4})


FAMILIES: dict[str, Callable[[], Family]] = {
    "cpd": _cpd,
    "cpd-noclose": lambda: _cpd(closing=False),
    "cpd-ftolnone": lambda: _cpd(ftol_none=True),
    "planted": _planted,
    "planted-null": _planted_null,
    "trigger": _trigger,
    "cr2wo6": _cr2wo6,
    "tut05-jump": lambda: _tut05(1.02, "tut05-jump"),
    "tut05-broken": lambda: _tut05(1.05, "tut05-broken"),
}


@functools.cache
def _family(name: str) -> Family:
    """Each family built once a process; ``start`` hands out fresh copies."""
    return FAMILIES[name]()


# -- the counting scaffold --------------------------------------------------

class _Counts:
    def __init__(self) -> None:
        self.nfev = 0
        self.njev = 0
        self.solves = 0

    def snapshot(self) -> tuple[int, int, int]:
        return self.nfev, self.njev, self.solves


@contextmanager
def _counting():
    """Count every solve at the two driver entry points, restoring on exit.

    ``least_squares._lm_outcome`` calls ``lm_mod.minimize`` through the module
    attribute and the TRF path calls scipy through ``least_squares.least_squares``,
    so patching both names reaches every solve the package makes.
    """
    from rietx.optimize import least_squares as lsq
    from rietx.optimize import lm

    counts = _Counts()
    orig_lm, orig_ls = lm.minimize, lsq.least_squares

    def lm_wrap(*a, **k):
        res = orig_lm(*a, **k)
        counts.nfev += int(res.nfev)
        counts.njev += int(res.njev)
        counts.solves += 1
        return res

    def ls_wrap(*a, **k):
        res = orig_ls(*a, **k)
        counts.nfev += int(getattr(res, "nfev", 0) or 0)
        counts.njev += int(getattr(res, "njev", 0) or 0)
        counts.solves += 1
        return res

    lm.minimize, lsq.least_squares = lm_wrap, ls_wrap
    try:
        yield counts
    finally:
        lm.minimize, lsq.least_squares = orig_lm, orig_ls


@contextmanager
def _path(numpy_path: bool):
    if not numpy_path:
        yield
        return
    was = compiled.set_enabled(False)
    try:
        yield
    finally:
        compiled.set_enabled(was)


# -- records ----------------------------------------------------------------

def _num(v):
    """JSON-safe float: a non-finite one as its string."""
    if v is None:
        return None
    v = float(v)
    return v if math.isfinite(v) else str(v)


def _sig(v, digits: int):
    """``_num`` rounded to ``digits`` significant figures."""
    v = _num(v)
    return float(f"{v:.{digits}g}") if isinstance(v, float) else v


def _values_sha(entry) -> str:
    """A hash of every refined value and esd at full precision, so two arms'
    rows can be called bit-identical although the stored numbers are rounded."""
    rows = sorted((p.path, repr(float(p.value)),
                   repr(None if p.stderr is None else float(p.stderr)))
                  for p in entry.parameters)
    if entry.qpa is not None:
        rows += sorted((p.name, repr(p.weight_fraction),
                        repr(p.weight_fraction_stderr)) for p in entry.qpa.phases)
    return hashlib.sha256(repr(rows).encode()).hexdigest()[:16]


def _entry_record(entry, result, wall, delta, warned) -> dict:
    stats = entry.statistics
    qpa = {}
    if entry.qpa is not None:
        qpa = {p.name: [_sig(p.weight_fraction, 12), _sig(p.weight_fraction_stderr, 4)]
               for p in entry.qpa.phases}
    return {
        "index": entry.index, "label": entry.label, "x": _num(entry.x),
        "status": entry.status, "rung": entry.rung,
        "rungs_tried": list(entry.rungs_tried),
        "rungs_raised": dict(entry.rungs_raised),
        "reseeded": entry.reseeded, "rwp_warm": _num(entry.rwp_warm),
        "rwp": _num(stats.rwp) if stats else None,
        "gof": _num(stats.gof) if stats else None,
        "rexp": _num(stats.rexp) if stats else None,
        "rwp_fence": _num(entry.rwp_fence), "above_fence": entry.above_fence,
        "n_iterations": entry.n_iterations,
        "kept_nfev": int(sum(s.n_iterations for s in result.stages)),
        "kept_status": result.status,
        "kept_stages": [[s.name, s.status, int(s.n_iterations)]
                        for s in result.stages],
        "solver_nfev": delta[0], "solver_njev": delta[1], "solver_calls": delta[2],
        "wall_s": round(wall, 3),
        "warnings": warned,
        "codes": sorted({d.code for d in entry.diagnostics}),
        "params": {p.path: [_sig(p.value, 12), _sig(p.stderr, 4)]
                   for p in entry.parameters},
        "qpa": qpa,
        "values_sha": _values_sha(entry),
        "magnetic": [{"path": m.path, "atom": m.atom,
                      "magnitude": _num(m.magnitude),
                      "magnitude_esd": _num(m.magnitude_esd),
                      "supported": m.supported} for m in entry.magnetic],
    }


def _chain(fam: Family, patterns, start, fit_kw, labels, x):
    """One ``SequentialRefinement.fit``; per-pattern counts and wall."""
    structure, ins = start()
    series = rx.SequentialRefinement(structure, ins)
    marks: dict[int, tuple] = {}
    with (_path(fam.numpy_path), _counting() as counts,
          warnings.catch_warnings(record=True) as caught):
        # every warning raised while a pattern is in flight, attributed to it
        # (the solver's trial points included); recording changes no value
        warnings.simplefilter("always")
        last = [time.perf_counter(), counts.snapshot(), 0]

        def on_result(k, _result):
            now, snap = time.perf_counter(), counts.snapshot()
            seen: dict[str, int] = {}
            for w in caught[last[2]:]:
                key = (f"{w.category.__name__} {Path(w.filename).name}:"
                       f"{w.lineno} {str(w.message)[:80]}")
                seen[key] = seen.get(key, 0) + 1
            marks[k] = (now - last[0],
                        tuple(a - b for a, b in zip(snap, last[1], strict=True)),
                        seen)
            print(f"    pattern {k}: {now - last[0]:.1f} s, solver nfev "
                  f"{marks[k][1][0]} njev {marks[k][1][1]}, kept Rwp "
                  f"{_result.statistics.rwp:.5f} {_result.status}", flush=True)
            last[0], last[1], last[2] = now, snap, len(caught)

        t0 = time.perf_counter()
        kw = dict(fit_kw)
        if x is not None:
            kw["x"] = x
        if labels is not None:
            kw["labels"] = labels
        result = series.fit(patterns, on_result=on_result, **kw)
        wall = time.perf_counter() - t0
        tail = tuple(a - b for a, b in zip(counts.snapshot(), last[1], strict=True))
        tail = (*tail, len(caught) - last[2])
    return series, result, marks, wall, tail


def run(family: str, arm: str, out: Path, first: int | None) -> Path:
    fam = _family(family)
    patterns = fam.patterns[:first] if first is not None else fam.patterns
    labels = fam.labels[:len(patterns)] if fam.labels else None
    xs = fam.x[:len(patterns)] if fam.x else None
    base_kw = dict(fam.fit_kw)
    if fam.x is not None:
        base_kw["x_label"] = fam.x_label
    record = {
        "family": family, "title": fam.title, "arm": arm,
        "protocol": fam.protocol, "n_patterns": len(patterns),
        "n_patterns_family": len(fam.patterns),
        "cut": None if len(patterns) == len(fam.patterns) else
        f"first {len(patterns)} of {len(fam.patterns)} patterns",
        "events": fam.events, "key_paths": fam.key_paths,
        "environment": _environment(fam),
        "anchored_dof_paths": _anchored(fam),
    }
    t_start = time.time()
    if arm in ARMS:
        kw = {**base_kw, **ARMS[arm]}
        record["settings"] = {k: _num(v) if isinstance(v, float) else v
                              for k, v in ARMS[arm].items()}
        statuses, codes = ESCALATE_ON.get(arm, ((), ()))
        with _escalating(statuses, codes):
            series, result, marks, wall, tail = _chain(fam, patterns, fam.start,
                                                       kw, labels, xs)
        if statuses:
            record["settings"]["escalates_on_status"] = list(statuses)
        if codes:
            record["settings"]["escalates_on_code"] = list(codes)
        record["patterns"] = [
            _entry_record(e, r, *marks[e.index])
            for e, r in zip(result.entries, series.results_, strict=True)]
        # a pattern every rung of which raised gets no on_result call, so its
        # wall, solver counts and warnings land in the next entry's row (or in
        # post_chain_solver): name it there rather than let the row read as
        # that pattern's own cost (the chain runs forward)
        failed = sorted(f.index for f in result.failures)
        previous = -1
        for row in record["patterns"]:
            charged = [i for i in failed if previous < i < row["index"]]
            if charged:
                row["charged_failures"] = charged
            previous = row["index"]
        record["failures"] = [f.model_dump(mode="json") for f in result.failures]
        record["series_codes"] = [[d.code, d.level, list(d.where or [])]
                                  for d in result.diagnostics]
        # the ten largest of SeriesResult.steps, which replaced the flagged
        # pairs with every step and no threshold (WP-2003, C4)
        record["steps"] = [[s.path, *s.indices, _num(s.size_esd) if s.size_esd
                            is not None else None] for s in (result.steps or [])[:10]]
        record["post_chain_solver"] = list(tail)
        record["wall_s"] = round(wall, 2)
    elif arm in REFERENCE_ARMS:
        if arm == "ref_seeded" and fam.seeded_start is None:
            raise SystemExit(f"{family} has no ref_seeded arm")
        from rietx.sequential import _labels_for

        # the chain's own names, so a family without labels does not name
        # every one-pattern reference fit p000
        names = _labels_for(patterns, labels)
        rows, wall = [], 0.0
        for k, data in enumerate(patterns):
            start = (fam.start if arm == "ref"
                     else (lambda k=k: fam.seeded_start(k)))
            series, result, marks, w, _tail = _chain(
                fam, [data], start, base_kw, [names[k]],
                [xs[k]] if xs else None)
            entry = result.entries[0]
            row = _entry_record(entry, series.results_[0], *marks[0])
            row["index"] = k
            row["series_codes"] = [[d.code, d.level, list(d.where or [])]
                                   for d in result.diagnostics]
            rows.append(row)
            wall += w
            print(f"  {arm} {k}: rwp {row['rwp']:.5f} nfev {row['n_iterations']} "
                  f"{row['wall_s']:.1f}s", flush=True)
        record["settings"] = {"cold": True, "independent": True,
                              "start": "chain's initial models" if arm == "ref"
                              else "seed_scales on each pattern"}
        record["patterns"] = rows
        record["wall_s"] = round(wall, 2)
    else:
        raise SystemExit(f"unknown arm {arm!r}")
    if fam.truth is not None:
        record["truth"] = [{p: _sig(v, 12) for p, v in fam.truth(k).items()}
                           for k in range(len(patterns))]
    if fam.weighed is not None:
        record["weighed"] = fam.weighed[:len(patterns)]
    record["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record["elapsed_s"] = round(time.time() - t_start, 1)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{family}_{arm}.json"
    path.write_text(dump(record), encoding="utf-8")
    return path


def dump(record: dict) -> str:
    """The record as JSON, one top-level key a line and one row a line.

    A list of per-pattern rows (``patterns``, ``truth``, ``weighed``) puts each
    row on its own compact line, so a diff between two runs reads by pattern.
    """
    def compact(v) -> str:
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))

    lines = ["{"]
    items = list(record.items())
    for i, (key, value) in enumerate(items):
        end = "," if i < len(items) - 1 else ""
        if isinstance(value, list) and value and isinstance(value[0], dict):
            rows = [f"  {compact(v)}" for v in value]
            lines.append(f" {compact(key)}:[")
            lines.append(",\n".join(rows))
            lines.append(f" ]{end}")
        else:
            lines.append(f" {compact(key)}:{compact(value)}{end}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _anchored(fam: Family) -> list[str]:
    """The family's anchored coordinate DOFs, read off its own table."""
    from rietx.params.vector import ParameterTable

    structure, ins = fam.start()
    return sorted(ParameterTable(structure, ins).anchored_dof_paths)


def annotate(out: Path) -> list[str]:
    """Add ``anchored_dof_paths`` to every JSON in ``out`` lacking it."""
    done = []
    for p in sorted(out.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if "anchored_dof_paths" in d:
            continue
        d["anchored_dof_paths"] = _anchored(_family(d["family"]))
        p.write_text(dump(d), encoding="utf-8")
        done.append(p.name)
    return done


def _extras() -> str:
    """The optional backends this interpreter imports, as the venv's extras:
    ``[dev]`` alone, or with ``jax``/``torch`` where they are installed."""
    from importlib.util import find_spec

    return "[" + ",".join(["dev"] + [m for m in ("jax", "torch")
                                     if find_spec(m) is not None]) + "]"


def _environment(fam: Family) -> dict:
    try:
        ps = subprocess.run(["ps", "-eo", "pid,etime,args"], capture_output=True,
                            text=True, timeout=10).stdout.splitlines()
        others = [line.strip()[:160] for line in ps
                  if ("python" in line and "pytest" in line
                      and "measure_reseed" not in line and "grep" not in line)]
    except (OSError, subprocess.SubprocessError):
        others = None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "rietx": rx.__version__,
            "venv": _extras(), "interpreter": sys.executable,
            "cpus": os.cpu_count(),
            "compiled_tier": not fam.numpy_path and compiled.enabled(),
            "compiled_threads": compiled.n_threads(),
            "blas_threads_env": {k: os.environ.get(k) for k in
                                 ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                                  "MKL_NUM_THREADS")},
            "load_average_at_start": [round(v, 2) for v in os.getloadavg()],
            "other_pytest_at_start": others}


# -- comparison ---------------------------------------------------------------

def _values(row: dict) -> dict[str, tuple[float, float | None]]:
    """Every refined path and every weight fraction, as (value, esd).

    The family's anchored coordinate DOFs are left out (``row["_skip"]``, set
    by :func:`table`): such a DOF is a displacement from where its own fit
    began, so across fits it compares starting points, and the coordinate
    rows it drives are absolute and carry the same esd (root CLAUDE.md,
    WP-1333; ``ParameterTable.anchored_dof_paths``).
    """
    skip = row.get("_skip", ())
    out = {}
    for path, (v, e) in row["params"].items():
        if path in skip:
            continue
        if isinstance(v, (int, float)):
            out[path] = (v, e if isinstance(e, (int, float)) else None)
    for name, (w, e) in (row.get("qpa") or {}).items():
        if isinstance(w, (int, float)):
            out[f"W.{name}"] = (w, e if isinstance(e, (int, float)) else None)
    return out


def worst(a: dict, b: dict) -> tuple[float | None, str | None, int]:
    """Worst |Δ|/esd of row ``a`` against the baseline row ``b``.

    The esd is the **baseline's** (``on``'s against ``on``, the reference's
    against a reference), ``a``'s only where the baseline has none.  Not the
    larger of the two: a fit that lands far off carries inflated esds, and
    dividing by them shrinks exactly the difference being asked about (cpd-1b
    under ``status``, GoF 8.37: 2.6 by the larger esd, 1 216 by ``on``'s).
    Also returns the number of paths only one row carries.
    """
    va, vb = _values(a), _values(b)
    best, where = None, None
    for path in va.keys() & vb.keys():
        (x, ex), (y, ey) = va[path], vb[path]
        e = ey if ey is not None and ey > 0 else ex
        if e is None or e <= 0:
            continue
        r = abs(x - y) / e
        if best is None or r > best:
            best, where = r, path
    return best, where, len(va.keys() ^ vb.keys())


#: an esd-less value counts as moved past this relative difference: no esd
#: scales it, and below this the two are the same number to the solver
NOESD_REL = 1e-6


def noesd_moved(a: dict, b: dict) -> list[str]:
    """Paths both rows carry with no esd in either, whose values differ.

    ``worst`` cannot see them (nothing to divide by), and they are where an
    arm's answer can differ while every esd-scaled path agrees: a held or
    unmeasured row keeps whatever start the rung that was kept began from.
    """
    va, vb = _values(a), _values(b)
    out = []
    for path in sorted(va.keys() & vb.keys()):
        (x, ex), (y, ey) = va[path], vb[path]
        if any(e is not None and e > 0 for e in (ex, ey)):
            continue
        if abs(x - y) > NOESD_REL * max(abs(x), abs(y), 1e-300):
            out.append(path)
    return out


def _wcell(w: float | None, path: str | None, n_only: int = 0,
           moved: list[str] | None = None) -> str:
    """A worst-|Δ| cell: the ratio and its path, ``0`` alone when equal;
    ``≠n`` names esd-less paths that moved, ``+n`` paths only one row has."""
    extra = f" +{n_only}" if n_only else ""
    if moved:
        extra += f" ≠{len(moved)} no-esd ({', '.join(moved[:3])}" + (
            ", …)" if len(moved) > 3 else ")")
    if w is None:
        return "—" + extra
    if w == 0:
        return "0" + extra
    return f"{w:.3g} ({path})" + extra


def from_truth(row: dict, truth: dict[str, float],
               paths: list[str]) -> tuple[float | None, str | None]:
    """Worst |Δ|/esd from the simulated truth over the family's key paths.

    Only the key paths: a protocol that holds a parameter away from the
    truth (the trigger plan holds the axial H/L at its 0.020 start against a
    true 0.030, so S/L absorbs it) would otherwise name that row everywhere.
    """
    best, where = None, None
    for path, (v, e) in _values(row).items():
        if path not in paths or path not in truth or e is None or e <= 0:
            continue
        r = abs(v - truth[path]) / e
        if best is None or r > best:
            best, where = r, path
    return best, where


def _load(out: Path) -> dict[str, dict[str, dict]]:
    runs: dict[str, dict[str, dict]] = {}
    for p in sorted(out.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        runs.setdefault(d["family"], {})[d["arm"]] = d
    return runs


def _f(v, fmt="{:.4f}", none="—"):
    if v is None:
        return none
    if isinstance(v, str):
        return v
    return fmt.format(v)


_RUNG = {"warm": "w", "warm_staged": "ws", "cold": "c"}


def _rungs(row: dict) -> str:
    tried = "→".join(_RUNG.get(r, r) for r in row["rungs_tried"]) or "—"
    kept = _RUNG.get(row["rung"], row["rung"])
    raised = "!" if row["rungs_raised"] else ""
    return f"{tried} [{kept}]{raised}"


def _codes_here(d: dict, row: dict) -> list[str]:
    here = set()
    for code, _lvl, where in d.get("series_codes", []):
        if row["label"] in where or str(row["index"]) in where:
            here.add(code)
    return sorted(here)


def _short(code: str) -> str:
    return (code.replace("SEQUENTIAL_", "S_").replace("PHASE_", "P_")
            .replace("UNCONSTRAINED", "UNC"))


def _ref_of(fam: dict) -> tuple[str, dict | None]:
    if "ref_seeded" in fam:
        return "ref_seeded", fam["ref_seeded"]
    if "ref" in fam:
        return "ref", fam["ref"]
    return "", None


def differ(a: dict, b: dict) -> bool:
    """The accepted values differ: a path by > DIFFER_ESD esd, an esd-less
    path moved, or a path only one row carries."""
    w, _, n_only = worst(a, b)
    return (w is not None and w > DIFFER_ESD) or bool(n_only) or bool(
        noesd_moved(a, b))


def _values_differ(fam: dict, k: int, arms: list[str], ref: dict | None) -> bool:
    """Any two arms, or any arm and the reference, differ (:func:`differ`)."""
    rows = [fam[a]["patterns"][k] for a in arms]
    if ref is not None:
        rows.append(ref["patterns"][k])
    return any(differ(a, b) for i, a in enumerate(rows) for b in rows[i + 1:])


def _ladder_differs(fam: dict, k: int, arms: list[str]) -> bool:
    """Any two arms differ in rungs tried or kept, status, fence verdict or
    entry codes (the values are :func:`_values_differ`'s)."""
    keys = {(tuple(r["rungs_tried"]), r["rung"], r["status"], r["above_fence"],
             tuple(r["codes"])) for r in (fam[a]["patterns"][k] for a in arms)}
    return len(keys) > 1


def table(out: Path) -> str:
    runs = _load(out)
    lines: list[str] = []
    for name in [n for n in FAMILIES if n in runs]:
        fam = runs[name]
        arms = [a for a in ARMS if a in fam]
        if not arms:
            continue
        head = fam[arms[0]]
        if "anchored_dof_paths" not in head:
            raise SystemExit(f"{name}: no anchored_dof_paths; run --annotate")
        skip = frozenset(head["anchored_dof_paths"])
        for d in fam.values():
            for row in d["patterns"]:
                row["_skip"] = skip
        ref_name, ref = _ref_of(fam)
        # the reference is indexed per pattern too, so a shorter (cut) one
        # bounds the tables that compare against it
        compared = arms + ([ref_name] if ref else [])
        n = min(len(fam[a]["patterns"]) for a in compared)
        truth = head.get("truth")
        cuts = [f"`{a}` {fam[a]['cut']}" for a in compared if fam[a]["cut"]]
        lines += [f"## {head['title']}", "",
                  f"Protocol: {head['protocol']}.  "
                  + (f"Cut: {'; '.join(cuts)}, so the tables comparing arms "
                     f"carry patterns 0-{n - 1} and the patterns past the cut "
                     f"follow them for the arms that ran them.  " if cuts else "")
                  + f"Arms: {', '.join(arms)}"
                  + (f"; reference `{ref_name}`" if ref else "")
                  + ("; truth: the simulation" if truth else "") + ".", ""]
        ks = ks_values = list(range(n))
        if n > 40:
            ev = set()
            for i in (head.get("events") or {}).values():
                ev |= {j for j in range(i - 2, i + 3) if 0 <= j < n}
            moved = {k for k in range(n) if _values_differ(fam, k, arms, ref)}
            ks = [k for k in ks if k in ev or k in moved
                  or _ladder_differs(fam, k, arms)]
            ks_values = sorted(ev | moved)
            lines += [f"{n} patterns.  The ladder, codes and accepted-value "
                      f"tables carry the {len(ks)} where any two arms differ "
                      f"(rungs tried or kept, status, fence verdict, entry codes, "
                      f"or a value by > {DIFFER_ESD} esd) or an arm differs from "
                      f"`{ref_name}` by > {DIFFER_ESD} esd, plus every event "
                      f"pattern ±2; the key-value tables carry only the "
                      f"{len(ks_values)} of those where a value differs, plus the "
                      f"events ±2.  Every other pattern has the same rungs, "
                      f"status, verdict and codes in every arm and values within "
                      f"{DIFFER_ESD} esd of each other and of `{ref_name}`; all "
                      f"of them are in the JSON.  Distance from truth selects "
                      f"no row (every pattern is some esd from it).", ""]
        # ladder table
        hdr = ["k", "label"]
        for a in arms:
            hdr += [f"{a}: rungs [kept]", f"{a}: Rwp warm→kept", f"{a}: fence",
                    f"{a}: nfev"]
        lines += ["### Ladder, per pattern", "",
                  "Rungs: w = collapsed warm, ws = staged from warm, c = cold; "
                  "[kept]; `!` a rung raised.  nfev = `SeriesEntry.n_iterations` "
                  "(residual evaluations over every returned rung).  Fence = "
                  "`rwp_fence`; `*` marks `above_fence`.", "",
                  "| " + " | ".join(hdr) + " |",
                  "|" + "---|" * len(hdr)]
        for k in ks:
            cells = [str(k), fam[arms[0]]["patterns"][k]["label"]]
            for a in arms:
                r = fam[a]["patterns"][k]
                warm = (f"{_f(r['rwp_warm'])}→" if r["rwp_warm"] is not None
                        else "")
                status = "" if r["status"] == "converged" else f" ({r['status']})"
                cells += [_rungs(r), f"{warm}{_f(r['rwp'])}{status}",
                          _f(r["rwp_fence"]) + ("*" if r["above_fence"] else ""),
                          str(r["n_iterations"])]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        # codes table
        lines += ["### Codes, per pattern", "",
                  "Entry codes and the series-level codes naming the pattern "
                  "(`S_` = `SEQUENTIAL_`, `P_UNC` = `PHASE_UNCONSTRAINED`); a "
                  "discontinuity names a path and is listed under the series "
                  "codes below.", "",
                  "| k | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
        for k in ks:
            cells = [str(k)]
            for a in arms:
                r = fam[a]["patterns"][k]
                codes = sorted(set(r["codes"]) | set(_codes_here(fam[a], r)))
                cells.append(", ".join(_short(c) for c in codes) or "—")
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        # values table
        hdr = ["k"]
        others = [a for a in arms if a != "on"] if "on" in fam else []
        hdr += [f"{a} vs on: worst |Δ|/esd (path)" for a in others]
        pairs = [(a, PAIRED[a]) for a in arms if PAIRED.get(a) in fam]
        hdr += [f"{a} vs {b}" for a, b in pairs]
        if ref:
            hdr += [f"{a} vs {ref_name}" for a in arms]
        if truth:
            hdr += [f"{a} vs truth" for a in arms]
        lines += ["### Accepted values, per pattern", "",
                  "Worst |Δ|/esd over every refined path both rows carry, and "
                  "the weight fractions (`W.<phase>`), with the esd of the row "
                  "compared against (`on`, the arm's pair, or the reference); "
                  "against truth, "
                  "|Δ|/esd with the arm's own esd over the key paths of the "
                  "key-value table only.  `0` = equal to the stored precision; "
                  "`≠n no-esd` = esd-less paths that moved; `+n` = paths only "
                  "one row carries.", "",
                  "| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
        for k in ks:
            cells = [str(k)]
            on = fam["on"]["patterns"][k] if others else None
            for a in others:
                r = fam[a]["patterns"][k]
                cells.append(_wcell(*worst(r, on), moved=noesd_moved(r, on)))
            for a, b in pairs:
                r, o = fam[a]["patterns"][k], fam[b]["patterns"][k]
                cells.append(_wcell(*worst(r, o), moved=noesd_moved(r, o)))
            if ref:
                for a in arms:
                    r, o = fam[a]["patterns"][k], ref["patterns"][k]
                    cells.append(_wcell(*worst(r, o), moved=noesd_moved(r, o)))
            if truth:
                for a in arms:
                    cells.append(_wcell(*from_truth(fam[a]["patterns"][k], truth[k],
                                                    head["key_paths"])))
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        # key values
        keys = [p for p in head["key_paths"]
                if any(p in fam[a]["patterns"][0]["params"] for a in arms)]
        if keys:
            cols = arms + ([ref_name] if ref else []) + (["truth"] if truth else [])
            lines += ["### Key values, per pattern", "",
                      "value(esd in the last digits shown) per arm"
                      + (f"; `{ref_name}` the reference" if ref else "")
                      + ("; truth the simulation" if truth else "")
                      + ".  `—`: the path is not refined in that row (held, "
                        "or no true value).", "",
                      "| k | path | " + " | ".join(cols) + " |",
                      "|---|---|" + "---|" * len(cols)]
            for k in ks_values:
                for p in keys:
                    cells = [str(k), f"`{p}`"]
                    for a in arms + ([ref_name] if ref else []):
                        src = ref if a == ref_name else fam[a]
                        cells.append(_ve(src["patterns"][k]["params"].get(p)))
                    if truth:
                        cells.append(_f(truth[k].get(p), "{:.6g}"))
                    lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
        if head.get("weighed") or any(len(fam[a]["patterns"][0]["qpa"]) > 1
                                      for a in arms):
            lines += _qpa_table(fam, arms, ref_name, ref, ks_values)
        if any(fam[a]["patterns"][0].get("magnetic") for a in arms):
            lines += _moment_table(fam, arms, ref_name, ref, ks_values)
        lines += _beyond_cut(fam, arms, n, ref_name, ref, head)
        lines += _totals(fam, arms, ref_name, ref, truth)
        lines += _series_codes(fam, arms)
        lines += _against_base(name, fam, runs.get(VARIANT_OF.get(name, "")), arms)
    return "\n".join(lines) + "\n"


#: a declared variant family → the family it changes one setting of, which
#: ``--table`` compares it against arm by arm
VARIANT_OF = {"cpd-noclose": "cpd", "cpd-ftolnone": "cpd"}


def _against_base(name, fam, base, arms) -> list[str]:
    """A declared variant against its base family, arm by arm and pattern by
    pattern, with the base's esd (:func:`worst`)."""
    shared = [a for a in arms if base is not None and a in base]
    if not shared:
        return []
    base_name = VARIANT_OF[name]
    skip = frozenset(base[shared[0]].get("anchored_dof_paths", ()))
    for a in shared:
        for row in base[a]["patterns"]:
            row["_skip"] = skip
    n = min(min(len(fam[a]["patterns"]), len(base[a]["patterns"])) for a in shared)
    hdr = ["k", "label"]
    for a in shared:
        hdr += [f"{a}: rungs [kept] ({base_name})", f"{a}: nfev ({base_name})",
                f"{a} vs {base_name} {a}"]
    out = [f"### Against `{base_name}`, arm by arm", "",
           f"Each arm against the same arm of `{base_name}`, the family this "
           f"one changes one setting of: rungs and nfev with `{base_name}`'s "
           f"in brackets, and the worst |Δ|/esd with `{base_name}`'s esd.", "",
           "| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for k in range(n):
        cells = [str(k), fam[shared[0]]["patterns"][k]["label"]]
        for a in shared:
            r, o = fam[a]["patterns"][k], base[a]["patterns"][k]
            cells += [f"{_rungs(r)} ({_rungs(o)})",
                      f"{r['n_iterations']} ({o['n_iterations']})",
                      _wcell(*worst(r, o), moved=noesd_moved(r, o))]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    for a in shared:
        pairs = list(zip(fam[a]["patterns"][:n], base[a]["patterns"][:n]))
        out.append(
            f"`{a}`: nfev {sum(r['n_iterations'] for r, _ in pairs)} against "
            f"{sum(o['n_iterations'] for _, o in pairs)}, bit-identical "
            f"{sum(r['values_sha'] == o['values_sha'] for r, o in pairs)} of "
            f"{n}, differ {_ix([r for r, o in pairs if differ(r, o)])}.")
    out.append("")
    return out


def _beyond_cut(fam, arms, n, ref_name, ref, head) -> list[str]:
    """Patterns past the shortest arm, for the arms that ran them."""
    longer = [a for a in arms if len(fam[a]["patterns"]) > n]
    if not longer:
        return []
    last = max(len(fam[a]["patterns"]) for a in longer)
    hdr = ["k", "label"]
    for a in longer:
        hdr += [f"{a}: rungs [kept]", f"{a}: Rwp warm→kept", f"{a}: fence",
                f"{a}: nfev"] + ([f"{a} vs {ref_name}"] if ref else []) + [
                f"{a}: codes"]
    out = [f"### Past the cut: patterns {n}-{last - 1}, "
           f"{', '.join(f'`{a}`' for a in longer)} only", "",
           "| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for k in range(n, last):
        cells = [str(k), fam[longer[0]]["patterns"][k]["label"]]
        for a in longer:
            r = fam[a]["patterns"][k]
            warm = f"{_f(r['rwp_warm'])}→" if r["rwp_warm"] is not None else ""
            status = "" if r["status"] == "converged" else f" ({r['status']})"
            cells += [_rungs(r), f"{warm}{_f(r['rwp'])}{status}",
                      _f(r["rwp_fence"]) + ("*" if r["above_fence"] else ""),
                      str(r["n_iterations"])]
            if ref:
                o = _at(ref, k)
                cells.append("—" if o is None else
                             _wcell(*worst(r, o), moved=noesd_moved(r, o)))
            codes = sorted(set(r["codes"]) | set(_codes_here(fam[a], r)))
            cells.append(", ".join(_short(c) for c in codes) or "—")
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    keys = [p for p in head["key_paths"] if p in fam[longer[0]]["patterns"][n]["params"]]
    phases = list(fam[longer[0]]["patterns"][n]["qpa"]) if len(
        fam[longer[0]]["patterns"][n]["qpa"]) > 1 else []
    weighed = head.get("weighed")
    if keys or phases:
        cols = longer + ([ref_name] if ref else [])
        out += ["| k | path | " + " | ".join(cols) + (" | weighed" if weighed else "")
                + " |", "|---|---|" + "---|" * (len(cols) + bool(weighed))]
        for k in range(n, last):
            for p in keys:
                cells = [str(k), f"`{p}`"]
                for a in cols:
                    row = _at(ref if a == ref_name else fam[a], k)
                    cells.append(_ve(None if row is None else row["params"].get(p)))
                out.append("| " + " | ".join(cells + ([""] if weighed else [])) + " |")
            for name in phases:
                cells = [str(k), f"W {name} (wt %)"]
                for a in cols:
                    row = _at(ref if a == ref_name else fam[a], k)
                    cells.append(_wt(None if row is None else row["qpa"].get(name)))
                if weighed:
                    cells.append(f"{weighed[k].get(name, float('nan')):.2f}")
                out.append("| " + " | ".join(cells) + " |")
        out.append("")
    return out


def _at(run: dict, k: int) -> dict | None:
    """Pattern ``k``'s row of a run, ``None`` past its end (a cut run)."""
    rows = run["patterns"]
    return rows[k] if k < len(rows) else None


def _wt(w) -> str:
    """A stored ``[W, σ(W)]`` as wt %, σ omitted where none was measured."""
    if not w or not isinstance(w[0], (int, float)):
        return "—"
    if not isinstance(w[1], (int, float)):
        return f"{100 * w[0]:.2f}"
    return f"{100 * w[0]:.2f}({100 * w[1]:.2f})"


def _ve(v) -> str:
    if v is None:
        return "—"
    x, e = v
    if not isinstance(x, (int, float)):
        return str(x)
    if not isinstance(e, (int, float)) or e <= 0:
        return f"{x:.6g}"
    digits = max(0, -int(math.floor(math.log10(e))) + 1)
    if digits > 10:
        return f"{x:.4g}({e:.2g})"
    return f"{x:.{digits}f}({round(e * 10 ** digits):d})"


def _qpa_table(fam, arms, ref_name, ref, ks) -> list[str]:
    head = fam[arms[0]]
    names = list(head["patterns"][0]["qpa"].keys())
    weighed = head.get("weighed")
    cols = arms + ([ref_name] if ref else []) + (["weighed"] if weighed else [])
    out = ["### Weight fractions, per pattern (wt %)", "",
           "W(σ(W)) per arm" + ("; weighed = the composition as weighed, the "
                                "QPA truth" if weighed else "") + ".", "",
           "| k | phase | " + " | ".join(cols) + " |",
           "|---|---|" + "---|" * len(cols)]
    for k in ks:
        for name in names:
            cells = [str(k), name]
            for a in arms + ([ref_name] if ref else []):
                src = ref if a == ref_name else fam[a]
                cells.append(_wt(src["patterns"][k]["qpa"].get(name)))
            if weighed:
                cells.append(f"{weighed[k].get(name, float('nan')):.2f}")
            out.append("| " + " | ".join(cells) + " |")
    out.append("")
    return out


def _moment_table(fam, arms, ref_name, ref, ks) -> list[str]:
    cols = arms + ([ref_name] if ref else [])
    out = ["### Moment evidence, per pattern (`SeriesEntry.magnetic`)", "",
           "|μ| (esd) μB and `supported`, per site.", "",
           "| k | site | " + " | ".join(cols) + " |",
           "|---|---|" + "---|" * len(cols)]
    for k in ks:
        sites = [m["atom"] for m in fam[arms[0]]["patterns"][k].get("magnetic", [])]
        for i, site in enumerate(sites):
            cells = [str(k), site]
            for a in cols:
                src = ref if a == ref_name else fam[a]
                rows = src["patterns"][k].get("magnetic", [])
                m = rows[i] if i < len(rows) else None
                cells.append("—" if m is None else
                             f"{_f(m['magnitude'], '{:.3f}')}"
                             f"({_f(m['magnitude_esd'], '{:.3f}')}) "
                             f"{m['supported']}")
            out.append("| " + " | ".join(cells) + " |")
    out.append("")
    return out


def _totals(fam, arms, ref_name, ref, truth) -> list[str]:
    paired = any(PAIRED.get(a) in fam for a in arms)
    hdr = ["arm", "patterns", "escalated", "reseeded (kept cold)", "quarantined",
           "above fence", "bit-identical to on", "differ from on",
           "pair: bit-identical, differ" if paired else None,
           f"differ from {ref_name}" if ref else None,
           "nfev (entries)", "kept-rung nfev", "solver nfev / njev",
           "wall per pattern (s)", "wall total (s)"]
    hdr = [h for h in hdr if h is not None]
    out = ["### Totals", "",
           f"\"Differ\" = a value apart by > {DIFFER_ESD} esd (the esd of the row "
           f"compared against: `on`, the arm's pair, or the reference), an "
           f"esd-less value moved by > {NOESD_REL:g} relative, or a path only "
           f"one row carries (the script's `differ`).  \"bit-identical\" "
           f"compares `values_sha`; \"pair\" is the arm differing from this "
           f"one by one switch (`PAIRED`).  nfev (entries) is `SeriesEntry.n_iterations`; "
           f"solver nfev / njev count every solve, the automatic "
           f"profile-interval refits included.  Counts are over each arm's own "
           f"patterns; comparisons over the patterns both rows have.", "",
           "| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    on = fam["on"]["patterns"] if "on" in fam else None
    for a in arms + ([ref_name] if ref else []):
        d = ref if a == ref_name else fam[a]
        rows = d["patterns"]
        same = moved = "—"
        if on is not None:
            pairs = list(zip(rows, on))   # a cut arm: its own prefix
            same = str(sum(r.get("values_sha") is not None
                           and r.get("values_sha") == o.get("values_sha")
                           for r, o in pairs))
            if a != "on":
                moved = _ix([r for r, o in pairs if differ(r, o)])
        cells = [a, str(len(rows)),
                 str(sum(len(r["rungs_tried"]) > 1 for r in rows)),
                 _ix([r for r in rows if r["reseeded"]]),
                 _ix([r for r in rows if r["status"] == "diverged"]),
                 _ix([r for r in rows if r["above_fence"]]),
                 same, moved]
        if paired:
            b = PAIRED.get(a)
            if b in fam:
                pairs = list(zip(rows, fam[b]["patterns"]))
                cells.append(f"`{b}`: " + str(sum(
                    r["values_sha"] == o["values_sha"] for r, o in pairs))
                    + ", " + _ix([r for r, o in pairs if differ(r, o)]))
            else:
                cells.append("—")
        if ref:
            cells.append("—" if a == ref_name else _ix(
                [r for r, o in zip(rows, ref["patterns"]) if differ(r, o)]))
        walls = [r["wall_s"] for r in rows]
        cells += [str(sum(r["n_iterations"] for r in rows)),
                  str(sum(r["kept_nfev"] for r in rows)),
                  f"{sum(r['solver_nfev'] for r in rows)} / "
                  f"{sum(r['solver_njev'] for r in rows)}",
                  f"{min(walls):.1f}-{max(walls):.1f}", f"{d['wall_s']:.0f}"]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    return out


def _ix(rows: list[dict]) -> str:
    if not rows:
        return "0"
    idx = [str(r["index"]) for r in rows]
    shown = ", ".join(idx[:12]) + (", …" if len(idx) > 12 else "")
    return f"{len(rows)} ({shown})"


def _series_codes(fam, arms) -> list[str]:
    codes = sorted({c for a in arms for c, _l, _w in fam[a]["series_codes"]})
    out = ["### Series-level codes", ""]
    if not codes:
        out += ["No series-level code in any arm."]
    else:
        out += ["| code | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
    for code in codes:
        cells = [f"`{code}`"]
        for a in arms:
            hits = [w for c, _l, w in fam[a]["series_codes"] if c == code]
            if code == "SEQUENTIAL_DISCONTINUITY":
                # a JSON written before WP-2003 removed the code
                steps = [f"{p} {i}→{j}" for p, i, j in fam[a].get("discontinuities", [])]
                cells.append(f"{len(hits)}: " + "; ".join(steps) if hits else "0")
            else:
                cells.append(str(len(hits)))
        out.append("| " + " | ".join(cells) + " |")
    out += ["", "Failures (`SeriesFailure`): "
            + ", ".join(f"{a} {len(fam[a]['failures'])}" for a in arms) + ".", ""]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", default="all",
                    choices=[*FAMILIES, "all"])
    ap.add_argument("--arm", default="all",
                    choices=[*ARMS, *REFERENCE_ARMS, "all"])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--first", type=int, default=None,
                    help="fit only the first N patterns of the family")
    ap.add_argument("--table", action="store_true",
                    help="render the markdown tables from the JSONs in --out")
    ap.add_argument("--annotate", action="store_true",
                    help="add anchored_dof_paths to JSONs written without it")
    args = ap.parse_args(argv)
    if args.first is not None and args.first < 1:
        ap.error("--first takes a pattern count of at least 1")
    if args.table:
        sys.stdout.write(table(args.out))
        return 0
    if args.annotate:
        print("\n".join(annotate(args.out)) or "nothing to annotate")
        return 0
    families = list(FAMILIES) if args.family == "all" else [args.family]
    for family in families:
        seeded = family.startswith("cpd")    # the families with seeded_start
        arms = [*ARMS, "ref"] + (["ref_seeded"] if seeded else [])
        if args.arm != "all":
            if args.arm == "ref_seeded" and not seeded and args.family == "all":
                continue                     # asked of every family that has it
            arms = [args.arm]
        for arm in arms:
            t0 = time.perf_counter()
            print(f"{family} / {arm} …", flush=True)
            path = run(family, arm, args.out, args.first)
            print(f"{family} / {arm}: {time.perf_counter() - t0:.0f} s → {path}",
                  flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
