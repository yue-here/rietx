"""WP-1418 (issue #1082): the ``magnetic_structural`` preset, and the plan that
frees no moment saying so (``PLAN_FREES_NO_MOMENT``).

The fixture is #1081's synthetic k = (0, 0, ½) child: a P 4/m m m parent
(a = 4.0, c = 4.2 Å), Mn1 at the origin and O1 at (½, ½, 0.2813), the first
``isotropy.candidates`` group at that k, Mn³⁺ at 3.0 μ_B, simulated with
Poisson-scale noise.  The start has the moment 20 % high (3.6 μ_B) and every
Biso 0.3 Å² high, the two offsets #1082's verification names.  The
anti-translation ties are applied on every fit, as a caller must for a
supercell statement.

Interpretation table (written before the test bodies)
-----------------------------------------------------
=====================  ==================================  ===============================
arm                    fit                                 if it fails, it means
=====================  ==================================  ===============================
positive (held)        ``mccusker_default``,               the moment moved without a
                       ``mccusker_structural``             stage freeing it, or the plan
                                                           check is silent on the case it
                                                           exists for
recovery               ``magnetic_structural``             the preset does not refine the
                                                           moment with the structure, or
                                                           refines it to a biased value
negative (nuclear)     a phase with no moment              the check fires with no moment
negative (freed)       a plan naming ``moment.dof*``,      the check fires on a plan that
                       one freeing it only in a later      frees the moment, or reads one
                       stage                               stage rather than the plan
negative (hold)        the moment held by the caller       the check overrides the
                                                           caller's own hold
series                 ``refine_sequential`` under         ``SEQUENTIAL_MOMENT_HOLD``
                       ``mccusker_default``                still blames a missing esd
                                                           rather than the plan
=====================  ==================================  ===============================

**Tolerance: 2 esd**, as ``test_magnetic_width_k_half``: on one noise draw a
1 esd bar fails about a third of the time for no reason but the seed.
Measured on this seed (macOS arm64, ``[dev]``): moment 2.9971 ± 0.0045 μ_B
(0.63 esd), Biso 0.466 ± 0.112, 0.331 ± 0.108, 0.617 ± 0.057 and
0.586 ± 0.056 Å² against 0.4, 0.4, 0.6 and 0.6 (at most 0.64 esd).  Each
child copy's Biso refines on its own (issue #1081), so the four are asserted
one by one.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.supercell import anti_translation_ties, magnetic_supercell
from rietx.schemas.structure import Atom, Cell, Parameter, Phase
from rietx.strategy.staged import PLAN_INFO, PLAN_PRESETS, RefinementPlan

pytestmark = pytest.mark.xdist_group("magnetic-structural-preset")

TRUE_M, START_M, DB = 3.0, 3.6, 0.3
TRUE_BISO = {"Mn": 0.4, "O": 0.6}
GRID = np.arange(5.0, 120.0, 0.05)
CODE = "PLAN_FREES_NO_MOMENT"
MODULI = ["phases.0.atoms.0.moment.dof0", "phases.0.atoms.1.moment.dof0"]


def _parent() -> Phase:
    def p(v):
        return Parameter(value=v)
    return Phase(
        name="tetragonal", space_group="P 4/m m m",
        cell=Cell(a=p(4.0), b=p(4.0), c=p(4.2), alpha=p(90.0), beta=p(90.0),
                  gamma=p(90.0)),
        atoms=[Atom(label="Mn1", species="Mn", x=p(0.0), y=p(0.0), z=p(0.0),
                    biso=p(TRUE_BISO["Mn"])),
               Atom(label="O1", species="O", x=p(0.5), y=p(0.5), z=p(0.2813),
                    biso=p(TRUE_BISO["O"]))])


def _instrument():
    return rx.Instrument.constant_wavelength_neutron(1.54, fwhm_deg=0.35)


def _child(magnitude: float) -> Phase:
    group = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]
    return magnetic_supercell(_parent(), group, magnetic_species=["Mn1"],
                              ion={"Mn1": "Mn3+"}, magnitude=magnitude).phase


def _simulate(seed: int = 20261028):
    ref = rx.Refinement(rx.Structure(phases=[_child(TRUE_M)]), _instrument())
    y = np.asarray(ref.predict(GRID)) + 40.0
    y = y + np.random.default_rng(seed).normal(scale=np.sqrt(np.maximum(y, 1.0)))
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


def _start() -> Phase:
    phase = _child(START_M)
    for atom in phase.atoms:
        atom.biso.value += DB
    return phase


def _tie(ref: rx.Refinement) -> None:
    for target, source, scale, offset in anti_translation_ties(
            ref.structure.phases[0]):
        ref.tie(target, source, scale=scale, offset=offset)


def _fit(data, plan, *, phase=None, hold=()):
    phase = phase or _start()
    ref = rx.Refinement(rx.Structure(phases=[phase]), _instrument())
    if phase.atoms[0].moment is not None:
        _tie(ref)
    if hold:
        ref.hold(list(hold))
    return ref, ref.fit(data, plan=plan, telemetry=False)


def _codes(result, code=CODE):
    return [d for d in result.diagnostics if d.code == code]


def _moduli(ref) -> list[float]:
    return [float(np.linalg.norm(a.moment.values()))
            for a in ref.fitted_structure.phases[0].atoms if a.moment is not None]


@pytest.fixture(scope="module")
def data():
    return _simulate()


@pytest.fixture(scope="module")
def arms(data):
    return {name: _fit(data, name) for name in
            ("mccusker_default", "mccusker_structural", "magnetic_structural")}


# ---------------------------------------------------------------- the preset

def test_the_preset_frees_the_moduli_then_the_moments_then_the_structure():
    plan = PLAN_PRESETS["magnetic_structural"]()
    names = [s.name for s in plan.stages]
    structural = [s.name for s in RefinementPlan.mccusker_structural().stages]
    assert names == [structural[0], "moment_moduli", "moments", *structural[1:]]
    assert plan.stages[1].turn_on == ["phases.*.atoms.*.moment.dof0"]
    assert plan.stages[2].turn_on == ["phases.*.atoms.*.moment.dof*"]
    # the nuclear stages are mccusker_structural's own, glob for glob
    assert [s.turn_on for s in plan.stages[3:]] == [
        s.turn_on for s in RefinementPlan.mccusker_structural().stages[1:]]
    # staging is cumulative and the closing stage frees every glob, so the
    # moments are free to the end
    assert "phases.*.atoms.*.moment.dof*" in plan.closing_stage().turn_on
    assert PLAN_INFO["magnetic_structural"].modes == ("rietveld",)


# ---------------------------------------------------------- the positive arm

@pytest.mark.parametrize("name", ["mccusker_default", "mccusker_structural"])
def test_a_plan_freeing_no_moment_leaves_it_at_its_start_and_says_so(arms, name):
    ref, result = arms[name]
    assert _moduli(ref) == pytest.approx([START_M, START_M], abs=1e-12)
    rows = {p.path: p for p in result.parameters}
    assert all(rows.get(p) is None or rows[p].stderr is None for p in MODULI)
    (diag,) = _codes(result)
    assert diag.level == "warning" and diag.where == [*MODULI, "phases.0.scale"]
    assert "this plan frees no moment" in diag.message.lower()
    assert "held at their start" in diag.message
    assert "Mn1_1 3.6 μ_B" in diag.message
    assert "magnetic_structural" in diag.suggestion
    assert "phases.*.atoms.*.moment.dof*" in diag.suggestion


@pytest.mark.parametrize("purpose", ["structure", "qpa", "magnetic"])
def test_the_held_moment_warns_under_every_purpose_the_shared_scale_reaches(arms, purpose):
    """The moment is read against the nuclear intensity through the scale the two
    share, so a caller fitting for structure or phase fractions hears it as a
    warning, not ``info`` (Yue's round 3, item 1)."""
    from rietx.schemas.results import level_under
    _, result = arms["mccusker_default"]
    (diag,) = _codes(result)
    assert level_under(diag, purpose) == "warning"


# ------------------------------------------------------------- the recovery

def test_the_preset_recovers_the_moment_and_every_biso(arms):
    ref, result = arms["magnetic_structural"]
    assert result.status == "converged"
    assert not _codes(result)
    rows = {p.path: p for p in result.parameters}
    m = rows[MODULI[0]]
    assert m.stderr is not None and abs(m.value - TRUE_M) <= 2 * m.stderr
    assert _moduli(ref) == pytest.approx([m.value, m.value], rel=1e-12)
    for i, atom in enumerate(ref.fitted_structure.phases[0].atoms):
        b = rows[f"phases.0.atoms.{i}.biso"]
        assert abs(b.value - TRUE_BISO[atom.species]) <= 2 * b.stderr, atom.label


def test_the_held_moment_is_the_one_mccusker_structural_spends_biso_on(arms):
    """Why the moment comes before the coordinates: held 20 % high, the O
    Biso has no support left (a flat direction: its esd is ~10^4 times the
    freed fit's, 772 against 0.057 Å² on macOS arm64) and its value is only
    where the solver stopped, so the claim is the esd, not the value."""
    held = {p.path: p for p in arms["mccusker_structural"][1].parameters}
    freed = {p.path: p for p in arms["magnetic_structural"][1].parameters}
    o = "phases.0.atoms.2.biso"
    assert freed[o].stderr is not None and held[o].stderr is not None
    assert held[o].stderr > 100 * freed[o].stderr
    assert abs(freed[o].value - TRUE_BISO["O"]) < 0.1


# ---------------------------------------------------------- the negative arms

def test_a_phase_without_a_moment_hears_nothing(data):
    nuclear = _start().model_copy(deep=True)
    for atom in nuclear.atoms:
        atom.moment = None
    nuclear.magnetic_symmetry = None
    _ref, result = _fit(data, "mccusker_structural", phase=nuclear)
    assert not _codes(result)


def test_a_moment_freed_in_any_stage_counts_as_freed(data):
    late = RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("moments", ["phases.*.atoms.*.moment.dof*"])])
    for plan in ("magnetic_width", late):
        _ref, result = _fit(data, plan)
        assert not _codes(result), plan


def test_a_moment_the_caller_holds_is_the_callers(data):
    _ref, result = _fit(data, "mccusker_default",
                        hold=["phases.*.atoms.*.moment.dof*"])
    assert not _codes(result)


# ----------------------------------------------------------------- the series

def test_the_series_hold_names_the_plan_as_the_cause():
    patterns = [_simulate(seed) for seed in (1, 2, 3)]

    def tie(_index, ref):
        _tie(ref)

    series = rx.refine_sequential(
        patterns, rx.Structure(phases=[_start()]), _instrument(),
        plan="mccusker_default", constrain=tie, x=[1.0, 2.0, 3.0])
    assert all(_codes(e) for e in series.entries)
    holds = [d for d in series.diagnostics if d.code == "SEQUENTIAL_MOMENT_HOLD"]
    assert [d.where for d in holds] == [[p] for p in MODULI]
    for d in holds:
        assert "because the plan frees no moment" in d.message
        assert "has no esd" not in d.message
