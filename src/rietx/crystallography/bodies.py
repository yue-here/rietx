"""Building rigid bodies: from placed atoms, or a template placed as new atoms.

The schema is ``schemas.structure.RigidBody`` and the refinement map is
``params.bodies.RigidBodyBlock`` (WP-1805); this module is the caller's side:

* :func:`body_from_atoms` — a body over atoms a phase already holds, its
  template their Cartesian positions about their centroid, so declaring it
  moves nothing (the table decodes them back to < 1e-12);
* :func:`add_body` — a template (a ``Fragment`` from ``fragments.from_zmatrix``,
  or Cartesian points) placed at an origin and orientation as **new** atoms;
* :func:`place_body_atoms` — rewrite every body atom from its body, after a
  caller moved a body's origin or orientation by hand;
* :func:`body_fractional` — where a body puts its atoms, without a table.

All four use the one map the table uses, x_i = o + M⁻¹·R·T_i, with M the
closed-form frame of ``params.derived``.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..schemas.common import Parameter
from ..schemas.structure import Atom, BodyOrigin, BodyTorsion, Phase, RigidBody
from . import rotation


def _frames(cell):
    from ..params.derived import cartesian_frame, fractional_frame
    return (np.asarray(cartesian_frame(tuple(cell)), dtype=np.float64),
            np.asarray(fractional_frame(tuple(cell)), dtype=np.float64))


def _points(body: RigidBody) -> np.ndarray:
    """The body-frame points the map places: the template after its torsions."""
    from ..params.bodies import apply_torsions

    pts = np.asarray(body.template, dtype=np.float64)
    if not body.torsions:
        return pts
    member = {label: i for i, label in enumerate(body.atoms)}
    return apply_torsions(
        pts, [(member[t.axis[0]], member[t.axis[1]], [member[m] for m in t.moves])
              for t in body.torsions], [t.angle for t in body.torsions])


def body_fractional(body: RigidBody, cell) -> np.ndarray:
    """Fractional coordinates (n, 3) of ``body``'s atoms at its record."""
    _, minv = _frames(cell)
    r = np.asarray(rotation.matrix_from_quaternion(np.array(body.orientation)))
    return np.asarray(body.origin.values()) + _points(body) @ (minv @ r).T


def body_from_atoms(phase: Phase, labels: Sequence[str], name: str, *,
                    rotation_vary: bool = False, origin_vary: bool = False
                    ) -> RigidBody:
    """A body over atoms ``phase`` already holds, placed where they are.

    The template is the atoms' Cartesian coordinates about their centroid (Å),
    the origin the centroid (fractional), the orientation the identity: so the
    body reproduces the atoms exactly and refining it moves them as one.  The
    atoms are taken as stored — each at its listed position, never a symmetry
    image — so a molecule split across the asymmetric unit must be listed
    whole first.
    """
    by_label = {a.label: a for a in phase.atoms}
    missing = [lab for lab in labels if lab not in by_label]
    if missing:
        raise ValueError(f"phase {phase.name!r} has no atom(s) {missing}")
    cell = phase.cell.lengths_angles()
    m, _ = _frames(cell)
    frac = np.array([[by_label[lab].x.value, by_label[lab].y.value,
                      by_label[lab].z.value] for lab in labels])
    centre = frac.mean(axis=0)
    template = (frac - centre) @ m.T
    return RigidBody(
        name=name, atoms=list(labels),
        template=[tuple(float(v) for v in t) for t in template],
        origin=BodyOrigin(**{c: Parameter(value=float(v), vary=origin_vary)
                             for c, v in zip("xyz", centre, strict=True)}),
        rotation_vary=rotation_vary)


def add_body(phase: Phase, name: str, labels: Sequence[str],
             species: Sequence[str], template, origin, *,
             orientation=(1.0, 0.0, 0.0, 0.0), biso: float = 1.0,
             occ: float = 1.0, centre: bool = True, rotation_vary: bool = False,
             origin_vary: bool = False, torsions: Sequence[BodyTorsion] = ()) -> Phase:
    """A copy of ``phase`` with a body's atoms appended and the body declared.

    ``template`` is (n, 3) Cartesian Å, or a ``fragments.Fragment`` (its
    ``xyz``); with ``centre`` it is shifted to its centroid first, so ``origin``
    (fractional) is where the body's centroid goes.  ``orientation`` is a unit
    quaternion (w, x, y, z), stored canonical.  ``torsions`` (WP-1808) are
    declared on the body and applied before the pose.  The new atoms take
    ``biso`` and ``occ`` and are written at the positions the body gives them.
    """
    pts = np.asarray(getattr(template, "xyz", template), dtype=np.float64)
    if pts.shape != (len(labels), 3) or len(species) != len(labels):
        raise ValueError(
            f"add_body {name!r}: {len(labels)} labels, {len(species)} species "
            f"and a template of shape {pts.shape} do not agree")
    if centre:
        pts = pts - pts.mean(axis=0)
    q = rotation.canonical_quaternion(np.asarray(orientation, dtype=np.float64)
                                      / np.linalg.norm(orientation))
    body = RigidBody(
        name=name, atoms=list(labels),
        template=[tuple(float(v) for v in t) for t in pts],
        origin=BodyOrigin(**{c: Parameter(value=float(v), vary=origin_vary)
                             for c, v in zip("xyz", origin, strict=True)}),
        orientation=tuple(float(v) for v in np.asarray(q)),
        rotation_vary=rotation_vary, torsions=list(torsions))
    frac = body_fractional(body, phase.cell.lengths_angles())
    atoms = list(phase.atoms) + [
        Atom(label=lab, species=sp, x=Parameter(value=float(f[0])),
             y=Parameter(value=float(f[1])), z=Parameter(value=float(f[2])),
             occ=Parameter(value=occ), biso=Parameter(value=biso))
        for lab, sp, f in zip(labels, species, frac, strict=True)]
    # validated, not ``model_copy``'d: the phase's own checks (a label the
    # phase already has, an atom in two bodies) then raise here, where the
    # mistake is made, rather than at the next JSON round trip (#801)
    return Phase.model_validate({
        **phase.model_dump(), "atoms": [a.model_dump() for a in atoms],
        "rigid_bodies": [*phase.model_dump()["rigid_bodies"], body.model_dump()]})


def place_body_atoms(phase: Phase) -> Phase:
    """A copy of ``phase`` with every body atom rewritten from its body."""
    out = phase.model_copy(deep=True)
    cell = out.cell.lengths_angles()
    index = {a.label: a for a in out.atoms}
    for body in out.rigid_bodies:
        for lab, f in zip(body.atoms, body_fractional(body, cell), strict=True):
            atom = index[lab]
            atom.x.value, atom.y.value, atom.z.value = (float(v) for v in f)
    return out
