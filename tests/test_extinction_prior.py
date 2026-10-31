"""Declared facts as a member filter on the extinction screen, and the Laue fork.

A powder pattern cannot separate the members of an extinction class, so the
choice inside one is chemistry — and ``restrict=`` is where the chemistry is
declared.  The claims, each with an arm that must come out a known way:

* **the vocabulary is derived** — Sohncke, centrosymmetric and polar are read
  off each group's operators, never transcribed; the polar test reproduces the
  ten polar crystal classes over gemmi's whole table;
* **a declared chirality is used** — on a P 2₁ specimen the screen's class is
  ``P 1 21 1`` = {P 2₁, P 2₁/m}; declared enantiopure, the answer is P 2₁ alone,
  with P 2₁/m named as excluded;
* **a wrong declaration is visible** — on a P 2₁/c specimen the same declaration
  empties the class the data prefer decisively, and the screen abstains with a
  warning instead of obeying it;
* **the Laue fork** — a class whose admitted members fall in two Laue classes
  says so (``LAUE_CLASS_NOT_SEPARABLE``), and one that does not, does not.

The specimens are the synthetic monoclinic of ``test_extinction_symbol.py``.
"""

from __future__ import annotations

import gemmi
import pytest

from rietx import determine_extinction_symbol
from rietx.indexing.diagnostics import extinction_diagnostics
from rietx.indexing.extinction import (
    DENSITY_Z_TOLERANCE,
    N_A_CM3_PER_A3,
    admits,
    declared_z,
    density_zs,
    is_polar,
    laue_classes,
)
from rietx.schemas.indexing import (
    ExtinctionCandidate,
    ExtinctionPrior,
    ExtinctionScreen,
)
from tests.test_extinction_symbol import (
    MONO_CELL,
    MONO_RANGE,
    _candidate,
    _mono_models,
    _pattern,
)

pytestmark = pytest.mark.xdist_group("extinction-prior")

ENANTIOPURE = ExtinctionPrior(sohncke=True)


def _codes(screen):
    return [d.code for d in screen.diagnostics]


def _screen(space_group: str, **kw):
    structure, instrument = _mono_models(space_group)
    return determine_extinction_symbol(
        _pattern(structure, instrument), _candidate(MONO_CELL, "monoclinic"),
        instrument, two_theta_limits=MONO_RANGE, **kw)


# ----------------------------------------------------------------------
# the vocabulary
# ----------------------------------------------------------------------
def test_the_polar_test_reproduces_the_ten_polar_classes():
    found = {sg.point_group_hm() for sg in gemmi.spacegroup_table() if is_polar(sg)}
    assert found == {"1", "2", "m", "mm2", "4", "4mm", "3", "3m", "6", "6mm"}


def test_an_enantiopure_declaration_admits_exactly_the_sohncke_types():
    numbers = {sg.number for sg in gemmi.spacegroup_table()
               if admits(ENANTIOPURE, sg)}
    assert len(numbers) == 65
    assert not any(admits(ENANTIOPURE, sg) for sg in gemmi.spacegroup_table()
                   if sg.is_centrosymmetric())


def test_a_contradictory_declaration_is_refused():
    with pytest.raises(ValueError, match="Sohncke"):
        ExtinctionPrior(sohncke=True, centrosymmetric=True)
    with pytest.raises(ValueError, match="inversion"):
        ExtinctionPrior(polar=True, centrosymmetric=True)
    assert ExtinctionPrior().declared() == {}


# ----------------------------------------------------------------------
# a declared chirality is used
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def p21_screens():
    return (_screen("P 1 21 1"), _screen("P 1 21 1", restrict={"sohncke": True}))


def test_a_declared_chirality_removes_the_centrosymmetric_partner(p21_screens):
    plain, declared = p21_screens
    best = plain.best_or_none()
    assert best is not None and best.symbol == "P 1 21 1"
    assert best.space_groups == ["P 1 21 1", "P 1 21/m 1"]
    assert "EXTINCTION_GROUPS_NOT_SEPARABLE" in _codes(plain)

    best = declared.best_or_none()
    assert best is not None and best.symbol == "P 1 21 1"
    assert best.space_groups == ["P 1 21 1"]
    assert best.excluded_groups == ["P 1 21/m 1"]
    assert declared.prior == ENANTIOPURE
    note = next(d for d in declared.diagnostics
                if d.code == "EXTINCTION_PRIOR_APPLIED")
    assert note.level == "info"
    assert any(w.startswith("P 1 21 1: excluded P 1 21/m 1") for w in note.where)
    assert "EXTINCTION_GROUPS_NOT_SEPARABLE" not in _codes(declared)


