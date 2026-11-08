"""A structure restated in P1: every atom of the cell listed, each with its moment.

The forward model never lists the cell.  It stores an asymmetric unit and, per
atom, the operations that generate its distinct images
(:func:`~rietx.crystallography.structure_factor.select_orbit_ops`), and a moment
rides each image through the matching operation of the magnetic group
(:func:`~.scattering._axial_matrices`).  :func:`restate_phase_in_p1` runs that
expansion once and writes the result down as a phase of ``P 1`` with magnetic
group 1.1: a plain list of atoms, each carrying its own position, occupancy,
displacement and moment, and nothing left for a symmetry operator to supply.

**What it is for.**  The list is what a program with no symmetry-generating
magnetic model can state (a TOPAS ``str`` in P1 with ``mag_space_group 1.1``),
and it is the check on a moment that does not depend on the operator
bookkeeping that produced it: the moment of every atom of the cell, in one
place, to be read, plotted or compared.  rietx's own prediction from the
restatement equals its prediction from the original, which is the positive
arm of the tests.

**The conventions are the model's own.**

* A position is ``R·x + t`` for each operation of the nuclear subset the forward
  model chose (one per distinct image), wrapped into [0, 1).
* A moment is ``ε·det(R)·R·m`` with the matching operation of the magnetic group
  (``MagneticOperator.moment_matrix``: an **axial** vector, and ε = −1 for a
  primed operation or an anti-translation), in the crystal-axis components, in
  μ_B, that :class:`~rietx.schemas.structure.Moment` stores.  Time reversal is
  therefore in the answer: dropping it from one operation changes the moment of
  every image that operation reaches.  The axial action and the sign of time
  reversal are those of the magnetic point-group tables (Litvin, 2013,
  *Magnetic Group Tables*, IUCr; Bertaut, 1968, *Acta Cryst.* A**24**,
  217, who writes the transform of an axial vector as det(R)·R).
* A displacement tensor is the rotated ``U* → R·U*·Rᵀ`` of the structure factor
  (:func:`~rietx.crystallography.structure_factor._aniso_dw`), held in the CIF
  ``U^ij`` convention.  ``U*`` is a tensor contracting with h twice, so it
  transforms as R·U*·Rᵀ with R untransposed (Grosse-Kunstleve & Adams, 2002,
  *J. Appl. Cryst.* **35**, 477, on the handling of anisotropic displacement
  parameters under a symmetry operation).

**Every parameter of the restatement is held.**  The copies are one value each:
the ties that made them one parameter (a site symmetry, an operator relation,
the cell's metric constraints) are not stated in P1, so freeing a copy would
refine a different model.  The restatement is for checking and export, and a
refinement starts from the original.  A k ≠ 0 structure is already a
commensurate supercell here (``MagneticSymmetry.propagation_vector_parent`` is
provenance only), so it restates like any other phase and the parent k is not
carried.
"""

from __future__ import annotations

import numpy as np

from ...schemas.common import Parameter
from ...schemas.structure import (
    AnisoU,
    Atom,
    MagneticSymmetry,
    Moment,
    Phase,
    Structure,
)
from ..adp import tensor_from_voigt, voigt_from_tensor
from ..structure_factor import select_orbit_ops
from ..symmetry import resolve_group
from .scattering import _axial_matrices

#: A coordinate this close to the next lattice point after wrapping is that
#: point: ``-1e-17 % 1.0`` is ``1.0`` in floating point, which is outside [0, 1).
_WRAP_TOL = 1e-12


def _held(parameter: Parameter, value: float | None = None) -> Parameter:
    """A copy of ``parameter`` as one fixed number: no flag, no tie, no esd."""
    update: dict = {"vary": False, "stderr": None}
    if value is not None:
        update["value"] = float(value)
    return parameter.model_copy(update=update)


def _wrap(position: np.ndarray) -> np.ndarray:
    wrapped = position % 1.0
    wrapped[wrapped >= 1.0 - _WRAP_TOL] = 0.0
    return wrapped


def _image_aniso(aniso: AnisoU, rot: np.ndarray, cell) -> AnisoU:
    """``U^ij`` of one image: ``U* → R·U*·Rᵀ``, in the CIF convention."""
    from ..adp import reciprocal_axis_lengths

    astar = np.asarray(reciprocal_axis_lengths(*cell), dtype=np.float64)
    scale = astar[:, None] * astar[None, :]
    ustar = tensor_from_voigt(aniso.values()) * scale
    rotated = rot @ ustar @ rot.T
    return AnisoU.from_values(voigt_from_tensor(rotated / scale), vary=False)


