"""WP-1025 — the extinction-symbol screen.

Four kinds of claim, and the first two need no refinement at all:

* **the derivation** — that the classes, the IT-style symbol and the reflection
  conditions come out of the operators rather than out of a table.  Tested by
  census over gemmi's whole space-group table where a table would be tested by
  spot checks, because "derived" is a claim about *every* setting;
* **the shape** — that the answer is a class and a class is a list.  Asserted
  against the type, like ``IndexingResult``'s one rank up: nothing here can
  return one space group, and ``EXTINCTION_GROUPS_NOT_SEPARABLE`` fires whenever
  the leading class holds more than one;
* **the detectors** — that the screen separates a screw axis from its screw-free
  partner, and that a forbidden position carrying intensity refutes its class
  with the hkl named.  Both are measured on a synthetic pattern built from a
  structure that *has* the symmetry, so the absences are physics rather than a
  fixture;
* **the null model** — the measurement that changed the design: on real data the
  same absence test refutes the true class when it is read against the fitted
  background and clears it when read against the class's own calculated pattern.

Every screen here declares its 2θ range explicitly.  The range is part of the
answer — two classes differing only outside it are one class — so inheriting it
from whatever the file happens to contain would make the assertions depend on a
detail the test never states.
"""

from __future__ import annotations

from pathlib import Path

import gemmi
import numpy as np
import pytest

from rietx import determine_extinction_symbol
from rietx.indexing.extinction import (
    DECISIVE_DELTA_BIC,
    absence_classes,
    compatible_groups,
    extinction_symbol,
    reflection_conditions,
)
from rietx.indexing.fom import lattice_group
from rietx.schemas.indexing import CellCandidate

pytestmark = pytest.mark.xdist_group("extinction-symbol")

DATA = Path(__file__).parent / "data"
LAM = 1.5405929
#: the synthetic monoclinic specimen: P 2₁/c, one atom in a general position.
MONO_CELL = (8.0, 10.0, 7.0, 90.0, 100.0, 90.0)
MONO_RANGE = (15.0, 70.0)
#: NIST SRM 676a α-Al₂O₃, the certified cell (``tests/data/README.md``).
CORUNDUM_CELL = (4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0)
CORUNDUM_RANGE = (20.0, 90.0)
#: the two forbidden positions that refuted ``R - c -`` before WP-1077 — the
#: (2,0,5) and (2,0,−7) lines, 2.8 and 1.5 FWHM below (1,1,6) and (3,0,0).
CORUNDUM_FLAGGED = (56.919, 67.840)


def _candidate(cell, system, centring="P") -> CellCandidate:
    return CellCandidate(cell=cell, cell_esd=(1e-4,) * 6, system=system,
                         centring=centring,
                         lattice_group=lattice_group(system, centring),
                         volume=float(np.prod(cell[:3])))


# ----------------------------------------------------------------------
# the derivation
# ----------------------------------------------------------------------
def test_the_absence_free_class_is_the_lattice_group():
    """The reference model must be the group the rest of the indexer uses.

    ``fom.lattice_group`` is what the figure-of-merit denominators count and what
    ``validate_by_lebail`` fits; if the class with no absences chose a different
    representative, the screen's reference would be a different model from the
    one the cell was validated against, and every ΔBIC would be measured from a
    moved zero.
    """
    for cell, system, centring in [((4.1566,) * 3 + (90.0,) * 3, "cubic", "P"),
                                   ((10.25,) * 3 + (90.0,) * 3, "cubic", "I"),
                                   (MONO_CELL, "monoclinic", "P"),
                                   ((9.37, 9.37, 6.89, 90.0, 90.0, 120.0),
                                    "hexagonal", "P"),
                                   ((4.76, 4.76, 12.99, 90.0, 90.0, 120.0),
                                    "trigonal", "R")]:
        cand = _candidate(cell, system, centring)
        classes = absence_classes(cand, LAM, 90.0, 15.0)
        free = [c for c in classes if not c.conditions]
        assert len(free) == 1, [c.symbol for c in classes]
        assert (gemmi.find_spacegroup_by_name(free[0].representative)
                == gemmi.find_spacegroup_by_name(cand.lattice_group))


def test_a_hexagonal_lattice_carries_the_trigonal_groups_too():
    """The powder determines a *lattice*, not a crystal system.

    ``P 3 c 1`` and ``P 3 1 c`` own absence classes no hexagonal-system group
    reproduces, and a hexagonal metric is exactly their lattice — enumerating by
    crystal system alone would drop those hypotheses without saying so.
    """
    cand = _candidate((9.37, 9.37, 6.89, 90.0, 90.0, 120.0), "hexagonal")
    names = {sg.xhm() for sg in compatible_groups("hexagonal", "P", cand.cell)}
    assert {"P 3 c 1", "P 3 1 c", "P 6/m m m", "P 63/m"} <= names
    # and the rhombohedral-axes settings are *not* this lattice
    assert not any(n.endswith(":R") for n in names)


