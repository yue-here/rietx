"""The GSAS-II ``.gpx`` reader, against two real projects and some written here.

``tests/data/gsas2_pbso4.gpx`` is the GSAS-II CIF tutorial's converged PbSO4
refinement — one phase against a constant-wavelength neutron histogram *and* a
laboratory X-ray one with a Kα doublet — so the rows below check the reader
against a protocol somebody already verified independently, including the one
number the file states twice: ``Nvars`` against the length of its own
``varyList``.

``tests/data/gsas2_lacamno3_magnetic.gpx`` is the SimpleMagnetic tutorial, and
carries three things the first cannot: a **magnetic** phase beside the nuclear
one, fourteen **constraints** naming their variables with GSAS-II's own objects,
and a pickle stream with **no protocol header** — which is a third of the
tutorial corpus and would have been declined by a sniff written to the magic
bytes alone.

The refusals are tested against files written here rather than vendored, for
``test_projects_gsas.py``'s reason: the shapes they test — a global nobody
vouched for, a truncated stream, a negative Uiso — are not in any file this repo
may carry, and a pickle written from the specification's own layout is
self-describing.  The bytes for the refused global are **literal**, not built
from the reader's own table, so the test cannot agree with the reader by
construction (``io/CLAUDE.md`` § Adding a format, rule 4).
"""

from __future__ import annotations

import math
import pickle
from pathlib import Path

import gemmi
import pytest

import rietx as rx
from rietx.crystallography.symmetry import operator_key, setting_from_operators
from rietx.io.projects.gsas2 import (
    _STATIC_GLOBALS,
    ALLOWED_GLOBALS,
    CW_CENTIDEGREE_POWER,
    TREE_ITEM_STANCE,
    Gsas2GpxError,
    Gsas2Phase,
    _numpy_globals,
    _report_setting,
    item_kind,
    read_gsas2_gpx,
    to_structure,
)
from rietx.optimize.qpa import phase_zmv

DATA = Path(__file__).parent / "data"
PBSO4 = DATA / "gsas2_pbso4.gpx"
MAGNETIC = DATA / "gsas2_lacamno3_magnetic.gpx"
SETTING = DATA / "gsas2_mn3o4_setting.gpx"


@pytest.fixture(scope="module")
def pbso4():
    return read_gsas2_gpx(PBSO4)


@pytest.fixture(scope="module")
def magnetic():
    return read_gsas2_gpx(MAGNETIC)


# --------------------------------------------------------------- what it says

def test_the_phase_and_its_refine_flags(pbso4):
    """One nuclear phase, its cell flagged, and every site refining X and U."""
    assert len(pbso4.phases) == 1
    phase = pbso4.phases[0]
    assert phase.name == "PBSO4"
    assert phase.kind == "nuclear"
    assert phase.space_group == "P n m a"
    assert phase.refine_cell is True
    assert phase.cell[0] == pytest.approx(8.4804429, abs=1e-6)
    assert phase.cell[3:] == (90.0, 90.0, 90.0)
    assert [a.label for a in phase.atoms] == ["Pb1", "S2", "O3", "O4", "O5"]
    assert {a.refine_flags for a in phase.atoms} == {"XU"}
    assert all(a.refine_xyz and a.refine_u for a in phase.atoms)
    assert not any(a.refine_occupancy for a in phase.atoms)
    assert not any(a.anisotropic for a in phase.atoms)


def test_the_two_histograms_and_their_ranges(pbso4):
    """A single-wavelength neutron bank and a laboratory doublet.

    The X-ray histogram's *used* range is not the range the file was loaded
    with, which is the pair that makes a narrowed range visible at all: a reader
    keeping one number could not tell "the author cut the low angles" from "the
    detector started there".
    """
    neutron, xray = pbso4.histograms
    assert (neutron.kind, xray.kind) == ("PNC", "PXC")
    assert neutron.wavelengths == (1.909,)
    assert xray.wavelengths == (1.5405, 1.5443)
    assert neutron.geometry == "Debye-Scherrer"
    assert xray.geometry == "Bragg-Brentano"
    assert neutron.limits == neutron.measured_limits
    assert xray.limits != xray.measured_limits
    assert xray.limits[0] == pytest.approx(14.452, abs=1e-3)
    assert xray.measured_limits[0] == pytest.approx(10.0)
    assert neutron.n_points == 2918
    assert neutron.excluded_regions == () and xray.excluded_regions == ()


def test_the_profile_coefficients_are_centidegrees(pbso4):
    """``U``, ``V``, ``W`` in centidegrees², ``Zero`` already in degrees.

    The conversion is corroborated across two formats by a file this repo
    already holds: the ``.gpx`` of the same 11-BM instrument states ``U`` =
    1.163 where ``tests/data/11bm_gsas.prm`` states 1.163e-4 deg².  ``Zero`` is
    deliberately absent from the map — GSAS-I writes it in centidegrees and
    GSAS-II in degrees, so a shared conversion would be wrong for one of them.
    """
    terms = pbso4.histograms[0].by_name()
    assert terms["U"].refined and terms["V"].refined and terms["W"].refined
    assert terms["U"].value == pytest.approx(291.8966, abs=1e-3)
    assert terms["U"].degrees == pytest.approx(291.8966e-4, abs=1e-8)
    assert terms["X"].degrees == pytest.approx(terms["X"].value / 100.0)
    assert terms["Zero"].degrees is None
    assert terms["Polariz."].degrees is None
    assert "Zero" not in CW_CENTIDEGREE_POWER


def test_the_initial_value_is_kept_beside_the_refined_one(pbso4):
    """Both numbers are the file's, and they are not the same number."""
    w = pbso4.histograms[0].by_name()["W"]
    assert w.initial == pytest.approx(651.592, abs=1e-3)
    assert w.value == pytest.approx(839.032, abs=1e-3)


def test_the_runs_own_figures(pbso4):
    assert pbso4.rwp == pytest.approx(6.1707, abs=1e-3)
    assert pbso4.n_observations == 8739
    assert pbso4.n_variables == 49
    assert pbso4.converged is True
    assert pbso4.version == "5046"


