"""A soft restraint on a linear sum of parameters across phases (WP-1942, #212).

`LinearRestraint` lives on `Structure.restraints` and compiles to one row
√w·(Σ cₖ·pₖ − target)/σ inside the soft-restraint block, beside the phases'
own rows.  `elemental_ratio_restraint` builds one for a conserved elemental
ratio from the phases' element counts and cell volumes.

Two synthetic two-phase cases carry the acceptance.  Cu and Ni, both fcc, on
one cell edge: their form factors differ by about one electron at every s, so
the pattern fixes the total and leaves the partition flat (an unrestrained
fit's weight fraction carries an esd near 1), and only the declared ratio
decides it.  The same pair on their own cells (3.615 and 3.524 Å): the lines
separate at high angle, the data measure the partition themselves, and a
declared ratio the data contradict is reported as `RESTRAINT_TENSION`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import PatternData, Refinement, Stage
from rietx.model.forward import compile_model
from rietx.model.restraints import (
    elemental_ratio_restraint,
    restraint_partials,
    restraint_residual,
    summarise_restraints,
)
from rietx.optimize.qpa import phase_zmv
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.structure import Atom, Cell, LinearRestraint, Phase, Structure

OUT = Path(__file__).parent / "output"
S_CU, S_NI = 1.0e-3, 0.6e-3
FLAT = (3.60, 3.60)          # one edge: the partition is flat
SEPARATE = (3.615, 3.524)    # the metals' own edges: the data measure it
TT = np.arange(30.0, 130.0, 0.02)
STAGE = ["phases.*.scale", "instrument.background.*"]


def _fcc(name: str, species: str, a: float, scale: float) -> Phase:
    return Phase(name=name, space_group="F m -3 m", cell=Cell.cubic(a),
                 atoms=[Atom(label=species, species=species, x=P(value=0.0),
                             y=P(value=0.0), z=P(value=0.0), biso=P(value=0.5))],
                 scale=P(value=scale, min=0.0))


def _pair(cells, scales=(S_CU, S_NI), restraints=()) -> Structure:
    return Structure(phases=[_fcc("Cu", "Cu", cells[0], scales[0]),
                             _fcc("Ni", "Ni", cells[1], scales[1])],
                     restraints=list(restraints))


def _instrument() -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=1.5406)
    ins.source.dispersion = None      # declared: the test pins numbers
    ins.profile.w.value = 8e-3
    return ins


def _pattern(cells, seed: int = 3, scales=(S_CU, S_NI)) -> PatternData:
    truth = _pair(cells, scales)
    blank = PatternData(two_theta=TT.tolist(), intensity=np.zeros_like(TT).tolist())
    model = compile_model(truth, _instrument(), blank, mode="rietveld")
    table = ParameterTable(truth, _instrument())
    y = model.evaluate(table.decode(table.x0())) + 50.0
    y = np.random.default_rng(seed).poisson(y).astype(float)
    return PatternData(two_theta=TT.tolist(), intensity=y.tolist())


def _truth(cells, scales=(S_CU, S_NI)) -> tuple[float, float]:
    """(true W_Cu, true moles Cu / moles Ni) of the synthetic specimen."""
    z = [phase_zmv("F m -3 m", (a, a, a, 90.0, 90.0, 90.0), [(sp, 0, 0, 0, 1.0)])
         for sp, a in zip(("Cu", "Ni"), cells, strict=True)]
    w = scales[0] * z[0].zmv / (scales[0] * z[0].zmv + scales[1] * z[1].zmv)
    ratio = (scales[0] * z[0].cell_volume * z[0].element_counts["Cu"]
             / (scales[1] * z[1].cell_volume * z[1].element_counts["Ni"]))
    return w, ratio


def _fit(cells, pattern, restraints=()):
    """One scale-and-background stage from equal starting scales."""
    ref = Refinement(_pair(cells, (8e-4, 8e-4), restraints), _instrument(),
                     history=False)
    return ref.run_stage(pattern, Stage("scales", STAGE))


def _ratio_row(cells, ratio, sigma):
    """The ratio row as a caller would declare it: at refined-scale values,
    here the truth's, so D₀ is the specimen's own denominator."""
    return elemental_ratio_restraint(_pair(cells), "Cu", "Ni", ratio, sigma)


# ----------------------------------------------------------------------
# the schema
# ----------------------------------------------------------------------
def test_the_row_round_trips_through_json():
    row = LinearRestraint(terms=[("phases.0.scale", 1.0), ("phases.1.scale", -2.5)],
                          target=0.1, sigma=0.02, weight=3.0, label="Cu/Ni",
                          occupancies={"phases.0.atoms.0.occ": 1.0,
                                       "phases.1.atoms.0.occ": 0.5})
    s = _pair(FLAT, restraints=[row])
    back = Structure.model_validate_json(s.model_dump_json())
    assert back == s and back.restraints == [row]


def test_a_structure_without_rows_reads_as_before():
    """Additive and defaulted: a stored structure with no key opens unchanged."""
    s = _pair(FLAT)
    stored = s.model_dump(mode="json")
    del stored["restraints"]
    assert Structure.model_validate(stored) == s


@pytest.mark.parametrize("terms, match", [
    ([("phases.0.scale", 1.0), ("phases.0.scale", 2.0)], "twice"),
    ([("phases.*.scale", 1.0)], "globs"),
    ([("phases.0.scale", 0.0)], "nonzero"),
    ([("phases.0.scale", float("nan"))], "finite"),
    ([], "at least 1"),
])
def test_a_malformed_row_is_refused(terms, match):
    with pytest.raises(ValueError, match=match):
        LinearRestraint(terms=terms, sigma=1.0)


def test_a_row_naming_a_phase_the_structure_lacks_is_refused():
    row = LinearRestraint(terms=[("phases.2.scale", 1.0)], sigma=1.0)
    with pytest.raises(ValueError, match="has 2 phase"):
        _pair(FLAT, restraints=[row])


def test_a_row_naming_an_entry_the_table_lacks_names_itself():
    row = LinearRestraint(terms=[("phases.0.nonesuch", 1.0)], sigma=1.0)
    with pytest.raises(ValueError, match="linear restraint 0 names phases.0.nonesuch"):
        _fit(FLAT, _pattern(FLAT), [row])


def test_a_phase_removed_by_an_edit_takes_its_carried_row_with_it():
    """The row is renumbered with the phases, through ``carry_restraints``:
    one naming a phase the edit removed is dropped and named."""
    row = LinearRestraint(terms=[("phases.0.scale", 1.0), ("phases.1.scale", -1.0)],
                          sigma=1.0)
    keep = LinearRestraint(terms=[("phases.1.scale", 1.0)], sigma=1.0)
    ref = Refinement(_pair(SEPARATE, restraints=[row, keep]), _instrument(),
                     history=False)
    edited = ref.structure.model_copy(update={"phases": [ref.structure.phases[1]]})
    with pytest.warns(UserWarning, match="linear restraint 0"):
        ref.edit(structure=edited)
    assert [r.terms for r in ref.structure.restraints] == [[("phases.0.scale", 1.0)]]


def test_a_trailing_phase_removed_by_an_edit_drops_the_row_that_named_it():
    """``atom_moves`` gives no key to a phase number past the new list, so the
    carry reads such a path as gone rather than refusing the edit."""
    row = LinearRestraint(terms=[("phases.1.scale", 1.0)], sigma=1.0)
    ref = Refinement(_pair(SEPARATE, restraints=[row]), _instrument(), history=False)
    edited = ref.structure.model_copy(update={"phases": [ref.structure.phases[0]]})
    with pytest.warns(UserWarning, match="linear restraint 0"):
        ref.edit(structure=edited)
    assert ref.structure.restraints == []


def test_deleting_a_row_in_an_edit_that_renumbers_phases_is_refused():
    """The place rule of a phase's own list (WP-2121): the row behind a deleted
    one moves up a place, and in the same edit that renumbers its phases its
    paths could mean either numbering."""
    third = _fcc("Al", "Al", 4.05, 5e-4)
    rows = [LinearRestraint(terms=[("phases.0.scale", 1.0)], sigma=1.0),
            LinearRestraint(terms=[("phases.1.scale", 1.0)], sigma=1.0, label="ni")]
    s = Structure(phases=[*_pair(SEPARATE).phases, third], restraints=rows)
    ref = Refinement(s, _instrument(), history=False)
    edited = ref.structure.model_copy(update={
        "phases": ref.structure.phases[1:], "restraints": rows[1:]})
    with pytest.raises(ValueError, match="linear restraint 0 differs"):
        ref.edit(structure=edited)


# ----------------------------------------------------------------------
# compile, residual, partials, report
# ----------------------------------------------------------------------
def test_the_row_is_the_coefficient_sum_and_its_partials_are_the_coefficients():
    row = LinearRestraint(terms=[("phases.0.scale", 2.0), ("phases.1.scale", -3.0),
                                 ("phases.1.cell.a", 0.25)],
                          target=0.5, sigma=0.01, weight=4.0)
    s = _pair(SEPARATE, restraints=[row])
    model = compile_model(s, _instrument(), _pattern(SEPARATE), mode="rietveld")
    table = ParameterTable(s, _instrument())
    values = table.decode(table.x0())
    total = 2.0 * S_CU - 3.0 * S_NI + 0.25 * SEPARATE[1]
    pref = np.sqrt(4.0) / 0.01
    assert float(restraint_residual(model.restraints, values)[0]) == pytest.approx(
        (total - 0.5) * pref, rel=1e-14)
    r_phys = restraint_partials(model.restraints, values, table)
    idx = table._paths
    assert r_phys[0, idx["phases.0.scale"]] == pytest.approx(2.0 * pref, rel=1e-15)
    assert r_phys[0, idx["phases.1.scale"]] == pytest.approx(-3.0 * pref, rel=1e-15)
    assert r_phys[0, idx["phases.1.cell.a"]] == pytest.approx(0.25 * pref, rel=1e-15)
    assert np.count_nonzero(r_phys) == 3
    rep = summarise_restraints(model.restraints, values)
    (r,) = rep.rows
    assert (r.kind, r.path, r.phase_index) == ("linear", "restraints.0", None)
    assert r.computed == pytest.approx(total, rel=1e-14)


def test_the_row_is_rietveld_only():
    row = LinearRestraint(terms=[("phases.0.scale", 1.0)], sigma=1.0)
    s = _pair(SEPARATE, restraints=[row])
    model = compile_model(s, _instrument(), _pattern(SEPARATE), mode="lebail")
    assert model.restraints is None


# ----------------------------------------------------------------------
# the helper
# ----------------------------------------------------------------------
def test_the_ratio_row_reads_the_ratio_minus_its_target_at_the_declared_scales():
    """At the scales it was declared at, the row is r − ratio exactly, so
    ``sigma`` is a σ on the ratio itself."""
    w, ratio = _truth(SEPARATE)
    s = _pair(SEPARATE)
    row = elemental_ratio_restraint(s, "Cu", "Ni", 1.5, 0.02)
    assert row.occupancies == {"phases.0.atoms.0.occ": 1.0,
                               "phases.1.atoms.0.occ": 1.0}
    value = sum(c * s.phases[int(p.split(".")[1])].scale.value for p, c in row.terms)
    assert value == pytest.approx(ratio - 1.5, rel=1e-12)
    assert row.label == "Cu/(Ni) = 1.5"


def test_the_ratio_row_refuses_what_it_cannot_build():
    s = _pair(SEPARATE)
    with pytest.raises(ValueError, match="both sides"):
        elemental_ratio_restraint(s, "Cu", ["Cu", "Ni"], 1.0, 0.1)
    with pytest.raises(ValueError, match=r"no phase spanned holds \['Al'\]"):
        elemental_ratio_restraint(s, "Cu", "Al", 1.0, 0.1)
    # a misspelt or absent numerator would drive the other side's scales to 0
    with pytest.raises(ValueError, match=r"no phase spanned holds \['Zn'\]"):
        elemental_ratio_restraint(s, "Zn", "Ni", 1.0, 0.1)
    # an ion names its element
    assert elemental_ratio_restraint(s, "Cu2+", "Ni", 1.5, 0.1).terms


@pytest.mark.parametrize("phases, error, match", [
    ([0, 2], ValueError, r"phases\[1\] is 2, but the structure has 2 phase\(s\)"),
    ([0, -1], ValueError, r"phases\[1\] is -1, but the structure has 2 phase\(s\)"),
    ([0, 0, 1], ValueError, r"phases names phase 0 twice"),
    ([0, 1.0], TypeError, r"phases\[1\] is 1\.0, not an integer"),
    ([0, True], TypeError, r"phases\[1\] is True, not an integer"),
    (1, TypeError, r"phases must be a list of phase indices, got 1"),
])
def test_the_ratio_row_refuses_a_phase_index_it_cannot_honour(phases, error, match):
    """Each index is a distinct non-negative integer below the phase count,
    checked before any volume or count is read (Design Rule 4): past the end
    raised a bare IndexError, a negative one built ``phases.-1.scale``, which
    no table holds, and a repeat was caught only after the work."""
    s = _pair(SEPARATE)
    with pytest.raises(error, match=match) as info:
        elemental_ratio_restraint(s, "Cu", "Ni", 1.5, 0.1, phases=phases)
    assert "by its index, 0 to 1, or leave phases=None" in str(info.value)
    # numpy integers are indices too
    assert elemental_ratio_restraint(s, "Cu", "Ni", 1.5, 0.1,
                                     phases=np.arange(2)).terms


# ----------------------------------------------------------------------
# the acceptance: a flat partition decided by the ratio; a wrong ratio reported
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def flat_pattern():
    return _pattern(FLAT)


@pytest.fixture(scope="module")
def separate_pattern():
    return _pattern(SEPARATE)


def test_diffraction_alone_leaves_the_flat_partition_unmeasured(flat_pattern):
    """The premise: unrestrained, W_Cu's esd is of order one (0.97 measured)."""
    res = _fit(FLAT, flat_pattern)
    assert res.qpa.phases[0].weight_fraction_stderr > 0.3


