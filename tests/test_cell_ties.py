"""A cell entry its space group ties to another is checked, never dropped (WP-2150).

Issue #1669: ``ParameterTable`` built a tied length (b and c from a on a cubic
cell) and a tied rhombohedral angle (β and γ from α) from its source and never
read the stored value, so ``b = 5.9`` under ``F m -3 m`` with ``a = 5.641``
built ``b = 5.641`` with no word.  Now the table refuses a tied entry further
from its source than ``SYMMETRY_LENGTH_RTOL`` (or ``SYMMETRY_ANGLE_TOL_DEG``),
a CIF reader reads one within the file's printed digits as its source and
records it, a project reader refuses one by name, and a stored history whose
fits always built the entry from its source is read that way and said so.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.symmetry import (
    SYMMETRY_LENGTH_RTOL,
    check_cell_ties,
    get_spacegroup,
)
from rietx.io.recipe import RecipeError, read_recipe
from rietx.params.vector import ParameterTable

DATA = Path(__file__).parent / "data"
INSTRUMENT = rx.Instrument.debye_scherrer(wavelength=1.54)

# The six cases of the WP's table: (symbol, entry, its source, the cell).
SIX = [
    ("F m -3 m", "b", "a", (5.641, 5.641, 5.641, 90.0, 90.0, 90.0)),
    ("P 4/m m m", "b", "a", (4.0, 4.0, 5.0, 90.0, 90.0, 90.0)),
    ("P 6/m m m", "b", "a", (3.0, 3.0, 5.0, 90.0, 90.0, 120.0)),
    ("R -3 m:R", "beta", "alpha", (5.0, 5.0, 5.0, 60.0, 60.0, 60.0)),
    ("R -3 m:R", "c", "a", (5.0, 5.0, 5.0, 60.0, 60.0, 60.0)),
    ("F m -3 m", "c", "a", (5.641, 5.641, 5.641, 90.0, 90.0, 90.0)),
]
NAMES = ("a", "b", "c", "alpha", "beta", "gamma")


def _structure(symbol: str, cell) -> rx.Structure:
    values = dict(zip(NAMES, cell, strict=True))
    return rx.Structure(phases=[rx.Phase(
        name="p", space_group=symbol,
        cell=rx.Cell(**{n: rx.Parameter(value=v) for n, v in values.items()}),
        atoms=[rx.Atom(label="Cu1", species="Cu", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))])])


def _off(cell, entry: str, by: float) -> tuple[float, ...]:
    """``cell`` with ``entry`` moved: relatively for a length, in degrees for
    an angle."""
    values = dict(zip(NAMES, cell, strict=True))
    values[entry] = (values[entry] * (1 + by) if entry in "abc"
                     else values[entry] + by)
    return tuple(values[n] for n in NAMES)


# --- the table -------------------------------------------------------------


@pytest.mark.parametrize(("symbol", "entry", "source", "cell"), SIX)
def test_the_table_refuses_a_tied_entry_far_from_its_source(symbol, entry, source, cell):
    by = 0.046 if entry in "abc" else 1.0
    stored = _off(cell, entry, by)
    with pytest.raises(ValueError) as exc:
        ParameterTable(_structure(symbol, stored), INSTRUMENT)
    message = str(exc.value)
    value = dict(zip(NAMES, stored, strict=True))
    assert f"phases.0.cell.{entry} to {source}" in message
    assert f"{entry} = {value[entry]}" in message
    assert f"{source} = {value[source]}" in message
    assert repr(symbol) in message


@pytest.mark.parametrize(("symbol", "entry", "source", "cell"), SIX)
def test_the_table_builds_a_tied_entry_inside_its_tolerance(symbol, entry, source, cell):
    by = 0.5 * SYMMETRY_LENGTH_RTOL if entry in "abc" else 5e-4
    table = ParameterTable(_structure(symbol, _off(cell, entry, by)), INSTRUMENT)
    values = table.decode(table.x0())
    assert values[f"phases.0.cell.{entry}"] == values[f"phases.0.cell.{source}"]


def test_the_length_tolerance_is_relative_and_inclusive():
    sg = get_spacegroup("F m -3 m")
    for a in (1.0, 50.0):
        cell = {"a": a, "b": a * (1 + 0.99 * SYMMETRY_LENGTH_RTOL), "c": a,
                "alpha": 90.0, "beta": 90.0, "gamma": 90.0}
        check_cell_ties(sg, cell)
        cell["b"] = a * (1 + 1.01 * SYMMETRY_LENGTH_RTOL)
        with pytest.raises(ValueError, match="ties b to a"):
            check_cell_ties(sg, cell)


def test_a_source_edited_alone_is_refused_and_set_values_moves_both():
    """Editing ``a`` on the model and leaving ``b`` is a contradiction the
    table cannot read, while ``set_values`` moves every dependent with it."""
    structure = _structure("F m -3 m", (5.641, 5.641, 5.641, 90.0, 90.0, 90.0))
    ref = rx.Refinement(structure, INSTRUMENT, history=False)
    ref.set_values({"phases.0.cell.a": 5.7})
    assert ref.structure.phases[0].cell.b.value == 5.7
    ParameterTable(ref.structure, INSTRUMENT)
    structure.phases[0].cell.a.value = 5.8
    with pytest.raises(ValueError, match="ties phases.0.cell.b to a"):
        ParameterTable(structure, INSTRUMENT)


# --- the CIF reader --------------------------------------------------------

CIF = """data_t
_symmetry_space_group_name_H-M '{symbol}'
_cell_length_a {a}
_cell_length_b {b}
_cell_length_c {c}
_cell_angle_alpha {alpha}
_cell_angle_beta {beta}
_cell_angle_gamma {gamma}
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Cu1 Cu 0 0 0
"""


def _read(tmp_path, symbol: str, **printed) -> tuple[rx.Structure, list]:
    path = tmp_path / "t.cif"
    path.write_text(CIF.format(symbol=symbol, **printed), encoding="utf-8")
    diagnostics: list = []
    return structure_from_cif(path, diagnostics=diagnostics), diagnostics


# (symbol, printed cell, entry, its source) for a disagreement the file's
# own digits cannot resolve: each is read as its source and reported
WITHIN_PRINT = [
    ("F m -3 m", dict(a="5.641", b="5.64101", c="5.641", alpha="90", beta="90",
                      gamma="90"), "b", "a"),
    ("P 4/m m m", dict(a="4.000", b="4.0004", c="5.000", alpha="90", beta="90",
                       gamma="90"), "b", "a"),
    ("P 6/m m m", dict(a="3.000", b="3.0003", c="5.000", alpha="90", beta="90",
                       gamma="120"), "b", "a"),
    ("R -3 m:R", dict(a="5.000", b="5.000", c="5.000", alpha="60.00",
                      beta="60.004", gamma="60.00"), "beta", "alpha"),
    ("R -3 m:R", dict(a="5.000", b="5.000", c="5.0004", alpha="60.0",
                      beta="60.0", gamma="60.0"), "c", "a"),
]

# the same entries, past the file's digits: read as written, refused by the table
PAST_PRINT = [
    ("F m -3 m", dict(a="5.641", b="5.900", c="5.641", alpha="90", beta="90",
                      gamma="90"), "b", "a"),
    ("P 4/m m m", dict(a="4.0000", b="4.1000", c="5.0000", alpha="90", beta="90",
                       gamma="90"), "b", "a"),
    ("P 6/m m m", dict(a="3.0000", b="3.2000", c="5.0000", alpha="90", beta="90",
                       gamma="120"), "b", "a"),
    ("R -3 m:R", dict(a="5.000", b="5.000", c="5.000", alpha="60.00",
                      beta="61.00", gamma="60.00"), "beta", "alpha"),
    ("R -3 m:R", dict(a="5.000", b="5.000", c="5.300", alpha="60.0",
                      beta="60.0", gamma="60.0"), "c", "a"),
]


@pytest.mark.parametrize(("symbol", "printed", "entry", "source"), WITHIN_PRINT)
def test_a_cif_tie_within_its_printed_digits_is_read_as_its_source(
        tmp_path, symbol, printed, entry, source):
    structure, diagnostics = _read(tmp_path, symbol, **printed)
    cell = structure.phases[0].cell
    assert getattr(cell, entry).value == getattr(cell, source).value
    found = [d for d in diagnostics if d.code == "CIF_CELL_TIE_CORRECTED"]
    assert len(found) == 1
    assert found[0].where == [f"phases.0.cell.{entry}"]
    assert f"{entry} = {float(printed[entry])}" in found[0].message
    ParameterTable(structure, INSTRUMENT)


@pytest.mark.parametrize(("symbol", "printed", "entry", "source"), PAST_PRINT)
def test_a_cif_tie_past_its_printed_digits_is_left_for_the_table_to_refuse(
        tmp_path, symbol, printed, entry, source):
    structure, diagnostics = _read(tmp_path, symbol, **printed)
    assert getattr(structure.phases[0].cell, entry).value == float(printed[entry])
    assert not [d for d in diagnostics if d.code == "CIF_CELL_TIE_CORRECTED"]
    with pytest.raises(ValueError, match=f"ties phases.0.cell.{entry} to {source}"):
        ParameterTable(structure, INSTRUMENT)


def test_a_cif_tie_within_its_own_rounding_is_read_quietly(tmp_path):
    """``b`` printed ``5.641`` stands for every value within 5e-4 of it, so
    reading it as ``a = 5.64101`` is the file's own rounding, not a repair."""
    structure, diagnostics = _read(tmp_path, "F m -3 m", a="5.64101", b="5.641",
                                   c="5.641", alpha="90", beta="90", gamma="90")
    assert structure.phases[0].cell.lengths_angles()[:3] == (5.64101,) * 3
    assert not [d for d in diagnostics if d.code == "CIF_CELL_TIE_CORRECTED"]