def test_the_vary_list_is_the_protocol_and_matches_the_stated_count(pbso4):
    """``Nvars`` and ``varyList`` are two statements of one fact.

    The file writes the count in ``Rvals`` and the names in ``varyList``, and
    nothing in the format makes them agree, so checking one against the other
    is a check of the whole recovery rather than of one field.  The esds are a
    third statement of the same length.
    """
    assert len(pbso4.vary_list) == pbso4.n_variables
    assert len(pbso4.esds) == pbso4.n_variables
    assert "0::A0" in pbso4.vary_list


def test_gof_is_the_root_of_reduced_chi_squared(pbso4):
    """Measured, because the sibling reader's docstring claimed the opposite.

    ``Rvals['GOF']`` is ``sqrt(chisq / (Nobs - Nvars))`` — on this file and on
    all six corpus projects stating the four numbers, to six figures.  GSAS-I's
    ``GDNFT`` really is a reduced χ² rather than its root, so the two formats do
    **not** share a convention and a reader that assumed they did would report
    the square of the number meant.
    """
    reduced = pbso4.chi2 / (pbso4.n_observations - pbso4.n_variables)
    assert pbso4.gof == pytest.approx(reduced ** 0.5, rel=1e-9)
    assert pbso4.gof == pytest.approx(2.10143, abs=1e-5)


def test_the_background_is_carried_as_the_file_states_it(pbso4):
    background = pbso4.histograms[1].background
    assert background.function == "chebyschev-1"
    assert background.refined is True
    assert len(background.coefficients) == 6
    assert background.n_debye == 0 and background.n_peaks == 0


def test_the_sample_broadening_is_per_phase_and_histogram(pbso4):
    """Size and microstrain refined against the X-ray bank and not the neutron."""
    neutron = pbso4.hap[("PBSO4", "PWDR PBSO4.CWN Bank 1")]
    xray = pbso4.hap[("PBSO4", "PWDR PBSO4.XRA Bank 1")]
    assert neutron.size.kind == "isotropic"
    assert not neutron.size.values[0].refined
    assert xray.size.values[0].refined
    assert xray.size.values[0].value == pytest.approx(0.2367, abs=1e-4)
    assert xray.mustrain.values[0].refined
    assert not xray.lebail and xray.used


def test_the_sample_parameters_carry_their_flags(pbso4):
    """A Bragg-Brentano ``Shift`` refined, a Debye-Scherrer ``DisplaceX`` too."""
    xray = pbso4.histograms[1]
    assert xray.sample["Shift"].refined
    assert xray.sample["Shift"].value == pytest.approx(75.842, abs=1e-3)
    assert not xray.sample["Absorption"].refined
    assert pbso4.histograms[0].sample["DisplaceX"].refined


# ------------------------------------------------------------ what it becomes

def test_to_structure_carries_the_flags_across(pbso4):
    """The cell's one flag, and each site's letters, land on the parameters."""
    structure = to_structure(pbso4)
    phase = structure.phases[0]
    assert phase.name == "PBSO4"
    assert phase.space_group == "P n m a"
    assert phase.cell.a.value == pytest.approx(8.4804429, abs=1e-6)
    assert phase.cell.a.vary and phase.cell.b.vary and phase.cell.c.vary
    assert len(phase.atoms) == 5
    assert all(a.biso.vary for a in phase.atoms)
    assert not any(a.occ.vary for a in phase.atoms)


def test_uiso_becomes_biso(pbso4):
    """``B = 8π²U``, and nothing else touches the number."""
    import math

    structure = to_structure(pbso4)
    stated = pbso4.phases[0].atoms[0].uiso
    assert structure.phases[0].atoms[0].biso.value == pytest.approx(
        8.0 * math.pi ** 2 * stated, rel=1e-12)


def test_the_x_flag_is_read_through_the_site_symmetry(pbso4):
    """GSAS-II's flag means "as permitted by symmetry", and so does the import.

    Every PbSO4 site sits on the mirror at y = ¼, so ``x`` and ``z`` move and
    ``y`` does not — carrying the flag onto all three would free a coordinate
    the refinement never moved.
    """
    structure = to_structure(pbso4)
    pb = structure.phases[0].atoms[0]
    assert pb.x.vary and pb.z.vary
    refinement = rx.Refinement(structure, rx.Instrument.bragg_brentano())
    free = {row.path for row in refinement.parameters() if row.refinable}
    assert any(p.startswith("phases.0.atoms.0.dof") for p in free)


def test_the_build_reports_what_it_did_not_take(pbso4):
    """The phase scale is seeded, not converted, and the row says so."""
    found: list = []
    to_structure(pbso4, diagnostics=found)
    codes = {d.code for d in found}
    assert "GSAS2_GPX_SCALE_NOT_COMPARABLE" in codes


# ------------------------------------------------------------- the second file

def test_a_headerless_pickle_is_still_claimed(magnetic):
    """A third of the corpus carries no protocol header, and this is one."""
    assert MAGNETIC.open("rb").read(2) != b"\x80\x02"
    assert rx.identify_project_format(MAGNETIC).name == "gsas2_gpx"
    assert len(magnetic.phases) == 2


def test_a_magnetic_phase_is_refused_by_name(magnetic):
    """The nuclear half would look complete, which is the whole objection."""
    nuclear, mag = magnetic.phases
    assert nuclear.kind == "nuclear" and mag.magnetic
    assert to_structure(magnetic, phase=nuclear.name) is not None
    with pytest.raises(Gsas2GpxError, match="magnetic"):
        to_structure(magnetic, phase=mag.name)


def test_a_magnetic_phase_reads_its_own_atom_columns(magnetic):
    """``AtomPtrs`` moves for a magnetic phase, and the reader follows it.

    A magnetic phase carries three moment columns after the occupancy, so its
    site symmetry and ADP flag sit at 10 and 12 rather than at 7 and 9.  Read at
    the nuclear phase's fixed offsets, the label and species would still look
    right and everything after them would be wrong — which is why this asserts a
    field from *beyond* the moved boundary.
    """
    atom = magnetic.phases[1].atoms[0]
    assert atom.species.startswith("Mn")
    assert atom.adp in ("I", "A")
    assert atom.refine_moment