def test_the_declared_ratio_decides_a_flat_partition(flat_pattern):
    """Restrained at the true ratio (σ 0.02), the fit recovers the true weight
    fractions within their esds; measured 0.643426 ± 0.0032 against 0.643425."""
    w_true, ratio = _truth(FLAT)
    res = _fit(FLAT, flat_pattern, [_ratio_row(FLAT, ratio, 0.02)])
    q = res.qpa.phases[0]
    assert abs(q.weight_fraction - w_true) < q.weight_fraction_stderr
    assert q.weight_fraction_stderr < 0.01
    assert not [d for d in res.diagnostics if d.code == "RESTRAINT_TENSION"]
    _save(res, "linear_restraint_flat.png")


def test_a_ratio_the_data_cannot_see_is_never_in_tension(flat_pattern):
    """The other side of a flat partition: wrong by 5σ, the row is still met,
    since nothing in the pattern disagrees.  A ratio is checked only where the
    data measure the partition themselves (the next test)."""
    _, ratio = _truth(FLAT)
    res = _fit(FLAT, flat_pattern, [_ratio_row(FLAT, ratio + 0.1, 0.02)])
    assert not [d for d in res.diagnostics if d.code == "RESTRAINT_TENSION"]
    assert abs(res.restraints.rows[0].deviation_over_sigma) < 0.1