def test_the_declaration_moves_no_number_the_data_produced(p21_screens):
    plain, declared = p21_screens
    assert [c.symbol for c in plain.candidates] == \
           [c.symbol for c in declared.candidates]
    for a, b in zip(plain.candidates, declared.candidates, strict=True):
        assert (a.delta_bic, a.n_testable, a.refuted) == \
               (b.delta_bic, b.n_testable, b.refuted)
        assert sorted(a.space_groups) == sorted(b.space_groups + b.excluded_groups)


def test_a_declaration_the_data_contradict_makes_the_screen_abstain():
    """P 2₁/c declared enantiopure: the data's class has no admissible member,
    and it leads the first admissible class by more than the decisive margin."""
    screen = _screen("P 1 21/c 1", restrict=ENANTIOPURE)
    lead = screen.candidates[0]
    assert lead.symbol == "P 1 21/c 1" and lead.space_groups == []
    assert lead.excluded_groups == ["P 1 21/c 1"]
    assert screen.best_or_none() is None
    note = next(d for d in screen.diagnostics if d.code == "EXTINCTION_PRIOR_APPLIED")
    assert note.level == "warning"
    ambiguous = next(d for d in screen.diagnostics
                     if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")
    assert "excludes" in ambiguous.message


# ----------------------------------------------------------------------
# the Laue fork
# ----------------------------------------------------------------------
def test_laue_classes_partition_a_class_by_which_reflections_are_equivalent():
    assert laue_classes(["P 63", "P 63/m", "P 63 2 2"]) == {
        "6/m": ["P 63", "P 63/m"], "6/mmm": ["P 63 2 2"]}
    assert laue_classes(["P 1 21 1", "P 1 21/m 1"]) == {
        "2/m": ["P 1 21 1", "P 1 21/m 1"]}


def _one_class_screen(groups: list[str]) -> ExtinctionScreen:
    lead = ExtinctionCandidate(symbol="lead", representative=groups[-1],
                               space_groups=groups, laue_classes=laue_classes(groups),
                               n_absent=3, n_testable=3, screened=True,
                               delta_bic=-300.0)
    ref = ExtinctionCandidate(symbol="ref", representative="ref",
                              space_groups=["P 6/m m m"],
                              laue_classes=laue_classes(["P 6/m m m"]),
                              screened=True, delta_bic=0.0)
    return ExtinctionScreen(candidates=[lead, ref], system="hexagonal")


def test_a_class_spanning_two_laue_classes_says_so():
    diagnostics = extinction_diagnostics(_one_class_screen(["P 63", "P 63/m",
                                                           "P 63 2 2"]))
    fork = next(d for d in diagnostics if d.code == "LAUE_CLASS_NOT_SEPARABLE")
    assert fork.where == ["6/m: P 63, P 63/m", "6/mmm: P 63 2 2"]


def test_a_class_inside_one_laue_class_does_not(p21_screens):
    plain, _ = p21_screens
    assert "LAUE_CLASS_NOT_SEPARABLE" not in _codes(plain)
    diagnostics = extinction_diagnostics(_one_class_screen(["P 63", "P 63/m"]))
    assert "LAUE_CLASS_NOT_SEPARABLE" not in [d.code for d in diagnostics]


# ----------------------------------------------------------------------
# the diagnostics name the right classes once a prior empties the leader
# ----------------------------------------------------------------------
def _cand(symbol: str, groups: list[str], delta_bic: float, excluded=()):
    return ExtinctionCandidate(
        symbol=symbol, representative=(groups or list(excluded))[0],
        space_groups=groups, excluded_groups=list(excluded),
        laue_classes=laue_classes(groups), n_absent=3, n_testable=3,
        screened=True, delta_bic=delta_bic)


def _prior_screen(candidates):
    return ExtinctionScreen(candidates=candidates, system="monoclinic",
                            prior=ENANTIOPURE)


def test_the_runners_up_exclude_the_leading_class_and_name_the_emptied_one():
    screen = _prior_screen([
        _cand("emptied", [], -300.0, excluded=["P 1 21/c 1"]),
        _cand("top", ["P 1 21 1"], -100.0),
        _cand("rival", ["P 1 1 21"], -98.0),
        _cand("third", ["P 1 1 2"], -50.0)])
    ambiguous = next(d for d in extinction_diagnostics(screen)
                     if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")
    assert ambiguous.where[0] == "leading: top"
    assert [w.split(" (")[0] for w in ambiguous.where[1:]] == [
        "then: rival", "then: third", "excluded by the prior: emptied"]


def test_a_prior_that_empties_every_class_does_not_call_one_admitted():
    screen = _prior_screen([
        _cand("emptied", [], -300.0, excluded=["P 1 21/c 1"]),
        _cand("also", [], -100.0, excluded=["P 1 21/m 1"])])
    note = next(d for d in extinction_diagnostics(screen)
                if d.code == "EXTINCTION_PRIOR_APPLIED")
    assert note.level == "warning"
    assert "first class the declaration admits" not in note.message
    assert "no admissible answer" in note.message


def test_the_polar_test_is_the_floating_origin_basis():
    from rietx.crystallography.wyckoff import floating_origin_basis
    for sg in gemmi.spacegroup_table():
        assert is_polar(sg) == (len(floating_origin_basis(sg)) > 0)


# ----------------------------------------------------------------------
# a declared Z or density (WP-2033)
# ----------------------------------------------------------------------
# Three synthetic specimens.  The monoclinic P 2₁ one above is #935's shape: a
# P 2₁ structure at Z = 2, whose class also holds P 2₁/m.  The cubic two are
# built here: a tetrahedrite-like I -4 3 m sulfosalt, Cu₁₂Sb₄S₁₃ at Z = 2
# (Cu on 12d and 12e, Sb on 8c, S on 24g and 2a; approximate coordinates, not
# a published refinement), and rock salt, NaCl at Z = 4 on 4a and 4b with the
# cell and density of the textbook structure.
LAM_CU = 1.5405929
CUBIC_RANGE = (15.0, 90.0)
TETRAHEDRITE_CELL = (10.33,) * 3 + (90.0,) * 3
TETRAHEDRITE_ATOMS = (("Cu", 0.25, 0.5, 0.0), ("Cu", 0.215, 0.0, 0.0),
                      ("Sb", 0.268, 0.268, 0.268), ("S", 0.115, 0.115, 0.362),
                      ("S", 0.0, 0.0, 0.0))
NACL_CELL = (5.6402,) * 3 + (90.0,) * 3
NACL_ATOMS = (("Na", 0.0, 0.0, 0.0), ("Cl", 0.5, 0.5, 0.5))
#: X-ray density of NaCl at that cell: 4 × 58.443 g/mol / (N_A × 179.43 Å³)
NACL_DENSITY = 2.163
#: the handbook's measured density of NaCl (CRC Handbook of Chemistry and
#: Physics, physical constants of inorganic compounds), g/cm³
NACL_MEASURED = 2.165


def _cubic_screen(space_group, cell, atoms, centring, **kw):
    import numpy as np

    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import BackgroundChebyshev, Instrument
    from rietx.schemas.pattern import PatternData
    from rietx.schemas.structure import Atom, Cell, Parameter, Phase, Structure

    a = cell[0]
    structure = Structure(phases=[Phase(
        name="synthetic", space_group=space_group,
        cell=Cell(a=Parameter(value=a, min=0.1), b=Parameter(value=a, min=0.1),
                  c=Parameter(value=a, min=0.1), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        scale=Parameter(value=3e-3, min=0.0, transform="softplus"),
        atoms=[Atom(label=f"{el}{i}", species=el, x=Parameter(value=x),
                    y=Parameter(value=y), z=Parameter(value=z))
               for i, (el, x, y, z) in enumerate(atoms)])])
    instrument = Instrument.debye_scherrer(wavelength=LAM_CU)
    instrument.profile.w.value = 4e-3
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 2.0)])
    tt = np.arange(CUBIC_RANGE[0], CUBIC_RANGE[1], 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())
    return determine_extinction_symbol(
        data, _candidate(cell, "cubic", centring), instrument,
        two_theta_limits=CUBIC_RANGE, **kw)


