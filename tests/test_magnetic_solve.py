"""`solve_magnetic`: the determination workflow, its criterion and its abstentions.

M-9.  Everything here is **synthetic** — the pattern is simulated from a
structure this file states, so the answer is known and a wrong ranking is a
failure rather than a disagreement with a tutorial.  The one real-data arm the
tree carries data for, Cr₂WO₆ at 4 K and 150 K, is
``test_magnetic_solve_acceptance.py``.

The tests worth having are the ones a *plausible wrong* implementation fails,
so each block below turns on something specific:

* the k step takes the **forbidden-lattice-point** route when that bucket
  fires, and never scores that excess against a candidate vector — a k = 0
  signature fed to the candidate ranking is the first way this workflow goes
  quietly wrong;
* the ranking is **not** Rwp: a family with more amplitudes reaches a lower Rwp
  and must still lose when BIC charges it for them;
* one trial per **equivalence class**, not per candidate — the count of fits is
  the assertion, because a workflow that refines every member produces the same
  table with a different bill and no visible difference;
* a **tie is an abstention**, and the abstention names every member of it;
* the null test is a **gate**: a pattern with no magnetic intensity produces no
  winner, whatever ΔBIC says;
* a **non-neutron histogram is refused by name**;
* the magnetic-only R is computed over the channels the nuclear model puts
  nothing on and nowhere else, which is what makes it comparable between
  candidates;
* a class with **more than one magnetic site** is refined from every one-site
  start as well as the flat one, because the flat unit-magnitude seed can land
  in a minimum that is provably not the optimum, and a ranking taken at
  non-optimal points measures the seed;
* every glob the default stages free actually frees something — a ``Stage``
  entry matching nothing is accepted silently.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
import rietx.strategy.magnetic as _magnetic_module
from rietx.crystallography.magnetic.form_factor import assumed_lande_g
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.moments import SEED_TILT, tilted_seed, warm_seed
from rietx.crystallography.symmetry import (
    resolve_group,
    unnamed_label,
)
from rietx.report.schemas import MOMENT_SUPPORT_SIGMA
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    MOMENT_FLOOR_MU_B,
    Atom,
    Cell,
    MagneticSymmetry,
    Moment,
    Phase,
)
from rietx.strategy.magnetic import (
    SOLVE_TIE_DELTA_BIC,
    MagneticSolution,
    MagneticTrial,
    MomentRow,
    _descend,
    _maximal_subgroups,
    _rank,
    _tie_lattice_lines,
    magnetic_channels,
    r_magnetic,
)

LAMBDA_CW = 2.4
GRID = np.arange(8.0, 130.0, 0.05)
MN_SITE = (0.0, 0.0, 0.5)

#: The A-type arrangement's group for an orthorhombic perovskite at k = 0.
#: A *number*, checked against MAGNDATA #0.642 (Elemans, van Laar, van der Veen
#: & Loopstra, 1971, J. Solid State Chem. 3, 238) and never a vendored file.
A_TYPE_BNS = "62.448"


def _cell(a, b, c):
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def _atom(label, species, xyz, biso=0.4, moment=None):
    x, y, z = xyz
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                biso=Parameter(value=biso), moment=moment)


def perovskite(moment=None, magnetic=None) -> Phase:
    """An orthorhombic perovskite, Mn on 4b — the shape LaMnO₃ has.

    Every coordinate is a plausible round number typed here, not a published
    one: what the tests measure is the workflow, and a published structure
    would put a number in the repository that the run does not need.
    """
    return Phase(
        name="perovskite", space_group="P n m a", cell=_cell(5.74, 7.70, 5.54),
        atoms=[_atom("A1", "La", (0.05, 0.25, 0.99)),
               _atom("Mn1", "Mn", MN_SITE, moment=moment),
               _atom("O1", "O", (0.48, 0.25, 0.07)),
               _atom("O2", "O", (0.31, 0.04, 0.72))],
        magnetic_symmetry=magnetic)


def tetragonal(moment=None, magnetic=None) -> Phase:
    return Phase(
        name="tetragonal", space_group="P 4/m m m", cell=_cell(4.0, 4.0, 4.2),
        atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
               _atom("O1", "O", (0.5, 0.5, 0.5), biso=0.6)],
        magnetic_symmetry=magnetic)


def candidate_named(space_group, site, k, bns: str):
    for c in candidates(space_group, site, k):
        if c.bns_number == bns:
            return c
    raise AssertionError(f"{bns} is not in the candidate list at k = {k}")


def stated(phase_factory, candidate, moment, ion="Mn3+") -> Phase:
    ops, cent = candidate.group.xyz_strings()
    return phase_factory(
        moment=Moment.from_values(moment, ion),
        magnetic=MagneticSymmetry(operations=list(ops), centerings=list(cent)))


def simulate(phase, instrument, *, background=40.0, seed=20260906,
             window_area_tol=None):
    """A pattern from a stated structure, with Poisson-scale noise: drawn by
    ``predict``, at the closing stage's windows, or at ``window_area_tol``."""
    if window_area_tol is None:
        ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
        y = np.asarray(ref.predict(GRID)) + background
    else:
        from rietx.model.forward import compile_model
        from rietx.params.vector import ParameterTable

        structure = rx.Structure(phases=[phase])
        grid = rx.PatternData(two_theta=GRID.tolist(), intensity=[0.0] * len(GRID))
        model = compile_model(structure, instrument, grid, window_area_tol=window_area_tol)
        table = ParameterTable(structure, instrument)
        y = np.asarray(model.evaluate(table.decode(table.x0()))) + background
    rng = np.random.default_rng(seed)
    y = y + rng.normal(scale=np.sqrt(np.maximum(y, 1.0)))
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


NUCLEAR_PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
    rx.Stage("cell", ["phases.*.scale", "instrument.background.c*",
                      "phases.*.cell.*"])])


def neutron():
    return rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.35)


def nuclear_fit(phase, data, instrument):
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    ref.fit(data, plan=NUCLEAR_PLAN)
    return ref


@pytest.fixture(scope="module")
def a_type():
    """A converged nuclear fit to a pattern that *is* magnetic, and its truth."""
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    data = simulate(stated(perovskite, truth, (3.5, 0.0, 0.0)), instrument)
    return nuclear_fit(perovskite(), data, instrument), data, truth


@pytest.fixture(scope="module")
def a_type_solution(a_type):
    """``solve_magnetic`` on ``a_type`` with the default options, solved once.

    Every test below that reads the default answer shares it; a test that
    changes an option runs its own.  **Consumers carry**
    ``@pytest.mark.xdist_group("magnetic-solve-a-type")``, or each xdist
    worker refits the fixture and re-solves.
    """
    ref, data, _truth = a_type
    return rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")


@pytest.fixture(scope="module")
def paramagnetic():
    """The same specimen with no moment — the null arm, same everything else."""
    instrument = neutron()
    data = simulate(perovskite(), instrument)
    return nuclear_fit(perovskite(), data, instrument), data


# ============================================================ the positive arm

@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_the_published_arrangement_ranks_first_and_the_rivals_are_listed(a_type, a_type_solution):
    """The whole workflow, on a pattern whose answer this file stated.

    Four Γ-point candidates at Mn, four classes (Pnma is low enough that the
    powder separates every one of them — M-7 measured exactly this), and the
    arrangement the pattern was simulated from is first.  The others are
    *reported*, with their ΔBIC, rather than dropped: a determination stage
    publishes the ranked list whole.
    """
    ref, data, truth = a_type
    solution = a_type_solution

    assert solution.verdict == "solved", solution.reason
    assert solution.best is not None
    assert solution.best.bns_number == truth.bns_number
    assert len(solution.trials) == 4, [t.bns_number for t in solution.trials]
    assert {t.bns_number for t in solution.trials} == {
        "62.448", "62.447", "62.446", "62.441"}
    # every rival carries its own ΔBIC, and the winner's lead is decisive
    assert all(t.delta_bic is not None for t in solution.trials)
    assert (solution.best.delta_bic - solution.trials[1].delta_bic
            > SOLVE_TIE_DELTA_BIC)
    assert solution.tied == (solution.best.class_index,)
    assert solution.best.moments[0].magnitude == pytest.approx(3.5, abs=0.2)
    assert solution.best.moments[0].supported


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_the_k_step_takes_the_forbidden_lattice_point_route(a_type, a_type_solution):
    """A k = 0 signature is never scored against a candidate propagation vector.

    A magnetic space group generally drops the parent's glides and screws, so a
    k = 0 structure puts intensity where the *nuclear* structure factor is
    identically zero, and no nuclear model — right or wrong — can put any
    there.  That excess is the hypothesis; feeding it to the candidate ranking
    would rank a k against evidence that is not about it, which is the first
    way this workflow can go quietly wrong.
    """
    ref, data, _truth = a_type
    solution = a_type_solution
    assert solution.k_route == "forbidden lattice points"
    assert solution.k == ("0", "0", "0")
    assert solution.n_on_forbidden_lattice_points > 0
    # the k step's own sentence survives a solved verdict — it is a separate
    # field, because a determination has to be able to say how it got its k
    assert "systematic absence" in solution.k_reason
    # and the candidate list was not consulted for the choice
    assert "the candidate-k ranking is not consulted" in solution.k_reason
    assert solution.reason != solution.k_reason


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_the_worst_candidate_is_the_negative_control_inside_the_experiment(
        a_type, a_type_solution):
    """One of the four puts no intensity where the data has some.

    It leaves Rwp at the nuclear-only value, its modulus comes back below three
    of its own esds, and the null test therefore disqualifies it — which is the
    control the positive arm needs and it runs in the same call.
    """
    ref, data, _truth = a_type
    solution = a_type_solution
    worst = solution.trials[-1]
    assert not worst.supported, worst.moments
    assert worst.rwp == pytest.approx(solution.nuclear_rwp, rel=5e-3)
    assert worst.delta_bic < 0.0
    assert solution.best is not worst


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_the_magnetic_only_r_separates_the_models_where_rwp_barely_does(a_type, a_type_solution):
    """R_mag reads ≈1 for a model that explains none of the magnetic intensity.

    The nuclear reference is the scale: it puts nothing in that region by
    construction, so its R_mag is the "explains none of it" end and the
    winner's is near zero.  A whole-pattern Rwp cannot make that statement —
    the nuclear lines dominate it.
    """
    ref, data, _truth = a_type
    solution = a_type_solution
    assert solution.n_magnetic_channels > 0
    assert solution.nuclear_r_magnetic == pytest.approx(1.0, abs=0.35)
    assert solution.best.r_magnetic < 0.2
    assert solution.trials[-1].r_magnetic > 3 * solution.best.r_magnetic


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_one_magcif_per_class_and_nothing_written_unless_asked(a_type, a_type_solution, tmp_path):
    """WP-1328's writer, one file per class, and only on request."""
    ref, data, _truth = a_type
    solution = a_type_solution
    assert not list(tmp_path.iterdir())
    written = solution.write_magcifs(tmp_path / "out")
    assert len(written) == sum(1 for t in solution.trials
                               if t.status == "refined")
    text = (tmp_path / "out" / Path(written[0]).name).read_text(
        encoding="utf-8")
    assert "_space_group_symop_magn_operation.xyz" in text
    assert "_atom_site_moment.crystalaxis_x" in text


# ================================================== one trial per class, not member

@pytest.mark.slow
def test_a_class_the_powder_cannot_separate_is_refined_once_and_named():
    """Three candidates, one class, one fit — and the members are in the answer.

    At k = (0,0,½) in P4/mmm three of the four candidates come back
    powder-equivalent (M-7's Shirane machinery), so the workflow refines the
    smallest of them and *names* the other two.  A workflow that refined every
    member would produce the same table at three times the cost and would let a
    reader rank models the data cannot separate.
    """
    instrument = neutron()
    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]
    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    statement = magnetic_supercell(tetragonal(), truth,
                                   magnetic_species=["Mn1"],
                                   ion={"Mn1": "Mn3+"}, magnitude=3.0)
    data = simulate(statement.phase, instrument)
    ref = nuclear_fit(tetragonal(), data, instrument)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")

    assert solution.k == ("0", "0", "1/2")
    assert len(solution.trials) == 2, [t.members for t in solution.trials]
    sizes = sorted(len(t.members) for t in solution.trials)
    assert sizes == [1, 3], sizes
    # the class of three names all three, and its representative is the
    # smallest family in it
    big = next(t for t in solution.trials if len(t.members) == 3)
    assert big.free_amplitudes == 1, big.free_amplitudes
    assert solution.verdict == "solved"
    assert solution.best.bns_number == truth.bns_number
    # the anti-centring was a constraint, not only a seed
    assert solution.best.anti_translation_drift == pytest.approx(0.0, abs=1e-8)