def test_the_constraints_are_resolved_into_names(magnetic):
    """Fourteen rows, each naming its variables in GSAS-II's own spelling.

    The file stores a variable as three random-number ids and a name, so a row
    is only readable after the ids are looked up in the project's own phases,
    histograms and atoms.  An equivalence is the one shape ``tie_equal``
    reproduces, and the count of them is what the diagnostic quotes.
    """
    assert len(magnetic.constraints) == 14
    equivalences = [c for c in magnetic.constraints if c.is_equivalence]
    assert len(equivalences) == 14
    first = equivalences[0]
    assert len(first.terms) == 2
    assert all(name.count(":") >= 2 for _, name in first.terms)
    assert "?" not in str(first)


def test_the_missing_variable_count_is_none_rather_than_zero(magnetic):
    """``Rvals`` need not state ``Nvars``, and a zero would read as an answer."""
    assert magnetic.n_variables is None
    assert magnetic.rwp is not None


def test_the_read_reports_the_magnetic_phase_and_the_constraints(magnetic):
    found: list = []
    read_gsas2_gpx(MAGNETIC, diagnostics=found)
    codes = {d.code for d in found}
    assert "GSAS2_GPX_PHASE_MAGNETIC" in codes
    assert "GSAS2_GPX_CONSTRAINT_NOT_CARRIED" in codes


def test_a_magphases_entry_is_reported_as_what_the_file_shows():
    """#606: the `magPhases` arm claimed the file's Rwp includes magnetic
    scattering.  On the Mn3O4 tutorial file the entry is one of the project's
    own histogram names, the project holds one nuclear phase and no magnetic
    one, so nothing magnetic is modelled: the row says that, at info."""
    found: list = []
    model = read_gsas2_gpx(SETTING, diagnostics=found)
    (phase,) = model.phases
    assert phase.kind == "nuclear"
    assert phase.magnetic_partner in {h.name for h in model.histograms}
    (d,) = [d for d in found if d.code == "GSAS2_GPX_PHASE_MAGNETIC"]
    assert d.level == "info"
    assert "one of this project's histogram names" in d.message
    assert "holds no phase GSAS-II types `magnetic`" in d.message
    assert "Rwp" not in d.message and "not comparable" not in d.message


def test_the_comparison_warning_rides_on_the_magnetic_phase():
    """#606's other half: the project that does hold a magnetic phase is
    where the file's figures include magnetic scattering, and the warning
    there says so; the nuclear phase beside it carries no `magPhases`."""
    found: list = []
    model = read_gsas2_gpx(MAGNETIC, diagnostics=found)
    assert [p.magnetic_partner for p in model.phases] == [None, None]
    (d,) = [d for d in found if d.code == "GSAS2_GPX_PHASE_MAGNETIC"]
    assert d.level == "warning" and d.where == ["phases.1"]
    assert "not comparable" in d.message


# ------------------------------------------------------------- through the door

def test_the_registry_claims_both_and_builds(pbso4):
    """``read_project_model`` is the one door, and it dispatches on content."""
    found: list = []
    model = rx.read_project_model(PBSO4, diagnostics=found)
    assert model.format.name == "gsas2_gpx"
    assert model.stated.phases[0].name == "PBSO4"
    assert model.to_structure().phases[0].space_group == "P n m a"
    assert model.diagnostics  # the read's half, kept on the answer itself


def test_the_sniff_does_not_claim_the_other_formats():
    """Content dispatch, not suffix: a ``.EXP`` is still a ``.EXP``."""
    assert rx.identify_project_format(DATA / "FAP.EXP").name == "gsas_exp"


# ------------------------------------------------------------ what it refuses

def _write_gpx(path: Path, items: list) -> Path:
    """Write a ``.gpx``: one ``pickle.dump`` per top-level tree item."""
    with path.open("wb") as handle:
        for item in items:
            pickle.dump(item, handle, protocol=2)
    return path


def _minimal_project(**phase_overrides) -> list:
    """The smallest tree this reader will build a structure from."""
    general = {
        "Name": "widget", "Type": "nuclear", "AtomPtrs": [3, 1, 7, 9],
        "SGData": {"SpGrp": "P m -3 m"},
        "Cell": [True, 4.0, 4.0, 4.0, 90.0, 90.0, 90.0, 64.0],
    }
    phase = {
        "General": general,
        "Atoms": [["Na1", "Na", "XU", 0.0, 0.0, 0.0, 1.0, "m3m", 1, "I",
                   0.01, 0, 0, 0, 0, 0, 0, 12345]],
        "Histograms": {},
        "pId": 0,
        "ranId": 999,
    }
    for key, value in phase_overrides.items():
        if key == "atoms":
            phase["Atoms"] = value
        else:
            general[key] = value
    return [
        [["Controls", {"LastSavedUsing": "5000"}]],
        [["Phases", None], ["widget", phase]],
    ]


# ---------------------------------------- the isotope a phase chooses (#554)
#
# GSAS-II keeps a site's isotope outside its atom type, in the phase's
# General['Isotope'] ("dict of isotopes for each atom type", GSASIIobj docs),
# as `add_phase` + `General['Isotope'].update({'H': '2', 'Ni': '58'})` stores
# it in GSAS-II 5.6.3. The fragment below is that dict, built here.

def _isotope_rows():
    return [["Ni1", "Ni+2", "XU", 0.0, 0.0, 0.0, 1.0, "m3m", 1, "I",
             0.005, 0, 0, 0, 0, 0, 0, 11],
            ["H1", "H", "", 0.5, 0.5, 0.5, 1.0, "m3m", 1, "I",
             0.01, 0, 0, 0, 0, 0, 0, 12],
            ["D1", "D", "", 0.5, 0.0, 0.0, 1.0, "4/mmm", 3, "I",
             0.01, 0, 0, 0, 0, 0, 0, 13]]


