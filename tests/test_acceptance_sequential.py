"""WP-0505 acceptance: a warm-started series on real data.

The IUCr CPD round-robin sample-1 mixtures (1a-1h) are the same three phases
— corundum, zincite, fluorite — measured on the same goniometer, so they are a
legitimate series in everything except the one thing that changes: the
composition, which swings from 1 to 94 wt % across the set.  That makes them a
deliberately **hostile** series, and the right one for this WP: it is exactly
where a naive "carry everything" warm start was expected to hurt.

It does not.  Measured here (1.7.0, under WP-1123's intermediate_ftol): 1826
iterations unchained, 725 with the scales excluded from the carry and
re-seeded per pattern, **627 carrying everything** — at identical mean Rwp
(0.1305) and weight fractions within 0.15 wt %.  The expectation
that a 1 → 94 wt % scale swing needs a narrower carry is refuted, and the
module keeps both passes so the number stays measured rather than assumed.
What the series does establish is that chaining is worth 2.5x in iterations
for the same answer.  In physical units under LM (WP-1938) the three read 1015,
278 and 260, so chaining is worth 3.7x.  Since WP-1953 the axial stage refines
S/L with H/L held at 0, and on 1.9.0 they read 1214, 403 and 365 at mean Rwp
0.1278, so chaining is worth 3.0x.

The protocol is imported wholesale from ``test_acceptance_qpa_roundrobin`` —
the same phases, instrument, staged plan and weighed truth table — so the
comparison is between *how the fits were chained*, never between two protocols.
Comparing against another result means adopting its protocol (CLAUDE.md), and
here the other result is this package's own independent-fit acceptance.

Three passes over the eight mixtures:

``independent``
    the v0.3 acceptance protocol, each mixture fitted from the initial model —
    the baseline both chains are measured against.
``chained``
    warm start restricted to the instrument, cells and broadening, with the
    phase scales re-estimated per pattern by the same ``seed_scales`` the
    independent fits use (a ``prepare`` hook — a ``carry`` glob alone could
    only fall back to the *first* mixture's guess, which is not the same thing).
``chained_all``
    the default, carrying everything including the scales.  Its job is to
    measure what that costs on a series whose scales genuinely jump — and the
    answer turned out to be "nothing".

Measured results are recorded in the module docstring of the WP handover log
and in ``docs/milestones/`` when v0.5 ships; the assertions here are the
participant-spread tolerances of the independent acceptance, unchanged — a
chained fit has to be as accurate as an unchained one or it is not usable.


Dispersion is **declined**, inherited from ``qarr_instrument`` in
``test_acceptance_qpa_roundrobin`` — this suite imports that protocol
wholesale so that what differs between the two is only the chaining, and that
includes inheriting its (explicit) dispersion-off setting.  Since WP-1001 made
the block a package default, "off" here is a declaration in the shared
builder, never an inherited default.
"""

import importlib

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.plan import CLOSING_WINDOW_TOL
from tests.test_acceptance_qpa_roundrobin import (
    DATA,
    MAJOR_TOL,
    OUT,
    SAMPLE1,
    TRACE_TOL,
    WEIGHED,
    corundum_phase,
    fluorite_phase,
    qarr_instrument,
    qpa_plan,
    seed_scales,
    zincite_phase,
)

#: every test here consumes ``chained``/``chained_all``/``independent``, and
#: ``independent`` is the session-scoped ``sample1_results`` shared with the QPA
#: acceptance — so the whole module pins to one xdist worker (without the group
#: mark a second worker would silently refit all eight mixtures)
pytestmark = pytest.mark.xdist_group("qpa-sample1")

#: everything except the phase scales: the instrument is one goniometer, the
#: cells and broadening belong to three phases that are the same material in
#: every mixture, and only the scales encode the composition that changes
CARRY = ["instrument.*", "phases.*.cell.*", "phases.*.lor_*",
         "phases.*.gauss_*", "phases.*.atoms.*.biso"]