# ============================================================== the abstentions

def _trial(index, *, delta_bic, r_mag, free, bns="1.1", supported=True):
    return MagneticTrial(
        class_index=index, representative=f"S{index}(a)",
        members=(f"{bns} S{index}(a)",), site="Mn1", irrep=f"S{index}",
        direction="(a)", bns_number=bns, uni_number=None, msg_type=1,
        free_amplitudes=free, determinable_amplitudes=1, status="refined",
        rwp=0.1, gof=1.0, delta_bic=delta_bic, r_magnetic=r_mag,
        n_moment_parameters=free, n_free_parameters=free + 5,
        moments=(MomentRow(label="Mn1", ion="Mn3+", magnitude=3.0,
                           esd=0.1 if supported else 30.0,
                           crystalaxis=(3.0, 0.0, 0.0), supported=supported),))


def test_a_constructed_tie_is_an_abstention_that_names_both_classes():
    """The rule the whole workflow exists to obey.

    Two classes with ΔBIC inside the stated width, the same magnetic-only R and
    the same amplitude count: nothing separates them, so the verdict is an
    abstention that names both.  Reporting the arithmetically-larger ΔBIC as a
    winner is the confident wrong singleton (WP-1043) — and at this separation
    the difference is not evidence.
    """
    a = _trial(0, delta_bic=120.0, r_mag=0.11, free=1)
    b = _trial(1, delta_bic=120.0 - 0.5 * SOLVE_TIE_DELTA_BIC, r_mag=0.11,
               free=1, bns="2.2")
    ordered, tied, verdict, reason = _rank([a, b], SOLVE_TIE_DELTA_BIC)

    assert verdict == "abstained"
    assert set(tied) == {0, 1}
    assert "class 0" in reason and "class 1" in reason
    assert "1.1" in reason and "2.2" in reason
    assert len(ordered) == 2


def test_the_magnetic_only_r_does_not_break_a_dbic_tie():
    """A ΔBIC tie stays a tie whatever R_mag says (WP-2002, B12).

    Until 1.10 an R_mag gap of more than 2 % chose class 1 here, a margin
    nobody had measured.  The classes now abstain together, and the reason
    gives each one's R_mag for the reader to weigh.
    """
    a = _trial(0, delta_bic=120.0, r_mag=0.40, free=1)
    b = _trial(1, delta_bic=118.0, r_mag=0.11, free=1, bns="2.2")
    _o, tied, verdict, reason = _rank([a, b], SOLVE_TIE_DELTA_BIC)
    assert verdict == "abstained" and set(tied) == {0, 1}
    assert "R_mag 0.400" in reason and "R_mag 0.110" in reason
    assert "nor R_mag ranks them" in reason


def test_a_dbic_tie_abstains_and_lists_the_simplest_class_first():
    """Fewer moment parameters orders a tie and never breaks it: the ΔBIC
    already charges each one (WP-2002, ruled 2026-10-20)."""
    a = _trial(0, delta_bic=120.0, r_mag=0.11, free=3)
    b = _trial(1, delta_bic=119.0, r_mag=0.11, free=1, bns="2.2")
    ordered, tied, verdict, reason = _rank([a, b], SOLVE_TIE_DELTA_BIC)
    assert verdict == "abstained" and tied == (1, 0)
    assert ordered[0] is b
    assert "fewest moment parameters first" in reason


def test_an_unsupported_moment_cannot_win_however_good_its_dbic():
    """The null test is a gate, not a column.

    A trial whose modulus is below three of its own esds is what an
    unmagnetised pattern looks like under a magnetic model, and a large ΔBIC
    there is the criterion being fooled by extra freedom rather than evidence.
    """
    a = _trial(0, delta_bic=5000.0, r_mag=0.01, free=3, supported=False)
    _o, tied, verdict, reason = _rank([a], SOLVE_TIE_DELTA_BIC)
    assert verdict == "nothing to solve"
    assert tied == ()
    assert "not one came back with a supported moment" in reason
    # and the reason is true of the state it reports: this trial *refined*, so
    # it must not be described as one that could not be stated
    assert "could not be stated" not in reason


def test_candidates_that_could_not_be_stated_are_not_called_a_null_result():
    """A refusal never had a modulus to test, so the null test cannot have failed.

    The two states reach the same "no winner" and mean opposite things: one is
    an answer about the specimen, the other is the workflow saying it could not
    ask the question. Reporting the first when the second happened is a
    diagnostic that is true of an intermediate state and false of the reported
    one, and it is what the Cr₂WO₆ 150 K arm produced before this branch
    existed.
    """
    refused = MagneticTrial(
        class_index=0, representative="S1(a)", members=("1.1 S1(a)",),
        site="Mn1", irrep="S1", direction="(a)", bns_number="1.1",
        uni_number=None, msg_type=1, free_amplitudes=1,
        determinable_amplitudes=0, status="refused",
        refusal="ValueError: the child cell carries no symbol")
    _o, tied, verdict, reason = _rank([refused], SOLVE_TIE_DELTA_BIC)
    assert verdict == "abstained"
    assert tied == ()
    assert "could be stated as a refinable model" in reason
    assert "not a result about the specimen" in reason
    assert "null test" not in reason and "modulus" not in reason


@pytest.mark.slow
def test_a_pattern_with_no_unexplained_intensity_says_there_is_nothing_to_solve(
        paramagnetic):
    """The 150 K arm of a two-temperature acceptance, synthetically.

    Not a refusal and not an error: the nuclear model accounts for the pattern,
    so the workflow says so and names the counts it read.
    """
    ref, data = paramagnetic
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert solution.verdict == "nothing to solve", solution.reason
    assert solution.trials == ()
    assert solution.best is None
    assert solution.n_on_forbidden_lattice_points == 0
    assert solution.n_unexplained == 0
    assert "no magnetic intensity to model" in solution.reason


# ================================================================ the refusals

@pytest.mark.slow
def test_an_xray_histogram_is_refused_by_name():
    """A satellite on an X-ray pattern is a superstructure reflection.

    The positions are the same and the inference is not; a moment refined
    against X-rays has no gradient anywhere, so the workflow declines rather
    than producing a table of models fitted to nothing.
    """
    instrument = rx.Instrument.debye_scherrer(1.5406)
    data = simulate(perovskite(), instrument, background=200.0)
    ref = nuclear_fit(perovskite(), data, instrument)
    with pytest.raises(ValueError, match="neutron histogram and nothing else"):
        rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")


def test_a_phase_that_already_states_a_magnetic_group_is_refused():
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    phase = stated(perovskite, truth, (3.5, 0.0, 0.0))
    data = simulate(phase, instrument)
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"])]))
    with pytest.raises(ValueError, match="already declares a magnetic space"):
        rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")


def test_a_site_with_no_tabulated_form_factor_is_refused_with_the_keys_there_are():
    instrument = neutron()
    data = simulate(perovskite(), instrument)
    ref = nuclear_fit(perovskite(), data, instrument)
    with pytest.raises(ValueError, match="not a magnetic form-factor key"):
        rx.solve_magnetic(ref, data, sites=["O1"])


def test_calling_before_a_fit_is_refused():
    instrument = neutron()
    data = simulate(perovskite(), instrument)
    ref = rx.Refinement(rx.Structure(phases=[perovskite()]), instrument)
    with pytest.raises(RuntimeError, match="call fit\\(\\) on the nuclear model"):
        rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")


# ================================================= the magnetic-only region itself

@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_the_magnetic_region_is_built_from_peaks_no_tick_explains(a_type):
    """Bucket 1 is out, and it is out on purpose.

    A residual peak sitting on a calculated reflection is a nuclear misfit or a
    k = 0 structure and this route cannot separate them, so scoring a magnetic
    model there would reward a candidate for absorbing somebody else's error.

    The property is about the **peaks the region is built from**, not about
    every channel of it: a window is a peak's own validity radius wide, so a
    channel at the edge of an included peak's window may sit closer to a tick
    than the peak does. Asserting on the channels instead is what a first
    version of this test did, and it failed for that reason rather than for a
    defect. So: every residual peak the region covers is more than its own
    radius from the nearest tick, and the region is a strict subset of what an
    unsorted "all residual peaks" region would have been.
    """
    from rietx.params.vector import ParameterTable
    from rietx.report import _resid_norm
    from rietx.report.layer0 import residual_peak_indices
    from rietx.report.schemas import VALIDITY_RADIUS_FWHM
    from rietx.strategy.magnetic import _peak_positions_and_widths

    ref, _data, _truth = a_type
    table = ParameterTable(ref.structure, ref.instrument)
    values = table.decode(table.x0())
    mask = magnetic_channels(ref._model, values, ref.result_)
    assert mask.any()

    tt = np.asarray(ref.result_.two_theta)
    ticks = np.asarray([t for p in ref.result_.ticks.values() for t in p])
    peaks = tt[residual_peak_indices(_resid_norm(ref.result_),
                                     min_peak_sigma=5.0)]
    pos, fwhm = _peak_positions_and_widths(ref._model, values)
    radius = VALIDITY_RADIUS_FWHM * fwhm[
        np.argmin(np.abs(peaks[:, None] - pos[None, :]), axis=1)]
    to_tick = np.min(np.abs(peaks[:, None] - ticks[None, :]), axis=1)

    covered = np.array([bool(mask[np.argmin(np.abs(tt - p))]) for p in peaks])
    # a peak inside the region is one no tick explains, and every peak a tick
    # does explain is outside it
    assert np.all(to_tick[covered] > radius[covered])
    # and the exclusion is exactly the tick test, not something looser
    assert np.all(to_tick[~covered] <= radius[~covered])
    assert covered.sum() < len(peaks), "no peak was excluded — bucket 1 empty?"


def test_an_empty_region_reports_none_rather_than_a_zero():
    """The honest empty state: no channels means no number, never R = 0."""

    class _Result:
        y_obs = [1.0, 2.0]
        y_calc = [1.0, 2.0]
        y_background = [1.0, 2.0]

    assert r_magnetic(_Result(), np.zeros(2, dtype=bool)) is None
    assert r_magnetic(_Result(), np.ones(2, dtype=bool)) is None


# ============================== the multi-site sweep, and dead free-list entries

def two_site(m1=None, m2=None, magnetic=None) -> Phase:
    """The same parent with a moment on **two** sites, which is where the sweep bites."""
    return Phase(
        name="two-site", space_group="P n m a", cell=_cell(5.74, 7.70, 5.54),
        atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.5), moment=m1),
               _atom("Mn2", "Mn", (0.0, 0.0, 0.0), moment=m2),
               _atom("O1", "O", (0.48, 0.25, 0.07)),
               _atom("O2", "O", (0.31, 0.04, 0.72))],
        magnetic_symmetry=magnetic)


