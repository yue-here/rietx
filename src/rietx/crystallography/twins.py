"""The one verb that puts a site's coinciding images on its special position (#1007).

:func:`~.symmetry.site_twin_merge` is the rule; this is where a ``Structure``
meets it, from every boundary that can say so.  The schema is strict and has no
diagnostics channel (root ``CLAUDE.md``: *a silent correction is a reader's to
make, never a table's*), so ``Phase`` validation moves nothing.  Instead each
boundary that builds or changes a structure calls :func:`merge_site_twins` and
reports on its own channel: ``structure_from_cif`` (as ``CIF_SITE_TWINS_MERGED``,
through its own message), the project readers' ``to_structure``,
``RefinementTree.load``, and the ``Refinement`` verbs that take a structure in
(construction, ``edit``, ``set_values``, ``checkout``), which carry the finding
to the next result they return.
"""

from __future__ import annotations

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.structure import Structure
from .symmetry import resolve_group, site_twin_merge


def merge_site_twins(structure: Structure, *,
                     diagnostics: list[Diagnostic] | None = None,
                     source: str | None = None) -> Structure:
    """``structure`` with every site whose own images coincide moved onto its position.

    A site whose images are closer than
    :data:`~.symmetry.TWIN_DISTANCE` (0.02 Å) is one atom counted twice; it is
    moved to the special position its orbit collapses to, and one
    ``SITE_TWINS_MERGED`` warning per site is appended to ``diagnostics``.  A
    split site (images ≥ 0.20 Å apart), a site already on its position and a
    rigid-body atom (the body's pose writes it; a body across a symmetry
    element is the body's own question, #876) are left alone.  Returns the
    argument itself when nothing moved, and never mutates it.

    ``source`` prefixes the message (a file path, as the readers' messages do).
    """
    phases = list(structure.phases)
    changed = False
    for i, phase in enumerate(phases):
        try:
            sg = resolve_group(phase.space_group, phase.symmetry_operations)
        except (ValueError, RuntimeError):
            continue             # the symbol's own refusal is someone else's
        bodied = {label for body in phase.rigid_bodies for label in body.atoms}
        cell = phase.cell.lengths_angles()
        atoms = list(phase.atoms)
        moved_any = False
        for j, atom in enumerate(atoms):
            if atom.label in bodied:
                continue
            xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
            try:
                merge = site_twin_merge(sg, cell, xyz)
            except ValueError:
                continue         # an orbit refusal speaks at compile
            if merge is None:
                continue
            position = [float(v) for v in merge.position]
            atoms[j] = atom.model_copy(update={
                n: getattr(atom, n).model_copy(update={"value": v})
                for n, v in zip("xyz", position, strict=True)})
            moved_any = True
            if diagnostics is not None:
                diagnostics.append(Diagnostic(
                    level="warning", code="SITE_TWINS_MERGED",
                    where=[f"phases.{i}.atoms.{j}"], value=merge.gap,
                    message=(
                        f"{source + ': ' if source else ''}site "
                        f"{atom.label!r} of phase {phase.name!r} was given at "
                        f"{[round(float(v), 6) for v in xyz]}, where it puts "
                        f"{merge.before} atoms in the cell in pairs "
                        f"{merge.gap:.2g} Å apart; it was moved onto the "
                        f"special position {[round(v, 6) for v in position]}, "
                        f"{merge.after} atoms"),
                    suggestion=(
                        "check the coordinate against its source: a special "
                        "position stated a few 1e-5 off (a hand edit, a "
                        "rounded project file) is the usual cause. To keep a "
                        "genuinely displaced atom, state it at least 0.02 Å "
                        "from its own images")))
        if moved_any:
            # model_copy skips validation on purpose: the move is the repair,
            # and an assignment would re-run every validator of the phase
            phases[i] = phase.model_copy(update={"atoms": atoms})
            changed = True
    if not changed:
        return structure
    return structure.model_copy(update={"phases": phases})
