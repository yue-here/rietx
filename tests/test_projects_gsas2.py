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

import pickle
from pathlib import Path

import pytest

import rietx as rx
from rietx.io.projects.gsas2 import (
    _STATIC_GLOBALS,
    ALLOWED_GLOBALS,
    CW_CENTIDEGREE_POWER,
    TREE_ITEM_STANCE,
    Gsas2GpxError,
    _numpy_globals,
    item_kind,
    read_gsas2_gpx,
    to_structure,
)

DATA = Path(__file__).parent / "data"
PBSO4 = DATA / "gsas2_pbso4.gpx"
MAGNETIC = DATA / "gsas2_lacamno3_magnetic.gpx"


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


def test_a_negative_uiso_is_refused_rather_than_built(tmp_path):
    """A real refinement reaches one, and no Debye-Waller factor survives it."""
    atoms = [["Na1", "Na", "XU", 0.0, 0.0, 0.0, 1.0, "m3m", 1, "I",
              -0.004, 0, 0, 0, 0, 0, 0, 12345]]
    path = _write_gpx(tmp_path / "negative.gpx", _minimal_project(atoms=atoms))
    model = read_gsas2_gpx(path)
    with pytest.raises(Gsas2GpxError) as caught:
        to_structure(model)
    assert "negative Uiso" in str(caught.value)
    assert "Na1" in str(caught.value)


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

    for path in (PBSO4, MAGNETIC):
        with path.open("rb") as stream:
            names = []
            while stream.read(1):
                stream.seek(stream.tell() - 1)
                for opcode, argument, _ in pickletools.genops(stream):
                    if opcode.name == "GLOBAL":
                        names.append(tuple(str(argument).split(" ", 1)))
        assert names, f"{path.name} names no globals at all"
        assert set(names) <= set(ALLOWED_GLOBALS), sorted(set(names) - set(ALLOWED_GLOBALS))