@pytest.mark.slow
def test_a_class_with_two_magnetic_sites_is_started_from_every_one_of_them():
    """The flat seed is not enough, and the answer records how many were tried.

    A moment stage over several sites is not convex.  Measured on Ba₆Co₆ with a
    nuclear model as complete as the GSAS-II tutorial's: the three-amplitude fit
    from a flat unit-magnitude seed reaches Rwp 0.08952 while its own
    **one-amplitude submodel** reaches 0.08867 — a superset model cannot fit
    worse than its own submodel at the true minimum, so the flat start was not
    at one.  Released from the one-site solution the same model reaches 0.08752
    with the moment on the other site, which is the published answer.

    A ranking taken at such points measures the seed, not the model, so the
    workflow sweeps one start per site plus the flat one and keeps the best.
    `MagneticTrial.n_starts` and `MagneticTrial.n_minima` are that sweep made
    visible; more than one minimum is a fact about the candidate, and it is a
    caveat on the answer rather than something the run hides.
    """
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    ops, cent = truth.group.xyz_strings()
    data = simulate(two_site(
        m1=Moment.from_values((3.5, 0.0, 0.0), "Mn3+"),
        m2=Moment.from_values((0.7, 0.0, 0.0), "Mn3+"),
        magnetic=MagneticSymmetry(operations=list(ops),
                                  centerings=list(cent))), instrument)
    ref = nuclear_fit(two_site(), data, instrument)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1", "Mn2"], ion="Mn3+")

    winner = solution.trials[0]
    # flat + one per site
    assert winner.n_starts == 3, winner.n_starts
    assert winner.start in ("flat", "Mn1 only, then released",
                            "Mn2 only, then released")
    assert winner.n_minima >= 1
    # a multimodal class says so in the answer, not only in a log
    multimodal = [t for t in solution.trials if (t.n_minima or 0) > 1]
    if multimodal:
        assert any(f"class {t.class_index}" in c and "distinct minima" in c
                   for t in multimodal for c in solution.caveats)
    # and the sweep did not cost correctness: the stated arrangement still wins
    assert solution.verdict == "solved", solution.reason
    assert winner.bns_number == A_TYPE_BNS


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_a_single_site_class_is_started_once(a_type, a_type_solution):
    """Nothing to hold out, so no sweep and no extra fits."""
    ref, data, _truth = a_type
    solution = a_type_solution
    assert all(t.n_starts == 1 for t in solution.trials
               if t.status == "refined")
    assert all(t.start == "flat" for t in solution.trials
               if t.status == "refined")


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_the_default_stages_free_nothing_dead(a_type, a_type_solution):
    """A `Stage` entry that matches no parameter is accepted **silently**.

    In a *ranking* a dead entry is worse than a wasted line — it makes the
    models that were compared differ from the ones the plan describes — so the
    workflow reports any glob that froze nothing.
    """
    ref, data, _truth = a_type
    solution = a_type_solution
    assert not [c for c in solution.caveats if "freed no parameter" in c], \
        [c for c in solution.caveats if "freed no parameter" in c]


def test_a_dead_glob_is_detected_and_a_live_one_is_not():
    """`_dead_globs` reads what the fit *froze*, not what the table holds.

    Reading the parameter table would miss exactly the case that matters: a
    path can exist in the table and still never be freed, so "the path exists"
    is not the question. What was actually freed is.
    """
    from rietx.strategy.magnetic import _dead_globs

    class _P:
        def __init__(self, path, vary):
            self.path, self.vary = path, vary

    class _R:
        parameters = [_P("phases.0.scale", True),
                      _P("phases.0.atoms.0.moment.dof0", True),
                      _P("phases.0.lor_size", False)]

    plan = rx.RefinementPlan(stages=[
        rx.Stage("s", ["phases.*.scale", "phases.*.lor_size",
                       "instrument.nonesuch"])])
    dead = _dead_globs(plan, _R())
    assert set(dead) == {"phases.*.lor_size", "instrument.nonesuch"}


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_widening_the_tie_hands_the_decision_to_the_next_key_and_says_so(a_type, a_type_solution):
    """When ΔBIC stops separating, the reason names whichever key did decide.

    The abstention rule itself is pinned by the constructed-tie unit tests
    above; this is the end-to-end half, and what it catches is subtler than a
    missing abstention — a workflow that keeps the ΔBIC leader while quietly
    reporting the tie. Widen the width past the real ΔBIC spread and the
    leader must stop being chosen *for that reason*, and since nothing below
    ΔBIC breaks a tie (WP-2002, 2026-10-20) the verdict is an abstention with
    the tied classes listed fewest moment parameters first.

    **Why a real tie is rare here, and that is by design.** Two models a powder
    cannot separate are merged into one class before anything is ranked, so the
    ties the class machinery would otherwise produce never reach the ranking.
    That is why the exact-tie case is constructed rather than found.
    """
    ref, data, _truth = a_type
    solved = a_type_solution
    assert solved.verdict == "solved"
    assert "leads on ΔBIC" in solved.reason
    spread = solved.trials[0].delta_bic - solved.trials[-1].delta_bic

    widened = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+",
                                tie_width=spread * 1.5)
    assert "leads on ΔBIC" not in widened.reason, widened.reason
    assert f"tie width of {spread * 1.5:.1f}" in widened.reason
    assert widened.verdict == "abstained"
    assert len(widened.tied) >= 2
    assert widened.best is None
    for index in widened.tied:
        assert f"class {index}" in widened.reason
    counts = [t.n_moment_parameters for t in widened.trials[:len(widened.tied)]]
    assert counts == sorted(counts), counts


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_a_widened_tie_of_equally_free_classes_is_an_abstention(a_type, a_type_solution):
    """With ΔBIC widened out nothing ranks: the magnetic-only R since WP-2002,
    B12, and the moment-parameter count since 2026-10-20.  Classes with the
    same count are a genuine abstention naming every one of them."""
    ref, data, _truth = a_type
    solved = a_type_solution
    spread = solved.trials[0].delta_bic - solved.trials[-1].delta_bic
    equal = [t for t in solved.trials
             if t.n_moment_parameters == solved.trials[0].n_moment_parameters]
    assert len(equal) >= 2, "the fixture no longer has two equally free classes"

    widened = rx.solve_magnetic(
        ref, data, sites=["Mn1"], ion="Mn3+",
        tie_width=spread * 1.5,
        # only the classes with the same free moment count
        top_k=1)
    assert widened.verdict == "abstained"
    assert len(widened.tied) >= 2
    for index in widened.tied:
        assert f"class {index}" in widened.reason
    assert "does not choose between them" in widened.reason


# ============================================================ the g/ion plumbing
#
# solve_magnetic's own candidate builder used to construct every trial Phase
# with no g and no ion-inference at all, so a 4f/5f site abstained on every
# candidate class regardless of what structure_from_cif's own g/ion defaults
# would have done for it (WP-1327; found on a MAGNDATA sweep, where most
# 4f/5f entries abstained this way).  These tests are the positive arm (both
# the direct ion-in-species shape the sweep measured, and the bare-element resolve_assumed_ion fallback
# the CIF reader already had) and the negative controls: a caller-stated ion
# still needs an explicit g (issue #257 A5, carried over unchanged), a
# caller-stated g always wins, and a 3d ion's behaviour never moves.

def perovskite_re(species="Dy3+", moment=None, magnetic=None) -> Phase:
    """A rare-earth analogue of :func:`perovskite`: same cell and site, the
    transition-metal species swapped for a lanthanide — a synthetic
    substitution, not a claim about a real Dy compound, exactly as the
    lande-g-default and magnetic-ion-default fixtures swap LaMnO3's Mn for a
    bare Dy."""
    return Phase(
        name="perovskite_re", space_group="P n m a", cell=_cell(5.74, 7.70, 5.54),
        atoms=[_atom("A1", "La", (0.05, 0.25, 0.99)),
               _atom("RE1", species, MN_SITE, moment=moment),
               _atom("O1", "O", (0.48, 0.25, 0.07)),
               _atom("O2", "O", (0.31, 0.04, 0.72))],
        magnetic_symmetry=magnetic)


def stated_re(nuclear_species, moment_ion, candidate, moment, g) -> Phase:
    """``perovskite_re`` stated with a magnetic moment, for simulation only.

    ``nuclear_species`` is the *nuclear* ``Atom.species`` solve_magnetic will
    see on the fitted structure (charged, ``"Dy3+"``, or bare, ``"Dy"``, per
    the two shapes the sweep found); ``moment_ion``/``g`` are the real magnetic
    form-factor key and Landé g the simulated pattern is generated from —
    always the resolved ion, since a bare nuclear species is a nuclear-only
    fact and the moment needs a real ⟨j0⟩/⟨j2⟩ row regardless of it.
    """
    ops, cent = candidate.group.xyz_strings()
    return perovskite_re(
        species=nuclear_species,
        moment=Moment.from_values(moment, moment_ion, g=g),
        magnetic=MagneticSymmetry(operations=list(ops), centerings=list(cent)))


DY_G = assumed_lande_g("Dy3+")  # Hund's rule, 4f9 6H15/2: g_J = 4/3


@pytest.fixture(scope="module")
def dy_charged_type():
    """A 4f site whose nuclear species already states its charge (``"Dy3+"``)
    — the shape most of the sweep's g-abstentions took: the
    ion needs no ``resolve_assumed_ion`` fallback at all, only a Landé g."""
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    data = simulate(
        stated_re("Dy3+", "Dy3+", truth, (3.5, 0.0, 0.0), DY_G), instrument)
    return nuclear_fit(perovskite_re(species="Dy3+"), data, instrument), data, truth


@pytest.fixture(scope="module")
def dy_bare_element():
    """A 4f site whose nuclear species is the bare element (``"Dy"``, no
    neutral-atom ⟨j0⟩ row at all) — needs both the ``resolve_assumed_ion``
    fallback and the Landé g default."""
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    data = simulate(
        stated_re("Dy", "Dy3+", truth, (3.5, 0.0, 0.0), DY_G), instrument)
    return nuclear_fit(perovskite_re(species="Dy"), data, instrument), data, truth


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-dy-charged")
def test_a_charged_rare_earth_species_defaults_g_and_recovers_the_moment(
        dy_charged_type):
    """The sweep's majority shape: the nuclear species already names the ion
    and only the Landé g is missing — and it was not the caller who named
    that ion, so the g default fires (issue #257 A5's exemption does not
    apply to an ion nobody but the structure itself stated)."""
    ref, data, truth = dy_charged_type
    solution = rx.solve_magnetic(ref, data)

    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number
    assert solution.best.moments[0].ion == "Dy3+"
    assert solution.best.moments[0].magnitude == pytest.approx(3.5, abs=0.4)
    # review of #592, item 7: the species already carries its charge, so the
    # "neutral-atom form factor was used" caveat is false of this run
    assert not any("neutral-atom" in c for c in solution.caveats), solution.caveats
    codes = {d.code for d in solution.diagnostics}
    assert "LANDE_G_ASSUMED" in codes
    assert "MAGNETIC_ION_ASSUMED" not in codes  # the ion was already stated
    lande = next(d for d in solution.diagnostics if d.code == "LANDE_G_ASSUMED")
    assert lande.value == pytest.approx(DY_G)
    assert "Dy1" not in lande.message  # the label is RE1, not a stale copy


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-dy-bare")
def test_a_bare_rare_earth_element_resolves_through_the_cif_readers_own_fallback(
        dy_bare_element):
    """The sweep's second shape: a bare 4f element with no neutral-atom row
    at all resolves through the same ``resolve_assumed_ion`` the CIF reader
    already applies at read, and its Landé g defaults alongside it."""
    ref, data, truth = dy_bare_element
    solution = rx.solve_magnetic(ref, data)

    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number
    assert solution.best.moments[0].ion == "Dy3+"
    codes = {d.code for d in solution.diagnostics}
    assert {"MAGNETIC_ION_ASSUMED", "LANDE_G_ASSUMED"} <= codes
    ion_diag = next(d for d in solution.diagnostics if d.code == "MAGNETIC_ION_ASSUMED")
    assert "Dy3+" in ion_diag.message
    assert "moment_ions" not in ion_diag.message  # solve_magnetic's own route
    assert "ion={'RE1'" in ion_diag.suggestion.replace('"', "'")


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-dy-charged")
def test_a_caller_stated_ion_still_needs_an_explicit_g_issue_257_a5(dy_charged_type):
    """A caller who names the ion explicitly gets the pre-existing refusal,
    unchanged: the g default is only for an ion this call inferred itself
    (from the table or from ``resolve_assumed_ion``), never for one the
    caller stated — mirroring issue #257 A5's rule for
    ``structure_from_cif``'s ``moment_ions=``.  Every candidate class fails
    to build (the g requirement is a validation error, not a raise from this
    function), so the verdict is a workflow abstention naming why, exactly
    the sweep's own measured shape."""
    ref, data, _truth = dy_charged_type
    solution = rx.solve_magnetic(ref, data, sites=["RE1"], ion="Dy3+")

    assert solution.verdict == "abstained"
    assert "Landé g factor" in solution.reason, solution.reason
    assert all(t.status == "refused" and "4f/5f ion" in (t.refusal or "")
              for t in solution.trials)
    # review of #592, item 8: nothing was fitted, so nothing is reported as if
    # it had been (one start, one minimum, a flat start, zero free parameters,
    # "the powder determines none")
    for t in solution.trials:
        assert (t.determinable_amplitudes, t.n_starts, t.n_minima, t.start,
                t.n_moment_parameters, t.n_free_parameters,
                t.fit_status, t.reference_status) == (None,) * 8
    codes = {d.code for d in solution.diagnostics}
    assert "LANDE_G_ASSUMED" not in codes


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-dy-charged")
def test_a_caller_stated_g_wins_over_the_hunds_rule_default(dy_charged_type):
    """A caller-passed ``g=`` always wins, even when it differs from the
    Hund's-rule default — the same "caller wins" rule ``ion=`` already had."""
    ref, data, _truth = dy_charged_type
    off_g = DY_G + 0.2
    solution = rx.solve_magnetic(ref, data, g=off_g)

    assert solution.verdict == "solved", solution.reason
    codes = {d.code for d in solution.diagnostics}
    assert "LANDE_G_ASSUMED" not in codes  # the caller stated it; not defaulted
    assert solution.best is not None


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-a-type")
def test_a_3d_ion_never_sees_the_g_default_bit_identical(a_type, a_type_solution):
    """Bit-identity for every non-4f/5f case: the g/ion plumbing above
    added must never fire a diagnostic, or change a result, for the existing
    Mn3+ fixture every other test in this file already exercises."""
    ref, data, _truth = a_type
    solution = a_type_solution
    codes = {d.code for d in solution.diagnostics}
    assert "LANDE_G_ASSUMED" not in codes
    assert "MAGNETIC_ION_ASSUMED" not in codes


