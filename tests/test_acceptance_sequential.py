"""WP-0505 acceptance: a warm-started series on real data.

The IUCr CPD round-robin sample-1 mixtures (1a-1h) are the same three phases
— corundum, zincite, fluorite — measured on the same goniometer, so they are a
legitimate series in everything except the one thing that changes: the
composition, which swings from 1 to 94 wt % across the set.  That makes them a
deliberately **hostile** series, and the right one for this WP: it is exactly
where a naive "carry everything" warm start was expected to hurt.

It does not.  Measured here: 2863 iterations unchained, 904 with the scales
excluded from the carry and re-seeded per pattern, **838 carrying everything**
— at identical Rwp (0.1278) and identical weight fractions.  The expectation
that a 1 → 94 wt % scale swing needs a narrower carry is refuted, and the
module keeps both passes so the number stays measured rather than assumed.
What the series does establish is that chaining is worth 3.2x in iterations
for the same answer.

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

import numpy as np
import pytest

import rietx as rx
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
    same instrument, same ``seed_scales``, same ``qpa_plan()``.  They are
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


@pytest.fixture(scope="module")
def chained_all():
    """The naive default: carry everything, scales included."""
    _require_data()
    structure = rx.Structure(phases=_phases())
    ins = qarr_instrument()
    seed_scales(structure, ins, rx.read_pattern(DATA / f"{SAMPLE1[0]}.prn"))
    return rx.SequentialRefinement(structure, ins).fit(
        _patterns(), labels=list(SAMPLE1), plan=qpa_plan())


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
    is a measurement, and it does: ~900 iterations against 2863 unchained, for
    the same fractions.  Which `carry` policy gets there is measured too, and
    the difference is small in iterations and nil in Rwp — so what is
    *asserted* is only the part that would matter to a user: neither chain
    diverged, and restricting the carry did not make the fit worse.
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