@pytest.mark.parametrize("choices, species, b_fm", [
    ({"Ni+2": "58", "H": "2", "D": "2"}, ["58Ni2+", "2H", "D"], [14.4, 6.671, 6.671]),
    ({"Ni+2": "Nat. Abund.", "H": "Nat. Abund.", "D": "Nat. Abund."},
     ["Ni2+", "H", "D"], [10.3, -3.739, 6.671]),
    ({}, ["Ni2+", "H", "D"], [10.3, -3.739, 6.671]),
])
def test_the_phases_isotope_choice_is_the_sites_species(tmp_path, choices,
                                                        species, b_fm):
    from rietx.crystallography.neutron import b_coh
    path = _write_gpx(tmp_path / "iso.gpx", _minimal_project(
        atoms=_isotope_rows(), Isotope=choices))
    model = read_gsas2_gpx(path)
    assert model.phases[0].isotope == choices
    found: list = []
    atoms = to_structure(model, diagnostics=found).phases[0].atoms
    assert [a.species for a in atoms] == species
    assert [b_coh(a.species) for a in atoms] == pytest.approx(b_fm)
    said = [d.message for d in found if d.code == "GSAS2_GPX_SPECIES_NORMALISED"]
    if choices.get("H") == "2":
        assert any("'H'" in m and "isotope 2" in m for m in said)


@pytest.mark.parametrize("choice, match", [
    ("99", "no neutron scattering length"),   # a mass the Sears table lacks
    ("heavy", "neither"),
])
def test_an_isotope_choice_rietx_cannot_scatter_is_refused(tmp_path, choice, match):
    path = _write_gpx(tmp_path / "iso.gpx", _minimal_project(
        atoms=_isotope_rows(), Isotope={"Ni+2": choice}))
    with pytest.raises(Gsas2GpxError, match=match) as exc:
        to_structure(read_gsas2_gpx(path))
    assert "'Ni+2'" in str(exc.value) and "iso.gpx" in str(exc.value)


@pytest.mark.parametrize("isotope", [None, "2", ["H", "2"]])
def test_an_isotope_entry_that_is_not_a_dict_is_refused(tmp_path, isotope):
    """Present and not a dict is not "none chosen": reading it as ``{}`` made
    a malformed choice indistinguishable from natural abundance (#570
    review, follow-up 1).  Absent stays natural abundance (the ``{}`` row of
    the parametrisation above)."""
    path = _write_gpx(tmp_path / "iso.gpx", _minimal_project(
        atoms=_isotope_rows(), Isotope=isotope))
    with pytest.raises(Gsas2GpxError, match=r"General\['Isotope'\]") as exc:
        read_gsas2_gpx(path)
    assert "not taken as natural abundance" in str(exc.value)


def test_a_global_nobody_vouched_for_refuses_the_whole_file(tmp_path):
    """The bytes are literal, so this cannot agree with the reader by accident.

    ``c`` is pickle's GLOBAL opcode and what follows is a module and a name on
    their own lines.  ``pickle.load`` would import and call it; this reader
    names it and reads nothing.
    """
    path = tmp_path / "hostile.gpx"
    path.write_bytes(b"\x80\x02cos\nsystem\nq\x00.")
    with pytest.raises(Gsas2GpxError) as caught:
        read_gsas2_gpx(path)
    assert "os.system" in str(caught.value)
    assert "hostile.gpx" in str(caught.value)
    assert "ALLOWED_GLOBALS" in str(caught.value)


def test_a_refused_global_is_refused_even_after_good_items(tmp_path):
    """Half a project is not a model, so the file is refused entire."""
    path = tmp_path / "late.gpx"
    with path.open("wb") as handle:
        pickle.dump([["Controls", {"LastSavedUsing": "5000"}]], handle, protocol=2)
        handle.write(b"\x80\x02cos\nsystem\nq\x00.")
    with pytest.raises(Gsas2GpxError, match="os.system"):
        read_gsas2_gpx(path)