@pytest.mark.slow
def test_the_g_default_also_threads_through_the_k_nonzero_supercell_route():
    """The k = 0 route (``_state_k0``) and the k ≠ 0 route
    (``magnetic_supercell``) are two different code paths threading g into
    the candidate's ``Moment`` — this exercises the second one, mirroring
    ``test_a_class_the_powder_cannot_separate_is_refined_once_and_named``'s
    own P4/mmm, k = (0,0,½) fixture with the site's ion swapped for a bare
    4f element."""
    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    instrument = neutron()
    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]

    def dy_tetragonal(species="Dy", moment=None, magnetic=None) -> Phase:
        return Phase(
            name="tetragonal_re", space_group="P 4/m m m", cell=_cell(4.0, 4.0, 4.2),
            atoms=[_atom("RE1", species, (0.0, 0.0, 0.0), moment=moment),
                   _atom("O1", "O", (0.5, 0.5, 0.5), biso=0.6)],
            magnetic_symmetry=magnetic)

    statement = magnetic_supercell(dy_tetragonal(species="Dy3+"), truth,
                                   magnetic_species=["RE1"], ion={"RE1": "Dy3+"},
                                   g=DY_G, magnitude=3.0)
    data = simulate(statement.phase, instrument)
    ref = nuclear_fit(dy_tetragonal(species="Dy"), data, instrument)
    solution = rx.solve_magnetic(ref, data)

    assert solution.k == ("0", "0", "1/2")
    assert solution.verdict == "solved", solution.reason
    codes = {d.code for d in solution.diagnostics}
    assert {"MAGNETIC_ION_ASSUMED", "LANDE_G_ASSUMED"} <= codes


# ======================================================== the unnamed parent
#
# solve_magnetic used to refuse outright whenever the nuclear parent's group
# was a bracketed, unnamed label — "no Hermann-Mauguin symbol generates this
# group in its cell" — on the stated grounds that the small representations
# of a k-vector come from tables keyed on the space-group *number*, and an
# operator list has none.  That reasoning does not hold for this engine (M-6,
# WP-1418: every small irrep is built from the little group's own
# operators, projectively, with no tabulated-number lookup anywhere in
# ``crystallography.representation.irreps``/``crystallography.magnetic.isotropy``), so the parent's group is
# now resolved from its operators via the same ``OperatorGroup``
# ``Phase.symmetry_operations`` uses everywhere else, and threaded through
# instead of refusing before either candidate enumeration or the k ≠ 0
# supercell statement is tried.

#: Pnma's own tabulated operator list (gemmi), carried under a bracketed
#: label as if no symbol named it — a synthetic non-standard-setting stand-in
#: (the same shape as the magCIF reader's synthetic Ima2 fixture):
#: the mechanism under test is "an explicit operator list with no resolvable
#: symbol", and this operator list is real Pnma, independently checked back
#: to it by ``resolve_group(...).operations()`` matching gemmi's own table.
def _pnma_operations() -> tuple[str, ...]:
    import gemmi

    return tuple(op.triplet() for op in
                gemmi.find_spacegroup_by_name("P n m a").operations())


UNNAMED_PNMA = unnamed_label("P n m a", "unnamed for a synthetic test")


def perovskite_unnamed(moment=None, magnetic=None) -> Phase:
    """``perovskite()``, restated with its own operators under a bracketed,
    unnamed label — the WP-1328 escape-hatch shape ``structure_from_cif``
    already writes for a real setting mismatch, built synthetically here."""
    return Phase(
        name="perovskite_unnamed", space_group=UNNAMED_PNMA,
        symmetry_operations=list(_pnma_operations()),
        cell=_cell(5.74, 7.70, 5.54),
        atoms=[_atom("A1", "La", (0.05, 0.25, 0.99)),
               _atom("Mn1", "Mn", MN_SITE, moment=moment),
               _atom("O1", "O", (0.48, 0.25, 0.07)),
               _atom("O2", "O", (0.31, 0.04, 0.72))],
        magnetic_symmetry=magnetic)


@pytest.fixture(scope="module")
def a_type_unnamed_parent():
    """``a_type``'s own A-type Pnma structure, with the nuclear parent stated
    as an unnamed operator list instead of the symbol ``"P n m a"``."""
    instrument = neutron()
    parent_group = resolve_group(UNNAMED_PNMA, _pnma_operations())
    truth = candidate_named(parent_group, MN_SITE, (0, 0, 0), A_TYPE_BNS)
    ops, cent = truth.group.xyz_strings()
    truth_phase = perovskite_unnamed(
        moment=Moment.from_values((3.5, 0.0, 0.0), "Mn3+"),
        magnetic=MagneticSymmetry(operations=list(ops), centerings=list(cent)))
    data = simulate(truth_phase, instrument)
    return nuclear_fit(perovskite_unnamed(), data, instrument), data, truth


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-unnamed")
def test_an_unnamed_bracketed_parent_still_enumerates_and_recovers(
        a_type_unnamed_parent):
    """The positive arm: candidate enumeration, the k = 0 statement and the
    ranking all still work when the parent's group is a bracketed, unnamed
    operator list rather than a symbol gemmi resolves."""
    ref, data, truth = a_type_unnamed_parent
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")

    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number
    assert solution.best.moments[0].magnitude == pytest.approx(3.5, abs=0.4)
    assert solution.space_group == UNNAMED_PNMA


@pytest.mark.slow
def test_an_unnamed_parent_also_threads_through_the_k_nonzero_supercell_route():
    """The k ≠ 0 route (``magnetic_supercell``) had its *own* copy of the same
    refusal — this exercises that second call site, mirroring
    ``test_a_class_the_powder_cannot_separate_is_refined_once_and_named``'s
    P4/mmm, k = (0,0,½) fixture with the parent's group stated as an unnamed
    operator list."""
    import gemmi

    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    instrument = neutron()
    ops = tuple(op.triplet() for op in
               gemmi.find_spacegroup_by_name("P 4/m m m").operations())
    label = unnamed_label("P 4/m m m", "unnamed for a synthetic test")
    parent_group = resolve_group(label, ops)
    truth = candidates(parent_group, (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]

    def tetragonal_unnamed(moment=None, magnetic=None) -> Phase:
        return Phase(
            name="tetragonal_unnamed", space_group=label,
            symmetry_operations=list(ops), cell=_cell(4.0, 4.0, 4.2),
            atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
                   _atom("O1", "O", (0.5, 0.5, 0.5), biso=0.6)],
            magnetic_symmetry=magnetic)

    statement = magnetic_supercell(tetragonal_unnamed(), truth,
                                   magnetic_species=["Mn1"], ion={"Mn1": "Mn3+"},
                                   magnitude=3.0)
    data = simulate(statement.phase, instrument)
    ref = nuclear_fit(tetragonal_unnamed(), data, instrument)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")

    assert solution.k == ("0", "0", "1/2")
    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number


# =========================================================================
# Issue #390: the two negative-margin sweep entries (the margin); a kernel/
# general-direction candidate's seed (the tilt); the descent audit after
# selection; the group-subgroup lattice among near-ties.
# =========================================================================

def _solution(trials, tied, verdict, why, tie_width=SOLVE_TIE_DELTA_BIC):
    """The minimum ``MagneticSolution`` a ``_rank`` output needs to exercise
    ``.margin``/``__str__`` without running the whole ``solve_magnetic`` chain."""
    return MagneticSolution(
        verdict=verdict, reason=why, criterion="test", phase="p",
        space_group="P 1", k=("0", "0", "0"), k_route="given by the caller",
        k_reason="test", k_candidates=(), sites=("Mn1",),
        n_residual_peaks=0, n_on_nuclear_lines=0,
        n_on_forbidden_lattice_points=0, n_unexplained=0,
        trials=trials, tied=tied, tie_width=tie_width, d_min=1.5,
        nuclear_rwp=None, nuclear_gof=None, nuclear_r_magnetic=None,
        n_magnetic_channels=0)


# ---------------------------------------------------------------- margin --

def test_margin_is_the_true_gap_between_two_eligible_classes():
    winner = _trial(0, delta_bic=200.0, r_mag=0.1, free=2, bns="1.1")
    runner_up = _trial(1, delta_bic=140.0, r_mag=0.2, free=1, bns="1.2")
    ordered, tied, verdict, why = _rank((winner, runner_up), SOLVE_TIE_DELTA_BIC)
    assert _solution(ordered, tied, verdict, why).margin == pytest.approx(60.0)


def test_a_tie_reports_the_dbic_leaders_nuclear_reference():
    """The tie lists the simplest class first, and the reported nuclear numbers
    stay the ΔBIC leader's, as before that order (WP-2002 code review)."""
    from rietx.strategy.magnetic import _reported_reference

    a = _trial(0, delta_bic=120.0, r_mag=0.11, free=3)
    b = _trial(1, delta_bic=119.0, r_mag=0.11, free=1, bns="2.2")
    ordered, tied, verdict, _why = _rank([a, b], SOLVE_TIE_DELTA_BIC)
    assert verdict == "abstained" and ordered[0] is b
    kk = (0, 0, 0)
    refs = {(kk, 0): "leader's", (kk, 1): "simplest's"}
    assert _reported_reference(refs, {}, kk, ordered, tied) == "leader's"


def test_a_tie_has_no_winner_and_so_no_margin():
    """Review of #592, item 4 asked for the margin after a tie-break; since
    2026-10-20 nothing breaks a ΔBIC tie (WP-2002), so a tie has no winner and
    its margin is ``None``.  A winner's margin is against the best *other*
    eligible class, and positive."""
    a = _trial(0, delta_bic=120.0, r_mag=0.40, free=3)
    b = _trial(1, delta_bic=118.0, r_mag=0.11, free=1, bns="2.2")
    ordered, tied, verdict, why = _rank((a, b), SOLVE_TIE_DELTA_BIC)
    solution = _solution(ordered, tied, verdict, why)
    assert verdict == "abstained" and solution.best is None
    assert solution.margin is None
    c = _trial(2, delta_bic=90.0, r_mag=0.5, free=1, bns="3.3")
    ordered, tied, verdict, why = _rank((a, c), SOLVE_TIE_DELTA_BIC)
    assert _solution(ordered, tied, verdict, why).margin == pytest.approx(30.0)