def test_a_class_lists_every_group_and_chooses_none():
    """The founding rule, at the level below the screen."""
    cand = _candidate((9.37, 9.37, 6.89, 90.0, 90.0, 120.0), "hexagonal")
    classes = {c.symbol: c for c in absence_classes(cand, LAM, 90.0, 15.0)}
    screw = classes["P 63 - -"]
    assert screw.space_groups == ["P 63", "P 63/m", "P 63 2 2"]
    assert screw.conditions == ["00l: l = 2n"]
    # the 6₃ screw and the 6₂/3₁ screws are different classes, not degrees of one
    assert classes["P 31 - -"].conditions == ["00l: l = 3n"]
    assert classes["P 61 - -"].conditions == ["00l: l = 6n"]


@pytest.mark.parametrize("group,expect", [
    ("P 1 21/c 1", "P 1 21/c 1"),          # the 2₁ and the c both extinguish
    ("P 1 c 1", "P 1 c 1"),
    ("P 63/m", "P 63 - -"),                # the mirror does not
    ("P m -3 m", "P - - -"),               # nothing does
    ("P a -3", "P a - -"),
    ("P b c a", "P b c a"),
    ("P m m a", "P - - a"),                # the 2₁ of P m m a is subsumed
    ("I 41/a c d", "I 41/a c d"),
])
def test_the_symbol_is_derived_from_the_members(group, expect):
    """IT's own convention, read backwards.

    The extinction symbol is the member whose H-M symbol already *is* the
    extinction symbol — the one carrying the fewest absence-generating elements —
    with every non-extinguishing position dashed.  ``P m m a``'s class is the
    check that matters: it contains ``P 21 m a``, whose 2₁ produces no condition
    the a glide does not already, so the symbol is ``P - - a`` and not
    ``P 21 - a``.
    """
    sg = gemmi.find_spacegroup_by_name(group)
    members = [s for s in gemmi.spacegroup_table()
               if s.crystal_system_str() == sg.crystal_system_str()
               and s.centring_type() == sg.centring_type()]
    hkl = np.array([(h, k, ell) for h in range(-4, 5) for k in range(-4, 5)
                    for ell in range(-4, 5) if (h, k, ell) != (0, 0, 0)],
                   dtype=np.int64)
    key = np.asarray(sg.operations().systematic_absences(hkl), dtype=bool)
    same = [s for s in members
            if np.array_equal(np.asarray(s.operations().systematic_absences(hkl),
                                         dtype=bool), key)
            and s.monoclinic_unique_axis() == sg.monoclinic_unique_axis()]
    assert extinction_symbol(same, sg.crystal_system_str(),
                             sg.centring_type()) == expect


@pytest.mark.parametrize("group,expect", [
    ("P 21/c", ["h0l: l = 2n", "0k0: k = 2n"]),
    ("P 63/m", ["00l: l = 2n"]),
    ("P n m a", ["0kl: k+l = 2n", "hk0: h = 2n"]),
    ("P b c a", ["0kl: k = 2n", "h0l: l = 2n", "hk0: h = 2n"]),
    ("F d d d", ["0kl: k+l = 4n", "h0l: h+l = 4n", "hk0: h+k = 4n"]),
    ("P 41 21 2", ["h00: h = 2n", "0k0: k = 2n", "00l: l = 4n"]),
    ("R 3 c", ["0kl: l = 2n", "h0l: l = 2n", "h-hl: l = 2n"]),
])
def test_conditions_are_fitted_to_the_absences(group, expect):
    """Every printed condition reproduces its zone's absences exactly, or is not
    printed — and an axial condition a zone already implies is left out.

    ``P b c a`` and ``P 41 21 2`` are the pair to read together.  Both have
    ``h00: h = 2n``, ``0k0: k = 2n`` and ``00l: l = 2n`` (4n) in IT; in P b c a
    every one of them is *implied* by a glide's zone condition and is dropped,
    while P 4₁2₁2 has no glide at all, so its axial conditions are the whole
    content and all three stay.  ``R 3 c`` shows the hexagonal-axes images of one
    c glide, which is why the zone list has to contain them.
    """
    assert _conditions_for(group) == (expect, True)


def _conditions_for(group: str, half: int = 5):
    sg = gemmi.find_spacegroup_by_name(group)
    rng = np.arange(-half, half + 1)
    grid = np.meshgrid(rng, rng, rng, indexing="ij")
    hkl = np.column_stack([g.ravel() for g in grid]).astype(np.int64)
    hkl = hkl[~np.all(hkl == 0, axis=1)]
    absent = np.asarray(sg.operations().systematic_absences(hkl), dtype=bool)
    centring = gemmi.find_spacegroup_by_name(
        {"P": "P 1", "A": "A 1", "B": "B 1", "C": "C 1", "I": "I 1", "F": "F 1",
         "R": "R 3:H"}[sg.centring_type()])
    keep = ~np.asarray(centring.operations().systematic_absences(hkl), dtype=bool)
    return reflection_conditions(hkl[keep], absent[keep])