def test_a_truncated_stream_names_the_file(tmp_path):
    """Never the parser's own exception (``io/CLAUDE.md`` § Refusals)."""
    good = PBSO4.read_bytes()
    path = tmp_path / "cut.gpx"
    path.write_bytes(good[: len(good) // 3])
    with pytest.raises(Gsas2GpxError, match="cut.gpx"):
        read_gsas2_gpx(path)


def test_an_empty_file_is_refused(tmp_path):
    path = tmp_path / "empty.gpx"
    path.write_bytes(b"")
    with pytest.raises(Gsas2GpxError, match="empty"):
        read_gsas2_gpx(path)


def test_a_missing_file_names_itself(tmp_path):
    with pytest.raises(Gsas2GpxError, match="absent.gpx"):
        read_gsas2_gpx(tmp_path / "absent.gpx")


def test_a_negative_uiso_is_read_with_its_bound_widened(tmp_path):
    """A real refinement reaches one and GSAS-II stores it, so the reader
    keeps the file's number, widens the floor to hold it and says so
    (PR #663)."""
    atoms = [["Na1", "Na", "XU", 0.0, 0.0, 0.0, 1.0, "m3m", 1, "I",
              -0.004, 0, 0, 0, 0, 0, 0, 12345]]
    path = _write_gpx(tmp_path / "negative.gpx", _minimal_project(atoms=atoms))
    diagnostics = []
    biso = to_structure(read_gsas2_gpx(path),
                        diagnostics=diagnostics).phases[0].atoms[0].biso
    b = -0.004 * 8 * math.pi ** 2
    assert (biso.value, biso.min) == (pytest.approx(b), pytest.approx(b))
    assert "BISO_BOUND_WIDENED" in [d.code for d in diagnostics]


def test_a_phase_with_no_sites_is_refused(tmp_path):
    path = _write_gpx(tmp_path / "lebail.gpx", _minimal_project(atoms=[]))
    model = read_gsas2_gpx(path)
    assert model.phases[0].atoms == ()
    with pytest.raises(Gsas2GpxError, match="no sites"):
        to_structure(model)


def test_a_pawley_phase_is_refused(tmp_path):
    path = _write_gpx(tmp_path / "pawley.gpx", _minimal_project(doPawley=True))
    with pytest.raises(Gsas2GpxError, match="Pawley"):
        to_structure(read_gsas2_gpx(path))


def test_a_symbol_this_build_cannot_resolve_is_refused(tmp_path):
    path = _write_gpx(tmp_path / "symbol.gpx",
                      _minimal_project(SGData={"SpGrp": "P wobble"}))
    with pytest.raises(Gsas2GpxError, match="P wobble"):
        to_structure(read_gsas2_gpx(path))


def test_a_schema_refusal_is_converted_rather_than_leaked(tmp_path):
    """The class, not a third instance: no pydantic error reaches a caller.

    An occupancy of 40 is nothing the corpus contains and nothing the reader
    checks for by name.  It must still come back naming the file, because a
    message about a ``Parameter`` tells a caller nothing about which file they
    handed in (``io/CLAUDE.md`` § Refusals — the rule ``read_gsas_prm`` paid for).
    """
    atoms = [["Na1", "Na", "XU", 0.0, 0.0, 0.0, 40.0, "m3m", 1, "I",
              0.01, 0, 0, 0, 0, 0, 0, 12345]]
    path = _write_gpx(tmp_path / "occ.gpx", _minimal_project(atoms=atoms))
    with pytest.raises(Gsas2GpxError, match="occ.gpx"):
        to_structure(read_gsas2_gpx(path))


# --------------------------------------------------------- what it says it does

def test_excluded_regions_are_read_from_the_limits_tail(tmp_path):
    """``Limits[2:]`` are ranges masked *out*, which no corpus file carries.

    The layout is GSAS-II's own statement rather than a guess — its refinement
    setup reads ``Limits[2:]`` as the excluded list and masks the data inside
    each pair — but none of the 34 tutorial projects has one, so the path is
    exercised here or nowhere.
    """
    tree = _minimal_project()
    tree.append([
        ["PWDR sample.xye", [{"hId": 0, "ranId": 7}, None]],
        ["Limits", [[5.0, 90.0], [10.0, 80.0], [41.0, 43.5]]],
        ["Instrument Parameters", [{"Type": ["PXC", "PXC", 0],
                                    "Lam": [1.5406, 1.5406, 0]}, {}]],
    ])
    model = read_gsas2_gpx(_write_gpx(tmp_path / "excluded.gpx", tree))
    histogram = model.histograms[0]
    assert histogram.limits == (10.0, 80.0)
    assert histogram.measured_limits == (5.0, 90.0)
    assert histogram.excluded_regions == ((41.0, 43.5),)


def test_an_unclassified_tree_item_is_reported_not_dropped(tmp_path):
    """A kind with no stance says so, which is the point of the table."""
    tree = _minimal_project()
    tree.append([["Wombat data", {"nothing": True}]])
    model = read_gsas2_gpx(_write_gpx(tmp_path / "wombat.gpx", tree))
    assert any("Wombat data" in line for line in model.unsupported)


def test_an_item_with_no_label_is_reported_by_every_pass(tmp_path):
    """A malformed item is reported once and crashes nothing afterwards.

    The reader walks the tree three times: once to build the model, twice more
    to resolve the random-number ids a constraint names. The later passes used
    to assume the shape the first had already reported as unreadable, so a
    project holding a bare ``[42]`` raised ``TypeError`` out of the reader
    rather than a refusal or a report. Found by the review pass.
    """
    tree = _minimal_project()
    tree.append([42])
    tree.append("not a tree item at all")
    model = read_gsas2_gpx(_write_gpx(tmp_path / "malformed.gpx", tree))
    assert sum("could not label" in line for line in model.unsupported) == 2
    assert model.phases[0].name == "widget"


def test_an_empty_atom_row_does_not_reach_a_negative_index(tmp_path):
    """``_atom`` tolerates a short row, so the id pass must tolerate it too."""
    tree = _minimal_project(atoms=[[], ["Na1", "Na", "XU", 0.0, 0.0, 0.0, 1.0,
                                        "m3m", 1, "I", 0.01, 0, 0, 0, 0, 0, 0,
                                        12345]])
    model = read_gsas2_gpx(_write_gpx(tmp_path / "shortrow.gpx", tree))
    assert [a.label for a in model.phases[0].atoms] == ["Na1"]


def test_every_stance_key_is_a_kind_the_reader_computes():
    """The table is keyed by what ``item_kind`` produces, both ways.

    A label like ``Rigid bodies`` is its own key and ``PWDR sample.xye`` keys on
    its first word; a row written under ``Rigid`` would never be looked up, and
    nothing would fail — the item would simply be reported as unclassified.
    """
    for key in TREE_ITEM_STANCE:
        assert item_kind(key) == key, key
    assert item_kind("PWDR sample.xye Bank 1") == "PWDR"
    assert item_kind("Sequential results") == "Sequential results"


def test_the_allow_list_and_the_resolver_agree_both_ways():
    """A declared name is a claim (WP-1076), and this is the claim's test.

    ``ALLOWED_GLOBALS`` is what the module *says* it admits and the resolver is
    what it does admit.  Partitioned both ways, so a name documented but not
    wired refuses a real file, and a name wired but not documented widens the
    trust boundary without saying so.
    """
    resolved = {**_numpy_globals(), **_STATIC_GLOBALS}
    assert set(resolved) == set(ALLOWED_GLOBALS)
    assert all(reason for reason in ALLOWED_GLOBALS.values())
    assert ("os", "system") not in resolved


def test_the_corpus_fixtures_name_nothing_outside_the_allow_list():
    """The two vendored projects exercise the boundary they are here to prove."""
    import pickletools

    for path in (PBSO4, MAGNETIC, SETTING):
        with path.open("rb") as stream:
            names = []
            while stream.read(1):
                stream.seek(stream.tell() - 1)
                for opcode, argument, _ in pickletools.genops(stream):
                    if opcode.name == "GLOBAL":
                        names.append(tuple(str(argument).split(" ", 1)))
        assert names, f"{path.name} names no globals at all"
        assert set(names) <= set(ALLOWED_GLOBALS), sorted(set(names) - set(ALLOWED_GLOBALS))


# ------------------------------------------ the setting the operators state

def test_the_operators_settle_a_symbol_that_names_two_settings():
    """``tests/data/gsas2_mn3o4_setting.gpx`` writes ``I 41/a m d`` bare.

    A bare symbol is two groups and gemmi has to pick one; it picks ``:1``.  The
    project also writes the operations themselves, and they are ``:2`` — so the
    setting is *read* here rather than assumed, and the phase is built under the
    group the file describes (issue #101, WP-1118).
    """
    phase = read_gsas2_gpx(SETTING).phases[0]
    assert phase.space_group == "I 41/a m d"          # the file's own string
    assert phase.space_group_from_operators == "I 41/a m d:2"
    assert phase.resolved_space_group == "I 41/a m d:2"
    assert to_structure(read_gsas2_gpx(SETTING)).phases[0].space_group \
        == "I 41/a m d:2"


def test_reading_the_setting_is_reported_rather_than_done_in_silence():
    diagnostics: list = []
    read_gsas2_gpx(SETTING, diagnostics=diagnostics)
    found = [d for d in diagnostics
             if d.code == "GSAS2_GPX_SETTING_FROM_OPERATORS"]
    assert len(found) == 1
    assert found[0].level == "info"        # nothing lost; the answer improved
    assert "I 41/a m d:2" in found[0].message
    assert found[0].where == ["phases.0.space_group"]
    # and the fit-time report is not also raised about a setting that was read
    assert [d for d in diagnostics
            if d.code == "SPACE_GROUP_SETTING_ASSUMED"] == []

    # and it names what the bare symbol would have resolved to, which is the
    # whole content of the row: the operators overturned that reading
    assert "I 41/a m d:1" in found[0].message


def test_operators_that_confirm_the_bare_reading_do_not_claim_to_overturn_it():
    """Reading a setting is not the same as changing one (WP-1118 review).

    Every rhombohedral GSAS-II phase writes a bare ``R -3 c`` with hexagonal
    operators, and hexagonal axes are what the bare symbol resolves to anyway.
    Saying the phase was built under something "rather than" that reading would
    be a confident wrong statement about a file nothing was taken from.
    """
    phase = Gsas2Phase(
        name="calcite", kind="nuclear", space_group="R -3 c",
        space_group_from_operators="R -3 c:H",
        cell=(4.9896, 4.9896, 17.061, 90.0, 90.0, 120.0),
        refine_cell=False, number=0)
    diagnostics: list = []
    _report_setting("<model>", phase, diagnostics)
    (found,) = diagnostics
    assert found.code == "GSAS2_GPX_SETTING_FROM_OPERATORS"
    assert "confirm that reading" in found.message
    assert "is built under" not in found.message


def test_the_settings_this_file_chooses_between_swap_its_two_sites():
    """Why the choice matters here, where the *composition* cannot show it.

    Mn3O4 is Mn12 O16 under either setting because both cation sites are Mn.
    What differs is which site carries which multiplicity, so a reader that took
    gemmi's ``:1`` would put 8 Mn where the file puts 4.
    """
    import numpy as np

    from rietx.crystallography.symmetry import expand_positions, get_spacegroup

    sites = [(0.0, 0.75, 0.125), (0.0, 0.0, 0.5), (0.0, 0.02775, 0.25924)]
    counts = {s: [len(expand_positions(get_spacegroup(s), np.array(p)))
                  for p in sites]
              for s in ("I 41/a m d:1", "I 41/a m d:2")}
    assert counts["I 41/a m d:1"] == [8, 4, 16]
    assert counts["I 41/a m d:2"] == [4, 8, 16]


def test_a_single_setting_symbol_says_nothing_either_way():
    """The vendored PbSO4 is ``P n m a``, which the tables hold once."""
    diagnostics: list = []
    phase = read_gsas2_gpx(PBSO4, diagnostics=diagnostics).phases[0]
    assert phase.space_group_from_operators is None
    assert phase.resolved_space_group == "P n m a"
    assert [d for d in diagnostics if "SETTING" in d.code] == []


#: ``F d d d:2``'s coset representatives, written out rather than generated.  A
#: fixture built from gemmi could only show the reader agreeing with itself
#: (``io/CLAUDE.md`` § Adding a format, rule 4), so these come from the tables,
#: in GSAS-II's own ``(rotation, translation)`` shape; the F centring and the
#: inversion are the ``SGCen``/``SGInv`` entries beside them, as GSAS-II stores
#: them.
_FDDD_2_OPS = [
    ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0.0, 0.0, 0.0]),
    ([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], [0.75, 0.75, 0.0]),
    ([[-1, 0, 0], [0, 1, 0], [0, 0, -1]], [0.75, 0.0, 0.75]),
    ([[1, 0, 0], [0, -1, 0], [0, 0, -1]], [0.0, 0.75, 0.75]),
]
_FDDD_CEN = [[0.0, 0.0, 0.0], [0.0, 0.5, 0.5], [0.5, 0.0, 0.5], [0.5, 0.5, 0.0]]
_FDDD_CELL = [True, 7.7127, 8.54329, 8.53643, 90.0, 90.0, 90.0, 562.48]