def test_a_nuclear_reference_that_stopped_short_keeps_its_trials_out_of_the_ranking():
    """Review of #592, item 6: a reference short of its minimum has a χ² too
    high, which inflates every ΔBIC measured against it by the same amount and
    can turn "nothing to solve" into "solved".  Such a trial is treated like
    one whose own fit stopped short: not eligible, and an abstention when it
    would have mattered."""
    from dataclasses import replace

    from rietx.strategy.magnetic import _converged, _eligible_trials

    ok = _trial(0, delta_bic=150.0, r_mag=0.1, free=1)
    assert _converged(ok) and _eligible_trials([ok]) == [ok]
    # positive arm: the same trial against a converged reference is a winner
    converged_ref = replace(ok, reference_status="converged")
    assert _rank([converged_ref], SOLVE_TIE_DELTA_BIC)[2] == "solved"

    short = replace(ok, reference_status="max_iter")
    assert not _converged(short) and _eligible_trials([short]) == []
    assert "nuclear reference stopped at 'max_iter'" in short.stopped_short
    _o, tied, verdict, reason = _rank([short], SOLVE_TIE_DELTA_BIC)
    assert verdict == "abstained" and tied == ()
    assert "nuclear reference stopped at 'max_iter'" in reason
    # and it is the printed table's business too, not only the verdict's
    text = str(_solution((short,), (), verdict, reason))
    assert "its nuclear reference stopped at 'max_iter', not 'converged'" in text
    # a short reference cannot *create* evidence: ΔBIC ≤ 0 there stays an
    # answer about the specimen
    null = replace(_trial(0, delta_bic=-12.0, r_mag=0.1, free=1),
                   reference_status="max_iter")
    assert _rank([null], SOLVE_TIE_DELTA_BIC)[2] == "nothing to solve"


def test_the_effective_count_is_n_over_the_solves_own_f_squared():
    """``_solve_inflation`` reads the factor the solve applied off a row, and
    ``_effective_count`` divides the channel count by its square (WP-2002, B12).
    A row without both esds is skipped, and no factor at all charges N."""
    from types import SimpleNamespace

    from rietx.schemas.results import RefinedParameter
    from rietx.strategy.magnetic import _effective_count, _solve_inflation

    rows = [RefinedParameter(path="phases.0.scale", value=1.0),
            RefinedParameter(path="phases.0.cell.a", value=4.0, stderr=0.03,
                             stderr_uncorrected=0.01)]
    result = SimpleNamespace(parameters=rows,
                             statistics=SimpleNamespace(n_points=1800))
    assert _solve_inflation(result) == pytest.approx(3.0)
    assert _effective_count(result) == pytest.approx(200.0)
    bare = SimpleNamespace(parameters=rows[:1],
                           statistics=SimpleNamespace(n_points=1800))
    assert _solve_inflation(bare) is None
    assert _effective_count(bare) == 1800.0


@pytest.mark.xdist_group("magnetic-k-trials-true-k")
def test_every_dbic_of_a_solve_charges_its_restricted_fits_n_over_f_squared(monkeypatch):
    """Each trial's ΔBIC charges N/f², f the nuclear reference's own factor
    (WP-2002, B12).  On this fixture f is 3.73, so the count is 175 of the
    2440 channels, a fourteenth of the N it charged before."""
    import rietx.report.layer2 as layer2
    from rietx.strategy.magnetic import _effective_count
    from tests.test_magnetic_k_trials import true_k_and_data

    ref, data, _truth = true_k_and_data.__wrapped__()
    fits, calls = [], []
    real_fit, real_dbic = _magnetic_module._fit, layer2.delta_bic

    def fit(structure, *args, **kw):
        out = real_fit(structure, *args, **kw)
        fits.append((structure, out[1]))
        return out

    def dbic(chi2_r, chi2_f, n_points, n_added, *, n_effective=None):
        calls.append((n_points, n_effective))
        return real_dbic(chi2_r, chi2_f, n_points, n_added, n_effective=n_effective)

    monkeypatch.setattr(_magnetic_module, "_fit", fit)
    monkeypatch.setattr(layer2, "delta_bic", dbic)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+",
                                 k=(0, 0, "1/2"))
    assert solution.verdict == "solved", solution.reason
    nuclear = [r for s, r in fits
               if all(a.moment is None for a in s.phases[0].atoms)]
    assert len(nuclear) == 1
    n_eff = _effective_count(nuclear[0])
    n = nuclear[0].statistics.n_points
    assert n_eff < 0.2 * n   # f > 2.2; measured 3.73
    refined = [t for t in solution.trials if t.status == "refined"]
    assert refined and len(calls) == len(refined)
    for n_points, charged in calls:
        assert n_points == n and charged == n_eff
    assert any(f"ΔBIC charges {n_eff:.0f} observations, not the {n} " in c
               for c in solution.caveats), solution.caveats


def test_the_reported_nuclear_numbers_are_the_leading_trials_reference():
    """Review of #592, item 5: ``next(iter(references.values()))`` was the
    first child cell built, which is the losing k's when the second k wins."""
    from rietx.strategy.magnetic import _reported_reference

    ref_k1 = (100.0, 5, 0.31, 2.0, 0.9, "converged")
    ref_k2 = (80.0, 6, 0.22, 1.4, 0.5, "converged")
    references = {"cell-k1": ref_k1, "cell-k2": ref_k2}
    reference_of = {((0, 0), 0): ref_k1, ((1, 1), 0): ref_k2,
                    ((1, 1), 1): ref_k2}
    winner = _trial(1, delta_bic=40.0, r_mag=0.1, free=1)
    assert _reported_reference(reference_of, references, (1, 1), [winner]) is ref_k2
    assert _reported_reference(reference_of, references, (0, 0),
                               [_trial(0, delta_bic=3.0, r_mag=0.1, free=1)]) is ref_k1
    # no trial (nothing ranked): any reference built at the winning k
    assert _reported_reference(reference_of, references, (1, 1), []) is ref_k2
    # a refused leader has no entry of its own; its k's reference stands in
    assert _reported_reference(reference_of, references, (1, 1),
                               [_trial(7, delta_bic=1.0, r_mag=0.1, free=1)]) is ref_k2
    assert _reported_reference({}, {}, (0, 0), []) is None


def test_no_internal_fit_records_itself_as_a_run(monkeypatch):
    """Review of #592, item 2 (root CLAUDE.md, "Every fit records itself", 4):
    every fit ``_fit`` makes — the first and each continuation — is a trial the
    package may discard, so none is a run.  ``_fit`` cannot tell the winner's
    fit from the rest, so all of them decline."""
    import importlib
    from types import SimpleNamespace

    refine_module = importlib.import_module("rietx.refine")   # `rietx.refine` the name is the function

    calls = []
    statuses = iter(["max_iter", "max_iter", "converged"])

    class _Stub:
        def __init__(self, structure, instrument):
            pass

        def tie(self, *a, **k):
            pass

        def fit(self, data, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status=next(statuses))

    class _Instrument:
        def model_copy(self, deep=False):
            return self

    plan = rx.RefinementPlan(stages=[rx.Stage("m", ["phases.*.scale"])])
    monkeypatch.setattr(refine_module, "Refinement", _Stub)
    _ref, result = _magnetic_module._fit(object(), _Instrument(), None, plan)
    assert result.status == "converged"
    assert len(calls) == 3                       # one fit and two continuations
    assert [c.get("telemetry", "unset") for c in calls] == [False] * 3


def test_margin_is_none_not_negative_when_the_second_row_is_disqualified():
    """The mechanism behind the two negative-margin entries of issue #390's
    MAGNDATA sweep.
    ``MagneticSolution.trials`` is eligible classes (best ΔBIC first) **then**
    the disqualified ``rest``, each sorted by its own raw ΔBIC — so an
    unsupported model that happens to fit the noise better than the true
    winner (a real possibility: BIC alone does not know the null test
    disqualified it) sorts second and carries a *higher* raw ΔBIC.  A naive
    ``trials[0].delta_bic - trials[1].delta_bic`` diff against it is negative;
    ``_rank`` never considered that class a competitor in the first place, and
    ``.margin`` says so by returning ``None``, never a negative number.
    """
    winner = _trial(0, delta_bic=225.0, r_mag=0.1, free=8, bns="5.13")
    disqualified = _trial(1, delta_bic=533.0, r_mag=0.1, free=8, bns="5.15",
                          supported=False)
    ordered, tied, verdict, why = _rank((winner, disqualified),
                                        SOLVE_TIE_DELTA_BIC)
    assert verdict == "solved"
    assert ordered[0].bns_number == "5.13"
    assert ordered[1].bns_number == "5.15"
    naive_margin = ordered[0].delta_bic - ordered[1].delta_bic
    assert naive_margin < 0.0, "this is the bug's own shape, reproduced"
    assert _solution(ordered, tied, verdict, why).margin is None


def test_margin_is_none_on_an_abstention():
    tied_trials = (_trial(0, delta_bic=10.0, r_mag=0.1, free=1, bns="1.1"),
                  _trial(1, delta_bic=9.0, r_mag=0.1, free=1, bns="1.2"))
    ordered, tied, verdict, why = _rank(tied_trials, SOLVE_TIE_DELTA_BIC)
    assert verdict == "abstained"
    assert _solution(ordered, tied, verdict, why).margin is None


# ---------------------------------------------------------- the seed tilt --

def test_a_rank_one_basis_seed_is_untouched_by_the_tilt():
    """Negative control: a single-copy, one-amplitude basis (the ordinary
    case, every site this workflow refined before WP-1418) is bit-identical
    to the pre-fix seed, whatever the tilt."""
    basis = [[1, 0, 0]]
    cell = (4.0, 4.0, 4.2, 90.0, 90.0, 90.0)
    old = tilted_seed(basis, cell, 3.0, tilt=0.0)
    new = tilted_seed(basis, cell, 3.0, tilt=SEED_TILT)
    assert np.allclose(old, new)
    assert np.allclose(new, [3.0, 0.0, 0.0])


def test_a_rank_two_basis_seed_moves_every_row_and_keeps_the_modulus():
    """The bug's own shape: tilt = 0 places nothing at all on the second row
    — the angle DOF then starts at exactly the value of pointing along the
    first, WP-1418's stationary-point mechanism.  ``SEED_TILT`` does not, and
    the modulus is exactly what was asked for either way (the frame is
    metric-orthonormal by construction, so a unit-Euclidean-norm coefficient
    vector gives a unit modulus automatically)."""
    basis = [[1, 0, 0], [0, 1, 0]]
    cell = (4.0, 4.0, 4.2, 90.0, 90.0, 90.0)
    old = tilted_seed(basis, cell, 3.0, tilt=0.0)
    new = tilted_seed(basis, cell, 3.0, tilt=SEED_TILT)
    assert old[1] == pytest.approx(0.0, abs=1e-12)
    assert abs(new[1]) > 1e-3
    assert np.linalg.norm(old) == pytest.approx(3.0)
    assert np.linalg.norm(new) == pytest.approx(3.0)


def test_warm_seed_keeps_the_preferred_direction_and_tilts_the_rest():
    """``warm_seed`` (the descent audit's own seed): anchored on a caller-given
    direction rather than the basis's own row 0, for warm-starting a subgroup
    refit from a supergroup's converged moment."""
    basis = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    cell = (5.0, 5.0, 5.0, 90.0, 90.0, 90.0)
    preferred = (0.0, 4.0, 0.0)
    seed = warm_seed(basis, cell, preferred)
    assert np.linalg.norm(seed) == pytest.approx(4.0)
    cos_to_preferred = float(np.dot(seed, preferred) / (4.0 * 4.0))
    assert cos_to_preferred > 0.97        # mostly along the preferred direction
    assert seed[0] != 0.0 and seed[2] != 0.0    # the other two rows still tilted