def test_the_condition_derivation_is_measured_over_the_whole_table():
    """"Derived" is a claim about every setting, so it is tested on every setting.

    Measured on gemmi 0.7.5: **1** of 550 settings has an absence no fitted rule
    names — ``C 4 2 21``, a non-standard tetragonal C setting — and it reports
    ``conditions_complete = False`` rather than printing a partial list as if it
    were whole.  A spot check would have found the 77 failures the first
    derivation had, but not told anyone the true number.
    """
    incomplete = [sg.xhm() for sg in gemmi.spacegroup_table()
                  if sg.ext != "R" and not _conditions_for(sg.xhm(), half=4)[1]]
    assert incomplete == ["C 4 2 21"], incomplete


def test_the_unreadable_ccp4_settings_lose_no_class():
    """Dropping a symbol nobody can parse must not drop a hypothesis.

    gemmi carries CCP4 origin-shifted entries (``P 21212(a)``, ``I 2 3a``) whose
    symbols are not H-M, so their positions cannot be read and they are excluded.
    This asserts what makes that safe: each one's absence set is already some
    kept setting's, so it would have joined an existing class and only made the
    label underivable.
    """
    hkl = np.array([(h, k, ell) for h in range(-4, 5) for k in range(-4, 5)
                    for ell in range(-4, 5) if (h, k, ell) != (0, 0, 0)],
                   dtype=np.int64)

    def key(sg):
        return np.asarray(sg.operations().systematic_absences(hkl),
                          dtype=bool).tobytes()

    kept: dict[tuple[str, str], set[bytes]] = {}
    dropped = []
    for sg in gemmi.spacegroup_table():
        if sg.ext == "R":
            continue
        where = (sg.crystal_system_str(), sg.centring_type())
        if sg in compatible_groups_for(sg):
            kept.setdefault(where, set()).add(key(sg))
        else:
            dropped.append(sg)
    assert dropped, "the filter must actually drop something"
    for sg in dropped:
        where = (sg.crystal_system_str(), sg.centring_type())
        assert key(sg) in kept.get(where, set()), sg.xhm()


def compatible_groups_for(sg):
    """The enumeration this setting would face, for its own system/centring."""
    cell = {"triclinic": (5.0, 6.0, 7.0, 80.0, 85.0, 95.0),
            "monoclinic": MONO_CELL,
            "orthorhombic": (7.0, 8.0, 9.0, 90.0, 90.0, 90.0),
            "tetragonal": (5.0, 5.0, 13.0, 90.0, 90.0, 90.0),
            "trigonal": (4.76, 4.76, 12.99, 90.0, 90.0, 120.0),
            "hexagonal": (9.37, 9.37, 6.89, 90.0, 90.0, 120.0),
            "cubic": (4.1566,) * 3 + (90.0,) * 3}[sg.crystal_system_str()]
    if sg.crystal_system_str() == "monoclinic":
        cell = {"a": (10.0, 8.0, 7.0, 100.0, 90.0, 90.0),
                "b": MONO_CELL,
                "c": (8.0, 10.0, 7.0, 90.0, 90.0, 100.0)}[
                    sg.monoclinic_unique_axis()]
    return compatible_groups(sg.crystal_system_str(), sg.centring_type(), cell)


# ----------------------------------------------------------------------
# the screen, on a specimen that has the symmetry
# ----------------------------------------------------------------------
def _mono_models(space_group: str = "P 1 21/c 1"):
    from rietx.schemas.instrument import BackgroundChebyshev, Instrument
    from rietx.schemas.structure import Atom, Cell, Parameter, Phase, Structure

    a, b, c, alpha, beta, gamma = MONO_CELL
    structure = Structure(phases=[Phase(
        name="synthetic", space_group=space_group,
        cell=Cell(a=Parameter(value=a, min=0.1), b=Parameter(value=b, min=0.1),
                  c=Parameter(value=c, min=0.1),
                  alpha=Parameter(value=alpha), beta=Parameter(value=beta),
                  gamma=Parameter(value=gamma)),
        scale=Parameter(value=3e-3, min=0.0, transform="softplus"),
        atoms=[Atom(label="Si", species="Si", x=Parameter(value=0.211),
                    y=Parameter(value=0.317), z=Parameter(value=0.123)),
               Atom(label="O", species="O", x=Parameter(value=0.402),
                    y=Parameter(value=0.081), z=Parameter(value=0.294))])])
    instrument = Instrument.debye_scherrer(wavelength=LAM)
    instrument.profile.w.value = 4e-3
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 2.0)])
    return structure, instrument


