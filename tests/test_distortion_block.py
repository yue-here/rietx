"""The mode-amplitude block in the parameter table (WP-1419 chunk 3a, #286).

``Phase.distortion_modes`` states a child as base positions plus absolute
amplitudes, and ``ParameterTable`` derives the moved atoms' coordinates from
them: x = base + Σ A·v, one affine row per coordinate, the record's base as
the constant.  These tests build the record by hand on the NaTaO₃ P4/mbm child
(one M-point mode on O2 at 4g, Kennedy, Prodjosantoso & Howard 1999,
*J. Phys.: Condens. Matter* 11, 6319, Table 1) so that what is pinned is the
table's behaviour, not the statement that normally writes the record
(``tests/test_displacive_statement.py``).

Each refusal has its positive arm beside it: an all-zero free block is refused
and a block of identity-irrep modes at zero is not; a hand edit is refused and
round-off is not; a vector the site forbids is refused and the one it allows
is not.
"""

from __future__ import annotations

import importlib
import math

import numpy as np
import pytest

import rietx as rx
from rietx.optimize import least_squares as LS
from rietx.params.vector import DISTORTION_DRIFT_TOL, ParameterTable
from rietx.refine import mode_fixed_path
from rietx.schemas.structure import DistortionMode, DistortionModes, Structure

P_ = rx.Parameter
A = 5.5503
C = 3.9335
#: one O2 mode, normalised in the AMPLIMODES unit: 4 O2 per primitive cell,
#: each moved (w, w, 0) in fractions, so 4·(w·a·√2)² = 1
W = 1.0 / (2.0 * A * math.sqrt(2.0))
AMP = "phases.0.distortion_modes.modes.0.amplitude"
BASE = [(0.0, 0.0, 0.0), (0.0, 0.5, 0.5), (0.0, 0.0, 0.5), (0.25, 0.75, 0.0)]


def _atom(label, species, x, y, z):
    return rx.Atom(label=label, species=species, x=P_(value=x), y=P_(value=y), z=P_(value=z))


def _phase(amplitude=0.2, *, vector=(W, W, 0.0), vary=False, invariant=False,
           edit=0.0) -> rx.Phase:
    """NaTaO₃ P4/mbm on one mode; ``edit`` moves O2's stored x off the rows."""
    o2 = np.array(BASE[3]) + amplitude * np.array(vector)
    record = DistortionModes(
        parent_space_group="P m -3 m", transform="a-b,a+b,c;0,0,0",
        reference_cell=(A, A, A / math.sqrt(2.0), 90.0, 90.0, 90.0), base=BASE,
        modes=[DistortionMode(
            irrep="S6", k=("1/2", "1/2", "0"), isotropy_group="P4/mbm (127)", index=0,
            site="O", parent_invariant=invariant,
            vectors=[(0.0, 0.0, 0.0)] * 3 + [tuple(vector)],
            amplitude=P_(value=amplitude, vary=vary, unit="A"))])
    cell = rx.Cell(a=P_(value=A), b=P_(value=A), c=P_(value=C), alpha=P_(value=90.0),
                   beta=P_(value=90.0), gamma=P_(value=90.0))
    return rx.Phase(name="NaTaO3", space_group="P 4/m b m", cell=cell, atoms=[
        _atom("Ta", "Ta", *BASE[0]), _atom("Na", "Na", *BASE[1]), _atom("O1", "O", *BASE[2]),
        _atom("O2", "O", o2[0] + edit, o2[1], o2[2])], distortion_modes=record)


def _instrument():
    return rx.Instrument.constant_wavelength_neutron(1.5, fwhm_deg=0.3)


def _table(phase) -> ParameterTable:
    return ParameterTable(Structure(phases=[phase]), _instrument())


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------

def test_the_record_round_trips_through_json():
    phase = _phase()
    back = rx.Phase.model_validate_json(phase.model_dump_json())
    assert back == phase
    assert back.distortion_modes.modes[0].amplitude.value == 0.2


def test_the_record_needs_one_base_and_one_vector_per_atom():
    phase = _phase()
    record = phase.distortion_modes
    with pytest.raises(ValueError, match="4 base positions for 3 atoms"):
        rx.Phase.model_validate({**phase.model_dump(), "atoms": phase.model_dump()["atoms"][:3]})
    with pytest.raises(ValueError, match="has 3 vectors for 4 base positions"):
        DistortionModes.model_validate({**record.model_dump(), "modes": [
            {**record.modes[0].model_dump(), "vectors": [(0.0, 0.0, 0.0)] * 3}]})
    with pytest.raises(ValueError, match="twice"):
        DistortionModes.model_validate({**record.model_dump(),
                                        "modes": [record.modes[0].model_dump()] * 2})


# --------------------------------------------------------------------------
# the rows: absolute, derived, written back
# --------------------------------------------------------------------------