def _note(screen):
    return next(d for d in screen.diagnostics if d.code == "EXTINCTION_PRIOR_APPLIED")


def test_a_declared_z_is_validated_where_it_is_declared():
    with pytest.raises(ValueError):
        ExtinctionPrior(z=0)
    with pytest.raises(ValueError, match="formula"):
        ExtinctionPrior(density=2.16)
    with pytest.raises(ValueError, match="z or a density"):
        ExtinctionPrior(formula="NaCl")
    with pytest.raises(ValueError, match="Qq"):
        ExtinctionPrior(z=2, formula="NaQq")
    assert ExtinctionPrior(z=2, formula="SiO").declared() == {"z": 2, "formula": "SiO"}
    # a noble gas is an element even where Hofmann (2002) has no volume for it
    assert ExtinctionPrior(z=4, formula="XeF2").declared()["formula"] == "XeF2"


def test_an_element_count_its_orbits_cannot_hold_excludes_the_group():
    from rietx.indexing.extinction import content_exclusion

    tetrahedrite = {"Cu": 12.0, "Sb": 4.0, "S": 13.0}
    # I 2₁3's orbits are 8, 12 and 24: S 26 is none of their sums
    why = content_exclusion(gemmi.find_spacegroup_by_name("I 21 3"), 2, tetrahedrite)
    assert why is not None and "S 26" in why
    for group in ("I 2 3", "I m -3", "I 4 3 2", "I -4 3 m", "I m -3 m"):
        assert content_exclusion(gemmi.find_spacegroup_by_name(group), 2,
                                 tetrahedrite) is None, group
    # one formula unit of SiO in a P 2₁ cell: Si 1, and P 2₁'s only orbit is 2
    assert "Si 1" in content_exclusion(gemmi.find_spacegroup_by_name("P 1 21 1"),
                                       1, {"Si": 1.0, "O": 1.0})