def test_a_ratio_wrong_by_five_sigma_is_reported_under_one_key(separate_pattern):
    """Where the data measure the partition (W_Cu ± 0.002 unrestrained), a
    ratio declared 5σ off fires ``RESTRAINT_TENSION`` (−3.6σ measured), once,
    keyed on the row and not its paths; the true ratio does not.

    The margin over the 3σ threshold (0.62σ) is the fixed noise draw's
    (seed 3), not the solver's: refitting from a start scale moved by
    (1 + k·1e-14), k = ±1, ±3, ±7, 20, moved −3.616085σ by under 1e-12σ
    (darwin arm64, 2026-11-25)."""
    _, ratio = _truth(SEPARATE)
    good = _fit(SEPARATE, separate_pattern, [_ratio_row(SEPARATE, ratio, 0.02)])
    assert not [d for d in good.diagnostics if d.code == "RESTRAINT_TENSION"]
    bad = _fit(SEPARATE, separate_pattern, [_ratio_row(SEPARATE, ratio + 0.1, 0.02)])
    found = [d for d in bad.diagnostics if d.code == "RESTRAINT_TENSION"]
    assert len(found) == 1 and found[0].where == ["restraints.0"]
    assert "linear restraint restraints.0 (Cu/(Ni) = " in found[0].message
    _save(bad, "linear_restraint_tension.png")