def _pattern(structure, instrument, *, seed: int = 7):
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    tt = np.arange(MONO_RANGE[0], MONO_RANGE[1], 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


@pytest.fixture(scope="module")
def mono_screen():
    """The screen on a P 2₁/c specimen — module-scoped and pinned to one worker
    (``pytestmark``) because it costs eight Le Bail fits."""
    structure, instrument = _mono_models()
    data = _pattern(structure, instrument)
    return determine_extinction_symbol(
        data, _candidate(MONO_CELL, "monoclinic"), instrument,
        two_theta_limits=MONO_RANGE)


def test_the_screw_axis_is_separated_from_its_screw_free_partner(mono_screen):
    """P 2₁/c against P c: the same glide, one extra screw, and the only
    evidence is the handful of 0k0 lines with k odd.

    This is the whole method in one assertion.  Both classes fit the pattern
    equally well — the screw-free one predicts *more* reflections, so it can only
    fit better — and what separates them is that the extra lines it predicts are
    testable and absent, which the nested comparison charges it for.
    """
    ranked = [c.symbol for c in mono_screen.candidates]
    assert ranked[0] == "P 1 21/c 1", ranked
    assert "P 1 c 1" in ranked
    top, partner = mono_screen.candidates[0], _by_symbol(mono_screen, "P 1 c 1")
    assert not top.refuted and not partner.refuted
    assert top.n_testable >= 2, "the 0k0 lines are what carry the difference"
    assert partner.delta_bic - top.delta_bic > DECISIVE_DELTA_BIC
    # **Rwp cannot separate them at all** — measured, 0.080939 against 0.080949,
    # a difference of 1e-5 between a class with three more reflections and one
    # without them.  (It is not even ordered: a Le Bail extraction is iterative
    # rather than a least-squares optimum over the intensities, so the fuller
    # model is not guaranteed to fit better.  One more reason the score is the
    # nested comparison and not the agreement index.)
    assert abs(top.rwp - partner.rwp) < 2e-3


def test_the_answer_is_a_class_and_a_class_is_a_list(mono_screen):
    """No accessor anywhere returns one space group.

    Asserted against the type, the same way ``IndexingResult`` is: here the
    leading class happens to contain exactly one group, and even then it arrives
    as a one-element list rather than as a symbol.
    """
    from rietx.schemas.indexing import ExtinctionScreen

    for forbidden in ("space_group", "symbol", "best", "solution"):
        assert forbidden not in ExtinctionScreen.model_fields
        assert not hasattr(ExtinctionScreen, forbidden)
    best = mono_screen.best_or_none()
    assert best is not None, [c.refuted_reason for c in mono_screen.candidates]
    assert best.space_groups == ["P 1 21/c 1"]
    # one group in the class ⇒ nothing to warn about; the info code is reserved
    # for the case where the data genuinely cannot choose
    assert not any(d.code == "EXTINCTION_GROUPS_NOT_SEPARABLE"
                   for d in mono_screen.diagnostics)


def test_every_wrong_class_is_refuted_by_a_named_reflection(mono_screen):
    """A refutation the user cannot check is not evidence."""
    refuted = [c for c in mono_screen.candidates if c.refuted]
    assert refuted, [c.symbol for c in mono_screen.candidates]
    for cand in refuted:
        assert cand.forbidden_hkl and cand.forbidden_two_theta
        assert len(cand.forbidden_hkl) == cand.n_present
        codes = {d.code for d in cand.diagnostics}
        assert "EXTINCTION_FORBIDDEN_INTENSITY" in codes
        # every named position is inside the range that was screened
        lo, hi = mono_screen.two_theta_range
        assert all(lo <= t <= hi for t in cand.forbidden_two_theta)


def test_a_cancelled_screen_abstains_and_says_which_classes_it_reached():
    """WP-1006's token works here unchanged, and the granularity is one class.

    It is deliberately *not* threaded into the individual class fits: a
    ``RefinementCancelled`` raised inside one would be indistinguishable from a
    class whose physics failed, and a cancelled run would come back looking like
    a refutation. Each class fit is ~0.1 s, so between-class is granular enough.
    The cell-free prefit (``refine_cell=True``) *does* take the token, being a
    five-stage fit, and a stop there returns before any class exists
    (``test_extinction_gate``); this test holds the cell to reach the classes.
    """
    from rietx.optimize.cancel import CancelToken

    structure, instrument = _mono_models()
    data = _pattern(structure, instrument)
    token = CancelToken()
    token.cancel()
    screen = determine_extinction_symbol(
        data, _candidate(MONO_CELL, "monoclinic"), instrument,
        two_theta_limits=MONO_RANGE, cancel=token, refine_cell=False)
    assert screen.status == "cancelled"
    assert screen.n_classes and screen.n_screened == 0
    assert screen.best_or_none() is None
    assert all(not c.refuted for c in screen.candidates), (
        "a cancelled screen has refuted nothing — it asked nothing")


def test_a_screen_that_cannot_run_reports_rather_than_raises():
    """A cell with no reflections in range fails *every* class identically, so it
    is a statement about the input — reported as a failed screen with a reason,
    never as a traceback that would abandon the caller mid-workflow."""
    from rietx.schemas.instrument import Instrument
    from rietx.schemas.pattern import PatternData

    tt = np.arange(5.0, 8.0, 0.02)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 100.0).tolist())
    screen = determine_extinction_symbol(
        data, _candidate((4.0,) * 3 + (90.0,) * 3, "cubic"),
        Instrument.debye_scherrer(wavelength=LAM), two_theta_limits=(5.0, 8.0))
    assert screen.status == "failed"
    assert screen.best_or_none() is None
    assert [d.code for d in screen.diagnostics] == ["EXTINCTION_SCREEN_FAILED"]


