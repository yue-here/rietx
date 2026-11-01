"""A moment through a series: the onset, the hold, the trajectory (WP-1329).

Everything here is **synthetic**.  The patterns are simulated from a structure
this file states, with a declared m(T) and a declared T_N, so the onset has a
right answer and a wrong one is a failure rather than a disagreement with a
tutorial.  The one real-data arm is the Cr₂WO₆ 4 K/150 K pair the tree
already carries (``tests/data/gsas2_hb2a_cr2wo6_*.dat``), refined as a
two-pattern series at the end of this file and marked slow.

What a plausible wrong implementation would pass, and therefore what each
block below turns on:

* **the onset is read off the verdicts, never off the values.**  A warm-started
  chain produces a smooth |m| column *through* the transition, so a threshold
  on the numbers would locate wherever the chain relaxed.  The tests assert on
  ``supported``, and one of them puts a value above the transition that a
  value-threshold would accept;
* **a held point keeps its value and loses its esd.**  Not zero (no fit
  measured zero) and not a small number with a small bar (which is the one
  misreading this whole arm exists to prevent);
* **the ± is the pattern spacing.**  A bracket is not a fitted critical point,
  and the field that says so is asserted rather than described;
* **the bracket is refused when its supported side did not converge.**  The
  asymmetry is measured here in both directions: a descent to nothing does not
  terminate and must not invalidate anything, while an ascent out of the floor
  terminates at once, so only a *supported* verdict from a truncated fit is
  suspect;
* **the two chain directions are compared.**  The failure a single pass cannot
  see is a moment carried across the transition by one warm start and not the
  other, so the agreement is a property of the pair;
* **a pattern that gives no verdict is left out, never read as held.**  A
  closed-shutter frame beside the transition (issue #481's blank, on a moment
  ramp) has its phase held and its modulus without an esd; counted as held it
  moved the bracket one pattern early and kept it confident;
* **a non-magnetic series is untouched.**  No rows, no diagnostics, and no
  ``ParameterTable`` built to find that out.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.report.schemas import MOMENT_SUPPORT_SIGMA, MomentEvidence
from rietx.schemas.common import Parameter
from rietx.schemas.results import Statistics
from rietx.schemas.sequential import (
    MagneticOnset,
    MagneticTrajectory,
    SeriesEntry,
    SeriesResult,
    locate_onset,
)
from rietx.schemas.structure import (
    MOMENT_FLOOR_MU_B,
    Atom,
    Cell,
    Moment,
    Phase,
    Structure,
)
from rietx.sequential import (
    _floor_unsupported_moments,
    _moment_diagnostics,
    _with_onset_agreement,
)

OUT = Path(__file__).resolve().parent / "output"

#: MnF₂ — rutile-structured, uniaxial, and a real collinear antiferromagnet, so
#: the moment axis the site allows is the one a reader expects.  The cell and
#: the fluorine coordinate are the ones ``test_magnetic.py`` states; the BNS
#: number is its ``MNF2_BNS``, the type-IV group with the moment along c.
MNF2_CELL = (4.8734, 4.8734, 3.3099, 90.0, 90.0, 90.0)
MNF2_BNS = "136.499"
LAMBDA_CW = 2.4

#: The declared order parameter: |m|(T) = m₀(1 − T/T_N)^β below T_N and nothing
#: above it.  β = 0.35 is a three-dimensional Heisenberg-ish value and is here
#: only to make the ramp curve — **nothing in WP-1329 fits it** (the
#: parametric form of m(T) is WP-1325's question and this WP's non-goal), so
#: no test below asserts on β.
M0_MU_B, T_N_K, BETA = 5.0, 67.0, 0.35

#: Coarse enough that the whole nine-pattern chain is a second or two, fine
#: enough that the magnetic lines are resolved at λ = 2.4 Å.
GRID = np.arange(12.0, 120.0, 0.2)


def _cell(a, b, c, alpha=90.0, beta=90.0, gamma=90.0) -> Cell:
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=alpha), beta=Parameter(value=beta),
                gamma=Parameter(value=gamma))


def _atom(label, species, xyz, *, moment=None, biso=0.4) -> Atom:
    x, y, z = xyz
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                biso=Parameter(value=biso, unit="A^2"), moment=moment)


def mnf2(mz: float, *, vary: bool = True) -> Phase:
    """MnF₂ with a moment of ``mz`` μ_B along c."""
    return Phase(
        name="MnF2", space_group="P 42/m n m", cell=_cell(*MNF2_CELL),
        atoms=[_atom("Mn", "Mn", (0.0, 0.0, 0.0), biso=0.3,
                     moment=Moment.from_values((0.0, 0.0, mz), "Mn2+",
                                               vary=vary)),
               _atom("F", "F", (0.3050, 0.3050, 0.0))],
        magnetic_symmetry=MNF2_BNS)


def nuclear_mnf2() -> Phase:
    """The same phase with no moment block at all — the absence arm."""
    return Phase(
        name="MnF2", space_group="P 42/m n m", cell=_cell(*MNF2_CELL),
        atoms=[_atom("Mn", "Mn", (0.0, 0.0, 0.0), biso=0.3),
               _atom("F", "F", (0.3050, 0.3050, 0.0))])


def neutron():
    return rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.4)


def moment_at(t_kelvin: float) -> float:
    """The declared |m|(T), exactly zero above T_N."""
    if t_kelvin >= T_N_K:
        return 0.0
    return M0_MU_B * (1.0 - t_kelvin / T_N_K) ** BETA


def simulate(mz: float, seed: int, *, scale: float = 200.0,
             background: float = 40.0) -> rx.PatternData:
    """A pattern from a stated moment, with the pattern's own Poisson noise.

    ``sigma`` is √counts rather than left to the default, because the whole
    arm turns on the *ratio* |m|/σ and a σ the caller did not state is a σ the
    test is not measuring against.
    """
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    # A moment block refuses to be free at exactly zero, so the paramagnetic
    # arm is simulated at the floor rather than at nothing: the two differ by
    # 1e-3 μ_B, whose |F_m|² is 1e-6 of a 1 μ_B one and is below the noise of
    # any pattern here by many orders.
    structure = Structure(phases=[mnf2(max(mz, MOMENT_FLOOR_MU_B))])
    instrument = neutron()
    blank = rx.PatternData(two_theta=GRID.tolist(),
                           intensity=np.ones_like(GRID).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    values["phases.0.scale"] = scale
    clean = np.asarray(model.evaluate(values), dtype=np.float64) + background
    counts = np.random.default_rng(seed).poisson(
        np.clip(clean, 1e-6, None)).astype(float)
    return rx.PatternData(two_theta=GRID.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.clip(counts, 1.0, None)).tolist())


def moment_plan(max_iter: int = 100) -> rx.RefinementPlan:
    """Scale and background, then the moment beside them."""
    return rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=max_iter),
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*", "phases.*.scale",
                            "instrument.background.c*"], max_iter=max_iter)])


#: The ramp's temperatures.  60 K and 75 K straddle T_N = 67 K, so the bracket
#: the chain should find is 60 → 75, i.e. 67.5 ± 7.5 — which contains the
#: declared T_N, and could not be tighter with these patterns however good each
#: fit is.  That is the point the ± exists to make.
RAMP_T = [15.0, 35.0, 55.0, 60.0, 75.0, 95.0]
RAMP_BRACKET = (60.0, 75.0)


def _row(path="phases.0.atoms.0.moment.dof0", *, magnitude, esd, supported,
         atom="Mn") -> MomentEvidence:
    return MomentEvidence(phase="MnF2", atom=atom, ion="Mn2+", path=path,
                          magnitude=magnitude, magnitude_esd=esd,
                          crystalaxis=[0.0, 0.0, magnitude],
                          approximation="dipole, <j0> only (g = 2)",
                          supported=supported)


def _hand_built(points, *, statuses=None) -> SeriesResult:
    """A ``SeriesResult`` assembled from verdicts, with no fit behind it.

    The onset, the trajectory and the two diagnostics are functions of the
    verdicts alone, so the unit block states verdicts directly.  That is not a
    convenience: it is what makes those tests independent of whether any
    particular solver run happens to converge.
    """
    statuses = statuses or ["converged"] * len(points)
    entries = []
    for i, ((x, magnitude, esd, supported), status) in enumerate(
            zip(points, statuses, strict=True)):
        entries.append(SeriesEntry(
            index=i, label=f"p{i}", x=x, status=status,
            magnetic=[_row(magnitude=magnitude, esd=esd, supported=supported)]))
    return SeriesResult(entries=entries, x_label="T (K)")


# ============================================================ the onset, alone

def test_the_onset_is_a_bracket_and_its_esd_is_half_the_gap():
    """Where the verdict switches, and what the ± is about.

    The bracket is the last released pattern and the first held one; the
    midpoint is the estimate and **half the gap** is the uncertainty, because
    what limits it is the spacing of the measurements and not the quality of
    any fit.  ``sense="falls"`` records which way round the transition runs, so
    a field-ramp that *gains* a moment with x is not silently read as a
    temperature ramp that loses one.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 2.0, 0.05, True),
                          (50.0, 0.02, 0.4, False), (70.0, 0.01, 0.4, False)])
    onset = series.magnetic_trajectory().onset

    assert onset.bracket == [30.0, 50.0]
    assert onset.bracket_labels == ["p1", "p2"]
    assert onset.x == pytest.approx(40.0)
    assert onset.x_esd == pytest.approx(10.0)
    assert onset.sense == "falls"
    assert onset.monotone and onset.bracket_verdicts_final is True
    assert (onset.n_supported, onset.n_held) == (2, 2)
    assert "WP-1325" in onset.note, "the ± must say what it is not"