def _phases():
    return [corundum_phase(), zincite_phase(), fluorite_phase()]


def _require_data():
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")


def _patterns():
    return [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1]


def _fractions_pct(qpa) -> dict[str, float]:
    return {r.name: 100.0 * r.weight_fraction for r in qpa.phases}


def _seed_hook(index, data, structure, instrument):
    """Re-estimate the phase scales from *this* mixture before fitting it.

    The independent fits do exactly this (``seed_scales`` is part of the v0.3
    QPA protocol), so the chain has to as well or the two would differ by more
    than the chaining.
    """
    seed_scales(structure, instrument, data)


@pytest.fixture(scope="module")
def independent(sample1_results):
    """Each mixture fitted from the initial model — the unchained baseline.

    These are the *same* eight fits the v0.3 QPA acceptance runs: same phases,
    same instrument, same ``seed_scales``, same ``qpa_plan()`` — including the
    convergence schedule that builder declares (``intermediate_ftol``,
    WP-1123, and ``closing_window_tol``, WP-2002), inherited deliberately,
    since a chain is only comparable to the
    unchained baseline if both stop their stages in the same place.  They are
    therefore shared, from ``tests/conftest.py``, rather than re-derived here
    (which cost eight full refinements per run).  Two deliberate semantics
    deltas, neither of which touches a value: the shared fits record history
    and write the QPA suite's per-sample plots, where this fixture used to pass
    ``history=False`` and plot nothing.
    """
    return [sample1_results[s] for s in SAMPLE1]


@pytest.fixture(scope="module")
def chained():
    """The series, warm-started on everything the mixtures share."""
    _require_data()
    structure = rx.Structure(phases=_phases())
    ins = qarr_instrument()
    series = rx.SequentialRefinement(structure, ins, carry=CARRY)
    result = series.fit(_patterns(), labels=list(SAMPLE1), plan=qpa_plan(),
                        prepare=_seed_hook)
    OUT.mkdir(exist_ok=True)
    for entry, res in zip(result.entries, series.results_, strict=True):
        res.plot(path=str(OUT / f"seq_{entry.label}.png"))
    import matplotlib.pyplot as plt
    plt.close("all")
    result.plot(["phases.0.cell.a", "phases.1.cell.a", "phases.2.cell.a"],
                path=str(OUT / "seq_qarr_cells.png"))
    plt.close("all")
    result.write_csv(OUT / "seq_qarr.csv")
    return result


def _chained_all(**kw):
    _require_data()
    structure = rx.Structure(phases=_phases())
    ins = qarr_instrument()
    seed_scales(structure, ins, rx.read_pattern(DATA / f"{SAMPLE1[0]}.prn"))
    return rx.SequentialRefinement(structure, ins).fit(
        _patterns(), labels=list(SAMPLE1), plan=qpa_plan(), **kw)


@pytest.fixture(scope="module")
def chained_all():
    """The naive default: carry everything, scales included."""
    return _chained_all()


class _Runaway(BaseException):
    """Raised from the closing compile, past every handler a series has."""