def test_a_capped_screen_abstains_because_the_question_was_not_asked():
    """``max_classes`` bounds the cost, and the answer says it was bounded.

    The same rule as the indexing gate's ``checked`` caveat one rank up: a class
    nobody fitted has an unasked question behind it, and an unasked question must
    not read as a clean answer — even when the classes that *were* fitted look
    decisive on their own.
    """
    structure, instrument = _mono_models()
    data = _pattern(structure, instrument)
    screen = determine_extinction_symbol(
        data, _candidate(MONO_CELL, "monoclinic"), instrument,
        two_theta_limits=MONO_RANGE, max_classes=2)
    assert screen.n_classes > screen.n_screened == 2
    assert screen.best_or_none() is None
    note = next(d for d in screen.diagnostics
                if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")
    assert "never fitted" in note.message


def test_intensity_at_a_forbidden_position_refutes_the_class():
    """Inject one peak where P 2₁/c forbids a reflection, and the class falls.

    The 0k0 lines with k odd are the 2₁ screw's whole evidence, so a peak at one
    of them is the sharpest possible counter-example: the pattern is otherwise
    the same specimen, and the class that was ranked first without it must come
    back refuted **naming that reflection** rather than merely scoring worse.
    """
    from rietx.schemas.pattern import PatternData

    structure, instrument = _mono_models()
    data = _pattern(structure, instrument)
    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=np.float64)
    # 0 3 0: d = b/3, well inside the range and clear of its neighbours
    d = MONO_CELL[1] / 3.0
    position = float(np.degrees(2.0 * np.arcsin(LAM / (2.0 * d))))
    y = y + 4000.0 * np.exp(-0.5 * ((tt - position) / 0.03) ** 2)
    spiked = PatternData(two_theta=data.two_theta, intensity=y.tolist())

    screen = determine_extinction_symbol(
        spiked, _candidate(MONO_CELL, "monoclinic"), instrument,
        two_theta_limits=MONO_RANGE)
    fallen = _by_symbol(screen, "P 1 21/c 1")
    assert fallen.refuted, fallen.refuted_reason
    assert (0, 3, 0) in [tuple(h) for h in fallen.forbidden_hkl]
    assert any(abs(t - position) < 0.05 for t in fallen.forbidden_two_theta)
    # the screw-free partner keeps every reflection the spike sits on, so it is
    # untouched — the two answers differ by exactly the evidence that changed
    assert not _by_symbol(screen, "P 1 c 1").refuted
    assert screen.candidates[0].symbol == "P 1 c 1"


def _by_symbol(screen, symbol: str):
    for cand in screen.candidates:
        if cand.symbol == symbol:
            return cand
    raise AssertionError(f"{symbol} not enumerated: "
                         f"{[c.symbol for c in screen.candidates]}")


# ----------------------------------------------------------------------
# real data
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def fap_screen():
    """Fluorapatite, GSAS-II's LabData tutorial pattern — a real lab specimen
    whose space group (P 6₃/m) is known from the tutorial's own refinement."""
    import rietx as rx
    from rietx.schemas.instrument import BackgroundChebyshev, EmissionLine, Source

    path = DATA / "FAP.XRA"
    if not path.exists():
        pytest.skip("GSAS-II LabData tutorial dataset not present")
    raw = rx.read_pattern(path)
    data = rx.PatternData(two_theta=raw.two_theta, intensity=raw.intensity,
                          sigma=raw.sigma, metadata=raw.metadata)
    instrument = rx.Instrument.bragg_brentano()
    instrument.source = Source(
        lines=[EmissionLine(wavelength=1.5405),
               EmissionLine(wavelength=1.5443,
                            weight=rx.Parameter(value=0.5, min=0.0, max=1.0))],
        polarization=rx.Parameter(value=0.5, min=0.0, max=1.0),
        # the cross-code protocol this dataset is pinned to declines dispersion
        # (tests/test_acceptance_fap.py); a screen is not the place to change it
        dispersion=None)
    instrument.profile.u.value = 2e-4
    instrument.profile.v.value = -2e-4
    instrument.profile.w.value = 5e-4
    instrument.background = BackgroundChebyshev.with_terms(6)
    cand = _candidate((9.3717, 9.3717, 6.8859, 90.0, 90.0, 120.0), "hexagonal")
    return determine_extinction_symbol(data, cand, instrument,
                                       two_theta_limits=(15.0, 90.0))