def test_the_onset_is_read_off_the_verdicts_and_not_off_the_values():
    """The discriminating case: a *large* |m| above the transition.

    The third pattern's modulus is 1.9 μ_B — larger than the second pattern's
    released 0.9 — but its esd is 0.8, so it is 2.4σ and unsupported.  Any
    implementation that located the onset by thresholding |m|, or by looking
    for the largest step in it, puts the boundary in the wrong place here; one
    that reads ``supported`` puts it between p1 and p2.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 0.9, 0.05, True),
                          (50.0, 1.9, 0.8, False), (70.0, 0.01, 0.4, False)])
    onset = series.magnetic_trajectory().onset

    assert onset.bracket == [30.0, 50.0]
    # and the trap is real: the largest step in the value column is elsewhere
    values = series.magnetic_trajectory().value
    steps = np.abs(np.diff(values))
    assert int(np.argmax(steps)) == 0, "the biggest step is p0→p1, not the onset"


def test_a_moment_supported_everywhere_locates_no_onset():
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 3.0, 0.05, True)])
    onset = series.magnetic_trajectory().onset

    assert onset.x is None and onset.x_esd is None
    assert onset.sense == "none" and onset.bracket == []
    assert onset.n_held == 0
    assert "outside the measured window" in onset.note


def test_a_moment_supported_nowhere_locates_no_onset():
    """The negative control's shape: unsupported throughout, and no onset.

    A series with no moment anywhere must not produce a boundary — and the note
    has to say the result is about the window rather than about the specimen,
    since "no onset in 10-70 K" and "this specimen never orders" are different
    claims and only the first one was measured.
    """
    series = _hand_built([(10.0, 0.02, 0.4, False), (30.0, 0.01, 0.5, False),
                          (50.0, 0.03, 0.6, False)])
    onset = series.magnetic_trajectory().onset

    assert onset.x is None and onset.bracket == []
    assert (onset.n_supported, onset.n_held) == (0, 3)
    assert "about the window and not about the specimen" in onset.note


def test_an_interleaved_verdict_withholds_the_bracket_and_lists_the_switches():
    """Two boundaries are not one onset, and are not averaged into one.

    A verdict that switches more than once along the axis is a statement about
    the *fits* — a pattern the ladder rescued cold, a moment a warm start
    carried across — and the honest answer is the list of switches with no
    single number, not the mean of them.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 0.02, 0.4, False),
                          (50.0, 3.0, 0.05, True), (70.0, 0.01, 0.4, False)])
    onset = series.magnetic_trajectory().onset

    assert onset.x is None and not onset.monotone
    assert onset.boundaries == [[10.0, 30.0], [30.0, 50.0], [50.0, 70.0]]
    assert "switches 3 times" in onset.note


def test_no_bracket_means_no_claim_about_the_bracket_verdicts():
    """``bracket_verdicts_final`` is ``None`` in every state without a bracket.

    Root ``CLAUDE.md`` § "A declared name is a claim": a defaulted ``True``
    said "verdicts final" about a bracket that does not exist.  The five
    states are no rows, no verdict, supported everywhere, supported nowhere
    and interleaved; ``str`` must not call any of them unquotable.
    """
    onsets = {
        "no rows": locate_onset(MagneticTrajectory(path="")),
        "no verdict": _hand_built([(10.0, 4.0, None, None),
                                   (30.0, 3.0, None, None)]),
        "everywhere": _hand_built([(10.0, 4.0, 0.05, True),
                                   (30.0, 3.0, 0.05, True)]),
        "nowhere": _hand_built([(10.0, 0.02, 0.4, False),
                                (30.0, 0.01, 0.5, False)]),
        "interleaved": _hand_built([(10.0, 4.0, 0.05, True),
                                    (30.0, 0.02, 0.4, False),
                                    (50.0, 3.0, 0.05, True),
                                    (70.0, 0.01, 0.4, False)]),
    }
    for name, got in onsets.items():
        onset = (got if isinstance(got, MagneticOnset)
                 else got.magnetic_trajectory().onset)
        assert onset.x is None, name
        assert onset.bracket_verdicts_final is None, name
        assert "NOT QUOTABLE" not in str(onset), name
    # round-trips as the absent state, not as a coerced False
    back = MagneticOnset.model_validate(
        onsets["everywhere"].magnetic_trajectory().onset.model_dump(mode="json"))
    assert back.bracket_verdicts_final is None


def test_the_onset_is_ordered_by_the_axis_and_not_by_the_walk():
    """A cooling chain reports its onset on the temperature axis.

    The entries of a backward chain come back in *series* order already, but
    nothing stops a caller handing in patterns whose x descends.  The bracket
    is located after sorting by x, so the same six patterns give the same
    onset whichever order they were listed in — which is what makes a warming
    pass and a cooling pass comparable at all.
    """
    rising = [(10.0, 4.0, 0.05, True), (30.0, 2.0, 0.05, True),
              (50.0, 0.02, 0.4, False)]
    a = _hand_built(rising).magnetic_trajectory().onset
    b = _hand_built(list(reversed(rising))).magnetic_trajectory().onset

    assert a.bracket == b.bracket == [30.0, 50.0]
    assert a.x == b.x == pytest.approx(40.0)
    assert a.sense == b.sense == "falls"


def test_a_rising_sense_is_recorded_as_rising():
    """x is not always a temperature: a field ramp gains a moment with x."""
    onset = _hand_built([(0.0, 0.01, 0.4, False), (2.0, 0.02, 0.5, False),
                         (4.0, 1.5, 0.05, True)]).magnetic_trajectory().onset

    assert onset.sense == "rises"
    assert onset.bracket == [2.0, 4.0]


# ================================== the bracket, and a fit that stopped early

def test_a_supported_verdict_from_a_truncated_fit_makes_the_bracket_unquotable():
    """The fence, and it is the one the reseed rule cannot supply.

    ``supported`` is |m| against *that pattern's own* esd, so a fit stopped at
    its iteration cap can hand back a verdict about an intermediate state — a
    modulus that had not finished falling.  Measured on a starved chain below,
    that is exactly how a moment above the transition survives as a small
    confident number while Rwp stays fine and no other fence fires.
    """
    series = _hand_built(
        [(10.0, 4.0, 0.05, True), (30.0, 0.6, 0.05, True),
         (50.0, 0.02, 0.4, False)],
        statuses=["converged", "max_iter", "converged"])
    onset = series.magnetic_trajectory().onset

    assert onset.x == pytest.approx(40.0), "the bracket is still located"
    assert onset.bracket_verdicts_final is False
    assert onset.n_unconverged == 1
    assert "Do not quote it" in onset.note and "p1" in onset.note
    assert "NOT QUOTABLE" in str(onset)


def test_a_held_verdict_from_a_truncated_fit_does_not_invalidate_the_bracket():
    """The other half of the asymmetry, and it is the load-bearing half.

    A modulus descending to nothing **does not terminate**: |F_m|² ∝ m², so the
    column vanishes with the moment and the flat direction WP-1327 holds for the
    angles opens up for the modulus itself.  The first pattern above a
    transition can report ``max_iter`` with the modulus near 1e-6 μ_B — the
    null control below does, on one of its four patterns — and refusing the
    bracket for it would refuse every ordering
    transition there is.  So a truncated fit that came back *unsupported* is
    left alone.
    """
    series = _hand_built(
        [(10.0, 4.0, 0.05, True), (30.0, 2.0, 0.05, True),
         (50.0, 1e-6, 0.4, False)],
        statuses=["converged", "converged", "max_iter"])
    onset = series.magnetic_trajectory().onset

    assert onset.bracket_verdicts_final is True, "a held truncation is not a doubt"
    assert onset.n_unconverged == 1, "and it is still reported"
    assert "Do not quote it" not in onset.note


@pytest.mark.parametrize(("solver", "max_iter"), [("trf", 1), ("lm", 3)])
def test_the_ascent_out_of_the_floor_terminates_at_once(solver, max_iter):
    """The measurement the asymmetry above rests on, run rather than quoted.

    Seeded *at* the floor against a pattern carrying a real 4.5 μ_B, a few
    iterations per stage already reach a supported moment.  So a truncated fit
    cannot manufacture "unsupported" the way it can manufacture "supported",
    and the asymmetric fence is not a convenience.

    How few depends on the driver.  TRF's first trust region is sized from
    the start, so one iteration (4 evaluations) reaches 4.56 μ_B.  The LM
    driver's first step is Gauss-Newton's, and the moment's column vanishes
    at the floor, so its first three trials overshoot (λ = 0, 1, 10) and one
    iteration leaves the moment at 0.001.  Two reach 0.85 μ_B, unsupported,
    and three reach 2.05 μ_B, supported (WP-1938).
    """
    from rietx.params.vector import ParameterTable
    from rietx.report.magnetic import analyse_moments

    data = simulate(4.5, 4400, scale=6.0, background=300.0)
    ref = rx.Refinement(Structure(phases=[mnf2(MOMENT_FLOOR_MU_B)]), neutron(),
                        solver=solver)
    plan = moment_plan(max_iter=max_iter)
    # the declared stages' iteration budget; the closing stage is tests/test_closing_stage.py's
    plan.closing_window_tol = None
    result = ref.fit(data, plan=plan)
    table = ParameterTable(ref.structure, ref.instrument)
    row = analyse_moments(
        ref._model, table.decode(table.x0()), ref.structure,
        held=list(result.stages[-1].held),
        esd={p.path: p.stderr for p in result.parameters
             if p.stderr is not None})[0]

    assert result.status == "max_iter", "the point is that it was cut short"
    assert row.supported, (row.magnitude, row.magnitude_esd)
    assert row.magnitude > 1.0