def test_freeing_an_occupancy_the_coefficients_read_is_reported(separate_pattern):
    _, ratio = _truth(SEPARATE)
    ref = Refinement(_pair(SEPARATE, (8e-4, 8e-4), [_ratio_row(SEPARATE, ratio, 0.02)]),
                     _instrument(), history=False)
    res = ref.run_stage(separate_pattern,
                        Stage("occ", [*STAGE, "phases.1.atoms.0.occ"]))
    (d,) = [d for d in res.diagnostics if d.code == "LINEAR_RESTRAINT_STALE"]
    assert d.where == ["restraints.0", "phases.1.atoms.0.occ"]
    assert "phases.1.atoms.0.occ 1 -> " in d.message
    quiet = _fit(SEPARATE, separate_pattern, [_ratio_row(SEPARATE, ratio, 0.02)])
    assert not [d for d in quiet.diagnostics if d.code == "LINEAR_RESTRAINT_STALE"]


def test_an_occupancy_an_earlier_stage_moved_is_still_reported(separate_pattern):
    """The row is compared with the values, not with the last stage's free set:
    an occupancy refined in stage 1 and held in stage 2 is still stale."""
    _, ratio = _truth(SEPARATE)
    ref = Refinement(_pair(SEPARATE, (8e-4, 8e-4), [_ratio_row(SEPARATE, ratio, 0.02)]),
                     _instrument(), history=False)
    ref.run_stage(separate_pattern, Stage("occ", [*STAGE, "phases.1.atoms.0.occ"]))
    res = ref.run_stage(separate_pattern, Stage("scales", STAGE))
    assert [d.code for d in res.diagnostics].count("LINEAR_RESTRAINT_STALE") == 1