@pytest.mark.slow
def test_the_hostile_pairs_warm_stage_stops_short_of_the_runaway(monkeypatch):
    """WP-2045: cpd-1b's warm stage, carried from cpd-1a's answer, converges.

    Under a 1e-6 tolerance the warm stage stopped "converged" at
    ``axial_sl`` 555, on a plateau of its frozen windows, which then dropped
    73 % of the Bragg intensity a fresh compile computes.  The closing compile
    at that answer held 1 608× the warm stage's point-nodes and ran for tens
    of minutes.  At the solver's 1e-9 the same stage reaches 0.0139.  A
    closing compile at an axial ratio above 1 fails the test at once, where
    the shipped 1.10.0 tree would otherwise run that stage to its budget.
    """
    _require_data()
    refine_mod = importlib.import_module("rietx.refine")
    real = refine_mod.compile_model

    def guarded(structure, instrument, pattern, **kw):
        if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
                and instrument.geometry.axial_sl.value > 1.0):
            raise _Runaway(f"a closing compile at axial_sl "
                           f"{instrument.geometry.axial_sl.value:.4g}")
        return real(structure, instrument, pattern, **kw)

    monkeypatch.setattr(refine_mod, "compile_model", guarded)
    structure = rx.Structure(phases=_phases())
    ins = qarr_instrument()
    patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
    seed_scales(structure, ins, patterns[0])
    series = rx.SequentialRefinement(structure, ins)
    try:
        result = series.fit(patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan())
    except _Runaway as exc:
        pytest.fail(f"cpd-1b's warm stage ran away: {exc}")
    entry = result.entries[1]
    assert entry.rung == "warm", entry.rungs_tried
    axial = next(p.value for p in series.results_[1].parameters
                 if p.path == "instrument.geometry.axial_sl")
    assert axial < 1.0
    # and the stage that the collapse rescued ended on windows that hold
    # its peaks, so the report stays silent (WP-2047)
    warm = series.results_[1].stages[0]
    assert warm.window_loss is not None and warm.window_loss < 0.02
    assert "STAGE_WINDOWS_STALE" not in {d.code for d in series.results_[1].diagnostics}


@pytest.mark.slow
def test_the_hostile_pairs_runaway_reports_its_stale_windows(monkeypatch):
    """WP-2047: under the tolerance schedule before WP-2045, cpd-1b's warm
    stage still runs to ``axial_sl`` 558, and its record says so.

    At that answer its frozen windows drop 73 % of the Bragg intensity that
    windows sized there hold, against the 2 % each may drop.  The closing
    compile at that answer would run for tens of minutes, so the test reads the
    warm stage's ``stage_end`` event, which carries ``window_loss`` as the stage
    ends, and stops the fit at the closing compile as the test above does.
    """
    _require_data()
    refine_mod = importlib.import_module("rietx.refine")
    real = refine_mod.compile_model

    def guarded(structure, instrument, pattern, **kw):
        if (kw.get("window_area_tol") == CLOSING_WINDOW_TOL
                and instrument.geometry.axial_sl.value > 1.0):
            raise _Runaway()
        return real(structure, instrument, pattern, **kw)

    def pre_2045(self):
        # every stage at intermediate_ftol but the closing one
        stages = self.run_stages()
        return [s.ftol if s.ftol is not None
                else (None if i == len(stages) - 1 else self.intermediate_ftol)
                for i, s in enumerate(stages)]

    monkeypatch.setattr(refine_mod, "compile_model", guarded)
    monkeypatch.setattr(rx.RefinementPlan, "stage_ftols", pre_2045)
    structure = rx.Structure(phases=_phases())
    ins = qarr_instrument()
    patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1[:2]]
    seed_scales(structure, ins, patterns[0])
    ends = []

    def listen(event):
        if event["kind"] == "stage_end":
            ends.append(event["data"])

    with pytest.raises(_Runaway):
        rx.SequentialRefinement(structure, ins).fit(
            patterns, labels=list(SAMPLE1[:2]), plan=qpa_plan(), events=listen)
    cpd_1a = [e["window_loss"] for e in ends if e["series_index"] == 0]
    assert all(x < 0.02 for x in cpd_1a), cpd_1a
    warm = [e for e in ends if e["series_index"] == 1][-1]
    assert warm["window_loss"] > 0.5, warm


# -- accuracy: a chained fit must be as good as an unchained one ----------

@pytest.mark.slow
@pytest.mark.parametrize("sample", SAMPLE1)
def test_chained_qpa_within_participant_spread(chained, sample):
    """The same criterion the independent acceptance uses, unchanged."""
    entry = next(e for e in chained if e.label == sample)
    assert entry.status == "converged"
    assert entry.statistics.n_points == 7251
    got = _fractions_pct(entry.qpa)
    for name, truth in WEIGHED[sample].items():
        tol = TRACE_TOL if truth < 5.0 else MAJOR_TOL
        assert got[name] == pytest.approx(truth, abs=tol), (
            f"{sample} {name}: {got[name]:.2f} vs weighed {truth:.2f} wt %")