# ========================================================= the trajectory view

def test_a_held_point_keeps_its_value_and_loses_its_esd():
    """Not zero, and not a small number with a small bar.

    The value is the modulus the fit reached and it is the numerator of the
    ratio that called the point unsupported, so it stays; the esd is withheld
    so that a plotted point cannot read as a small *measured* moment.
    ``arrays()`` turns the withheld one into the NaN an errorbar ignores.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (70.0, 0.067, 0.395, False)])
    traj = series.magnetic_trajectory()

    assert traj.value == [4.0, 0.067], "the held value is not overwritten"
    assert traj.stderr == [0.05, None]
    assert traj.supported == [True, False]
    assert traj.held == [False, True]
    assert traj.status == ["converged", "converged"]
    assert traj.atom == "Mn" and traj.ion == "Mn2+"
    _x, value, sd = traj.arrays()
    assert value[1] == pytest.approx(0.067)
    assert np.isnan(sd[1]) and sd[0] == pytest.approx(0.05)
    assert "HELD" in str(traj)


def test_a_pattern_without_the_site_is_skipped_rather_than_filled():
    """A gap in a trajectory is a real thing, for ``trajectory``'s reason."""
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 3.0, 0.05, True)])
    series.entries[1].magnetic = []
    traj = series.magnetic_trajectory()

    assert len(traj.value) == 1 and traj.x == [10.0]
    assert series.magnetic_sites() == ["phases.0.atoms.0.moment.dof0"]


def test_two_magnetic_sites_must_be_named_and_are_not_silently_picked():
    """"The moment" is not well defined on a two-sublattice structure."""
    series = _hand_built([(10.0, 4.0, 0.05, True)])
    series.entries[0].magnetic.append(
        _row(path="phases.0.atoms.1.moment.dof0", magnitude=1.0, esd=0.05,
             supported=True, atom="Mn2"))

    assert len(series.magnetic_sites()) == 2
    with pytest.raises(ValueError, match="name one by its path or label"):
        series.magnetic_trajectory()
    with pytest.raises(ValueError, match="name one by its path or label"):
        series.entries[0].moment()
    # named, either way round, it resolves
    assert series.magnetic_trajectory("Mn2").value == [1.0]
    assert series.entries[0].moment(
        "phases.0.atoms.1.moment.dof0").atom == "Mn2"