@pytest.mark.slow
def test_fap_returns_the_p63_class_with_its_groups_listed(fap_screen):
    """The acceptance criterion: the right class first, its groups **listed**.

    P 6₃/m is the answer the tutorial refines, and it is *not* what this returns —
    what it returns is ``P 63 - -``, the class {P 6₃, P 6₃/m, P 6₃22}, because a
    powder cannot tell those three apart.  The mirror and the two-folds produce no
    absences, so no counting time separates them; the diagnostic says so and names
    the alternative arbiter.
    """
    best = fap_screen.best_or_none()
    assert best is not None, [(c.symbol, c.refuted_reason)
                              for c in fap_screen.candidates]
    assert best.symbol == "P 63 - -"
    assert best.space_groups == ["P 63", "P 63/m", "P 63 2 2"]
    assert best.conditions == ["00l: l = 2n"]
    assert not best.refuted and best.n_testable >= 1
    assert best.delta_bic < -DECISIVE_DELTA_BIC

    note = next(d for d in fap_screen.diagnostics
                if d.code == "EXTINCTION_GROUPS_NOT_SEPARABLE")
    for group in best.space_groups:
        assert group in note.where[0]
    assert note.level == "info"

    # every other class is refuted, and by named reflections
    others = [c for c in fap_screen.candidates if c.symbol not in
              (best.symbol, "P - - -")]
    assert others and all(c.refuted and c.forbidden_hkl for c in others)


@pytest.mark.slow
def test_fap_would_be_refuted_by_the_background_null_model(fap_screen):
    """The measurement that changed the design, pinned so it is not undone.

    The 003 reflection P 6₃/m forbids sits **0.89 FWHM** from the allowed (3,-1,2),
    which is ten times stronger.  Read against the fitted *background* — WP-1024's
    ``absent_reflections`` as the plan called for — its window carries +27 σ and
    the true class is refuted.  Read against the class's own ``y_calc``, which
    contains that neighbour, the same window reads about −4 σ.  The test asserts
    both halves, because the first is the reason the second is not obvious.
    """
    from rietx.indexing.extinction import _fit_class
    from rietx.indexing.peaks import predicted_fwhm
    from rietx.indexing.workflow import structure_from_candidate, validation_plan
    from rietx.refine import Refinement

    data, cand, instrument = _fap_inputs()
    pre = Refinement(structure_from_candidate(cand), instrument, history=False)
    # ``two_theta_max`` as ``determine_extinction_symbol`` passes it: without
    # it the plan takes the 6° slack cap, its profile stage never converges,
    # and where it stopped moved with WP-1930's floor seed (over_model 1.1
    # unseeded, 20.1 seeded).  With it both arms converge to this docstring's
    # 0.89 FWHM, +27.7 σ and −3.7 σ.
    pre.fit(data, mode="lebail",
            plan=validation_plan(cand, instrument, two_theta_max=90.0),
            two_theta_limits=(15.0, 90.0))
    frozen = pre.fitted_instrument
    # 003's *fitted* position, from the absence-free fit that still predicts it —
    # the ideal Bragg angle is 0.05° away here, which is itself the milestone's
    # standing lesson about assumed versus measured positions
    lattice_fit, _lattice_result = _fit_class(cand, data, frozen, "P 6/m m m",
                                              (15.0, 90.0))
    position = next(r.two_theta for r in lattice_fit.reflection_table()
                    if r.line == 0 and (r.h, r.k, r.l) == (0, 0, 3))

    fit, result = _fit_class(cand, data, frozen, "P 63 2 2", (15.0, 90.0))
    rows = [r for r in fit.reflection_table() if r.line == 0]
    tt = np.array([r.two_theta for r in rows])
    hkl = np.array([(r.h, r.k, r.l) for r in rows])

    # the class no longer predicts 003, and its nearest surviving neighbour is
    # inside one FWHM — close enough to fill the window, too far for
    # ``_overlap_groups`` to call the two unresolvable
    width = float(predicted_fwhm(np.array([position]), frozen)[0])
    nearest = int(np.argmin(np.abs(tt - position)))
    gap = float(abs(tt[nearest] - position))
    assert tuple(hkl[nearest]) != (0, 0, 3)
    assert 0.5 * width < gap < 1.5 * width, (gap, width)

    data_tt = np.asarray(result.two_theta)
    inside = np.abs(data_tt - position) <= 0.5 * width
    noise = float(np.sqrt((np.asarray(result.sigma)[inside] ** 2).sum()))
    y_obs = np.asarray(result.y_obs)[inside]
    over_background = (y_obs - np.asarray(result.y_background)[inside]).sum() / noise
    over_model = (y_obs - np.asarray(result.y_calc)[inside]).sum() / noise
    assert over_background > 10.0, over_background
    assert over_model < 3.0, over_model


@pytest.fixture(scope="module")
def nac_screen():
    """11-BM synchrotron NAC (Na₂Ca₃Al₂F₁₄, I 2₁3) with its CaF₂ impurity, over
    the acceptance suite's own 2-24° 2θ window and its declined dispersion —
    adopting a protocol means adopting what it did *not* model too."""
    import rietx as rx
    from rietx.schemas.instrument import BackgroundChebyshev

    path = DATA / "11BM_NAC.fxye"
    if not path.exists():
        pytest.skip("11-BM NAC dataset not present")
    data = rx.read_pattern(path)
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = BackgroundChebyshev.with_terms(6)
    instrument.source.dispersion = None
    cand = _candidate((10.2513,) * 3 + (90.0,) * 3, "cubic", "I")
    return determine_extinction_symbol(data, cand, instrument,
                                       two_theta_limits=(2.0, 24.0))