def test_a_series_where_the_ratio_decides_each_partition():
    """Three flat patterns of one conserved ratio and a moving partition's
    noise: every pattern's W_Cu lands within two esds of the truth, and a
    second chain declared 5σ wrong on the separated pair counts its tension
    as one row of the series, keyed ``restraints.0``."""
    w_true, ratio = _truth(FLAT)
    plan = rx.RefinementPlan(stages=[Stage("scales", STAGE)])
    patterns = [_pattern(FLAT, seed) for seed in (11, 12, 13)]
    series = rx.refine_sequential(
        patterns, _pair(FLAT, (8e-4, 8e-4), [_ratio_row(FLAT, ratio, 0.02)]),
        _instrument(), plan=plan)
    for entry in series.entries:
        q = entry.qpa.phases[0]
        assert abs(q.weight_fraction - w_true) < 2.0 * q.weight_fraction_stderr

    _, ratio = _truth(SEPARATE)
    patterns = [_pattern(SEPARATE, seed) for seed in (21, 22, 23)]
    series = rx.refine_sequential(
        patterns, _pair(SEPARATE, (8e-4, 8e-4),
                        [_ratio_row(SEPARATE, ratio + 0.1, 0.02)]),
        _instrument(), plan=plan)
    rows = [c for c in series.code_counts or [] if c.code == "RESTRAINT_TENSION"]
    # one row of the series, never one per path the row reads; the noise puts
    # a 5σ error at about 4σ, so it fires on most patterns: 2 of 3 measured
    # (seeds 21 and 23 at -3.4σ and -4.1σ, seed 22 under 3σ; darwin arm64,
    # 2026-11-25), so ``>= 2`` holds while the draws do; the nearest firing
    # sits 0.4σ over the threshold, against under 1e-12σ that a perturbed
    # start moved the single fit's deviation (the test above)
    assert [(c.path, c.n_patterns) for c in rows] == [("restraints.0", 3)]
    assert rows[0].count >= 2