@pytest.mark.slow
def test_chained_agrees_with_independent_fits(chained, independent):
    """Chaining changes the starting point, not the answer.

    Agreement is asserted against the *participant spread* rather than against
    the esds: both fits carry the same intensity-level systematics, and the
    question this test asks is whether a user would draw a different conclusion
    from the chained series, not whether two minimisations landed on the same
    floating-point value.
    """
    for entry, indep in zip(chained.entries, independent, strict=True):
        got = _fractions_pct(entry.qpa)
        ref = _fractions_pct(indep.qpa)
        for name in ref:
            assert got[name] == pytest.approx(ref[name], abs=1.0), (
                f"{entry.label} {name}: chained {got[name]:.2f} vs "
                f"independent {ref[name]:.2f} wt %")
        assert entry.statistics.rwp == pytest.approx(indep.statistics.rwp,
                                                     abs=0.005)


@pytest.mark.slow
def test_cells_are_stable_across_the_series(chained):
    """Eight mixtures of the *same* three materials: the cells must not move.

    A trajectory that ought to be flat is the cleanest possible check that the
    chain is not imprinting a trend — and unlike Rwp it would show a drift
    immediately.
    """
    for ip, name in enumerate(("corundum", "zincite", "fluorite")):
        traj = chained.trajectory(f"phases.{ip}.cell.a")
        _, value, sd = traj.arrays()
        spread = float(np.ptp(value))
        assert spread < 20e-4, f"{name} a spans {spread:.2e} Å across the series"
        # ... and no monotone drift larger than the spread it is drawn from
        slope = np.polyfit(np.arange(len(value)), value, 1)[0]
        assert abs(slope) * len(value) < spread + 5 * float(np.nanmax(sd))


# -- the warm start: measured, not assumed --------------------------------

@pytest.mark.slow
def test_warm_start_iteration_cost_is_reported(chained, chained_all,
                                               independent):
    """The headline warm-start number, reported rather than gated.

    Whether a warm start pays on a series whose composition swings by 90 wt %
    is a measurement, and it does: ~400 iterations against 1214 unchained, for
    the same fractions (~280 against 1015 on 1.8.0, before WP-1953; ~700
    against 1826 on 1.7.0, before WP-1938).  Which `carry` policy gets there is measured too, and
    the difference is small in iterations and nil in Rwp — so what is
    *asserted* is only the part that would matter to a user: neither chain
    diverged, and restricting the carry did not make the fit worse.

    It was a strict xfail from WP-2002's width twin hold (restricted-carry Rwp
    0.1282 against carry=* 0.1256, 2026-10-23) until WP-2045 converged the
    last declared stage.  Since then both chains read mean Rwp 0.1282 against
    0.1258 independent, at 408 and 655 iterations against 1255 (macOS arm64,
    ``[dev]``, 2026-10-25).
    """
    baseline = sum(sum(s.n_iterations for s in r.stages) for r in independent)
    print(f"\niterations over sample 1a-1h: independent={baseline} "
          f"chained(carry={len(CARRY)} globs)={chained.n_iterations} "
          f"chained(carry=*)={chained_all.n_iterations}")
    print("Rwp: independent="
          f"{np.mean([r.statistics.rwp for r in independent]):.4f} "
          f"chained={np.mean(chained.rwp):.4f} "
          f"chained_all={np.mean(chained_all.rwp):.4f}")
    print(f"reseeds: chained={sum(e.reseeded for e in chained)} "
          f"chained_all={sum(e.reseeded for e in chained_all)}")

    assert all(e.status == "converged" for e in chained)
    assert np.mean(chained.rwp) <= np.mean(chained_all.rwp) + 1e-3