def test_a_magnetic_display_path_resolves_through_the_one_dispatch():
    """``resolve_trajectory`` is the single authority the plot layer calls.

    ``"magnetic."`` with nothing after it names the only site, which is what a
    one-sublattice structure has; the site may also be named by label or by
    path.  And the prefix is a *derived* path, so the caller that must skip the
    forward/backward comparison for a curve with no per-point σ skips this one
    too.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (70.0, 0.02, 0.4, False)])

    for name in ("magnetic.", "magnetic.Mn",
                 "magnetic.phases.0.atoms.0.moment.dof0"):
        traj = series.resolve_trajectory(name)
        assert isinstance(traj, MagneticTrajectory), name
        assert traj.supported == [True, False], name
    assert series.is_derived_path("magnetic.Mn")
    # and an ordinary dot-path still falls through untouched
    assert not isinstance(series.resolve_trajectory("phases.0.cell.a"),
                          MagneticTrajectory)


def test_a_magnetic_path_exports_through_to_table_and_write_csv(tmp_path):
    """``to_table`` aligns a derived curve by ``Trajectory.positions``.

    A magnetic trajectory that left ``positions`` empty was refused as "no
    pattern carries it" by every export, with every entry carrying the row.
    The held point exports its value with a blank esd, as it plots; a pattern
    without the site is a blank row, not a shifted one; and a site no pattern
    has is refused naming the magnetic sites, not the agreement phases.
    """
    series = _hand_built([(10.0, 4.0, 0.1, True), (40.0, 3.0, 0.1, True),
                          (55.0, 2.0, 0.1, True), (70.0, 0.001, 0.5, False)])
    series.entries[2].magnetic = []
    assert series.magnetic_trajectory().positions == [0, 1, 3]

    header, rows = series.to_table(paths=["magnetic.Mn"])
    assert header[-2:] == ["magnetic.Mn", "magnetic.Mn_esd"]
    assert [r[-2:] for r in rows] == [[4.0, 0.1], [3.0, 0.1], [None, None],
                                      [0.001, None]]

    out = tmp_path / "moment.csv"
    series.write_csv(out, paths=["magnetic.Mn"])
    assert out.read_text(encoding="utf-8").splitlines()[0].endswith(
        "magnetic.Mn,magnetic.Mn_esd")

    with pytest.raises(ValueError, match="no magnetic site 'Fe'") as err:
        series.to_table(paths=["magnetic.Fe"])
    assert "phases.0.atoms.0.moment.dof0" in str(err.value)
    assert "agreement index" not in str(err.value)


def test_the_moment_rows_survive_a_json_round_trip():
    """``SeriesEntry.magnetic`` is a stored field, so it has to reload."""
    series = _hand_built([(10.0, 4.0, 0.05, True), (70.0, 0.067, 0.395, False)])
    back = SeriesResult.model_validate(series.model_dump(mode="json"))

    assert back == series
    assert back.entries[1].magnetic[0].supported is False
    assert back.entries[1].magnetic[0].path.endswith("moment.dof0")
    assert back.magnetic_trajectory().onset.x == pytest.approx(40.0)


def test_the_trajectory_plots_and_marks_the_held_points():
    pytest.importorskip("matplotlib")
    series = _hand_built([(15.0, 4.6, 0.05, True), (35.0, 3.9, 0.05, True),
                          (55.0, 2.7, 0.06, True), (75.0, 0.02, 0.4, False),
                          (95.0, 0.01, 0.5, False)])
    OUT.mkdir(exist_ok=True)
    fig = series.plot(["magnetic.Mn"], path=str(OUT / "wp1329_trajectory.png"))
    ax = fig.axes[0]
    # the hollow-square series and the shaded onset bracket are both drawn
    assert any(line.get_marker() == "s" for line in ax.lines)
    assert (OUT / "wp1329_trajectory.png").exists()
    # and no filled measurement marker sits under a held point's square: the
    # filled circles are drawn at the supported points and nowhere else
    filled = [(float(px), float(py)) for line in ax.lines
              if line.get_marker() == "o" and line.get_markerfacecolor() != "none"
              for px, py in zip(line.get_xdata(), line.get_ydata(), strict=True)
              if np.isfinite(py)]
    assert sorted(filled) == [(15.0, 4.6), (35.0, 3.9), (55.0, 2.7)]
    # while the line still runs through every point, held ones included
    assert any(line.get_marker() in ("None", "", None) and len(line.get_xdata()) == 5
               for line in ax.lines)


# ============================================== the carry rule, on its mechanics

def test_the_floor_carry_scales_an_unsupported_modulus_and_keeps_its_direction():
    """What crosses the boundary when a pattern did not support its moment.

    The components are **scaled**, not zeroed: the modulus lands on its floor
    and the site's direction — the thing the angle DOFs encode, and the thing
    the powder often cannot see at all — is preserved.  And the source object
    is not touched, because the caller reads it back as
    ``fitted_structures()``.
    """
    structure = Structure(phases=[mnf2(3.0)])
    row = _row(magnitude=0.02, esd=0.4, supported=False)

    out, floored = _floor_unsupported_moments(structure, [row])

    assert floored == ["phases.0.atoms.0.moment.dof0"]
    components = out.phases[0].atoms[0].moment.values()
    assert components[2] == pytest.approx(MOMENT_FLOOR_MU_B)
    assert components[0] == components[1] == 0.0
    # unchanged in the source
    assert structure.phases[0].atoms[0].moment.values()[2] == pytest.approx(3.0)


def test_the_floor_carry_leaves_a_supported_site_alone_and_copies_nothing():
    structure = Structure(phases=[mnf2(3.0)])
    out, floored = _floor_unsupported_moments(
        structure, [_row(magnitude=3.0, esd=0.05, supported=True)])

    assert floored == []
    assert out is structure, "a supported chain must not pay for a deep copy"


def test_the_floor_carry_is_a_no_op_on_a_modulus_already_at_nothing():
    """There is nothing stale to reseed, so nothing is reported as reseeded."""
    structure = Structure(phases=[mnf2(1e-9)])
    out, floored = _floor_unsupported_moments(
        structure, [_row(magnitude=1e-9, esd=0.4, supported=False)])

    assert floored == [] and out is structure


# ============================================================ the ramp, refined

@pytest.fixture(scope="module")
def ramp():
    """Six patterns from the declared m(T), refined forward as one chain."""
    patterns = [simulate(moment_at(t), 1329 + i) for i, t in enumerate(RAMP_T)]
    series = rx.refine_sequential(
        patterns, Structure(phases=[mnf2(3.0)]), neutron(),
        plan=moment_plan(), x=RAMP_T, x_label="T (K)")
    return series, patterns


@pytest.mark.xdist_group("wp1329-ramp")
def test_the_ramp_recovers_the_declared_onset_and_holds_above_it(ramp):
    """WP-1329's acceptance, on a ramp whose T_N this file declared.

    Every pattern below T_N = 67 K reports the block released and every pattern
    above it reports it held; the bracket is the pair that straddles the
    declared T_N, and the declared value lies inside ``x ± x_esd`` — which it
    must, since the bracket *contains* it by construction once the verdicts are
    right.  The magnitudes are checked loosely against the declared m(T)
    because what WP-1329 owns is the verdict and the bracket; the magnitude
    is WP-1327's, tested there.
    """
    series, _patterns = ramp
    traj = series.magnetic_trajectory()

    assert [e.status != "diverged" for e in series.entries] == [True] * 6
    verdicts = dict(zip(traj.x, traj.supported, strict=True))
    for t, ok in verdicts.items():
        assert ok is (t < T_N_K), (t, ok)

    onset = traj.onset
    assert tuple(onset.bracket) == RAMP_BRACKET
    assert onset.monotone and onset.sense == "falls"
    assert onset.bracket_verdicts_final is True, onset.note
    assert abs(onset.x - T_N_K) <= onset.x_esd, (onset.x, onset.x_esd)

    # the released magnitudes track the declared order parameter, and every
    # one of them carries an esd while no held one does
    for t, value, sd, ok in zip(traj.x, traj.value, traj.stderr,
                                traj.supported, strict=True):
        if ok:
            assert value == pytest.approx(moment_at(t), abs=0.25), t
            assert sd is not None and sd > 0.0, t
        else:
            assert sd is None, t
            assert value < 0.1, (t, value)


@pytest.mark.xdist_group("wp1329-ramp")
def test_the_ramp_reports_both_codes_with_the_counts_and_the_bracket(ramp):
    """The two diagnostics, in the WP-1333 idiom: "N of M", and the bracket."""
    series, _patterns = ramp
    codes = {d.code: d for d in series.diagnostics}

    hold = codes["SEQUENTIAL_MOMENT_HOLD"]
    assert hold.level == "warning"
    assert hold.value == pytest.approx(2.0), "two patterns above T_N"
    assert "2 of 6 pattern(s)" in hold.message and "33%" in hold.message
    assert hold.where == ["phases.0.atoms.0.moment.dof0"]
    assert "at or below" in hold.message

    onset = codes["SEQUENTIAL_MOMENT_ONSET"]
    assert onset.level == "info"
    assert onset.value == pytest.approx(67.5)
    assert "60 → 75" in onset.message
    assert "set by the spacing of the patterns" in onset.message


@pytest.mark.xdist_group("wp1329-ramp")
def test_the_ramp_draws_obs_calc_diff_and_the_trajectory(ramp):
    """Rwp hides a locally bad fit, so every refinement here draws itself."""
    pytest.importorskip("matplotlib")
    from rietx.viz.plots import plot_result

    series, patterns = ramp
    OUT.mkdir(exist_ok=True)
    for t, result in zip(RAMP_T, series.entries, strict=True):
        assert result.statistics is not None
    for t, pattern in zip(RAMP_T, patterns, strict=True):
        ref = rx.Refinement(Structure(phases=[mnf2(3.0)]), neutron())
        plot_result(ref.fit(pattern, plan=moment_plan()),
                    path=str(OUT / f"wp1329_ramp_{t:g}K.png"))
    series.plot(["magnetic.Mn", "phases.0.scale"],
                path=str(OUT / "wp1329_ramp_trajectory.png"))
    assert (OUT / "wp1329_ramp_trajectory.png").exists()


def test_both_directions_agree_on_the_onset_and_the_row_says_so():
    """The check a single pass cannot make (WP-1329, WP-1076's machinery).

    The failure it is for: a chain that carried a moment across the transition
    in one direction and not in the other.  Run both ways, the onset row
    carries the *other* chain's bracket and stays ``info`` only when the two
    overlap — and the reverse chain is reachable on ``result.backward``, so a
    caller of the one-shot verb can see the trajectory the comparison is about.
    """
    patterns = [simulate(moment_at(t), 1329 + i) for i, t in enumerate(RAMP_T)]
    series = rx.refine_sequential(
        patterns, Structure(phases=[mnf2(3.0)]), neutron(), plan=moment_plan(),
        x=RAMP_T, x_label="T (K)", direction="both")

    forward = series.magnetic_trajectory().onset
    assert series.backward is not None
    backward = series.backward.magnetic_trajectory().onset
    assert tuple(forward.bracket) == tuple(backward.bracket) == RAMP_BRACKET

    row = next(d for d in series.diagnostics
               if d.code == "SEQUENTIAL_MOMENT_ONSET")
    assert row.level == "info"
    assert "backward chain brackets it 60 → 75" in row.message
    assert "the onset is the data's" in row.message
    # the comparison has been made, so the row no longer asks for it
    assert "direction='both'" not in row.suggestion
    assert "Quote the bracket" in row.suggestion
    # the reverse pass carries its own reading, not the forward one's
    assert any(d.code == "SEQUENTIAL_MOMENT_ONSET"
               for d in series.backward.diagnostics)


# Verdict columns for the two-chain comparison, on the ramp's own axis.  The
# backward chain is hand-built in axis order: ``locate_onset`` orders by x, so
# the walk direction does not enter the bracket.
_AXIS = (15.0, 45.0, 60.0, 75.0, 90.0)
_BRACKETED = (True, True, True, False, False)        # 60 → 75
_EVERYWHERE = (True, True, True, True, True)         # a carried moment
_INTERLEAVED = (True, False, True, False, False)     # three switches
_NOWHERE = (False, False, False, False, False)       # a floor never left


def _verdicts(flags) -> SeriesResult:
    return _hand_built([(x, 4.0 if ok else 0.01, 0.05 if ok else 0.4, ok)
                        for x, ok in zip(_AXIS, flags, strict=True)])


def _agreement(forward_flags, backward_flags):
    forward, back = _verdicts(forward_flags), _verdicts(backward_flags)
    rows = _with_onset_agreement(_moment_diagnostics(forward), forward,
                                 back)
    return [d for d in rows if d.code == "SEQUENTIAL_MOMENT_ONSET"]


def test_a_backward_bracket_is_reported_when_the_forward_chain_wrote_no_onset():
    """Forward "supported everywhere", backward 60 → 75: the case ``both`` is for.

    The forward pass writes no onset row when every pattern supports the
    moment, so a fold over the forward rows alone had nothing to fold the
    backward bracket into and the disagreement vanished.
    """
    (row,) = _agreement(_EVERYWHERE, _BRACKETED)
    assert row.level == "warning"
    assert row.value == pytest.approx(67.5)
    assert "the backward chain brackets the onset 60 → 75" in row.message
    assert "the forward chain located none" in row.message
    assert "every one of the 5 pattern(s) supports a moment" in row.message

    # and an interleaved backward verdict is a disagreement too
    (row,) = _agreement(_EVERYWHERE, _INTERLEAVED)
    assert row.level == "warning" and row.value is None
    assert "has no single onset" in row.message

    # while two chains that both read "supported everywhere" say nothing
    assert _agreement(_EVERYWHERE, _EVERYWHERE) == []
    assert _agreement(_NOWHERE, _NOWHERE) == []


@pytest.mark.parametrize("forward_flags, backward_flags, first, second", [
    (_EVERYWHERE, _NOWHERE, "supports none of the 5 pattern(s)",
     "supports all 5"),
    (_NOWHERE, _EVERYWHERE, "supports all 5", "supports none of the 5"),
])
def test_a_total_disagreement_between_the_chains_is_reported(
        forward_flags, backward_flags, first, second):
    """One chain supported on every pattern, the other on none: no bracket on
    either side, and still the extreme of what ``direction="both"`` is for.

    Skipping every monotone backward reading without a bracket wrote nothing
    here, in both orderings — and neither the forward diagnostics nor
    ``SEQUENTIAL_PATH_DEPENDENT`` (which divides by the held point's esd) said
    it anywhere else.
    """
    (row,) = _agreement(forward_flags, backward_flags)
    assert row.level == "warning" and row.value is None
    assert f"the backward chain {first}" in row.message
    assert f"the forward chain {second}" in row.message
    # one side is a floor that never climbed, not only a carried moment
    assert "never climbed out of the floor" in row.message
    assert "direction='both'" not in row.suggestion


def test_the_mixed_onset_row_blames_the_chain_that_located_none():
    """Each of the three ways of lacking an onset names the chain lacking it.

    Forward interleaved against a backward bracket used to read "the backward
    chain located no onset at all", quoting the backward chain's own
    successful-bracket sentence as the reason.
    """
    (row,) = _agreement(_INTERLEAVED, _BRACKETED)
    assert row.level == "warning"
    assert "located no onset" not in row.message
    assert "backward chain brackets it 60 → 75 (67.5 ± 7.5)" in row.message
    assert "switches 3 times" in row.message

    (row,) = _agreement(_BRACKETED, _EVERYWHERE)
    assert row.level == "warning"
    assert "backward chain located no onset at all" in row.message
    assert "every one of the 5 pattern(s) supports a moment" in row.message

    # an interleaved backward chain has boundaries, just not one of them
    (row,) = _agreement(_BRACKETED, _INTERLEAVED)
    assert "located no onset at all" not in row.message
    assert "backward chain located no single onset" in row.message

    (row,) = _agreement(_INTERLEAVED, _INTERLEAVED)
    assert row.level == "warning"
    assert "backward chain located no single onset either" in row.message

    (row,) = _agreement(_BRACKETED, _BRACKETED)
    assert row.level == "info" and "the onset is the data's" in row.message


_RISES = (False, False, False, True, True)          # 60 → 75, other side


@pytest.mark.parametrize("backward_flags, agrees", [
    (_BRACKETED, True), (_RISES, False)], ids=["same-sense", "opposite-sense"])
def test_brackets_in_one_place_agree_only_when_they_order_the_same_side(
        backward_flags, agrees):
    """Two chains bracketing 60 → 75, one reading the moment supported below
    it and the other above, overlap and still disagree about which side is
    ordered; the row called that agreement (#522 review, follow-up 2)."""
    (row,) = _agreement(_BRACKETED, backward_flags)
    assert "backward chain brackets it 60 → 75" in row.message
    assert (row.level == "info") is agrees
    assert ("the onset is the data's" in row.message) is agrees
    assert ("disagree about which side is ordered" in row.message) is not agrees


@pytest.mark.parametrize("forward_flags, backward_flags", [
    (_BRACKETED, _BRACKETED), (_BRACKETED, _EVERYWHERE),
    (_BRACKETED, _INTERLEAVED), (_INTERLEAVED, _BRACKETED),
    (_INTERLEAVED, _INTERLEAVED), (_BRACKETED, (True, False, False, False,
                                                False)),
])
def test_a_folded_onset_row_never_asks_for_the_run_that_just_ran(
        forward_flags, backward_flags):
    """Every branch of the fold replaces the forward row's advice to run
    ``direction='both'``, and only that advice.

    The forward row, written before the backward chain existed, says "run the
    series direction='both'"; folded, it is the answer to that run.  An
    interleaved forward row's advice never asked for it and is kept.
    """
    (row,) = _agreement(forward_flags, backward_flags)
    assert "direction='both'" not in row.suggestion
    if forward_flags == _INTERLEAVED:     # its own advice, which never asked
        assert row.suggestion.startswith(_OPEN_THE_SWITCHES)
    elif row.level == "warning":
        assert "series.backward.magnetic_trajectory()" in row.suggestion


def _quiet(flags) -> SeriesResult:
    """Five patterns that each gave **no verdict**: every fit diverged."""
    return _hand_built([(x, 0.3, 0.4, False) for x in _AXIS],
                       statuses=["diverged"] * len(_AXIS))


def _early(flags) -> SeriesResult:
    """``flags``'s verdicts with the last supported pattern of the bracket
    stopped at its cap, so that bracket is not quotable."""
    last = max(i for i, ok in enumerate(flags) if ok)
    return _hand_built([(x, 4.0 if ok else 0.01, 0.05 if ok else 0.4, ok)
                        for x, ok in zip(_AXIS, flags, strict=True)],
                       statuses=["max_iter" if i == last else "converged"
                                 for i in range(len(_AXIS))])


def _fold(forward: SeriesResult, back: SeriesResult):
    rows = _with_onset_agreement(_moment_diagnostics(forward), forward,
                                 back)
    return [d for d in rows if d.code == "SEQUENTIAL_MOMENT_ONSET"]


@pytest.mark.parametrize("forward, back, silent", [
    (lambda: _verdicts(_EVERYWHERE), lambda: _quiet(None), "backward"),
    (lambda: _quiet(None), lambda: _verdicts(_EVERYWHERE), "forward"),
    (lambda: _verdicts(_BRACKETED), lambda: _quiet(None), "backward"),
    (lambda: _quiet(None), lambda: _verdicts(_BRACKETED), "forward"),
], ids=["everywhere-vs-none", "none-vs-everywhere", "bracket-vs-none",
        "none-vs-bracket"])
def test_a_chain_that_gave_no_verdict_is_said_to_and_gets_no_cause(
        forward, back, silent):
    """A chain whose every pattern gave no verdict (all diverged, or all
    held) has nothing to disagree with.  The rows used to say the chains
    "disagree on every pattern they both judged", when they judged none in
    common, and blamed a warm start or a floor that nothing checked (review
    round 3, item 1)."""
    (row,) = _fold(forward(), back())
    assert f"{silent} chain gave no verdict on any pattern" in row.message
    for cause in ("warm start", "never climbed", "disagree on every pattern"):
        assert cause not in row.message, cause
    assert "series.backward.magnetic_trajectory()" not in row.suggestion
    assert "direction='both'" not in row.suggestion


def test_an_overlap_with_one_unquotable_bracket_names_it_and_asks_for_max_iter():
    """Overlapping brackets, only the **backward** one from a fit stopped at
    its cap: the row warns, and it used to say "the onset is the data's, not
    the ordering's" and hand out the carried-moment advice.  The reason is
    the stopped fit, and the fix is ``max_iter`` (review round 3, item 2)."""
    (row,) = _fold(_verdicts(_BRACKETED), _early(_BRACKETED))
    assert row.level == "warning"
    assert "the onset is the data's" not in row.message
    assert "the backward bracket" in row.message
    assert "stopped early" in row.message
    assert "max_iter" in row.suggestion
    assert "series.backward.magnetic_trajectory()" not in row.suggestion
    # the forward one unquotable: its own max_iter advice stands, named too
    (row,) = _fold(_early(_BRACKETED), _verdicts(_BRACKETED))
    assert row.level == "warning" and "max_iter" in row.suggestion
    assert "the forward bracket" in row.message
    assert "the onset is the data's" not in row.message


_OPEN_THE_SWITCHES = "Open the patterns either side of each switch"


@pytest.mark.parametrize("backward_flags", [_INTERLEAVED, _BRACKETED])
def test_an_interleaved_forward_row_keeps_its_own_advice(backward_flags):
    """The interleaved forward row never asked for ``direction="both"``, so
    the fold has nothing to replace there: with the same interleaved verdicts
    on both chains, "the pattern one chain supports and the other holds" does
    not exist (review round 3, item 3)."""
    (forward_row,) = [d for d in _moment_diagnostics(_verdicts(_INTERLEAVED))
                      if d.code == "SEQUENTIAL_MOMENT_ONSET"]
    assert forward_row.suggestion.startswith(_OPEN_THE_SWITCHES)
    (row,) = _agreement(_INTERLEAVED, backward_flags)
    assert row.suggestion == forward_row.suggestion


def test_a_pattern_above_the_rwp_fence_keeps_its_verdict():
    """WP-1469's fence is read, and deliberately not obeyed, by the onset.

    The fence reports and does not judge: it cannot tell a blank frame from a
    lasting change or a sound fit to fewer counts, and on the starved-chain
    ramp below it fires on a converged, correct pattern (see
    :attr:`MagneticTrajectory.measured`).  So an above-fence pattern that still
    gives a verdict gives it here too; a blank frame gives none for its own
    reason, the phase going unseen.
    """
    series = _verdicts(_BRACKETED)
    series.entries[3] = series.entries[3].model_copy(update={
        "rwp_fence": 0.0151, "statistics": Statistics(
            rwp=0.0166, rp=0.01, rexp=0.015, chi2=1.2, gof=1.1, n_points=100,
            n_free_parameters=5)})
    assert series.entries[3].above_fence

    traj = series.magnetic_trajectory()
    assert traj.measured == [True] * 5
    assert traj.onset.bracket == [60.0, 75.0]
    assert traj.onset.unmeasured_labels == []


# ================================================== the negative controls, refined

def test_a_series_with_no_moment_anywhere_reports_no_onset_and_holds_throughout():
    """Negative control: the same machinery on patterns that carry no moment.

    Every pattern unsupported, no onset, and a ``SEQUENTIAL_MOMENT_HOLD`` at
    100 % of the series.  What must *not* happen is a bracket somewhere inside
    a window where nothing ordered.
    """
    temperatures = [15.0, 35.0, 55.0, 75.0]
    patterns = [simulate(0.0, 3300 + i) for i in range(len(temperatures))]
    series = rx.refine_sequential(
        patterns, Structure(phases=[mnf2(3.0)]), neutron(), plan=moment_plan(),
        x=temperatures, x_label="T (K)")
    traj = series.magnetic_trajectory()

    assert traj.supported == [False] * 4, traj.value
    assert all(sd is None for sd in traj.stderr)
    assert traj.onset.x is None and traj.onset.bracket == []
    assert "no onset to locate" in traj.onset.note
    hold = next(d for d in series.diagnostics
                if d.code == "SEQUENTIAL_MOMENT_HOLD")
    assert "4 of 4 pattern(s) (100%" in hold.message
    assert not any(d.code == "SEQUENTIAL_MOMENT_ONSET"
                   for d in series.diagnostics)


def test_a_starved_chain_reports_a_supported_moment_above_the_transition_and_is_flagged():
    """The positive arm of the fence, beside the arm that must stay quiet.

    One pattern with a real 4.5 μ_B and three with none, refined twice: once
    with one iteration per stage and once with enough.  Starved, the modulus
    above the transition survives as a small **supported** number and the onset
    moves — so the run that a reader must not quote is the one the row refuses.
    Given enough iterations the same chain locates the boundary at the first
    pattern above the transition and the row goes quiet.

    This is also the measurement behind the manual's warning: neither
    the reseed fence nor the floor carry catches the starved case, because Rwp
    is fine and no pattern ever comes back unsupported for the carry to act on.
    """
    temperatures = [10.0, 70.0, 80.0, 90.0]
    patterns = [simulate(4.5, 4400, scale=6.0, background=300.0)]
    patterns += [simulate(0.0, 4401 + i, scale=6.0, background=300.0)
                 for i in range(3)]

    def run(max_iter):
        series = rx.refine_sequential(
            patterns, Structure(phases=[mnf2(4.5)]), neutron(),
            plan=moment_plan(max_iter), x=temperatures, x_label="T (K)")
        return series, series.magnetic_trajectory()

    starved, starved_traj = run(1)
    fed, fed_traj = run(20)

    # starved: a moment above the transition, supported, and the wrong bracket
    assert starved_traj.supported[1] is True, starved_traj.value
    assert starved_traj.value[1] > 0.1
    assert tuple(starved_traj.onset.bracket) != (10.0, 70.0)
    assert starved_traj.onset.bracket_verdicts_final is False
    starved_row = next(d for d in starved.diagnostics
                       if d.code == "SEQUENTIAL_MOMENT_ONSET")
    assert starved_row.level == "warning"
    assert "Do not quote it" in starved_row.message

    # fed: the boundary is at the first pattern above the transition, and quiet
    assert fed_traj.supported == [True, False, False, False], fed_traj.value
    assert tuple(fed_traj.onset.bracket) == (10.0, 70.0)
    assert fed_traj.onset.bracket_verdicts_final is True
    fed_row = next(d for d in fed.diagnostics
                   if d.code == "SEQUENTIAL_MOMENT_ONSET")
    assert fed_row.level == "info"


def test_an_unsupported_pattern_reseeds_its_successor_to_the_floor():
    """The hold along the series, measured on the chain that exercises it.

    The predecessor's modulus comes back unsupported *above* the floor, so the
    successor's warm start is the floor rather than that value, and
    ``SEQUENTIAL_MOMENT_HOLD`` names the patterns it happened to.  What it does
    **not** do is move the predecessor's own reported value — that number and
    its esd are the evidence the verdict was taken from.
    """
    temperatures = [10.0, 70.0, 80.0, 90.0]
    patterns = [simulate(4.5, 4400, scale=6.0, background=300.0)]
    patterns += [simulate(0.0, 4401 + i, scale=6.0, background=300.0)
                 for i in range(3)]
    series = rx.refine_sequential(
        patterns, Structure(phases=[mnf2(4.5)]), neutron(),
        plan=moment_plan(20), x=temperatures, x_label="T (K)")
    traj = series.magnetic_trajectory()

    hold = next(d for d in series.diagnostics
                if d.code == "SEQUENTIAL_MOMENT_HOLD")
    assert "reseeded to its floor" in hold.message
    assert "successor pattern(s)" in hold.message
    # the record the message is read from (WP-2003): each floored entry names
    # the modulus it received at the floor, and every warm start its source
    floored = [e for e in series.entries if e.floored]
    assert floored
    assert all(e.rung != "cold" for e in floored)
    assert all(e.label in hold.message for e in floored)
    assert all(hold.where[0] in e.floored for e in floored)
    assert [e.seeded_from for e in series.entries] == [None, 0, 1, 2]
    # the unsupported values are the fit's own, above the floor, with their esds
    # still on the evidence row even though the trajectory withholds them
    for entry, ok in zip(series.entries, traj.supported, strict=True):
        row = entry.moment()
        if not ok:
            assert row.magnitude_esd is not None, entry.label
            assert row.magnitude <= MOMENT_SUPPORT_SIGMA * row.magnitude_esd
            assert "unsupported, not as a small moment" in row.note


# =========================================================== absence for cause

def test_a_non_magnetic_series_carries_no_rows_and_no_moment_diagnostics():
    """Absence for cause, and it costs the chain nothing to establish.

    A phase that declares no moment produces no rows, no sites, no codes —
    and the guard is the compiled model's own frozen magnetic block, so a
    non-magnetic chain never builds a ``ParameterTable`` to find that out.
    """
    temperatures = [15.0, 35.0]
    patterns = [simulate(3.0, 5500 + i) for i in range(2)]
    series = rx.refine_sequential(
        patterns, Structure(phases=[nuclear_mnf2()]), neutron(),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"])]),
        x=temperatures)

    assert series.magnetic_sites() == []
    assert all(e.magnetic == [] for e in series.entries)
    assert not [d for d in series.diagnostics
                if d.code.startswith("SEQUENTIAL_MOMENT")]
    assert locate_onset(series.magnetic_trajectory()).x is None
    assert "no phase declared one" in series.magnetic_trajectory().onset.note


# ================================================ a frame that gives no verdict

def blank(seed: int, *, background: float = 40.0) -> rx.PatternData:
    """A closed-shutter frame: the background's Poisson noise and nothing else.

    Issue #481's blank, on a moment ramp.  The phase is invisible, so WP-1301
    holds its structural paths for the stage and the modulus comes back
    without an esd — a pattern that says nothing about the moment either way.
    """
    counts = np.random.default_rng(seed).poisson(
        np.full_like(GRID, background)).astype(float)
    return rx.PatternData(two_theta=GRID.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.clip(counts, 1.0, None)).tolist())


def _ramp_with_blank(where: int) -> SeriesResult:
    patterns = [simulate(moment_at(t), 1329 + i) for i, t in enumerate(RAMP_T)]
    patterns[where] = blank(7700 + where)
    return rx.refine_sequential(
        patterns, Structure(phases=[mnf2(3.0)]), neutron(), plan=moment_plan(),
        x=RAMP_T, x_label="T (K)")


def test_a_blank_frame_beside_the_transition_widens_the_bracket_rather_than_moving_it():
    """The #481 seam on a moment series: a blank frame must not place the onset.

    The 60 K pattern — the last ordered one — is replaced by a blank.  Read as
    *held*, it put the onset at 57.5 ± 2.5, a confident bracket that excludes
    the declared T_N = 67 K.  It gives no verdict, so it is left out: the
    bracket spans it, 55 → 75, and contains T_N, and both rows name it.
    """
    series = _ramp_with_blank(RAMP_T.index(60.0))
    traj = series.magnetic_trajectory()

    i = RAMP_T.index(60.0)
    assert traj.measured[i] is False
    assert traj.supported[i] is False and traj.stderr[i] is None
    assert traj.measured[:i] == [True] * i
    onset = traj.onset
    assert tuple(onset.bracket) == (55.0, 75.0)
    assert abs(onset.x - T_N_K) <= onset.x_esd, (onset.x, onset.x_esd)
    assert onset.n_unmeasured == 1 and onset.unmeasured_labels == ["p003"]
    assert onset.n_held == 2, "the blank is not counted as held"
    assert "spans p003" in onset.note
    assert "NO VERDICT" in str(traj)

    rows = {d.code: d for d in series.diagnostics}
    assert "1 more pattern(s) give no verdict at all (p003)" in (
        rows["SEQUENTIAL_MOMENT_HOLD"].message)
    assert "2 of 6 pattern(s)" in rows["SEQUENTIAL_MOMENT_HOLD"].message
    assert "spans p003" in rows["SEQUENTIAL_MOMENT_ONSET"].message
    assert rows["SEQUENTIAL_MOMENT_ONSET"].value == pytest.approx(65.0)


def test_a_blank_frame_inside_the_ordered_region_leaves_the_onset_where_it_was():
    """The same blank at 35 K, deep in the ordered region.

    Read as held it made the verdict switch three times and withheld the
    onset; left out, the clean ramp's bracket 60 → 75 comes back, and the
    pattern after the blank still climbs to its own moment from the carry.
    """
    series = _ramp_with_blank(RAMP_T.index(35.0))
    traj = series.magnetic_trajectory()

    assert traj.measured == [True, False, True, True, True, True]
    assert traj.onset.monotone
    assert tuple(traj.onset.bracket) == RAMP_BRACKET
    assert "spans" not in traj.onset.note
    assert traj.supported[2] is True
    assert traj.value[2] == pytest.approx(moment_at(55.0), abs=0.25)


def test_a_modulus_with_no_verdict_is_not_floored():
    """``supported is None`` is no verdict, and the carry leaves it alone.

    Two ways to reach it: a modulus the caller stated and held, and one
    WP-1301 held with a phase the pattern could not see.  Flooring either
    would overwrite a value no fit judged.
    """
    structure = Structure(phases=[mnf2(4.0)])
    row = _row(magnitude=4.0, esd=None, supported=None)
    out, floored = _floor_unsupported_moments(structure, [row])
    assert out is structure and floored == []


def test_a_diverged_pattern_gives_no_verdict_either():
    """A quarantined fit is not a measurement, so its verdict is left out."""
    series = _hand_built(
        [(10.0, 4.0, 0.1, True), (40.0, 3.0, 0.1, True),
         (70.0, 0.001, 0.5, False), (90.0, 0.001, 0.5, False)],
        statuses=["converged", "converged", "diverged", "converged"])
    traj = series.magnetic_trajectory()
    assert traj.measured == [True, True, False, True]
    assert traj.stderr[2] is None
    assert tuple(traj.onset.bracket) == (40.0, 90.0)
    assert traj.onset.unmeasured_labels == ["p2"]


# ============================================= the Cr₂WO₆ pair, as a series

@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-cr2wo6")
def test_the_cr2wo6_pair_as_a_series_gives_the_single_pattern_verdicts(
        cr2wo6_nuclear):
    """4 K released, 150 K held, as a two-pattern chain (the WP's acceptance).

    The 4 K pattern is the chain's first, refined cold from the same models
    under the same plan as WP-1327's single-pattern fit, so its row is
    **bit-identical** to that fit's report.  The 150 K pattern is warm-started
    from a supported 2.08 μ_B; what must match there is the *verdict*, because
    above T_N the modulus is a flat direction and its value is wherever the
    optimiser stopped in the valley.
    """
    from rietx.model import compiled
    from tests.test_acceptance_magnetic import (
        MAGNETIC_STAGES,
        _fit,
        _plan,
        _with_moment,
    )

    d4, d150 = cr2wo6_nuclear["d4"], cr2wo6_nuclear["d150"]
    ref4 = cr2wo6_nuclear["ref4"]
    start = _with_moment(ref4.structure, (2.0, 0.0, 0.0))
    # a bit-identity assertion declares its kernel path rather than inheriting
    # whatever an earlier test on this worker, or RIETX_COMPILED, left behind
    # (tests/CLAUDE.md § Quoting numbers); numpy is the tier's own oracle
    was = compiled.set_enabled(False)
    try:
        single, _ = _fit(start.model_copy(deep=True),
                         ref4.instrument.model_copy(deep=True), d4,
                         MAGNETIC_STAGES)
        (alone,) = single.report().magnetic

        series = rx.refine_sequential(
            [d4, d150], start, ref4.instrument.model_copy(deep=True),
            plan=_plan(MAGNETIC_STAGES), x=[4.0, 150.0], x_label="T (K)",
            labels=["4K", "150K"])
    finally:
        compiled.set_enabled(was)
    cold, hot = (e.moment() for e in series.entries)

    assert cold == alone, "the released pattern is the single fit, bit for bit"
    assert cold.supported is True and hot.supported is False
    assert hot.magnitude_esd is not None
    assert hot.magnitude <= MOMENT_SUPPORT_SIGMA * hot.magnitude_esd
    traj = series.magnetic_trajectory()
    assert traj.stderr[1] is None and traj.measured == [True, True]
    assert tuple(traj.onset.bracket) == (4.0, 150.0)
    assert traj.onset.sense == "falls" and traj.onset.bracket_verdicts_final is True


def test_a_trajectory_with_a_no_verdict_point_plots(tmp_path):
    """The no-verdict mark draws beside the held one, and the file is written."""
    pytest.importorskip("matplotlib")
    series = _hand_built(
        [(10.0, 4.0, 0.1, True), (40.0, 3.0, None, None),
         (70.0, 0.001, 0.5, False)])
    out = tmp_path / "blind.png"
    series.plot("magnetic.Mn", path=str(out))
    assert out.exists()


# ================================================ composing with solve_magnetic

@pytest.mark.slow
def test_solve_magnetic_on_the_first_pattern_gives_the_model_the_series_refines(
        tmp_path):
    """The two rungs compose: M-9 determines, WP-1329 follows it along the axis.

    ``solve_magnetic`` is run on the coldest pattern — the one with a moment to
    find — and the magnetic structure it refined is handed to
    ``refine_sequential`` as the starting model for the whole ramp.  The series
    then reports the moment released on the ordered patterns and held on the
    paramagnetic one, with an onset, from a model no human stated.

    It goes through the **magCIF** the solution writes rather than through the
    trial's in-memory structure, because that is the route a user has — the
    determination and the series need not be the same session — and it is
    therefore the one that has to keep working.
    """
    cold = simulate(4.5, 6600)
    hot = simulate(0.0, 6601)
    ref = rx.Refinement(Structure(phases=[nuclear_mnf2()]), neutron())
    ref.fit(cold, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("cell", ["phases.*.scale", "instrument.background.c*",
                          "phases.*.cell.*"])]))

    solution = rx.solve_magnetic(ref, cold, sites=["Mn"], ion="Mn2+")
    assert solution.verdict == "solved", solution.reason

    written = solution.write_magcifs(tmp_path)
    assert written, "a solved determination writes its class"
    best = f"class{solution.best.class_index}_"
    magcif = next(p for p in written if Path(p).name.startswith(best))
    solved = rx.Structure.from_cif(magcif)
    assert solved.phases[0].atoms[0].moment is not None
    assert solved.phases[0].magnetic_symmetry is not None

    series = rx.refine_sequential(
        [cold, hot], solved, ref.fitted_instrument, plan=moment_plan(),
        x=[10.0, 90.0], x_label="T (K)")
    traj = series.magnetic_trajectory()

    assert traj.supported == [True, False], traj.value
    assert traj.value[0] == pytest.approx(4.5, abs=0.4)
    assert traj.stderr[1] is None
    assert tuple(traj.onset.bracket) == (10.0, 90.0)