@pytest.mark.slow
def test_nac_returns_the_centred_class_and_claims_nothing_more(nac_screen):
    """The answer here is "no absences beyond the centring", and that is a result.

    NAC is I 2₁3, and **its screw axes are invisible in principle**: a 2₁ along
    **a** restricts h00 to h = 2n, which I-centring (h+k+l = 2n) already
    enforces on those very reflections, so the screw adds no absence.  So
    the honest answer is the absence-free I class — the true group listed among
    six, never chosen — and a screen that reported ``I 21 - -`` would be claiming
    evidence the lattice makes unobtainable.  Every class that does claim more is
    refuted, on a real pattern that also carries a CaF₂ impurity.
    """
    best = nac_screen.best_or_none()
    assert best is not None, [(c.symbol, c.refuted_reason)
                              for c in nac_screen.candidates]
    assert best.symbol == "I - - -"
    assert best.n_absent == 0 and best.conditions == []
    assert "I 21 3" in best.space_groups         # the truth, listed not chosen
    assert len(best.space_groups) == 6

    note = next(d for d in nac_screen.diagnostics
                if d.code == "EXTINCTION_GROUPS_NOT_SEPARABLE")
    for group in best.space_groups:
        assert group in note.where[0]
    others = [c for c in nac_screen.candidates if c is not best]
    assert others and all(c.refuted for c in others)


@pytest.fixture(scope="module")
def corundum_inputs():
    """SRM 676a corundum from the IUCr CPD round robin, on the CPD's own
    instrument (``tests/test_acceptance_qpa_roundrobin.qarr_instrument`` —
    Philips Bragg-Brentano, Cu Kα doublet, graphite monochromator, dispersion
    declined) with the certified cell.

    The dataset this suite was missing (WP-1077): a **rhombohedral glide** — the
    c of ``R -3 c`` — on **real laboratory data**, in a specimen carrying its own
    impurity lines and a strong unmodelled axial tail.  The three rows above are
    a synthetic monoclinic, a hexagonal screw axis and a cubic *I* lattice whose
    answer is "no absences at all", and none of them can fail this way.

    ``seed_widths`` is applied because the instrument declares the ``ProfileTCHZ``
    default (a synchrotron line, ~13× too narrow here) and the screen's whole
    argument rests on a profile fit; the range is trimmed to 20-90° for the same
    reason, which is what ``docs/docs/reference/extinction.md``'s ``peaks`` and
    ``two_theta_limits`` are for.
    """
    import rietx as rx
    from rietx.indexing.workflow import seed_widths
    from tests.test_acceptance_qpa_roundrobin import qarr_instrument

    path = DATA / "qarr" / "corundum.prn"
    if not path.exists():
        pytest.skip("IUCr round-robin corundum pattern not present")
    data = rx.read_pattern(path)
    instrument, seeded = seed_widths(qarr_instrument(), rx.pick_peaks(
        data, qarr_instrument()))
    assert seeded, "the declared profile is the one this protocol repairs"
    return data, _candidate(CORUNDUM_CELL, "trigonal", "R"), instrument


@pytest.fixture(scope="module")
def corundum_screen(corundum_inputs):
    data, cand, instrument = corundum_inputs
    return determine_extinction_symbol(data, cand, instrument,
                                       two_theta_limits=CORUNDUM_RANGE)


def test_corundum_returns_the_class_its_certificate_names(corundum_screen):
    """The acceptance criterion, and it is a **certificate**, not a fit.

    SRM 676a is α-Al₂O₃ in ``R -3 c``, so the c glide is the answer the specimen
    is certified to have — decided before the screen was ever run on it, which is
    what ``tests/CLAUDE.md`` asks of a scored row.  What comes back is
    ``R - c -`` = {R 3 c, R -3 c}: the certified group listed, never chosen, and
    its partner is the non-centrosymmetric one, so this is the doctrine's
    cleanest real-data instance — no counting time separates them.

    Before WP-1077 this returned ``R - - -``, whose five members do not include
    ``R -3 c`` at all.  That was not the package abstaining; it was a wrong
    answer, reached from the workflow the agent skill's §7d prescribes
    (``docs/skill/rietx/references/diagnostics-indexing.md``).
    """
    best = corundum_screen.best_or_none()
    assert best is not None, [(c.symbol, c.refuted_reason)
                              for c in corundum_screen.candidates]
    assert best.symbol == "R - c -"
    assert best.space_groups == ["R 3 c:H", "R -3 c:H"]
    assert "R -3 c:H" in best.space_groups          # the certificate's group
    assert best.conditions == ["0kl: l = 2n", "h0l: l = 2n", "h-hl: l = 2n"]
    assert best.conditions_complete
    assert not best.refuted and best.n_present == 0
    assert best.n_absent == 10 and 1 <= best.n_testable < best.n_absent
    assert best.delta_bic < -DECISIVE_DELTA_BIC

    note = next(d for d in corundum_screen.diagnostics
                if d.code == "EXTINCTION_GROUPS_NOT_SEPARABLE")
    assert note.level == "info"
    for group in best.space_groups:
        assert group in note.where[0]


