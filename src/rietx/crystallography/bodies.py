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

**A body on a special position** (WP-1807) lists one atom per image under its
origin's site symmetry G_o; the space group places the rest, as it does for
any atom.  :func:`body_from_atoms` takes the origin it is given
(``origin=``, an atom label or a point) so that the origin can sit on the
element the atoms share, and :func:`add_body`, the one caller that sees the
whole fragment, checks it maps onto itself under G_o and keeps the first atom
of each image set.
"""

from __future__ import annotations

import warnings
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
                    rotation_vary: bool = False, origin_vary: bool = False,
                    origin: str | Sequence[float] | None = None) -> RigidBody:
    """A body over atoms ``phase`` already holds, placed where they are.

    The template is the atoms' Cartesian coordinates about the origin (Å), the
    orientation the identity: so the body reproduces the atoms exactly and
    refining it moves them as one.  ``origin`` is the label of an atom of the
    phase, a fractional point, or ``None`` for the atoms' centroid.  The atoms
    are taken as stored — each at its listed position, never a symmetry image
    — so a molecule split across the asymmetric unit must be listed whole
    first, unless the body sits on a special position: then list one atom per
    image under the origin's site symmetry and put the origin on the element
    they share (PbSO₄'s SO₄ on the Pnma mirror: S, O1, O2, O3 with
    ``origin="S"``), which the table refines with only the turns that site
    allows (WP-1807).
    """
    by_label = {a.label: a for a in phase.atoms}
    missing = [lab for lab in labels if lab not in by_label]
    if isinstance(origin, str) and origin not in by_label:
        missing.append(origin)
    if missing:
        raise ValueError(f"phase {phase.name!r} has no atom(s) {missing}")
    cell = phase.cell.lengths_angles()
    m, _ = _frames(cell)
    frac = np.array([[by_label[lab].x.value, by_label[lab].y.value,
                      by_label[lab].z.value] for lab in labels])
    if origin is None:
        centre = frac.mean(axis=0)
    elif isinstance(origin, str):
        a = by_label[origin]
        centre = np.array([a.x.value, a.y.value, a.z.value], dtype=np.float64)
    else:
        centre = np.asarray(origin, dtype=np.float64).reshape(3)
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
    (fractional) is where the body's centroid goes.  On a special position the
    centroid is first projected onto the site's fixed space, so the shift
    commutes with the site operations and a template typed to three decimals
    keeps the miss ``RIGID_BODY_INVARIANCE_TOL`` bounds.  ``orientation`` is a unit
    quaternion (w, x, y, z), stored canonical.  ``torsions`` (WP-1808) are
    declared on the body and applied before the pose.  The new atoms take
    ``biso`` and ``occ`` and are written at the positions the body gives them.

    **With ``origin`` on a special position** (WP-1807) the whole template must
    map onto itself under the origin's site symmetry G_o: each point's image
    lands on a same-species point within ``RIGID_BODY_INVARIANCE_TOL``, or the
    call refuses ``RIGID_BODY_NOT_INVARIANT`` naming the first point that
    misses.  It then keeps the first listed point of each image set — the
    space group places the others — and warns naming the labels it dropped.
    """
    pts = np.asarray(getattr(template, "xyz", template), dtype=np.float64)
    if pts.shape != (len(labels), 3) or len(species) != len(labels):
        raise ValueError(
            f"add_body {name!r}: {len(labels)} labels, {len(species)} species "
            f"and a template of shape {pts.shape} do not agree")
    if centre:
        pts = pts - _site_fixed_part(phase, origin, pts.mean(axis=0))
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
    keep = _site_representatives(phase, name, labels, species, body, frac)
    if len(keep) < len(labels):
        dropped = [lab for k, lab in enumerate(labels) if k not in keep]
        warnings.warn(
            f"add_body {name!r}: its origin is on a special position, so the "
            f"space group places {dropped} as images of the atoms kept; the "
            f"body lists {len(keep)} of the template's {len(labels)} points",
            UserWarning, stacklevel=2)
        for t in torsions:
            named = {*t.axis, *t.moves} & set(dropped)
            if named:
                raise ValueError(
                    f"add_body {name!r}: its torsion {t.name!r} names "
                    f"{sorted(named)[0]!r}, which the space group places as an "
                    "image of an atom kept; a twist of one image is not a twist "
                    "of its set — name the kept atom in the torsion instead")
        labels = [labels[k] for k in keep]
        species = [species[k] for k in keep]
        frac = frac[keep]
        body = body.model_copy(update={
            "atoms": list(labels), "template": [body.template[k] for k in keep]})
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