def _unique(label: str, taken: set[str]) -> str:
    while label in taken:
        label += "_"
    taken.add(label)
    return label


def restate_phase_in_p1(phase: Phase, *, name: str | None = None,
                        species_as_ion: bool = False) -> Phase:
    """``phase`` as a ``P 1`` phase listing every atom of its cell.

    One atom per distinct image of each asymmetric-unit atom, labelled
    ``<label>_<k>`` (the label alone where the site has one image), in the order
    the forward model generates them.  A moment is carried to each image by the
    magnetic operation that reaches it; the restatement's magnetic group is 1.1.
    The module docstring has the conventions and what is held.

    ``species_as_ion=True`` also sets the species of every atom that carries a
    moment to its magnetic ion (``Fe`` → ``Fe3+``), which is what a program that
    reads the magnetic form factor from the scattering species needs
    (``write_topas_inp``).  It leaves a neutron pattern unchanged, the
    scattering length being keyed to the element, and changes an X-ray one.

    Refused by name: a phase with restraints (they name atoms of the
    asymmetric unit), a Stephens microstrain model or a spherical-harmonics
    texture (their terms are the Laue class's), none of which has a statement
    in P1 that would mean the same.
    A structure whose magnetic group does not determine a moment for every
    nuclear image is refused by :func:`~.scattering._axial_matrices`, with the
    message the forward model gives for the same phase.
    """
    if phase.restraints:
        raise ValueError(
            f"phase {phase.name!r} carries {len(phase.restraints)} "
            f"restraint(s), which name atoms of its asymmetric unit; a P 1 "
            f"list has no such atom to point at. Drop them before restating")
    if phase.microstrain is not None:
        raise ValueError(
            f"phase {phase.name!r} carries a Stephens microstrain model, "
            f"whose terms are those of its Laue class; in P 1 all fifteen "
            f"would be free and the model would be a different one. Restate "
            f"the phase without it")
    if phase.texture is not None:
        raise ValueError(
            f"phase {phase.name!r} carries a spherical-harmonics texture, whose "
            f"terms and their names belong to its Laue class and its frame; in "
            f"P 1 a name such as c4_1 is a different function. Restate the "
            f"phase without it")
    group_spec = phase.magnetic_symmetry
    magnetic = group_spec is not None and any(
        a.moment is not None for a in phase.atoms)
    mag_group = group_spec.group() if magnetic else None
    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    cell = phase.cell.lengths_angles()

    atoms: list[Atom] = []
    taken: set[str] = set()
    for atom in phase.atoms:
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        rot, tran = select_orbit_ops(sg, xyz)
        n = len(rot)
        axial = None
        if atom.moment is not None and mag_group is not None:
            axial = _axial_matrices(mag_group, xyz, rot, tran, phase.name,
                                    atom.label)
        for k in range(n):
            position = _wrap(rot[k] @ xyz + tran[k])
            update: dict = {
                "label": _unique(atom.label if n == 1
                                 else f"{atom.label}_{k + 1}", taken),
                "x": _held(atom.x, position[0]),
                "y": _held(atom.y, position[1]),
                "z": _held(atom.z, position[2]),
                "occ": _held(atom.occ),
                "biso": _held(atom.biso),
                "aniso": (None if atom.aniso is None
                          else _image_aniso(atom.aniso, np.asarray(rot[k]),
                                            cell)),
                "moment": None,
            }
            if axial is not None and species_as_ion:
                update["species"] = atom.moment.ion
            if axial is not None:
                m = axial[k] @ np.asarray(atom.moment.values())
                update["moment"] = Moment.from_values(
                    m, atom.moment.ion, g=atom.moment.g, vary=False)
            atoms.append(atom.model_copy(update=update))

    held_cell = phase.cell.model_copy(update={
        n: _held(getattr(phase.cell, n))
        for n in ("a", "b", "c", "alpha", "beta", "gamma")})
    return phase.model_copy(update={
        "name": name or f"{phase.name} (P1)",
        "space_group": "P 1",
        "symmetry_operations": None,
        "cell": held_cell,
        "atoms": atoms,
        "magnetic_symmetry": (
            MagneticSymmetry(operations=["x,y,z,+1"],
                             centerings=["x,y,z,+1"], bns_number="1.1",
                             symbol="P1")
            if magnetic else None),
        "propagation_vector": None,
    })


def restate_in_p1(structure: Structure, *,
                  species_as_ion: bool = False) -> Structure:
    """``structure`` with every phase restated by :func:`restate_phase_in_p1`."""
    return structure.model_copy(update={"phases": [
        restate_phase_in_p1(p, species_as_ion=species_as_ion)
        for p in structure.phases]})