def test_a_neighbours_tail_is_not_absence_evidence(corundum_screen,
                                                   corundum_inputs):
    """Why the certified class survives, measured on the pattern that broke it.

    The two positions that refuted ``R - c -`` before WP-1077 — (2,0,5) and
    (2,0,−7) — sit 2.8 and 1.5 FWHM below the strong (1,1,6) and (3,0,0), on the
    **low-angle** flank where the unmodelled axial tail lives.  Each window is
    already filled by its neighbour, so what the absence test read there was the
    accuracy of the profile model and not the absence.

    The control is the second half and it is what makes this a measurement rather
    than an excuse: at the same offset from an allowed line, at positions where
    **no reflection of any kind** is predicted, the same 3σ test fires on a large
    fraction of probes — and only below the line, never above it.  A test that
    fires on nothing cannot be evidence about something.
    """
    from rietx.indexing.extinction import _fit_class
    from rietx.indexing.peaks import predicted_fwhm
    from rietx.indexing.workflow import structure_from_candidate, validation_plan
    from rietx.refine import Refinement

    data, cand, instrument = corundum_inputs
    pre = Refinement(structure_from_candidate(cand), instrument, history=False)
    pre.fit(data, mode="lebail", plan=validation_plan(cand, instrument),
            two_theta_limits=CORUNDUM_RANGE)
    frozen = pre.fitted_instrument
    fit, result = _fit_class(cand, data, frozen, "R -3 c:H", CORUNDUM_RANGE)

    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    y_bkg = np.asarray(result.y_background)
    sigma = np.asarray(result.sigma)

    def window(position: float, width: float) -> tuple[float, float]:
        """(observed excess, predicted neighbour tail), both in units of σ."""
        inside = np.abs(tt - position) <= 0.5 * width
        noise = float(np.sqrt((sigma[inside] ** 2).sum()))
        return (float((y_obs[inside] - y_calc[inside]).sum()) / noise,
                float((y_calc[inside] - y_bkg[inside]).sum()) / noise)

    # the class no longer predicts either position, and both are far enough from
    # every surviving line for ``testable_mask`` to have called them separable
    for position in CORUNDUM_FLAGGED:
        width = float(predicted_fwhm(np.array([position]), frozen)[0])
        excess, tail = window(position, width)
        assert excess > 3.0, (position, excess)     # the old refutation
        assert tail > 10.0, (position, tail)        # and what was in the window
    assert corundum_screen.best_or_none().n_present == 0, (
        "the tail is what the gate removes, so neither position may refute")

    # the control: the same test at positions carrying no reflection at all
    lines = np.array(sorted({round(r.two_theta, 5)
                             for r in fit.reflection_table()}))
    lo, hi = CORUNDUM_RANGE

    def probe(offset: float) -> np.ndarray:
        out = []
        for line in lines:
            width = float(predicted_fwhm(np.array([line]), frozen)[0])
            position = line + offset * width
            if not lo + 0.3 < position < hi - 0.3:
                continue
            if float(np.min(np.abs(lines - position))) <= 0.5 * width:
                continue                    # a real line sits in the window
            out.append(window(position, width)[0])
        return np.array(out)

    below, above = probe(-1.5), probe(+1.5)
    assert len(below) > 20 and len(above) > 20
    assert float((below > 3.0).mean()) > 0.25, float((below > 3.0).mean())
    assert below.max() > 10.0, below.max()
    # and the asymmetry, which is what names the cause as the axial tail
    assert float((above > 3.0).mean()) < 0.15, float((above > 3.0).mean())
    assert np.median(below) > np.median(above) + 1.0


def _fap_inputs():
    import rietx as rx
    from rietx.schemas.instrument import BackgroundChebyshev, EmissionLine, Source

    raw = rx.read_pattern(DATA / "FAP.XRA")
    data = rx.PatternData(two_theta=raw.two_theta, intensity=raw.intensity,
                          sigma=raw.sigma, metadata=raw.metadata)
    instrument = rx.Instrument.bragg_brentano()
    instrument.source = Source(
        lines=[EmissionLine(wavelength=1.5405),
               EmissionLine(wavelength=1.5443,
                            weight=rx.Parameter(value=0.5, min=0.0, max=1.0))],
        polarization=rx.Parameter(value=0.5, min=0.0, max=1.0), dispersion=None)
    instrument.profile.u.value = 2e-4
    instrument.profile.v.value = -2e-4
    instrument.profile.w.value = 5e-4
    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, _candidate((9.3717, 9.3717, 6.8859, 90.0, 90.0, 120.0),
                            "hexagonal"), instrument