def test_operators_written_from_the_tables_pick_the_same_setting(tmp_path):
    """The corpus case, reproduced from the tables instead of from a file."""
    project = _minimal_project(
        SGData={"SpGrp": "F d d d", "SGOps": _FDDD_2_OPS,
                "SGCen": _FDDD_CEN, "SGInv": True},
        Cell=list(_FDDD_CELL))
    path = _write_gpx(tmp_path / "fddd.gpx", project)
    assert read_gsas2_gpx(path).phases[0].space_group_from_operators \
        == "F d d d:2"


def test_operators_matching_no_setting_leave_the_symbol_assumed(tmp_path):
    """A shape no corpus file has, so it is written here.

    Half of ``F d d d:2`` is a subgroup and no setting of the symbol, so the
    operators settle nothing — and the honest answer is the ordinary assumption
    with the ordinary report, not a confident wrong pin.
    """
    project = _minimal_project(
        SGData={"SpGrp": "F d d d", "SGOps": _FDDD_2_OPS[:2],
                "SGCen": _FDDD_CEN, "SGInv": True},
        Cell=list(_FDDD_CELL))
    path = _write_gpx(tmp_path / "partial.gpx", project)
    diagnostics: list = []
    phase = read_gsas2_gpx(path, diagnostics=diagnostics).phases[0]
    assert phase.space_group_from_operators is None
    assert phase.resolved_space_group == "F d d d"
    codes = [d.code for d in diagnostics]
    assert "SPACE_GROUP_SETTING_ASSUMED" in codes
    assert "GSAS2_GPX_SETTING_FROM_OPERATORS" not in codes