def test_warm_seed_falls_back_to_the_ordinary_seed_at_zero_preferred():
    """An atom whose winner moment was itself ~zero has nothing to anchor
    on; it still gets a real (nonzero) seed rather than staying at zero."""
    basis = [[1, 0, 0], [0, 1, 0]]
    cell = (5.0, 5.0, 5.0, 90.0, 90.0, 90.0)
    seed = warm_seed(basis, cell, (0.0, 0.0, 0.0))
    assert np.linalg.norm(seed) > 0.0


@pytest.mark.slow
def test_the_pre_fix_seed_leaves_a_general_direction_stuck_at_its_special_case(
       monkeypatch):
    """Issue #390's seed tilt, the mechanism verified end to end, not only inside
    ``tilted_seed`` itself.  P4/mmm's own S10 irrep at (0,0,0) gives a genuine
    general direction ("(a,b)", BNS 10.46, rank 2 at this atom) whose
    stabiliser is a real operator-list subgroup of the special direction's
    ("(a)", BNS 47.252, rank 1) — verified directly, not asserted.  Refit from
    a pattern simulated at a genuinely general moment (both components
    nonzero, neither along a symmetry axis), the pre-fix seed (tilt = 0,
    monkeypatched) never moves the second component off exactly zero; the fix
    does.

    **What this test does not claim.**  It does not claim the fit reaches a
    lower χ² with the fix — measured directly, Rwp is bit-identical either
    way (to 1e-6): the equivalence machinery already merges 47.252/65.486/
    10.46 into one powder-equivalence class
    (``analyse(candidates("P 4/m m m", (0,0,0), (0,0,0)))``, smallest first)
    before ``solve_magnetic`` ever refines the general one on its own — the
    same residual symmetry that pins the second DOF at zero is what makes the
    direction powder-degenerate, so failing to explore it costs nothing here.
    Flagged in the report rather than overclaimed: this session did not find
    a case where the fix changes a ranking outcome, only where it changes
    what the *reported direction* honestly says.
    """
    instrument = neutron()
    general = candidate_named("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, 0), "10.46")
    special = candidate_named("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, 0), "47.252")
    ops_g, _ = general.group.xyz_strings()
    ops_s, _ = special.group.xyz_strings()
    assert set(ops_g) < set(ops_s), "10.46 must be a genuine subgroup of 47.252"
    truth_xyz = tuple(float(v) for v in general.moments([2.4, 0.9])[0])
    data = simulate(stated(tetragonal, general, truth_xyz), instrument, seed=20260918)
    magnetic = [(0, "Mn1", "Mn3+")]
    plan = rx.RefinementPlan(stages=[rx.Stage(
        "moment", ["phases.*.atoms.*.moment.dof*", "phases.*.scale",
                  "instrument.background.c*"])])

    def refit(tilt):
        monkeypatch.setattr(_magnetic_module, "SOLVE_SEED_TILT", tilt)
        child = _magnetic_module._state_k0(tetragonal(), general, magnetic,
                                          _magnetic_module.SOLVE_SEED_MU_B, {})
        structure = rx.Structure(phases=[child])
        return _magnetic_module._fit(structure, instrument, data, plan)

    ref_stuck, stuck = refit(0.0)
    ref_fixed, fixed = refit(SEED_TILT)
    assert ref_stuck.fitted_structure.phases[0].atoms[0].moment.crystalaxis_y.value \
        == pytest.approx(0.0, abs=1e-9)
    assert abs(ref_fixed.fitted_structure.phases[0].atoms[0].moment
              .crystalaxis_y.value) > 1e-3
    assert stuck.statistics.rwp == pytest.approx(fixed.statistics.rwp, abs=1e-6)


# ------------------------------------------------------- the descent audit --

def test_maximal_subgroups_finds_a_genuine_operator_list_subgroup():
    cs = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, 0))
    by_bns = {c.bns_number: c for c in cs}
    winner = by_bns["47.252"]
    classes = [((c.label,), c, "Mn1") for c in
              (by_bns["65.486"], by_bns["10.46"], by_bns["123.345"])]
    found = _maximal_subgroups(winner, classes)
    assert [c.bns_number for _i, _m, c, _s in found] == ["10.46"]


def test_maximal_subgroups_drops_one_nested_inside_another_found_one():
    """A genuine three-level chain (F m -3 m at (0,0,0), S4's own directions):
    the fully general direction (BNS 2.4) is a subgroup of one of the two
    ``12.62`` domains (verified directly), which is itself a subgroup of the
    winner (71.536) — ``2.4`` must not be reported, since refitting it would
    only repeat what the larger ``12.62`` subgroup already tests.  The other
    ``12.62`` domain is *not* a subgroup of this particular winner (a
    different domain of the same label, verified directly) and must not be
    reported either — ``_maximal_subgroups`` only ever returns genuine
    subgroups, whatever else shares a class's bare label.
    """
    cs = candidates("F m -3 m", (0.0, 0.0, 0.0), (0, 0, 0))
    winner = next(c for c in cs if c.bns_number == "71.536")
    twelves = [c for c in cs if c.bns_number == "12.62"]
    general = next(c for c in cs if c.bns_number == "2.4")
    ops_g, _ = general.group.xyz_strings()
    ops_t0, _ = twelves[0].group.xyz_strings()
    ops_t1, _ = twelves[1].group.xyz_strings()
    ops_w, _ = winner.group.xyz_strings()
    assert set(ops_g) < set(ops_t0), "2.4 must nest inside twelves[0]"
    assert set(ops_t0) < set(ops_w), "twelves[0] must be a genuine subgroup of the winner"
    assert not set(ops_t1) < set(ops_w), "twelves[1] must not be"
    classes = [((c.label,), c, "site") for c in (*twelves, general)]
    found = _maximal_subgroups(winner, classes)
    assert len(found) == 1
    assert found[0][2] is twelves[0]


@pytest.mark.slow
def test_descend_reports_a_subgroup_and_does_not_let_it_win_on_noise():
    """The negative control the brief itself names: a pattern simulated from
    the *true* special direction (BNS 71.536, F m -3 m at (0,0,0)) must not
    have its subgroup (BNS 12.62, one extra free amplitude) beat it beyond
    the tie width once refit from the winner's own solution — the extra
    freedom has nothing real to buy on this data."""
    instrument = neutron()
    cs = candidates("F m -3 m", (0.0, 0.0, 0.0), (0, 0, 0))
    winner_candidate = next(c for c in cs if c.bns_number == "71.536")
    sub_candidate = next(c for c in cs if c.bns_number == "12.62")

    def cubic(moment=None, magnetic=None) -> Phase:
        return Phase(
            name="cubic", space_group="F m -3 m", cell=_cell(4.0, 4.0, 4.0),
            atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
                   _atom("O1", "O", (0.25, 0.25, 0.25), biso=0.6)],
            magnetic_symmetry=magnetic)

    magnetic = [(0, "Mn1", "Mn3+")]
    plan = rx.RefinementPlan(stages=[rx.Stage(
        "moment", ["phases.*.atoms.*.moment.dof*", "phases.*.scale",
                  "instrument.background.c*"])])
    truth_xyz = tuple(float(v) for v in winner_candidate.moments([3.0])[0])
    data = simulate(stated(cubic, winner_candidate, truth_xyz), instrument,
                    seed=20260918)

    child = _magnetic_module._state_k0(cubic(), winner_candidate, magnetic,
                                      _magnetic_module.SOLVE_SEED_MU_B, {})
    winner_ref, winner_result = _magnetic_module._fit(
        rx.Structure(phases=[child]), instrument, data, plan)
    winner_trial = MagneticTrial(
        class_index=0, representative=winner_candidate.label,
        members=(winner_candidate.label,), site="Mn1",
        irrep=winner_candidate.irrep_label,
        direction=winner_candidate.direction.label,
        bns_number=winner_candidate.bns_number, uni_number=None, msg_type=1,
        free_amplitudes=winner_candidate.free_amplitudes,
        determinable_amplitudes=1, status="refined",
        rwp=float(winner_result.statistics.rwp),
        gof=float(winner_result.statistics.gof), delta_bic=999.0,
        r_magnetic=None, n_moment_parameters=1,
        n_free_parameters=int(winner_result.statistics.n_free_parameters),
        _structure=winner_ref.fitted_structure, _result=winner_result)
    classes = [((sub_candidate.label,), sub_candidate, "Mn1")]

    audits, note, diagnostics = _descend(
        cubic(), winner_trial, winner_candidate, classes, magnetic, {},
        plan, instrument, data, None, SOLVE_TIE_DELTA_BIC, True)

    assert len(audits) == 1, audits
    assert audits[0].bns_number == "12.62"
    assert audits[0].status == "refined", audits[0].refusal
    assert audits[0].delta_bic_over_winner is not None
    assert audits[0].delta_bic_over_winner <= SOLVE_TIE_DELTA_BIC
    assert ("no subgroup beats the winner" in note
           or "no subgroup supported" in note), note
    assert diagnostics == ()


def test_descend_is_not_attempted_off_k_equals_zero():
    audits, note, diagnostics = _descend(
        None, None, None, [], [], {}, None, None, None, None,
        SOLVE_TIE_DELTA_BIC, False)
    assert audits == ()
    assert "only a k = 0 statement is warm-started" in note
    assert diagnostics == ()


# ------------------------------------------------- the tie-width lattice ---

def _cubic_phase(moment=None, magnetic=None) -> Phase:
    return Phase(
        name="cubic", space_group="F m -3 m", cell=_cell(4.0, 4.0, 4.0),
        atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
               _atom("O1", "O", (0.25, 0.25, 0.25), biso=0.6)],
        magnetic_symmetry=magnetic)


def _trial_with_structure(index, candidate, free=1):
    ops, cent = candidate.group.xyz_strings()
    moment_xyz = tuple(float(v) for v in
                       candidate.moments([1.0] * candidate.free_amplitudes)[0])
    phase = _cubic_phase(moment=Moment.from_values(moment_xyz, "Mn3+"),
                         magnetic=MagneticSymmetry(operations=list(ops),
                                                   centerings=list(cent)))
    structure = rx.Structure(phases=[phase])
    return MagneticTrial(
        class_index=index, representative=f"S{index}(a)",
        members=(f"{candidate.bns_number} S{index}(a)",), site="Mn1",
        irrep=f"S{index}", direction="(a)", bns_number=candidate.bns_number,
        uni_number=None, msg_type=1, free_amplitudes=free,
        determinable_amplitudes=1, status="refined",
        rwp=0.1, gof=1.0, delta_bic=100.0, r_magnetic=0.1,
        n_moment_parameters=free, n_free_parameters=free + 5,
        moments=(MomentRow(label="Mn1", ion="Mn3+", magnitude=3.0, esd=0.1,
                           crystalaxis=moment_xyz, supported=True),),
        _structure=structure)


def test_tie_lattice_lines_names_a_subgroup_and_an_unrelated_pair():
    """Data only, per the brief: no new ranking rule, just which tied class
    is a subgroup of which, read off the operator lists the trials
    themselves already carry (``trial._structure``)."""
    cs = candidates("F m -3 m", (0.0, 0.0, 0.0), (0, 0, 0))
    top = next(c for c in cs if c.bns_number == "71.536")
    sub = next(c for c in cs if c.bns_number == "12.62")
    other = next(c for c in cs if c.bns_number == "166.101")
    t0 = _trial_with_structure(0, top, free=1)
    t1 = _trial_with_structure(1, sub, free=2)
    t2 = _trial_with_structure(2, other, free=1)

    lines = _tie_lattice_lines((t0, t1, t2), (0, 1, 2))

    subgroup_lines = [line for line in lines if "subgroup of class 0" in line and "class 1" in line]
    assert subgroup_lines, lines
    unrelated_lines = [line for line in lines if "class 2" in line and "unrelated" in line]
    assert unrelated_lines, lines