def test_a_fixed_position_is_one_orbit_and_holds_its_count_once():
    """Fm-3m: Na 20 per cell.  Unbounded sums of the orbit sizes reach it (4 × 5);
    the orbits do not — 4a and 4b are one orbit each, 4 + 4 + 8 = 16, and the
    next orbit, 24, is too large."""
    from rietx.indexing.extinction import content_exclusion

    fm3m = gemmi.find_spacegroup_by_name("F m -3 m")
    assert "Na 20" in content_exclusion(fm3m, 4, {"Na": 5.0, "Cl": 1.0})
    assert content_exclusion(fm3m, 4, {"Na": 4.0, "Cl": 1.0}) is None   # 4a + 4b + 8c


def test_a_fractional_formula_count_declares_a_shared_site_and_is_not_counted():
    """Disordered CuAu (A1, Fm-3m): written Cu0.5Au0.5 at Z = 4 the two elements
    share 4a and nothing is excluded; written CuAu at Z = 2 it is the ordered
    reading, and Cu 2 fits no orbit of Fm-3m."""
    from rietx.indexing.extinction import content_exclusion

    fm3m = gemmi.find_spacegroup_by_name("F m -3 m")
    assert content_exclusion(fm3m, 4, {"Cu": 0.5, "Au": 0.5}) is None
    assert "Cu 2" in content_exclusion(fm3m, 2, {"Cu": 1.0, "Au": 1.0})


def test_z_prime_below_one_names_the_site_symmetry_and_removes_nothing():
    from rietx.indexing.extinction import special_site_note

    note = special_site_note(gemmi.find_spacegroup_by_name("P 1 21/m 1"), 2)
    assert "Z′ = 1/2" in note
    assert "-1 (2a, 2b, 2c, 2d)" in note and "m (2e)" in note
    assert special_site_note(gemmi.find_spacegroup_by_name("P 1 21 1"), 2) is None
    assert special_site_note(gemmi.find_spacegroup_by_name("P 1 21/m 1"), 4) is None
    # Z′ = 3/2: one general orbit and one formula unit's worth on a special one
    assert "Z′ = 3/2" in special_site_note(
        gemmi.find_spacegroup_by_name("P 1 21/m 1"), 6)
    # no special position at all: no formula unit sits whole on one site
    assert "no sum" in special_site_note(
        gemmi.find_spacegroup_by_name("P 21 21 21"), 2)
    # Yue's #1140 item 7: P 2₁/m at Z = 3 leaves a remainder of 3, which the
    # 2-fold positions cannot make; the note must not list them as if they did
    odd = special_site_note(gemmi.find_spacegroup_by_name("P 1 21/m 1"), 3)
    assert "no sum" in odd and "m (2e)" not in odd
    # Z = 5 is odd, and every orbit of this group is even
    assert "no sum" in special_site_note(gemmi.find_spacegroup_by_name("P 1 21/m 1"), 5)