def test_a_cif_tie_inside_the_table_tolerance_is_reported_past_its_print(tmp_path):
    """Two five-decimal lengths 3.5 ppm apart are past the file's digits but
    inside the table's tolerance: read as the source and said, so no reader
    leaves a disagreement that builds silently."""
    structure, diagnostics = _read(tmp_path, "F m -3 m", a="5.64100", b="5.64102",
                                   c="5.64100", alpha="90", beta="90", gamma="90")
    assert structure.phases[0].cell.b.value == 5.641
    assert [d.code for d in diagnostics if "CELL" in d.code] == ["CIF_CELL_TIE_CORRECTED"]


# --- the project readers ---------------------------------------------------


def test_a_recipe_with_a_tied_length_off_is_refused_by_name():
    doc = json.loads((DATA / "powderline" / "example_LaB6" / "input.json")
                     .read_text(encoding="utf-8"))
    read_recipe(copy.deepcopy(doc))
    doc["payload"]["phases"]["LaB6"]["structure"]["unit_cell"]["b"] = 4.2
    with pytest.raises(RecipeError) as exc:
        read_recipe(doc)
    message = str(exc.value)
    assert "payload.phases.LaB6.structure.unit_cell" in message
    assert "ties b to a" in message and "b = 4.2" in message and "a = 4.15682" in message