def test_the_tie_lattice_appears_in_str_only_for_a_genuine_tie():
    cs = candidates("F m -3 m", (0.0, 0.0, 0.0), (0, 0, 0))
    top = next(c for c in cs if c.bns_number == "71.536")
    sub = next(c for c in cs if c.bns_number == "12.62")
    t0 = _trial_with_structure(0, top, free=1)
    t1 = _trial_with_structure(1, sub, free=2)
    tied_solution = _solution((t0, t1), (0, 1), "abstained", "tied for test")
    assert "descent among the tied classes" in str(tied_solution)
    solved_solution = _solution((t0,), (0,), "solved", "solo for test")
    assert "descent among the tied classes" not in str(solved_solution)


# ================================== degenerate moment pairs and the null test

def _paired_trial(index, *, delta_bic, m, esd, pair_m, pair_esd, bns="1.1"):
    """A two-site trial whose moduli are a powder-degenerate pair: each row ``m ± esd``,
    their quadrature sum ``pair_m ± pair_esd``."""
    rows = tuple(
        MomentRow(label=lb, ion="Mn3+", magnitude=m, esd=esd,
                  crystalaxis=(m, 0.0, 0.0), supported=m > 3.0 * esd,
                  paired_with=(f"phases.0.atoms.{1 - i}.moment.dof0",),
                  paired_magnitude=pair_m, paired_magnitude_esd=pair_esd)
        for i, lb in enumerate(("Mn1", "Mn2")))
    return MagneticTrial(
        class_index=index, representative=f"S{index}(a)",
        members=(f"{bns} S{index}(a)",), site="Mn1", irrep=f"S{index}",
        direction="(a)", bns_number=bns, uni_number=None, msg_type=1,
        free_amplitudes=1, determinable_amplitudes=1, status="refined",
        rwp=0.1, gof=1.0, delta_bic=delta_bic, r_magnetic=0.07,
        n_moment_parameters=2, n_free_parameters=12, moments=rows)


def test_a_degenerate_pair_is_tested_as_the_pair_not_row_by_row():
    """Issue #458: each modulus of a powder-degenerate pair fails the ratio alone
    (esd 2.4× the value — the length of the flat valley), while the quadrature
    sum the powder measures sits 63 esds clear.  Reading the rows made the
    best class ineligible, and a class with a seventh of its ΔBIC won; the
    gate must read the measured number."""
    pair = _paired_trial(0, delta_bic=3500.0, m=2.0, esd=4.8,
                         pair_m=2.83, pair_esd=0.045, bns="1.1")
    assert not any(r.supported for r in pair.moments)
    assert all(r.pair_supported for r in pair.moments)
    assert pair.supported
    lesser = _trial(1, delta_bic=500.0, r_mag=0.48, free=2, bns="2.2")
    ordered, tied, verdict, _why = _rank([lesser, pair], SOLVE_TIE_DELTA_BIC)
    assert verdict == "solved" and tied == (0,)
    assert ordered[0].bns_number == "1.1"


def test_a_pair_whose_quadrature_sum_is_inside_its_esd_stays_unsupported():
    """The negative arm: the same gate, on the pair.  A null pattern's pair
    comes back small against its own esd and must not be let through."""
    null = _paired_trial(0, delta_bic=5000.0, m=0.3, esd=2.0,
                         pair_m=0.42, pair_esd=0.5)
    assert not null.supported
    _o, tied, verdict, reason = _rank([null], SOLVE_TIE_DELTA_BIC)
    assert verdict == "nothing to solve" and tied == ()
    assert "quadrature sum" in reason


@pytest.mark.parametrize(
    ("ratio", "fires"),
    [pytest.param(2.0, True, id="2x-the-gate-fires"),
     pytest.param(0.5, False, id="half-the-gate-is-silent")])
def test_the_pair_gate_on_pairs_well_clear_of_it_either_side(ratio, fires):
    """The gate's own logic, on constructed pairs (#820, WP-1418 option (a)).

    Cr₂WO₆ at 150 K put a real pair within 0.3 % of ``MOMENT_SUPPORT_SIGMA``
    before WP-1938 (2.9994σ on Linux, 2.9917σ on macOS), and its pair has
    moved with the solver since (2.07σ after #918 and #923), so the acceptance
    test no longer asserts which side it lands; this test owns the rule
    instead.  Each arm carries a quadrature sum of 0.6 μ_B, the size of that
    pair before WP-1938, with its esd
    set to put the sum at twice or half the gate.  Each row alone is 0.21× its
    esd in both arms, so only the pair can make the class supported, and the
    ranking follows the gate both ways.
    """
    pair_m = 0.6
    pair_esd = pair_m / (ratio * MOMENT_SUPPORT_SIGMA)
    trial = _paired_trial(0, delta_bic=500.0, m=0.42, esd=2.0,
                          pair_m=pair_m, pair_esd=pair_esd)
    assert not any(r.supported for r in trial.moments)
    assert all(r.pair_supported is fires for r in trial.moments)
    assert trial.supported is fires
    _o, tied, verdict, reason = _rank([trial], SOLVE_TIE_DELTA_BIC)
    if fires:
        assert verdict == "solved" and tied == (0,), reason
    else:
        assert verdict == "nothing to solve" and tied == (), reason
        assert "quadrature sum" in reason


def test_a_pair_at_the_moment_floor_is_silent_however_small_its_esd():
    """The gate's other condition: a quadrature sum at ``MOMENT_FLOOR_MU_B``
    fails even at many times ``MOMENT_SUPPORT_SIGMA`` of its esd, the shape of a
    class whose moduli all refined to zero."""
    pair_m = MOMENT_FLOOR_MU_B
    trial = _paired_trial(0, delta_bic=500.0, m=pair_m / 2, esd=1.0,
                          pair_m=pair_m, pair_esd=pair_m / 100.0)
    assert not any(r.pair_supported for r in trial.moments)
    assert not trial.supported


def test_nothing_to_solve_counts_the_supported_classes_not_the_refined_ones():
    """The sentence says how many trials carried a supported moment.

    Found on Cr₂WO₆ at 150 K (``test_magnetic_solve_acceptance.py``) when one
    class's degenerate pair read as clearing the null test, both classes at
    ΔBIC < 0: the verdict was right and the sentence said both had a
    supported moment.  That pair esd was a cross-stage ρ (review of #592) and
    the pair no longer clears, so the pattern no longer exercises this and the
    test is synthetic.
    """
    supported = _trial(0, delta_bic=-33.0, r_mag=0.14, free=2, bns="1.1")
    unsupported = _trial(1, delta_bic=-46.0, r_mag=0.14, free=2, bns="2.2",
                         supported=False)
    _o, tied, verdict, reason = _rank([supported, unsupported],
                                      SOLVE_TIE_DELTA_BIC)
    assert verdict == "nothing to solve" and tied == ()
    assert reason.startswith("1 of 2 refined candidate(s)"), reason


def test_an_ordinary_row_is_not_pair_supported():
    row = MomentRow(label="Mn1", ion="Mn3+", magnitude=3.0, esd=0.1,
                    crystalaxis=(3.0, 0.0, 0.0), supported=True)
    assert row.pair_supported is False


#: Cr₂WO₆ at 150 K on the pre-#527 tree (review of #592, the tree's tutorial
#: data): the final stage's σ's of the two child moduli, their signed DOFs,
#: the final stage's own ρ and the moment stage's ρ, which the run's
#: cross-stage HIGH_CORRELATION dedup kept because its |ρ| was larger.
_CR2WO6_SIGMA = (1.562, 4.486)
_CR2WO6_DOF = (0.563, 0.195)
_CR2WO6_RHO_FINAL = -0.98591
_CR2WO6_RHO_MOMENT_STAGE = -0.99821


def _cr2wo6_pair_fit(rho_final):
    """A stand-in fit with the Cr₂WO₆ pair: two free moduli, a top-five list
    crowded out by ρ = 1 Biso twins, the run's deduplicated HIGH_CORRELATION
    finding carrying the **moment stage's** ρ, and a kept answer covariance
    whose ρ is ``rho_final``."""
    from types import SimpleNamespace

    from rietx.schemas.common import Diagnostic
    from rietx.schemas.results import CorrelationPair

    a, b = "phases.0.atoms.0.moment.dof0", "phases.0.atoms.1.moment.dof0"
    sa, sb = _CR2WO6_SIGMA
    top = [CorrelationPair(path_a=f"phases.0.atoms.{i}.biso",
                           path_b=f"phases.0.atoms.{i + 1}.biso", rho=1.0)
           for i in range(2, 7)]
    stale = Diagnostic(
        level="warning", code="HIGH_CORRELATION",
        message="m — flagged in stages: moment, all", where=[a, b],
        value=_CR2WO6_RHO_MOMENT_STAGE)
    result = SimpleNamespace(
        identifiability=SimpleNamespace(top_correlations=top),
        diagnostics=[stale],
        parameters=[SimpleNamespace(path=a, vary=True, stderr=sa),
                    SimpleNamespace(path=b, vary=True, stderr=sb),
                    # a tied partner correlates at ±1 by construction
                    SimpleNamespace(path="phases.0.atoms.2.moment.dof0",
                                    vary=False, stderr=sa)])
    cov = np.array([[sa * sa, rho_final * sa * sb],
                    [rho_final * sa * sb, sb * sb]])

    class _Table:
        def physical_covariance(self, theta, stderr_internal, correlation,
                                paths):
            assert paths == [a, b]
            return cov

    ref = SimpleNamespace(_answer_covariance=(
        result, _Table(), None, np.ones(2), np.eye(2)))
    return ref, result, (a, b)


def _fold(pairs, paths):
    from rietx.report.magnetic import _pair_degenerate_moments
    from rietx.report.schemas import MomentEvidence

    rows = [MomentEvidence(atom=f"Cr{i}", phase="cr2wo6", ion="Cr3+",
                           magnitude=abs(d), magnitude_esd=s,
                           crystalaxis=[d, 0.0, 0.0], free_directions=["m"],
                           supported=False, approximation="dipole", path=p)
            for i, (p, d, s) in enumerate(zip(paths, _CR2WO6_DOF,
                                              _CR2WO6_SIGMA))]
    return _pair_degenerate_moments(rows, pairs, dict(zip(paths, _CR2WO6_DOF)))


def test_the_pair_rho_is_the_final_stages_never_the_cross_stage_worst():
    """Review of #592: the fold multiplied the final stage's σ's by a ρ read off
    the run's HIGH_CORRELATION findings, which keep the worst |ρ| across every
    stage.  On Cr₂WO₆ at 150 K that was the moment stage's −0.99821 against
    the final stage's −0.98591, and the pair esd came out 0.089 μ_B where the
    final stage's own covariance gives 0.247 — false support at 6.7σ.  The ρ
    must come from the covariance the σ's came from."""
    from rietx.strategy.magnetic import _moment_correlations

    ref, result, paths = _cr2wo6_pair_fit(_CR2WO6_RHO_FINAL)
    pairs = _moment_correlations(ref, result)
    assert len(pairs) == 1          # the tied partner is not paired
    assert {pairs[0].path_a, pairs[0].path_b} == set(paths)
    assert pairs[0].rho == pytest.approx(_CR2WO6_RHO_FINAL, abs=1e-12)
    folded = _fold(pairs, paths)
    assert folded[0].paired_magnitude == pytest.approx(0.596, abs=2e-3)
    assert folded[0].paired_magnitude_esd == pytest.approx(0.247, abs=2e-3)


def test_the_planted_cross_stage_rho_reproduces_the_false_support():
    """The positive arm of the test above: the same fold, handed the moment
    stage's ρ the old fallback read, reproduces the reported 0.0886 — so the
    arithmetic the fixed test relies on is the arithmetic that went wrong."""
    from rietx.schemas.results import CorrelationPair

    _ref, _result, paths = _cr2wo6_pair_fit(_CR2WO6_RHO_FINAL)
    planted = [CorrelationPair(path_a=paths[0], path_b=paths[1],
                               rho=_CR2WO6_RHO_MOMENT_STAGE)]
    folded = _fold(planted, paths)
    assert folded[0].paired_magnitude_esd == pytest.approx(0.0886, abs=5e-4)
    assert folded[0].paired_magnitude > 3.0 * folded[0].paired_magnitude_esd