# ============================ a real ramp through an onset: Ba₂FeSbSe₅ on G4.1
#
# Row H of the magnetic milestone (WP-1329 task 5): the moment's trajectory
# measured on real data, ``direction="both"``.  Everything above is synthetic
# or a two-pattern pair; this is twelve patterns of one specimen, 1.5-200 K,
# through T_N = 58 K, and the first *k != 0* series in the tree.
#
# **Data.**  LLB G4.1 (Saclay) constant-wavelength neutron, lambda = 2.426 A,
# 2theta 2-81.9 deg at 0.1 deg, two columns (2theta, counts), the corrected
# patterns of S. Maier, M. W. Gaultois, N. Matsubara, W. Surta, F. Damay,
# S. Hebert, V. Hardy, D. Berthebaud and F. Gascoin, Phys. Rev. B 103, 054115
# (2021), doi:10.1103/PhysRevB.103.054115 (arXiv:2102.06484).  M. W. Gaultois, a
# co-author, released the twelve patterns under CC BY 4.0 for this repository
# (https://github.com/yue-here/rietx/pull/1073#issuecomment-6316397776; terms and
# reference values in ``tests/data/README.md``).  We acknowledge the Laboratoire
# Leon Brillouin for the provision of neutron beam time.  The paper reports
# T_N = 58 K from chi(T) and c_p(T), k = (1/2, 0, 1/2), the Shubnikov group
# P_a 2_1/m (BNS 11.55, irreps Gamma4/Gamma8) with the moment along b, and
# m_y = 4.13(4) mu_B per Fe at 1.5 K with the two Fe moments constrained equal
# (p. 9; "5.8 mu_B" without the constraint, which is 4.13 * sqrt(2): the powder
# measures only the quadrature sum of the two orbits, so the tie is the paper's
# assumption and not a measurement).
#
# **Nothing here is tuned to this ramp.**  The plan is the one ``solve_magnetic``
# ships (``SOLVE_STAGE_PATHS``: moduli, moment, then the fuller stage) and the
# model is the one ``solve_magnetic`` selects on the 1.5 K pattern from the
# nuclear fit alone (class 11.55 S2(a,b); run 2026-10-20, recorded in the PR),
# built here directly so the test does not repeat that ten-minute search.  The
# ties are the statement's own (``anti_translation_ties``), the paper's
# equal-moment tie, and one Biso per parent site.  The starting nuclear model is
# the published 293 K single-crystal Pnma structure of Wang, Greenfield and
# Kovnir, J. Solid State Chem. 242, 22 (2016), refined here against the 1.5 K
# pattern.
#
# **Protocol** (revised 2026-10-21, measured on these patterns): the fit starts
# at 5.2 deg, above the direct-beam tail; the background is the P-spline
# ``auto_background`` sizes to the fitted range (it replaced a 4-term Chebyshev
# that bent the wrong way under the lowest magnetic line); the 28 child Biso are
# tied to their 7 parent sites (freed one by one, the Fe children alone ran to
# -8..+24 A^2).  Asymmetry stays at 0: one tied axial-divergence parameter
# fitted on the 100 K pattern lowers chi^2 but draws a low-angle tail the data
# do not have.  The unmodelled low-angle centroid shift that remains (about
# -50 mdeg at the 9.35 deg magnetic line, cot 2theta-shaped) is a named
# systematic worth +0.03 to +0.06 mu_B on the 1.5 K moment.  No magnetic width:
# with the Biso tied it costs BIC (-5.8 to -9) at every temperature measured.
# The parent Biso are not determined by these data (esds 2.6-5.8 A^2 in the
# nuclear fit; Ba1 comes out at -1.2(3.8) A^2 there and its child at
# -0.3(1.2) A^2 at 1.5 K, so BISO_NEGATIVE stays on); one overall B, free or
# held at 0.8 A^2, moves the 1.5 K moment by -0.04 and +0.004 mu_B, inside
# 0.3 esd, so per-site B is kept.
#
# **Tier: characterisation, never validation.**  The published 4.13(4) mu_B is a
# same-pattern result under another code and another protocol (FullProf,
# Gamma4/Gamma8; its profile, background and form-factor settings are not
# published), so it bounds the answer and verifies nothing about the physics.
# The onset has an independent reference (T_N from bulk probes), but a powder
# verdict can only see an order parameter once it is above its own esd, so the
# bracket is asserted to lie at or below T_N, within one grid step of it, and
# never above.  The assertions below were written after the first run, which is
# stated here and in the PR; none was widened afterwards, and the 2026-10-21
# protocol revision left every one of them unchanged.