@pytest.fixture(scope="module")
def p21_z_screens():
    """#935's case: the P 2₁ specimen at its own Z = 2, and at a wrong Z = 1."""
    return (_screen("P 1 21 1", restrict={"z": 2, "formula": "SiO"}),
            _screen("P 1 21 1", restrict={"z": 1, "formula": "SiO",
                                          "ordered": True}),
            _screen("P 1 21 1", restrict={"z": 1, "formula": "SiO"}))


def test_935_a_p21_specimen_at_z2_keeps_p21m_and_says_what_it_needs(
        p21_screens, p21_z_screens):
    plain, _ = p21_screens
    declared = p21_z_screens[0]
    best = declared.best_or_none()
    assert best is not None and best.symbol == "P 1 21 1"
    assert best.space_groups == ["P 1 21 1", "P 1 21/m 1"]
    assert best.excluded_groups == []
    assert "P 1 21/m 1" in best.special_positions
    assert "P 1 21 1" not in best.special_positions
    assert declared.z == 2 and declared.z_from_density is None
    note = _note(declared)
    assert note.level == "info"
    assert any(w.startswith("P 1 21 1: P 1 21/m 1 holds Z = 2 with Z′ = 1/2")
               for w in note.where)
    assert "EXTINCTION_GROUPS_NOT_SEPARABLE" in _codes(declared)
    for a, b in zip(plain.candidates, declared.candidates, strict=True):
        assert (a.symbol, a.delta_bic, a.n_testable, a.refuted) == \
               (b.symbol, b.delta_bic, b.n_testable, b.refuted)


def test_a_z_the_data_contradict_ends_in_an_abstention_when_declared_ordered(
        p21_z_screens):
    wrong = p21_z_screens[1]
    lead = wrong.candidates[0]
    assert lead.symbol == "P 1 21 1" and lead.space_groups == []
    assert lead.excluded_groups == ["P 1 21 1", "P 1 21/m 1"]
    assert "Si 1" in lead.exclusion_reasons["P 1 21 1"]
    assert "ordered" in lead.exclusion_reasons["P 1 21 1"]
    assert wrong.best_or_none() is None
    assert _note(wrong).level == "warning"


def test_the_same_wrong_z_is_a_statement_when_the_model_is_not_declared_ordered(
        p21_z_screens):
    """#1140 item 3: a count the orbits cannot hold removes nothing by default,
    since a disordered model shares a site; the group stays and says why."""
    stated = p21_z_screens[2]
    best = stated.best_or_none()
    assert best is not None and best.symbol == "P 1 21 1"
    assert best.excluded_groups == [] and best.exclusion_reasons == {}
    assert "Si 1" in best.count_notes["P 1 21 1"]
    assert any("kept though Si 1" in w and "ordered=True" in w
               for w in _note(stated).where)


@pytest.fixture(scope="module")
def tetrahedrite_screens():
    args = ("I -4 3 m", TETRAHEDRITE_CELL, TETRAHEDRITE_ATOMS, "I")
    return (_cubic_screen(*args),
            _cubic_screen(*args, restrict=ExtinctionPrior(
                z=2, formula="Cu12Sb4S13", ordered=True)),
            _cubic_screen(*args, restrict=ExtinctionPrior(z=2, formula="Cu12Sb4S13")))