def test_a_moment_pair_crowded_out_of_the_top_list_is_still_folded():
    """Issue #458: with coordinates free, the fit's worst-five |ρ| list was all
    coordinate pairs at ρ = 1 and the moment pair was not in it.  The pair is
    read off the kept covariance, so the top-k truncation cannot hide it."""
    from rietx.strategy.magnetic import _moment_correlations

    ref, result, paths = _cr2wo6_pair_fit(-1.0 + 1e-6)
    pairs = _moment_correlations(ref, result)
    assert [frozenset((c.path_a, c.path_b)) for c in pairs] == [
        frozenset(paths)]


def test_no_kept_covariance_and_a_stale_one_are_both_not_measured():
    """``None``, never a fallback to the cross-stage findings: a ref that kept
    no covariance, or kept another result's, says nothing about this pair."""
    from types import SimpleNamespace

    from rietx.strategy.magnetic import _moment_correlations

    ref, result, _paths = _cr2wo6_pair_fit(_CR2WO6_RHO_FINAL)
    assert _moment_correlations(SimpleNamespace(_answer_covariance=None),
                                result) is None
    other = SimpleNamespace(**vars(result))
    assert _moment_correlations(ref, other) is None


def test_the_kept_covariance_is_the_answer_stages():
    """``Refinement._answer_covariance`` is the covariance of the result it is
    stored beside: on a two-stage fit, the worst pair of the final stage's
    ``top_correlations`` is reproduced from it to the digit."""
    instrument = neutron()
    data = simulate(tetragonal(), instrument)
    ref = rx.Refinement(rx.Structure(phases=[tetragonal()]), instrument)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("all", ["phases.*.scale", "instrument.background.c*",
                         "phases.*.cell.*", "phases.*.atoms.*.biso"])])
    result = ref.fit(data, plan=plan)
    kept, table, theta, stderr_internal, correlation = ref._answer_covariance
    assert kept is result
    top = result.identifiability.top_correlations[0]
    cov = table.physical_covariance(theta, stderr_internal, correlation,
                                    [top.path_a, top.path_b])
    rho = cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1])
    assert rho == pytest.approx(top.rho, abs=1e-9)


# ============================================== a budget stop is not a minimum

def test_a_budget_stop_is_continued_from_where_it_stopped():
    """Review of #592: both 150 K Cr₂WO₆ trials stopped on TRF's evaluation
    budget 18.4 χ² above their minimum and were ranked as refined.  ``_fit``
    continues such a fit from where it stopped, freeing everything the plan
    freed by its end, at most ``SOLVE_MAX_CONTINUATIONS`` times."""
    from rietx.strategy.magnetic import _fit

    instrument = neutron()
    data = simulate(tetragonal(), instrument)
    starved = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=1),
        rx.Stage("all", ["phases.*.cell.*", "phases.*.atoms.*.biso"],
                 max_iter=1)])
    # The start is 0.004 Å off the simulated cell.  From the truth itself the
    # LM driver converges both one-iteration stages, so nothing is continued
    # and the test would not reach the code it is about (WP-1938).
    start = tetragonal()
    start.cell.a.value += 0.004
    start.cell.c.value += 0.004
    _ref, result = _fit(rx.Structure(phases=[start]), instrument,
                        data, starved)
    assert [s.name for s in result.stages] == ["all (continued)", "closing"]
    freed = {p.path for p in result.parameters if p.vary}
    assert "phases.0.scale" in freed and "phases.0.cell.a" in freed
    # each continuation keeps the last stage's one-iteration budget, so this
    # one may still stop short; whatever the last returns is the trial's
    assert result.status in ("converged", "max_iter")


def test_a_converged_fit_is_not_refitted():
    from rietx.strategy.magnetic import _fit

    instrument = neutron()
    data = simulate(tetragonal(), instrument)
    _ref, result = _fit(rx.Structure(phases=[tetragonal()]), instrument,
                        data, NUCLEAR_PLAN)
    assert result.status == "converged"
    assert [s.name for s in result.stages] == ["scale", "cell", "closing"]


def _short(trial, status="max_iter"):
    import dataclasses

    return dataclasses.replace(trial, fit_status=status)


def test_a_trial_that_stopped_on_its_budget_is_not_eligible():
    from rietx.strategy.magnetic import _eligible_trials

    good = _trial(0, delta_bic=900.0, r_mag=0.1, free=1, bns="1.1")
    assert _eligible_trials([good]) == [good]
    for status in ("max_iter", "diverged"):
        assert _eligible_trials([_short(good, status)]) == []


def test_a_budget_stopped_rival_makes_the_ranking_an_abstention():
    """The budget must not decide: a trial kept out only because it stopped
    short, whose ΔBIC would have reached the leader's tie width, is named and
    the answer is not stated."""
    leader = _trial(0, delta_bic=900.0, r_mag=0.1, free=1, bns="1.1")
    rival = _short(_trial(1, delta_bic=1200.0, r_mag=0.1, free=1, bns="2.2"))
    _o, tied, verdict, reason = _rank([leader, rival], SOLVE_TIE_DELTA_BIC)
    assert verdict == "abstained" and tied == ()
    assert "class 1" in reason and "'max_iter'" in reason
    # alone it would have been the only eligible class: still not a null result
    _o, _t, verdict, reason = _rank([rival], SOLVE_TIE_DELTA_BIC)
    assert verdict == "abstained" and "been eligible" in reason


def test_nothing_to_solve_says_which_trials_stopped_short():
    """An unsupported trial read at a budget stop still leaves nothing to
    solve, but the sentence says the reading is where the solver stopped."""
    short = _short(_trial(1, delta_bic=-40.0, r_mag=0.1, free=1, bns="2.2",
                          supported=False))
    done = _trial(0, delta_bic=-30.0, r_mag=0.1, free=1, bns="1.1",
                  supported=False)
    _o, _t, verdict, reason = _rank([done, short], SOLVE_TIE_DELTA_BIC)
    assert verdict == "nothing to solve"
    assert "1 of the 2 stopped short" in reason and "class 1" in reason
    _o, _t, _v, reason = _rank([done], SOLVE_TIE_DELTA_BIC)
    assert "stopped short" not in reason
    # the other "nothing to solve" sentence: supported, and ΔBIC ≤ 0
    held_back = _short(_trial(2, delta_bic=-10.0, r_mag=0.1, free=1,
                              bns="3.3"))
    _o, _t, verdict, reason = _rank([done, held_back], SOLVE_TIE_DELTA_BIC)
    assert verdict == "nothing to solve"
    assert reason.startswith("1 of 2 refined candidate(s)"), reason
    assert "1 of the 2 stopped short" in reason and "class 2" in reason


def test_a_budget_stopped_trial_far_behind_the_leader_does_not_block_it():
    leader = _trial(0, delta_bic=900.0, r_mag=0.1, free=1, bns="1.1")
    behind = _short(_trial(1, delta_bic=100.0, r_mag=0.1, free=1, bns="2.2"))
    ordered, tied, verdict, _why = _rank([leader, behind],
                                         SOLVE_TIE_DELTA_BIC)
    assert verdict == "solved" and tied == (0,)
    assert ordered[0].bns_number == "1.1"
    s = MagneticSolution(
        verdict=verdict, reason=_why, criterion="c", phase="p",
        space_group="P 1", k=("0", "0", "0"), k_route="given", k_reason="r",
        k_candidates=(), sites=("Mn1",), n_residual_peaks=0,
        n_on_nuclear_lines=0, n_on_forbidden_lattice_points=0,
        n_unexplained=0, trials=ordered, tied=tied,
        tie_width=SOLVE_TIE_DELTA_BIC, d_min=1.0, nuclear_rwp=0.2,
        nuclear_gof=1.0, nuclear_r_magnetic=0.5, n_magnetic_channels=10)
    assert "class 1: the fit stopped at 'max_iter'" in str(s)


# ================================ a k found only on the centred lattice's own set
#
# The X point of an F lattice, k = (1, 0, 0), is a zone-boundary point the
# conventional {0, ½}³ never listed (2·(½, 0, 0) = (1, 0, 0) is not an F
# reciprocal-lattice vector, while (1, 0, 0) itself is k ≡ −k).  With no k
# given, ``solve_magnetic`` takes its k from the satellite arm's ranking, so it
# can only reach X if the default generator lists it.  The structure is stated
# in the conventional cell, which holds it exactly: k·t is an integer for every
# primitive-conventional translation and ½ for the centrings (½, 0, ½) and
# (½, ½, 0), which therefore carry time reversal.  Moment along c on 4a, so the
# magnetic point group is m'm'm.

X_POINT_OPS = ["x,y,z,+1", "-x,-y,z,+1", "-x,y,-z,-1", "x,-y,-z,-1",
               "-x,-y,-z,+1", "x,y,-z,+1", "x,-y,z,-1", "-x,y,z,-1"]
X_POINT_CENTRINGS = ["x,y,z,+1", "x,y+1/2,z+1/2,+1", "x+1/2,y,z+1/2,-1",
                     "x+1/2,y+1/2,z,-1"]


def face_centred(moment=None, magnetic=None) -> Phase:
    return Phase(
        name="face_centred", space_group="F m m m", cell=_cell(5.0, 5.4, 5.8),
        atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
               _atom("O1", "O", (0.0, 0.0, 0.5), biso=0.6)],
        magnetic_symmetry=magnetic)


@pytest.fixture(scope="module")
def x_point_solution():
    """``solve_magnetic`` with no k on a pattern simulated at the X point.

    **Consumers carry** ``@pytest.mark.xdist_group("magnetic-solve-x-point")``.
    """
    instrument = neutron()
    truth = face_centred(
        moment=Moment.from_values((0.0, 0.0, 3.0), "Mn3+"),
        magnetic=MagneticSymmetry(operations=X_POINT_OPS,
                                  centerings=X_POINT_CENTRINGS))
    data = simulate(truth, instrument)
    ref = nuclear_fit(face_centred(), data, instrument)
    return rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")


@pytest.mark.xdist_group("magnetic-solve-x-point")
def test_with_no_k_given_the_x_point_of_an_f_lattice_is_the_k_chosen(
        x_point_solution):
    """The k step reaches X, and the isotropy route finds its candidate groups.

    Measured on this pattern: the arm's (1, 0, 0) indexes 13 of 13 unexplained
    peaks from 14 satellite positions, the runner-up (½, ½, ½) 1 from 35.  Under
    the conventional {0, ½}³ the vector was not a candidate, so whatever k the
    workflow chose was wrong.
    """
    solution = x_point_solution
    assert solution.k == ("1", "0", "0"), (solution.k, solution.k_reason)
    assert solution.k_route == "satellite ranking"
    assert solution.k_trials[0].k == ("1", "0", "0")
    assert solution.k_trials[0].matched == solution.n_unexplained
    # the k-subgroup step runs at X: three candidate classes at Mn on 4a
    assert len(solution.trials) == 3, [t.bns_number for t in solution.trials]
    assert {t.bns_number for t in solution.trials} == {"64.480", "66.500"}


@pytest.mark.xfail(strict=True, reason=(
    "magnetic_supercell refuses the X-point child cell of an F lattice "
    "(|det P| = 1/2, a primitive cell of the magnetic lattice) until the "
    "child-cell route of issue #612 lands; the k step above is unaffected"))
@pytest.mark.xdist_group("magnetic-solve-x-point")
def test_the_x_point_structure_is_solved(x_point_solution):
    solution = x_point_solution
    assert solution.verdict == "solved", solution.reason
    assert solution.best.moments[0].magnitude == pytest.approx(3.0, abs=0.3)


@pytest.mark.xdist_group("magnetic-solve-x-point")
def test_the_x_point_refusal_is_an_abstention_that_says_why(x_point_solution):
    """Until #612: every class is refused by name, and the verdict says so.

    The abstention must not read as a statement about the specimen.
    """
    solution = x_point_solution
    assert all(t.status == "refused" for t in solution.trials)
    assert solution.verdict == "abstained"
    assert "not a result about the specimen" in solution.reason
    # the refusal is magnetic_supercell's, named (its text cites issue #612)
    assert "|det P| = 1/2" in solution.reason