# --- a stored history ------------------------------------------------------


def test_a_history_holding_a_contradicting_tie_opens_as_its_fits_read_it(tmp_path):
    """A node an older release committed with ``b`` off is read with ``b`` on
    its source, which is what every fit of that node built, and said once."""
    from rietx.history.tree import RefinementTree
    from rietx.schemas.history import NodeAction, RefinementState, TreeHeader

    log = tmp_path / "history.jsonl"
    tree = RefinementTree(TreeHeader(tree_id="t0"), path=log)
    from rietx.history.store import append_record
    from rietx.schemas.history import HistoryRecord
    append_record(log, HistoryRecord(record="header", header=tree.header))
    stored = _structure("F m -3 m", (5.641, 5.9, 5.641, 90.0, 90.0, 90.0))
    root = tree.add(parents=[], action=NodeAction(kind="root"),
                    state=RefinementState(structure=stored, instrument=INSTRUMENT))
    tree.add(parents=[root.id], action=NodeAction(kind="set_vary"),
             state=RefinementState(structure=stored, instrument=INSTRUMENT))
    notes: list = []
    loaded = RefinementTree.load(log, diagnostics=notes)
    head = loaded["head"].state
    assert head.structure.phases[0].cell.b.value == 5.641
    (found,) = [d for d in notes if d.code == "HISTORY_CELL_TIE_CORRECTED"]
    assert found.where == ["phases.0.cell.b"]
    assert "b = 5.9" in found.message and "stored in 2 nodes" in found.message
    ParameterTable(head.structure, head.instrument)