def test_a_moved_coordinate_is_the_base_plus_the_amplitude_times_the_vector():
    """The row's constant is the record's base, never the stored coordinate."""
    table = _table(_phase(0.2))
    x = table.entries[table._paths["phases.0.atoms.3.x"]]
    assert x.tie is not None and x.tie.const == 0.25
    assert x.tie.terms == ((AMP, W),)
    z = table.entries[table._paths["phases.0.atoms.3.z"]]
    assert z.locked and z.tie is None
    # no displacement DOF exists for a moved atom, so nothing re-bases it
    assert not any(p.startswith("phases.0.atoms.3.dof") for p in table._paths)
    assert table.anchored_dof_paths == frozenset()
    values = table.decode(table.x0())
    assert values["phases.0.atoms.3.x"] == pytest.approx(0.25 + 0.2 * W, abs=1e-15)


def test_the_write_back_derives_the_coordinates_from_the_amplitude():
    ref = rx.Refinement(Structure(phases=[_phase(0.2)]), _instrument(), history=False)
    ref.set_values({AMP: -0.3})
    o2 = ref.structure.phases[0].atoms[3]
    assert ref.structure.phases[0].distortion_modes.modes[0].amplitude.value == -0.3
    assert o2.x.value == pytest.approx(0.25 - 0.3 * W, abs=1e-15)
    assert o2.y.value == pytest.approx(0.75 - 0.3 * W, abs=1e-15)
    assert o2.z.value == 0.0


def test_a_hand_edited_coordinate_is_refused_and_round_off_is_not():
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.3 \('O2'\)\.x .* place it"):
        _table(_phase(0.2, edit=1e-6))
    # within the bound, the rows win and the coordinate is rewritten from them
    table = _table(_phase(0.2, edit=0.1 * DISTORTION_DRIFT_TOL))
    assert table.decode(table.x0())["phases.0.atoms.3.x"] == pytest.approx(
        0.25 + 0.2 * W, abs=1e-15)


def test_a_mode_vector_its_site_does_not_allow_is_refused():
    """O2 sits on the z = 0 mirror of 4g: a z component is not a mode of it."""
    with pytest.raises(ValueError, match="site symmetry does not allow"):
        _table(_phase(0.2, vector=(W, W, 0.5 * W)))
    # its positive arm: the in-plane vector the site allows builds
    _table(_phase(0.2, vector=(W, W, 0.0)))
    # and one the x = y line does not allow (the diagonal 2-fold maps it off itself)
    with pytest.raises(ValueError, match="site symmetry does not allow"):
        _table(_phase(0.2, vector=(W, -W, 0.0)))


def test_a_vary_request_on_a_derived_coordinate_is_refused():
    phase = _phase(0.2)
    phase.atoms[3].x.vary = True
    with pytest.raises(ValueError, match="derived from the mode amplitudes"):
        _table(phase)


# --------------------------------------------------------------------------
# the all-zero refusal
# --------------------------------------------------------------------------

def test_a_free_block_exactly_at_the_parent_is_refused():
    """Every non-identity amplitude at zero: an exactly zero gradient, refused."""
    with pytest.raises(ValueError, match="exactly zero"):
        _table(_phase(0.0, vary=True))
    table = _table(_phase(0.0))
    with pytest.raises(ValueError, match="displacive_statement"):
        table.set_vary(["phases.*.distortion_modes.modes.*.amplitude"], True)


def test_the_refusal_spares_identity_modes_and_a_seeded_block():
    """Positive arms: an identity-irrep block at zero, and one off zero, both build."""
    _table(_phase(0.0, vary=True, invariant=True))
    table = _table(_phase(1e-3))
    assert table.set_vary(["phases.*.distortion_modes.modes.*.amplitude"], True) == [AMP]


def test_a_variable_driving_a_zero_block_is_refused_too():
    """Asked of what moves, so a caller's variable cannot carry the block past it."""
    ref = rx.Refinement(Structure(phases=[_phase(0.0)]), _instrument(), history=False)
    ref.add_variable("tilt", 0.0)
    with pytest.raises(ValueError, match="exactly zero"):
        ref.tie(AMP, "vars.tilt")
        ref.set_vary(["vars.tilt"], True)


# --------------------------------------------------------------------------
# what reads the block
# --------------------------------------------------------------------------

def test_le_bail_and_pawley_force_fix_an_amplitude():
    """An amplitude writes only coordinates, so an intensity model cannot see it."""
    assert mode_fixed_path(AMP, "lebail") and mode_fixed_path(AMP, "pawley")
    assert not mode_fixed_path(AMP, "rietveld")