def test_an_ionic_z_removes_the_group_whose_orbits_cannot_hold_it_when_ordered(
        tetrahedrite_screens):
    plain, declared, _ = tetrahedrite_screens
    best = plain.best_or_none()
    assert best is not None and best.symbol == "I - - -"
    assert "I 21 3" in best.space_groups

    best = declared.best_or_none()
    assert best is not None and best.symbol == "I - - -"
    assert best.excluded_groups == ["I 21 3"]
    assert best.space_groups == ["I 2 3", "I m -3", "I 4 3 2", "I -4 3 m", "I m -3 m"]
    assert "S 26" in best.exclusion_reasons["I 21 3"]
    note = _note(declared)
    assert note.level == "info"
    assert any(w.startswith("I - - -: excluded I 21 3 (z=2, ordered: S 26")
               for w in note.where)
    # every kept member needs special positions at Z = 2: one line, not five
    assert len(best.special_positions) == 5
    assert [w for w in note.where if "special positions" in w] == [
        "I - - -: every member holds Z = 2 only with formula units on special "
        "positions (special_positions names them)"]
    for a, b in zip(plain.candidates, declared.candidates, strict=True):
        assert (a.symbol, a.delta_bic, a.n_testable, a.refuted) == \
               (b.symbol, b.delta_bic, b.n_testable, b.refuted)


def test_an_ionic_z_only_states_the_failed_count_by_default(tetrahedrite_screens):
    plain, _, stated = tetrahedrite_screens
    best = stated.best_or_none()
    assert best is not None and best.excluded_groups == []
    assert best.space_groups == plain.best_or_none().space_groups
    assert list(best.count_notes) == ["I 21 3"]
    assert "S 26" in best.count_notes["I 21 3"]
    assert any("I 21 3 kept though S 26" in w for w in _note(stated).where)


@pytest.fixture(scope="module")
def nacl_screens():
    args = ("F m -3 m", NACL_CELL, NACL_ATOMS, "F")
    return {
        "plain": _cubic_screen(*args),
        "density": _cubic_screen(*args, restrict={"density": NACL_DENSITY,
                                                   "formula": "NaCl"}),
        "both": _cubic_screen(*args, restrict={"z": 4, "density": NACL_DENSITY,
                                                "formula": "NaCl"}),
        "disagree": _cubic_screen(*args, restrict={"z": 2, "density": NACL_DENSITY,
                                                    "formula": "NaCl"}),
        "wrong": _cubic_screen(*args, restrict={"z": 1, "formula": "NaCl",
                                                 "ordered": True}),
        "wrong_stated": _cubic_screen(*args, restrict={"z": 1, "formula": "NaCl"}),
        # a handbook density, not the X-ray one: 2.165 g/cm3 (CRC Handbook of
        # Chemistry and Physics, inorganic compounds), good to the 1 % a
        # pycnometer is, against the computed 2.163
        "measured": _cubic_screen(*args, restrict={"density": NACL_MEASURED,
                                                    "formula": "NaCl"}),
        # an unphysical density, only to put Z where two whole numbers fit
        "ambiguous": _cubic_screen(*args, restrict={"density": 25 * NACL_DENSITY,
                                                     "formula": "NaCl"}),
    }


def test_a_density_fixes_z_through_the_formula_and_the_cell(nacl_screens):
    plain = nacl_screens["plain"].best_or_none()
    for key in ("density", "both"):
        screen = nacl_screens[key]
        assert screen.z == 4
        assert screen.z_from_density == pytest.approx(4.0, abs=0.01)
        best = screen.best_or_none()
        assert best is not None and best.symbol == plain.symbol == "F - - -"
        assert best.space_groups == plain.space_groups and best.excluded_groups == []