# --- an indexing candidate -------------------------------------------------


@pytest.mark.parametrize(("system", "cell"), [
    ("cubic", (5.4309, 5.4309, 5.4309, 90.0, 90.0, 90.0)),
    ("tetragonal", (4.5937, 4.5937, 2.9587, 90.0, 90.0, 90.0)),
    ("hexagonal", (3.2498, 3.2498, 5.2066, 90.0, 90.0, 120.0)),
])
def test_an_indexing_candidate_still_builds(system, cell):
    """A cell the indexer solves from noisy lines arrives with its tied lengths
    equal to round-off, far inside the table's tolerance, so validation never
    refuses the indexer's own answer."""
    import gemmi
    import numpy as np

    from rietx.indexing.fom import lattice_group
    from rietx.indexing.qspace import refine_candidate
    from rietx.indexing.workflow import structure_from_candidate
    from rietx.schemas.indexing import CellCandidate

    uc = gemmi.UnitCell(*cell)
    hkl = np.array([(h, k, ll) for h in range(4) for k in range(4) for ll in range(4)
                    if (h, k, ll) != (0, 0, 0)])
    q = np.array([1.0 / uc.calculate_d([int(i) for i in m]) ** 2 for m in hkl])
    noisy = q * (1 + 1e-4 * np.random.default_rng(7).standard_normal(len(q)))
    fit = refine_candidate(noisy, 1e-4 * q, hkl, system=system)
    a = fit.cell[0]
    assert max(abs(fit.cell[1] - a), abs(fit.cell[2] - a) if system == "cubic"
               else 0.0) <= 1e-12 * a
    candidate = CellCandidate(system=system, cell=fit.cell, cell_esd=(0.0,) * 6,
                              lattice_group=lattice_group(system))
    ParameterTable(structure_from_candidate(candidate), INSTRUMENT)


# --- the verbs that write a cell -------------------------------------------


def test_a_project_is_not_created_around_a_cell_the_table_refuses(tmp_path):
    root = tmp_path / "off.rex"
    with pytest.raises(ValueError, match="ties phases.0.cell.b to a"):
        rx.Project.create(root, pattern=DATA / "llb_g41_ba2fesbse5_040K.xy",
                          structure=_structure("F m -3 m", (5.641, 5.9, 5.641,
                                                            90.0, 90.0, 90.0)),
                          instrument=INSTRUMENT)
    assert not root.exists()


def test_a_gui_limit_typed_with_a_value_moves_the_tied_entries():
    """``PATCH /api/params`` writes a value typed beside its limit into the
    dumped model, where no table moves b after a, so the edit does it."""
    from rietx.gui.session import _limit_and_restraint_edit

    ref = rx.Refinement(_structure("F m -3 m", (5.641,) * 3 + (90.0,) * 3),
                        INSTRUMENT, history=False)
    structure, _ = _limit_and_restraint_edit(
        ref, {"phases.0.cell.a": [5.0, None]}, {}, {"phases.0.cell.a": 5.7})
    assert structure.phases[0].cell.lengths_angles()[:3] == (5.7, 5.7, 5.7)
    ParameterTable(structure, INSTRUMENT)


# --- a phase stating its cell through a parent -----------------------------


def test_a_parent_cell_is_checked_under_the_parent_group():
    """The table ties the parent's cell under the parent's group, so the
    readers' helper checks that cell and names it by its own path."""
    from rietx.crystallography.symmetry import check_phase_cell_ties
    from rietx.schemas.structure import ParentCell

    phase = _structure("F m -3 m", SIX[0][3]).phases[0]
    parent = rx.Cell(**{n: rx.Parameter(value=v) for n, v in zip(
        NAMES, (5.641, 5.9, 5.641, 90.0, 90.0, 90.0), strict=True)})
    phase = phase.model_copy(update={"parent_cell": ParentCell(
        space_group="F m -3 m", transform="a,b,c;0,0,0", cell=parent)})
    with pytest.raises(ValueError, match=r"phases\.0\.parent_cell\.cell\.b to a"):
        check_phase_cell_ties(phase, prefix="phases.0")
    with pytest.raises(ValueError, match=r"parent_cell\.cell\.b to a"):
        ParameterTable(rx.Structure(phases=[phase]), INSTRUMENT)