@pytest.mark.parametrize("writer", [
    "rietx.io.projects.gsas:write_gsas_exp",
    "rietx.io.projects.gsas2:write_gsas2_phase_cif",
    "rietx.io.projects.topas:write_topas_inp",
    "rietx.io.projects.fullprof:write_fullprof_pcr",
])
def test_a_project_writer_refuses_a_phase_on_modes_by_name(writer, tmp_path):
    """None of these formats states a mode parameterisation (WP-1103's rule)."""
    module, name = writer.split(":")
    write = getattr(importlib.import_module(module), name)
    with pytest.raises(ValueError, match="1 distortion-mode amplitudes"):
        write(Structure(phases=[_phase(0.2)]), tmp_path / "out")
    assert not (tmp_path / "out").exists()
    # the way out the message names writes the coordinates as they stand
    plain = _phase(0.2).model_copy(update={"distortion_modes": None})
    write(Structure(phases=[plain]), tmp_path / "out")


def _model_and_table(phase):
    from rietx.model.forward import compile_model

    structure = Structure(phases=[phase])
    tt = np.arange(20.0, 70.0, 0.05)
    data = rx.PatternData(two_theta=tt.tolist(), intensity=(100.0 + 0.0 * tt).tolist())
    table = ParameterTable(structure, _instrument())
    table.set_vary(["*"], False)
    assert table.set_vary([AMP, "phases.0.scale", "phases.0.atoms.*.biso"], True)
    model = compile_model(structure, _instrument(), data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table


def test_an_amplitude_column_is_the_peak_chain_one_and_reaches_every_moved_atom(monkeypatch):
    """The dispatch is asserted, not assumed (kickoff Fable review § 2).

    No analytic branch claims an amplitude: it matches no ``_STRUCTURAL_PATH``
    and falls to ``_peak_chain_column``, which perturbs θ and decodes through
    C, so it is exact in what it reaches.  Its reach is the moved atom's x and
    y (z is held by the site), and the column equals a central difference of
    the residual.
    """
    model, table = _model_and_table(_phase(0.2))
    assert table.column_reach()[AMP] == [AMP, "phases.0.atoms.3.x", "phases.0.atoms.3.y"]
    calls: dict[str, list[str]] = {"peak": [], "structural": []}
    peak, structural = LS._peak_chain_column, LS._structural_column

    def record_peak(model, table, bases, theta, values, c, path, *a, **k):
        calls["peak"].append(path)
        return peak(model, table, bases, theta, values, c, path, *a, **k)

    def record_structural(model, table, bases, values, c, *a, **k):
        calls["structural"].append(table.free_paths[c])
        return structural(model, table, bases, values, c, *a, **k)

    monkeypatch.setattr(LS, "_peak_chain_column", record_peak)
    monkeypatch.setattr(LS, "_structural_column", record_structural)
    theta = table.x0()
    jac = LS._jacobian_for(model, table, "numpy")(theta)
    assert AMP in calls["peak"] and AMP not in calls["structural"]
    c = table.free_paths.index(AMP)
    residual = LS._make_residual(model, table)
    h = 1e-5
    tp, tm = theta.copy(), theta.copy()
    tp[c] += h
    tm[c] -= h
    fd = (residual(tp) - residual(tm)) / (2.0 * h)
    assert np.linalg.norm(jac[:, c] - fd) <= 1e-5 * np.linalg.norm(fd)


def test_a_moved_coordinates_esd_is_the_propagated_one():
    """σ²_x = diag(C·Cov·Cᵀ): one row of C per coordinate, through the vectors."""
    two = _phase(0.2)
    record = two.distortion_modes
    # a second, hypothetical mode on the same atom, so the propagation has a
    # cross term: the identity-irrep breathing of O2 along x = y, as a stand-in
    second = record.modes[0].model_copy(update={
        "index": 1, "vectors": [(0.0, 0.0, 0.0)] * 3 + [(0.5 * W, 0.5 * W, 0.0)],
        "amplitude": P_(value=0.1, unit="A")})
    o2 = np.array(BASE[3]) + 0.2 * np.array([W, W, 0.0]) + 0.1 * np.array([0.5 * W, 0.5 * W, 0.0])
    atoms = list(two.atoms)
    atoms[3] = atoms[3].model_copy(update={
        c: P_(value=float(v)) for c, v in zip("xyz", o2)})
    phase = two.model_copy(update={"atoms": atoms, "distortion_modes": record.model_copy(
        update={"modes": [record.modes[0], second]})})
    table = _table(phase)
    table.set_vary(["phases.0.distortion_modes.modes.*.amplitude"], True)
    theta = table.x0()
    sig = np.array([0.013, 0.021])
    corr = np.array([[1.0, -0.4], [-0.4, 1.0]])
    esd = table.stderr_physical(theta, sig, corr)
    cov = corr * np.outer(sig, sig)
    row = np.array([W, 0.5 * W])
    assert esd["phases.0.atoms.3.x"] == pytest.approx(math.sqrt(row @ cov @ row), rel=1e-12)
    assert "phases.0.atoms.3.z" not in esd