def test_a_density_that_contradicts_the_declared_z_abstains(nacl_screens):
    screen = nacl_screens["disagree"]
    assert screen.z is None
    assert screen.z_from_density == pytest.approx(4.0, abs=0.01)
    assert all(not c.excluded_groups for c in screen.candidates)
    assert screen.best_or_none() is None
    note = _note(screen)
    assert note.level == "warning" and "density" in note.message
    ambiguous = next(d for d in screen.diagnostics
                     if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")
    assert "density" in ambiguous.message


def test_a_wrong_z_on_rock_salt_empties_every_class_and_abstains_when_ordered(
        nacl_screens):
    screen = nacl_screens["wrong"]
    assert all(not c.space_groups for c in screen.candidates)
    assert screen.best_or_none() is None
    assert _note(screen).level == "warning"
    stated = nacl_screens["wrong_stated"]
    assert stated.best_or_none() is not None
    assert not any(c.excluded_groups for c in stated.candidates)


def test_a_measured_density_gives_z_within_its_own_tolerance(nacl_screens):
    """#1140 item 2: a handbook density, not the one computed from the cell
    and the formula, which only checks the arithmetic."""
    screen = nacl_screens["measured"]
    assert screen.z == 4 and not screen.density_contradicts_z()
    assert abs(screen.z_from_density / 4 - 1.0) < DENSITY_Z_TOLERANCE
    assert screen.best_or_none() is not None
    # the old 8 % would have taken a density 5 % off; 1.5 % does not
    off = declared_z(ExtinctionPrior(density=NACL_MEASURED * 1.05, formula="NaCl"),
                     179.43)
    assert off[0] is None and off[1] == pytest.approx(4.2, abs=0.01)


def test_a_density_names_a_whole_z_above_the_old_eight_percent_edge():
    """#1140 item 1: at Z = 12 the 8 % window held 12 and 13, and at 24 it held
    23 to 26; the measured-density window names the one Z."""
    for z in (12, 16, 24, 40):
        v = 100.0
        rho = z * 58.443 / (N_A_CM3_PER_A3 * v)       # the NaCl formula weight
        got, z_rho = declared_z(ExtinctionPrior(density=rho, formula="NaCl"), v)
        assert got == z and z_rho == pytest.approx(z, rel=1e-3), z
        assert density_zs(z_rho) == [z]


def test_a_density_that_fits_several_whole_z_is_ambiguous_not_contradicted(
        nacl_screens):
    screen = nacl_screens["ambiguous"]
    assert screen.z is None and len(screen.z_candidates) > 1
    assert not screen.density_contradicts_z()
    # nothing is filtered, and the screen does not abstain on its account
    assert all(not c.excluded_groups for c in screen.candidates)
    assert screen.best_or_none() is not None
    note = _note(screen)
    assert "fits Z =" in note.message and "abstains" not in note.message
    assert not any("density" in d.message for d in screen.diagnostics
                   if d.code == "EXTINCTION_SYMBOL_AMBIGUOUS")


def test_a_screen_that_computed_no_z_does_not_say_the_density_contradicts_it():
    """#1140 item 4: the early returns of ``determine_extinction_symbol`` come
    before ``declared_z``; a density that was never evaluated contradicts
    nothing."""
    prior = ExtinctionPrior(density=2.16, formula="NaCl")
    assert not ExtinctionScreen(prior=prior).density_contradicts_z()
    assert ExtinctionScreen(prior=prior, z_from_density=4.7).density_contradicts_z()
    assert not ExtinctionScreen(prior=prior, z_from_density=100.0,
                                z_candidates=[100, 101]).density_contradicts_z()


def test_disordered_cuau_keeps_its_true_group_unless_declared_ordered():
    """#1140 item 3: CuAu written with whole counts at Z = 2 fails the orbit
    count on every group of the fcc class, and its true Fm-3m must survive."""
    args = ("F m -3 m", (3.96,) * 3 + (90.0,) * 3, (("Cu", 0.0, 0.0, 0.0),), "F")
    kept = _cubic_screen(*args, restrict={"z": 2, "formula": "CuAu"})
    best = kept.best_or_none()
    assert best is not None and "F m -3 m" in best.space_groups
    assert best.excluded_groups == [] and "F m -3 m" in best.count_notes
    dropped = _cubic_screen(*args, restrict={"z": 2, "formula": "CuAu",
                                              "ordered": True})
    assert dropped.best_or_none() is None
    assert all(not c.space_groups for c in dropped.candidates if not c.refuted)


def test_ordered_is_declared_with_a_formula():
    with pytest.raises(ValueError, match="formula"):
        ExtinctionPrior(ordered=True)
    assert ExtinctionPrior(z=2, formula="SiO", ordered=True).declared()["ordered"] is True


def test_nothing_declared_moves_no_screen(nacl_screens, tetrahedrite_screens):
    """With no Z and no density the new fields stay empty on every screen."""
    for screen in (nacl_screens["plain"], tetrahedrite_screens[0]):
        assert screen.prior is None and screen.z is None
        assert screen.z_from_density is None and screen.z_candidates == []
        assert all(not c.excluded_groups and not c.exclusion_reasons
                   and not c.special_positions and not c.count_notes
                   for c in screen.candidates)