def test_a_phase_stating_no_operators_at_all_is_still_read(tmp_path):
    """``SGData`` with only ``SpGrp`` is what every other project reader has."""
    path = _write_gpx(tmp_path / "bare.gpx",
                      _minimal_project(SGData={"SpGrp": "F d d d"},
                                       Cell=list(_FDDD_CELL)))
    diagnostics: list = []
    phase = read_gsas2_gpx(path, diagnostics=diagnostics).phases[0]
    assert phase.space_group_from_operators is None
    assert [d.code for d in diagnostics].count("SPACE_GROUP_SETTING_ASSUMED") == 1


# ------------------------------------------ the phase CIF GSAS-II imports
#
# GSAS-II has no text project format, so the write direction is the pair it
# imports: this CIF for the phases and an `.instprm` for the machine
# (`test_gsas2_instprm.py`). The round trip is through `structure_from_cif`,
# and the setting is checked where GSAS-II checks it — in the operations.


def _spinel() -> rx.Structure:
    """Origin choice 2, the setting a bare ``F d -3 m`` cannot state here.

    The case issue #217 measured: read as choice 1 the 8a and 16d
    multiplicities swap, so AB₂O₄ becomes A₂BO₄ under a fit that converges.
    """
    def p(v):
        return rx.Parameter(value=v)

    def site(label, species, x, y, z):
        return rx.Atom(label=label, species=species, x=p(x), y=p(y), z=p(z))

    return rx.Structure(phases=[rx.Phase(
        name="spinel", space_group="F d -3 m:2",
        cell=rx.Cell(a=p(8.0831), b=p(8.0831), c=p(8.0831),
                     alpha=p(90.0), beta=p(90.0), gamma=p(90.0)),
        atoms=[site("Mg1", "Mg", 0.125, 0.125, 0.125),
               site("Al1", "Al", 0.5, 0.5, 0.5),
               site("O1", "O", 0.2624, 0.2624, 0.2624)])])


def test_the_phase_cif_round_trips_a_structure(tmp_path):
    out = tmp_path / "phases.cif"
    original = rx.Structure.from_cif(str(DATA / "fluorapatite.cif"))
    rx.write_gsas2_phase_cif(original, out)
    back = rx.Structure.from_cif(str(out))

    (a, b) = (original.phases[0], back.phases[0])
    assert b.space_group == a.space_group
    assert b.cell.a.value == pytest.approx(a.cell.a.value, rel=1e-9)
    assert b.cell.c.value == pytest.approx(a.cell.c.value, rel=1e-9)
    assert [at.label for at in b.atoms] == [at.label for at in a.atoms]
    for site, was in zip(b.atoms, a.atoms, strict=True):
        assert site.x.value == pytest.approx(was.x.value, abs=5e-7)
        assert site.biso.value == pytest.approx(was.biso.value, abs=5e-5)


def test_the_setting_travels_in_the_operations_and_in_the_alt_symbol(tmp_path):
    """Two readers, two spellings, and one machine channel.

    GSAS-II resolves a bare two-origin symbol to origin choice 2 and answers a
    colon-suffixed one by setting the phase to ``P 1``; gemmi resolves the same
    bare symbol to choice 1 and prefers ``_space_group_name_H-M_alt`` when both
    H-M tags are present.  So the bare symbol goes in the tag GSAS-II reads,
    the resolved one in the tag gemmi reads, and the operations state it
    outright.
    """
    out = tmp_path / "spinel.cif"
    diagnostics: list = []
    rx.write_gsas2_phase_cif(_spinel(), out, diagnostics=diagnostics)
    block = gemmi.cif.read(str(out)).sole_block()

    assert block.find_value("_symmetry_space_group_name_H-M").strip("'") == "F d -3 m"
    assert block.find_value("_space_group_name_H-M_alt").strip("'") == "F d -3 m:2"
    ops = [row.str(0) for row in
           block.find("_space_group_symop_", ["operation_xyz"])]
    # gemmi holds an operation's rotation and translation over ``DEN``, which
    # is what ``operator_keys`` divides them by
    keys = {operator_key([[v / op.DEN for v in row] for row in op.rot],
                         [t / op.DEN for t in op.tran])
            for op in (gemmi.Op(t) for t in ops)}
    assert setting_from_operators("F d -3 m", keys) == "F d -3 m:2"

    # and this package reads its own file back into the setting it wrote,
    # which is the difference between MgAl2O4 and Mg2AlO4 (issue #217)
    back = rx.Structure.from_cif(str(out)).phases[0]
    assert back.space_group == "F d -3 m:2"
    counts = phase_zmv(back.space_group, back.cell.lengths_angles(),
                       [(a.species, a.x.value, a.y.value, a.z.value,
                         a.occ.value) for a in back.atoms]).element_counts
    assert counts == {"Mg": 8.0, "Al": 16.0, "O": 32.0}
    (row,) = [d for d in diagnostics
              if d.code == "GSAS2_CIF_SETTING_IN_OPERATORS"]
    assert "F d -3 m:1" in row.message


def test_an_unambiguous_symbol_says_nothing_about_its_setting(tmp_path):
    diagnostics: list = []
    rx.write_gsas2_phase_cif(
        rx.Structure.from_cif(str(DATA / "fluorapatite.cif")),
        tmp_path / "fap.cif", diagnostics=diagnostics)
    assert not [d for d in diagnostics
                if d.code == "GSAS2_CIF_SETTING_IN_OPERATORS"]


def test_the_phase_cif_says_what_it_could_not_state(tmp_path):
    diagnostics: list = []
    rx.write_gsas2_phase_cif(_spinel(), tmp_path / "said.cif",
                             diagnostics=diagnostics)
    (row,) = [d for d in diagnostics if d.code == "GSAS2_CIF_FIELD_NOT_WRITTEN"]
    assert row.level == "warning"
    assert "the refine flags" in row.message