BA_DATA = Path(__file__).resolve().parent / "data"
BA_TEMPS = [1.5, 10.0, 20.0, 30.0, 40.0, 45.0, 50.0, 55.0, 65.0, 100.0,
            150.0, 200.0]
BA_T_N = 58.0
BA_PUBLISHED_MU_B = 4.13
BA_LAMBDA = 2.426
#: Wang, Greenfield & Kovnir (2016) at 293 K, Pnma, a, b, c = 12.650, 9.140,
#: 9.170 A: label, species, x, y, z, U_iso (A^2)
BA_ATOMS = [
    ("Ba1", "Ba", 0.17567, -0.00762, 0.37692, 0.0127),
    ("Sb1", "Sb", 0.02806, 0.25, 0.01240, 0.0133),
    ("Se1", "Se", -0.05782, -0.03987, 0.18326, 0.0133),
    ("Se2", "Se", 0.00716, -0.25, 0.54270, 0.0131),
    ("Se3", "Se", 0.21724, 0.25, 0.11656, 0.0129),
    ("Se4", "Se", 0.27926, 0.25, 0.60793, 0.0129),
    ("Fe1", "Fe", 0.09763, 0.25, 0.66698, 0.0107),
]


def _ba_tag(t: float) -> str:
    return "001p5" if t == 1.5 else f"{int(t):03d}"