def _site_fixed_part(phase: Phase, origin, v: np.ndarray) -> np.ndarray:
    """``v`` (Cartesian Å) projected onto the fixed space of the origin's site group.

    The mean of the site's Cartesian W_g, so ``v`` itself at a general origin.
    Centring a typed template on its plain centroid moves every point by the
    centroid's rounding error ε̄, which a site operation does not fix and which
    adds (I − W)·ε̄ to each miss; the fixed part of the centroid is W-invariant
    and adds nothing (WP-1807, #1005 round 3).
    """
    from .symmetry import resolve_group, site_orbit

    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    orbit = site_orbit(sg, np.asarray(origin, dtype=np.float64))
    if len(orbit.stabilizer_ops) == 1:
        return v
    m, minv = _frames(phase.cell.lengths_angles())
    proj = sum(m @ r.astype(np.float64) @ minv for r in orbit.stabilizer)
    return (proj / len(orbit.stabilizer)) @ v


def _site_representatives(phase: Phase, name: str, labels, species, body,
                          frac: np.ndarray) -> list[int]:
    """The template indices :func:`add_body` keeps: all, at a general origin.

    On a special position, every point's image under each g ∈ G_o (the
    Cartesian W_g = M·R_g·M⁻¹ about the origin, which g fixes) must land on a
    same-species point within ``RIGID_BODY_INVARIANCE_TOL``; the first listed
    point of each image set is kept.
    """
    from ..schemas.structure import RIGID_BODY_INVARIANCE_TOL
    from .symmetry import _group_arrays, group_key, resolve_group, site_orbit

    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    origin = np.asarray(body.origin.values(), dtype=np.float64)
    orbit = site_orbit(sg, origin)
    if len(orbit.stabilizer_ops) == 1:
        return list(range(len(labels)))
    ops = _group_arrays(group_key(sg))[0]
    m, minv = _frames(phase.cell.lengths_angles())
    rel = (frac - origin) @ m.T
    # G_o is a group, so the images of point k over every g are its whole
    # image set, the same set for each member: keep k when it is the least
    first = list(range(len(labels)))
    for g, r in zip(orbit.stabilizer_ops, orbit.stabilizer, strict=True):
        w = m @ r.astype(np.float64) @ minv
        for k, p in enumerate(rel):
            d = np.linalg.norm(rel - w @ p, axis=1)
            same = [j for j in np.argsort(d)
                    if species[j] == species[k] and d[j] <= RIGID_BODY_INVARIANCE_TOL]
            if not same:
                raise ValueError(
                    f"RIGID_BODY_NOT_INVARIANT: add_body {name!r} has its origin "
                    f"on a special position of {phase.space_group!r} (site "
                    f"symmetry of order {len(orbit.stabilizer_ops)}), and its "
                    f"point {labels[k]!r} maps under {ops[int(g)].triplet()} "
                    f"{float(d.min()):.3g} Å from the nearest {species[k]!r} point "
                    "of the template; a body on a site must map onto itself under "
                    "the site's symmetry — orient it so that it does, or list it "
                    "as atoms and declare the body over one atom per image "
                    "(body_from_atoms(..., origin=...))")
            first[k] = min(first[k], int(same[0]))
    return [k for k in range(len(labels)) if first[k] == k]


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