def test_the_phase_cif_refuses_a_non_finite_value(tmp_path):
    """``repr`` spells it ``inf`` and no CIF reader parses that — the refusal
    every writer here makes, and the only one a phase CIF needs."""
    structure = _spinel()
    structure.phases[0].atoms[0].biso.max = float("inf")
    structure.phases[0].atoms[0].biso.value = float("inf")
    with pytest.raises(ValueError, match="inf"):
        rx.write_gsas2_phase_cif(structure, tmp_path / "bad.cif")


def test_two_phases_of_one_name_get_two_blocks(tmp_path):
    """A CIF block name is a key, and gemmi answers a duplicate with a bare
    ``RuntimeError`` — so a two-phase mixture of one material under one name
    never reached a file. The phase index is what distinguishes them."""
    structure = _spinel()
    structure.phases.append(structure.phases[0].model_copy(deep=True))
    out = tmp_path / "twice.cif"
    rx.write_gsas2_phase_cif(structure, out)
    blocks = [b.name for b in gemmi.cif.read(str(out))]
    assert len(blocks) == 2 and len(set(blocks)) == 2


def test_a_site_label_a_cif_loop_cannot_carry_is_refused(tmp_path):
    """`write_structure_block` adds a label and a species as **bare** loop
    values, so whitespace in one splits the row and no reader can parse the
    block back. The three sibling writers refuse the same shape by name."""
    structure = _spinel()
    structure.phases[0].atoms[0].label = "Mg 1"
    with pytest.raises(ValueError, match="splits the row"):
        rx.write_gsas2_phase_cif(structure, tmp_path / "bad.cif")


# ------------------------------------ what GSAS-II's CIF import reads (#553)
#
# GSAS-II 5.6.3's importer (scriptable `add_phase`, run as a black box) made
# `7Li`/`2H`/`60Ni`/`7Li1+` into H and `Cu+` into C, saying so only on stdout,
# while this package's own `structure_from_cif` read every one back unchanged.
# So the round trip cannot see it and these pin the written symbol instead.

def _one_site(species: str) -> rx.Structure:
    return rx.Structure(phases=[rx.Phase(
        name="syn", space_group="Pm-3m", cell=rx.Cell.cubic(4.0),
        atoms=[rx.Atom(label="A1", species=species, x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                       biso=rx.Parameter(value=0.5, min=0.0, max=25.0))])])


def _type_symbol(path: Path) -> str:
    block = gemmi.cif.read(str(path)).sole_block()
    return gemmi.cif.as_string(block.find_values("_atom_site_type_symbol")[0])


@pytest.mark.parametrize("species, written", [
    ("Zr4+", "Zr4+"), ("O2-", "O2-"), ("Cu1+", "Cu1+"), ("Mn", "Mn"),
    ("D", "D"), ("2H", "D"),
    # WP-1527: the atom rietx computes, in the measured `Cu1+` form. A
    # digitless ion is the tabulated one; an untabulated ion is neutral.
    ("Cu+", "Cu1+"), ("Na+", "Na1+"), ("Fe+", "Fe"),
])
def test_the_type_symbol_is_one_gsas2_imports_as_that_species(tmp_path, species,
                                                              written):
    """Measured: GSAS-II stores these as Zr+4, O-2, Cu+1, Mn and D, with no
    'not found' line. `2H` is written `D`, the one isotope label it takes."""
    out = tmp_path / "one.cif"
    rx.write_gsas2_phase_cif(_one_site(species), out)
    assert _type_symbol(out) == written


@pytest.mark.parametrize("species, back, named", [
    ("Cu+", "Cu1+", False), ("Fe+", "Fe", True)])
def test_a_substituted_ion_is_written_neutral_and_named(tmp_path, species,
                                                        back, named):
    """The maintainer's rule (WP-1527, 2026-10-03): no species is refused for
    its charge. `Cu+` reads back as the ion; `Fe+`, which rietx computes as
    neutral Fe, is written so and named."""
    found: list = []
    out = tmp_path / "one.cif"
    rx.write_gsas2_phase_cif(_one_site(species), out, diagnostics=found)
    assert rx.Structure.from_cif(out).phases[0].atoms[0].species == back
    rows = [d for d in found if d.code == "GSAS2_CIF_SPECIES_WRITTEN_NEUTRAL"]
    assert [d.where for d in rows] == (
        [["phases.0.atoms.0.species"]] if named else [])


@pytest.mark.parametrize("species, respelled", [
    ("2H", True), ("D", False), ("H", None)])
def test_a_deuterium_site_is_named_with_gsas2s_own_b(species, respelled):
    """``2H`` → ``D`` is a respelling onto GSAS-II's D, whose b is 6.681 fm
    against Sears's 6.671 (#569 review, follow-up 1): an info row names
    every site written D, and a site that is not deuterium gets none."""
    from rietx.io.projects.gsas2 import from_structure
    found: list = []
    from_structure(_one_site(species), diagnostics=found)
    rows = [d for d in found if d.code == "GSAS2_CIF_DEUTERIUM_AS_D"]
    if respelled is None:
        assert rows == []
        return
    (row,) = rows
    assert row.level == "info" and row.where == ["phases.0.atoms.0"]
    assert "6.681" in row.message and "6.671" in row.message
    assert ("respelled from 2H" in row.message) is respelled


@pytest.mark.parametrize("species, match", [
    ("7Li", "is an isotope"), ("60Ni", "is an isotope"),
    ("7Li1+", "is an isotope"), ("157Gd", "is an isotope"),
])
def test_a_species_gsas2_would_import_as_another_element_is_refused(tmp_path,
                                                                    species, match):
    with pytest.raises(ValueError, match=match) as exc:
        rx.write_gsas2_phase_cif(_one_site(species), tmp_path / "bad.cif")
    assert "phases.0.atoms.0 ('A1')" in str(exc.value)
    if "isotope" in match:
        assert "General" in str(exc.value) and "Isotope" in str(exc.value)
    assert not (tmp_path / "bad.cif").exists()