#: below 5.2 deg 2theta is the direct-beam tail of the corrected patterns: the
#: fit starts above it rather than asking the background to follow it
BA_LOW = 5.2


def _ba_pattern(t: float):
    return rx.read_pattern(
        BA_DATA / f"llb_g41_ba2fesbse5_{_ba_tag(t)}K.xy"
    ).model_copy(update={"excluded_regions": [(0.0, BA_LOW)]})


@pytest.fixture(scope="module")
def ba2fesbse5_ramp():
    """The nuclear fit at 1.5 K, the magnetic statement, and the ramp both ways."""
    # the fixture's numbers declare their kernel path rather than inheriting
    # whatever an earlier test on this worker, or RIETX_COMPILED, left behind
    # (tests/CLAUDE.md § Quoting numbers); numpy is the tier's own oracle
    from rietx.model import compiled

    was = compiled.set_enabled(False)
    try:
        return _ba2fesbse5_ramp_fits()
    finally:
        compiled.set_enabled(was)


def _ba2fesbse5_ramp_fits():
    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.crystallography.magnetic.supercell import (
        anti_translation_ties,
        magnetic_supercell,
    )
    from rietx.strategy.magnetic import (
        SOLVE_SEED_MU_B,
        SOLVE_STAGE_NAMES,
        SOLVE_STAGE_PATHS,
    )

    def par(v, **kw):
        return Parameter(value=v, **kw)

    parent = rx.Phase(
        name="Ba2FeSbSe5", space_group="P n m a",
        cell=rx.Cell(a=par(12.650), b=par(9.140), c=par(9.170),
                     alpha=par(90.0), beta=par(90.0), gamma=par(90.0)),
        atoms=[rx.Atom(label=lab, species=sp, x=par(x), y=par(y), z=par(z),
                       occ=par(1.0), biso=par(u * 8.0 * np.pi ** 2, unit="A^2"))
               for lab, sp, x, y, z, u in BA_ATOMS])
    first = _ba_pattern(1.5)
    inst = rx.Instrument.constant_wavelength_neutron(BA_LAMBDA)
    inst.profile.w.value = 0.0025
    inst.profile.x.value = 0.0
    # the background rietx sizes to the data over the fitted range (a P-spline,
    # 3 deg knots), seeded; asymmetry stays at its default 0 (see the PR)
    inst.background = rx.auto_background(
        first, two_theta_limits=(BA_LOW, float(first.two_theta[-1])),
        wavelength=BA_LAMBDA, seed=True).background

    bkg = ["phases.0.scale", "instrument.background.c*"]
    width = [f"instrument.profile.{k}" for k in "uvwx"]
    cell = ["instrument.zero_shift", "phases.0.cell.*"]
    stages = [("scale_bkg", bkg), ("zero", bkg + cell[:1]), ("cell", bkg + cell),
              ("widths", bkg + cell + width),
              ("coords", bkg + cell + width + ["phases.0.atoms.*.dof.*"]),
              ("biso", bkg + cell + width + ["phases.0.atoms.*.dof.*",
                                             "phases.0.atoms.*.biso"])]
    nuclear_plan = rx.RefinementPlan(
        stages=[rx.Stage(n, list(p), max_iter=200) for n, p in stages],
        intermediate_ftol=1e-6)
    ref = rx.Refinement(rx.Structure(phases=[parent]), inst, history=False)
    nuclear = ref.fit(first, plan=nuclear_plan)

    fitted = ref.fitted_structure.phases[0]
    fe = next(a for a in fitted.atoms if a.label == "Fe1")
    cand = next(c for c in candidates(
        fitted.space_group, (fe.x.value, fe.y.value, fe.z.value),
        ("1/2", "0", "1/2")) if c.bns_number == "11.55" and c.label.startswith("S2"))
    statement = magnetic_supercell(
        fitted, candidate=cand, magnetic_species="Fe", ion="Fe3+",
        magnitude=SOLVE_SEED_MU_B, nuclear_group="magnetic")
    child = rx.Structure(phases=[statement.phase])
    moment_atoms = [j for j, a in enumerate(statement.phase.atoms)
                    if a.moment is not None]
    first_child: dict[int, int] = {}
    biso_ties = []
    for j, (parent_atom, _coset) in enumerate(statement.site_map):
        if parent_atom in first_child:
            biso_ties.append((f"phases.0.atoms.{j}.biso",
                              f"phases.0.atoms.{first_child[parent_atom]}.biso"))
        else:
            first_child[parent_atom] = j

    def constrain(_i, r):
        # the statement's own ties, then the paper's equal-moment tie
        ties = anti_translation_ties(r.structure.phases[0], 0)
        for target, source, scale, offset in ties:
            r.tie(target, source, scale=scale, offset=offset)
        followers = {t for t, *_ in ties}
        free = [j for j in moment_atoms
                if f"phases.0.atoms.{j}.moment.dof0" not in followers]
        for j in free[1:]:
            r.tie(f"phases.0.atoms.{j}.moment.dof0",
                  f"phases.0.atoms.{free[0]}.moment.dof0", scale=1.0)
        # one Biso per parent site: every child of a parent atom follows the
        # first (``site_map``), as tie_to_parent does; freed one by one, the 28
        # child Biso ran to -8..+24 A^2 on the Fe children alone
        for target, source in biso_ties:
            r.tie(target, source, scale=1.0)

    plan = rx.RefinementPlan(stages=[
        rx.Stage(n, list(p)) for n, p in zip(SOLVE_STAGE_NAMES,
                                              SOLVE_STAGE_PATHS, strict=True)])
    series = rx.refine_sequential(
        [_ba_pattern(t) for t in BA_TEMPS], child, ref.fitted_instrument,
        plan=plan, x=BA_TEMPS, x_label="T (K)",
        labels=[f"{t:g}K" for t in BA_TEMPS], direction="both",
        constrain=constrain)
    return {"nuclear": nuclear, "series": series}


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-ba2fesbse5")
def test_ba2fesbse5_ramp_the_moment_grows_below_the_onset_both_ways(
        ba2fesbse5_ramp):
    """Real ramp, k = (1/2, 0, 1/2): supported below ~T_N, held above, both chains.

    What a competent refiner asserts of twelve patterns through an ordering
    transition: the ordered moment is supported at every temperature up to
    50 K and not at any from 55 K; it grows monotonically on cooling; the
    onset is a bracket that lies at or below the bulk T_N (a bracket above it
    would be a moment carried through the transition by the warm start) and
    within one grid step of it; the forward and backward chains return the same
    verdicts, the same bracket and moduli that differ by less than their esds;
    the moment lies along b; and the 1.5 K modulus sits within about 12 % of
    the published 4.13(4) mu_B (an envelope: a different protocol, not agreement).
    """
    series = ba2fesbse5_ramp["series"]
    assert ba2fesbse5_ramp["nuclear"].status == "converged"
    # the fits the verdicts rest on converged, in both chains (all 24 do under
    # this protocol); the assertion covers the ordered side and 55 K, because a
    # moment held in the paramagnetic valley is not a fit result and its fit
    # may stop on its budget without moving a verdict
    for chain in (series, series.backward):
        assert [e.status for e, t in zip(chain.entries, BA_TEMPS, strict=True)
                if t <= 55.0] == ["converged"] * 8

    site = series.magnetic_sites()[0]
    fwd = series.magnetic_trajectory(site)
    assert series.backward is not None
    bwd = series.backward.magnetic_trajectory(site)
    assert fwd.x == BA_TEMPS

    # supported up to 50 K, never from 55 K; the paramagnetic side is not
    # merely unsupported on one pattern, it is on every one that gives a verdict
    for traj in (fwd, bwd):
        for t, sup in zip(traj.x, traj.supported, strict=True):
            assert sup is (t <= 50.0), (t, sup)
    ordered = [i for i, t in enumerate(BA_TEMPS) if t <= 50.0]
    assert all(fwd.stderr[i] is not None for i in ordered)

    # grows on cooling: strictly through 20-55 K, and by many sigma overall
    values = fwd.value
    assert all(values[i + 1] < values[i] for i in range(2, BA_TEMPS.index(55.0))), values
    i50 = BA_TEMPS.index(50.0)
    sigma = float(np.hypot(fwd.stderr[0], fwd.stderr[i50]))
    assert values[0] - values[i50] > 5.0 * sigma

    # the onset: a falling, monotone bracket, at or below T_N and within a step
    for traj in (fwd, bwd):
        onset = traj.onset
        assert onset.sense == "falls" and onset.monotone
        assert onset.bracket_verdicts_final is True
        lo, hi = onset.bracket
        assert 45.0 <= lo < hi <= BA_T_N, onset.bracket
        assert BA_T_N - hi <= 5.0, onset.bracket
    assert fwd.onset.bracket == bwd.onset.bracket

    # the two chains agree, per pattern, within their combined esd
    for i in ordered:
        d = abs(fwd.value[i] - bwd.value[i])
        assert d < 3.0 * float(np.hypot(fwd.stderr[i], bwd.stderr[i])), (BA_TEMPS[i], d)
    onset_rows = [d for d in series.diagnostics
                  if d.code == "SEQUENTIAL_MOMENT_ONSET"]
    assert onset_rows and all(d.level != "warning" for d in onset_rows)

    # along b, whatever the two Fe orbits' split (tied equal, as published)
    row = series.entries[0].moment(site)
    assert abs(row.crystalaxis[1]) / row.magnitude > 0.99, row.crystalaxis

    # the published value bounds the 1.5 K modulus; it does not validate it
    assert row.supported is True and row.magnitude_esd < 0.15
    assert abs(row.magnitude - BA_PUBLISHED_MU_B) <= 0.5, row.magnitude