def _save(result, name: str) -> None:
    pytest.importorskip("matplotlib")
    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

    plot_result(result, path=str(OUT / name))


def test_the_issue_probe_needs_no_variable_and_no_plan_edit():
    """Issue #212's probe, restated (WP-1942's Context, at ``f11e22d3``):
    rock salt and Si, Cu Kα1, 20-110°, true scale ratio 1/0.6.  Spelled as a
    variable, a multi-source tie and a ``ValueRestraint``, the unchanged
    ``mccusker_default`` plan never freed ``vars.*``, phase 1's scale went to
    its floor and ``MODEL_FAR_FROM_DATA`` and ``RESTRAINT_TENSION`` fired.
    As one row on the two scales the default plan carries it: the ratio comes
    back, and neither finding fires."""
    def phase(name, group, a, atoms, scale):
        return Phase(name=name, space_group=group, cell=Cell.cubic(a),
                     atoms=[Atom(label=lab, species=sp, x=P(value=x), y=P(value=x),
                                 z=P(value=x), biso=P(value=0.6))
                            for lab, sp, x in atoms],
                     scale=P(value=scale, min=0.0))

    def pair(s0, s1, restraints=()):
        return Structure(phases=[
            phase("NaCl", "F m -3 m", 5.6402, [("Na", "Na", 0.0), ("Cl", "Cl", 0.5)], s0),
            phase("Si", "F d -3 m", 5.4309, [("Si", "Si", 0.0)], s1)],
            restraints=list(restraints))

    ins = rx.Instrument.debye_scherrer(wavelength=1.5406)
    ins.source.dispersion = None
    ins.profile.w.value = 8e-3
    tt = np.arange(20.0, 110.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    truth = pair(1.0e-3, 0.6e-3)
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = np.random.default_rng(5).poisson(model.evaluate(table.decode(table.x0())) + 40.0)
    pattern = PatternData(two_theta=tt.tolist(), intensity=y.astype(float).tolist())

    row = LinearRestraint(terms=[("phases.0.scale", 0.6), ("phases.1.scale", -1.0)],
                          sigma=1e-5)
    res = Refinement(pair(8e-4, 8e-4, [row]), ins, history=False).fit(pattern)
    s0, s1 = (res.parameter(f"phases.{i}.scale").value for i in (0, 1))
    assert s0 / s1 == pytest.approx(1 / 0.6, rel=0.01)
    codes = {d.code for d in res.diagnostics}
    assert not codes & {"MODEL_FAR_FROM_DATA", "RESTRAINT_TENSION"}