@pytest.mark.slow
def test_the_hostile_series_exercises_the_reseed_fence(chained_all):
    """Carrying the scales across a 1 → 94 wt % swing is the failure the fence
    is for; whether it fires is data-dependent, but every fit it accepts must
    be the better of the ones it saw, and the ladder's accounting must add up.

    The escalation is only ever a *prefix* of the ladder (WP-1051) — a rung is
    reached because the one before it failed, so a series cannot report a cold
    refit it never climbed to, and the kept rung has to be one of the rungs
    actually tried.
    """
    from rietx.sequential import RUNGS

    for entry in chained_all:
        # the first pattern has nothing to warm from, so its ladder is one rung
        ladder = ["cold"] if entry.index == 0 else list(RUNGS)
        assert entry.rungs_tried == ladder[:len(entry.rungs_tried)], entry.label
        assert entry.rung in entry.rungs_tried
        assert entry.reseeded == (entry.rung == "cold" and entry.index > 0)
        if entry.reseeded:
            assert entry.rwp_warm is not None
            assert entry.statistics.rwp <= entry.rwp_warm
    print("\nrungs: " + ", ".join(f"{e.label}={'→'.join(e.rungs_tried)}"
                                  for e in chained_all))
    codes = [d.code for d in chained_all.diagnostics]
    assert codes.count("SEQUENTIAL_RESEED") == sum(e.reseeded
                                                   for e in chained_all)
    # every pattern converged, so the quarantine has nothing to hold
    assert codes.count("SEQUENTIAL_UNRECOVERED") == 0
    # …and every kept rung is inside the Rwp fence it recorded (WP-1469):
    # the code is counted off the entries, exactly, and on this series is 0
    assert codes.count("SEQUENTIAL_RWP_OUTLIER") == sum(
        e.above_fence for e in chained_all) == 0
    assert all(e.rwp_fence is not None for e in chained_all.entries[1:])


@pytest.fixture(scope="module")
def chained_all_unbounded():
    """``chained_all`` with WP-1127's first-rung bound switched off."""
    return _chained_all(first_rung_factor=None)


@pytest.mark.slow
def test_the_first_rung_bound_moves_no_accepted_value(chained_all,
                                                      chained_all_unbounded):
    """`FIRST_RUNG_FACTOR`'s invariance on a real chain (WP-2003).

    The thermal ramp's twin in `test_sequential.py`, on the hostile series:
    every accepted value, esd, rung and code is equal with the bound on and
    off, and every first rung the unbounded chain kept cost less than the
    budget the bound would have set there.
    """
    from rietx.sequential import FIRST_RUNG_FACTOR
    from tests.test_sequential import chain_answer, first_rung_ratios

    assert chain_answer(chained_all) == chain_answer(chained_all_unbounded)
    ratios = first_rung_ratios(chained_all_unbounded)
    print(f"\nfirst-rung ratios: {[round(r, 3) for r in ratios]}")
    assert ratios, "the bound armed on no pattern, so nothing was tested"
    assert max(ratios) < FIRST_RUNG_FACTOR


@pytest.mark.slow
def test_series_exports(chained):
    """A series has to leave the artefacts a user actually plots.

    The third column is ``x``, not a second ``index``: this run declares no
    coordinate, so ``x_label`` is its ``"index"`` default and WP-1076's rule —
    the axis column takes ``x_label`` unless that name is already a column —
    falls back. Asserted here rather than only in the fast suite because this is
    the row that reads a *real* series' table (WP-1077 found it stale: 1076
    changed the header and this row is `slow`, so the gate that closed 1076
    never ran it).
    """
    header, rows = chained.to_table(paths=["phases.0.cell.a"])
    assert header[:3] == ["index", "label", "x"]
    assert len(rows) == len(SAMPLE1)
    assert (OUT / "seq_qarr.csv").exists()
    assert (OUT / "seq_qarr_cells.png").stat().st_size > 5_000
