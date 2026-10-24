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

from collections.abc import Iterable, Sequence

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.params import TieSpec
from ..schemas.structure import Structure
from .adp import tensor_from_voigt, voigt_from_tensor
from .symmetry import (
    TWIN_COORD_TOL,
    TwinMerge,
    expand_positions,
    resolve_group,
    site_orbit,
    site_twin_merge,
)
from .wyckoff import coordinate_basis, stabilizer_rotations


def _num(v: float) -> str:
    return f"{v:.4g}"


def _content_change(occ: float, merge: TwinMerge) -> str:
    """The merge's atoms per cell both ways, for the message.

    The merge keeps the stated occupancy, so the site's content goes from
    ``before × occ`` to ``after × occ`` atoms per cell.  It happens only where
    the unmerged model puts more than one atom at one place
    (:func:`applied_twin_merges`), so the split-pair reading, which would
    divide the content by ``before/after``, is the kept branch's to say.
    """
    return (f"Atoms per cell (multiplicity × occupancy): {merge.before} × {_num(occ)} = "
            f"{_num(merge.before * occ)} → {merge.after} × {_num(occ)} = "
            f"{_num(merge.after * occ)}.")


def _fixed_by_symmetry(atom, sg, position: np.ndarray, diagnostics_note: list[str]):
    """``atom``'s coordinates and tensor as the special position ``position`` allows them.

    What the merge moves onto a position, the parameter table then checks
    against that position, and refuses what it did not allow before the move:
    a coordinate with ``vary=True`` where the site symmetry allows no positional
    freedom, and an anisotropic tensor outside the allowed subspace.  So the
    merge clears ``vary`` on exactly the coordinates
    :meth:`~rietx.refine.Refinement.fix_special_positions` would, and projects
    the tensor onto the allowed patterns by the group average U ↦ (1/|G|) Σ R·U·Rᵀ
    over the site group, R untransposed (the Reynolds operator; the patterns
    are :func:`~.wyckoff.adp_basis`'s, which is the same invariant subspace,
    Peterse & Palm, 1966, Acta Cryst. 20, 147).
    A mean of congruences of a positive-definite tensor is positive definite,
    so the projection cannot make a tensor the model then refuses
    (``ADP_NOT_POSITIVE_DEFINITE``), which a least-squares projection in the six
    components, whose metric the site group does not preserve, did on 1.3 % of
    hexagonal tensors (maintainer's measurement, #1014 round 4).  Each is said in
    ``diagnostics_note``.
    """
    rotations = stabilizer_rotations(sg, position)
    update: dict = {}
    coords = {}
    for n, v in zip("xyz", position, strict=True):
        param = getattr(atom, n).model_copy(update={"value": float(v)})
        coords[n] = param
    if len(coordinate_basis(rotations)) == 0 and any(p.vary for p in coords.values()):
        for p in coords.values():
            p.vary = False
        diagnostics_note.append(
            "Its coordinates were set to vary=False: the position allows no "
            "positional freedom.")
    update.update(coords)
    if atom.aniso is not None:
        u0 = np.array(atom.aniso.values(), dtype=np.float64)
        tensor = tensor_from_voigt(u0)
        mean = sum(r.astype(np.float64) @ tensor @ r.astype(np.float64).T
                   for r in rotations) / len(rotations)
        u1 = voigt_from_tensor(mean)
        change = float(np.abs(u1 - u0).max())
        if change > 1e-6 * max(float(np.abs(u0).max()), 1e-6):
            aniso = atom.aniso.model_copy(update={
                name: getattr(atom.aniso, name).model_copy(update={"value": float(v)})
                for name, v in zip(("u11", "u22", "u33", "u12", "u13", "u23"),
                                   u1, strict=True)})
            update["aniso"] = aniso
            diagnostics_note.append(
                f"Its anisotropic tensor was projected onto the tensors the "
                f"position allows (largest change {change:.2g} Å²).")
    return update


def _kept_message(atom, phase_name: str | None, source: str | None, xyz, merge: TwinMerge,
                  position: list[float]) -> tuple[str, str]:
    """Message and suggestion for a site left as stored, whose merge would lose content."""
    occ = atom.occ.value
    ratio = merge.before / merge.after
    message = (
        f"{source + ': ' if source else ''}site {atom.label!r}"
        f"{f' of phase {phase_name!r}' if phase_name else ''} is stated at {[round(float(v), 6) for v in xyz]}, "
        f"where it puts {merge.before} positions in the cell in pairs "
        f"{merge.gap:.2g} Å apart; nothing was moved. The coordinates cannot "
        f"say which of two things this is. One atom stated off its special "
        f"position {[round(v, 6) for v in position]} ({merge.after} positions) "
        f"holds {merge.after} × {_num(occ)} = {_num(merge.after * occ)} atoms "
        f"per cell there, at occupancy {_num(occ)}. A split pair of part-atoms "
        f"holds {merge.before} × {_num(occ)} = {_num(merge.before * occ)} as "
        f"stored, and {merge.after} × {_num(occ * ratio)} = "
        f"{_num(merge.before * occ)} on the position, at occupancy "
        f"{_num(occ * ratio)}. The model is left as stored and counts the "
        f"second.")
    suggestion = (
        f"state the site on the special position at occupancy {_num(occ)} if "
        f"it is one atom stated off its position, or at occupancy "
        f"{_num(occ * ratio)} if it is a split pair; or state it more than "
        f"{_num(TWIN_COORD_TOL)} (fractional) from the special position "
        f"to say it is split.")
    return message, suggestion


def _dof_moves(sg, before: np.ndarray, after: np.ndarray, prefix: str
               ) -> dict[str, tuple[str | None, float]]:
    """Where each coordinate DOF of a site goes when the site gains symmetry.

    ``phases.i.atoms.j.dof.k`` is the k-th direction the site symmetry allows,
    so a site that moves onto a special position renumbers them: PbSO₄'s O5 has
    x, y, z as DOFs 0-2 on the general position and x, z as DOFs 0-1 on the
    y = ¼ mirror, where ``dof.1`` is z (#1014, round 4).  Old DOF k maps to the
    new DOF whose direction is parallel to its own, with the factor ``s``
    such that old direction = s × new (a coefficient c on the old DOF is c/s on
    the new one), and to ``None`` where no new direction is parallel: the
    position fixes that coordinate (or mixes it), and nothing carries over.
    """
    old_basis = coordinate_basis(stabilizer_rotations(sg, before))
    new_basis = coordinate_basis(stabilizer_rotations(sg, after))
    moves: dict[str, tuple[str | None, float]] = {}
    for k, old in enumerate(old_basis):
        old = np.asarray(old, dtype=np.float64)
        target: tuple[str | None, float] = (None, 1.0)
        for j, new in enumerate(new_basis):
            new = np.asarray(new, dtype=np.float64)
            scale = float(old @ new) / float(new @ new)
            if np.allclose(old, scale * new, atol=1e-9):
                target = (f"{prefix}.dof.{j}", scale)
                break
        moves[f"{prefix}.dof.{k}"] = target
    return moves


def numbering_moves(old: Structure, new: Structure
                    ) -> dict[str, tuple[str | None, float]]:
    """Where each coordinate DOF of ``old`` goes in ``new``, wherever a site's DOFs differ.

    The one reading of "this structure's DOF numbering changed", whatever
    changed it: a merge, a coordinate a fit landed within 5e-5 of a mirror
    (which :func:`~.symmetry.site_orbit` already counts as special, so no
    merge fires), a value ``set_values`` wrote.  A holder of a hold, tie, free
    path or stored path applies it with :func:`carry_constraints`, so the
    carry does not depend on which route moved the site (#1014 round 5, items
    2-6).  Phases and atoms are matched by position and label; a phase whose
    group or atom list changed is a different model and is left to the
    caller's own reconciliation.
    """
    moves: dict[str, tuple[str | None, float]] = {}
    for i, (po, pn) in enumerate(zip(old.phases, new.phases, strict=False)):
        if (po.space_group != pn.space_group
                or [a.label for a in po.atoms] != [a.label for a in pn.atoms]):
            continue
        try:
            sg = resolve_group(pn.space_group, pn.symmetry_operations)
        except (ValueError, RuntimeError):
            continue
        for j, (ao, an) in enumerate(zip(po.atoms, pn.atoms, strict=True)):
            xo = np.array([ao.x.value, ao.y.value, ao.z.value])
            xn = np.array([an.x.value, an.y.value, an.z.value])
            if np.array_equal(xo, xn):
                continue
            try:
                bo = coordinate_basis(stabilizer_rotations(sg, xo))
                bn = coordinate_basis(stabilizer_rotations(sg, xn))
            except ValueError:
                continue
            if len(bo) == len(bn) and np.array_equal(
                    np.asarray(bo), np.asarray(bn)):
                continue
            moves.update(_dof_moves(sg, xo, xn, f"phases.{i}.atoms.{j}"))
    return moves


def carry_constraints(moves: dict[str, tuple[str | None, float]], *,
                      holds: Iterable[str] = (),
                      ties: dict[str, TieSpec] | None = None,
                      free_paths: Iterable[str] = ()
                      ) -> tuple[list[str], dict[str, TieSpec], list[str], list[str]]:
    """``holds``, user ``ties`` and ``free_paths`` carried through a DOF renumbering.

    ``moves`` is what :func:`merge_site_twins` reports.  A hold or a free path
    on a DOF follows it to its new number; one on a DOF the position now fixes
    is dropped.  A tie is carried only if its target and every source survive,
    its coefficients rescaled; otherwise it is dropped (a source that moved
    would otherwise change meaning in silence).  Returns
    ``(holds, ties, free_paths, notes)``, ``notes`` naming each thing dropped
    and each hold or tie that now sits on a different DOF number.
    """
    notes: list[str] = []

    def one(path: str) -> str | None:
        if path not in moves:
            return path
        return moves[path][0]

    def path_list(paths: Iterable[str], what: str) -> list[str]:
        out: list[str] = []
        for path in paths:
            new = one(path)
            if new is None:
                notes.append(f"the {what} on {path} was dropped: the special "
                             f"position fixes or couples that direction")
                continue
            if new != path:
                notes.append(f"the {what} on {path} now reads {new}")
            if new not in out:
                out.append(new)
        return out

    held = path_list(holds, "hold")
    free = path_list(free_paths, "free path")
    new_ties: dict[str, TieSpec] = {}
    for target, spec in (ties or {}).items():
        new_target = one(target)
        sources = [(one(p), c / moves[p][1] if p in moves else c)
                   for p, c in spec.terms]
        if new_target is None or any(p is None for p, _ in sources):
            notes.append(f"the tie on {target} was dropped: a direction it "
                         f"uses is fixed by the special position")
            continue
        if new_target != target or any(
                p != q for (p, _), (q, _) in zip(sources, spec.terms, strict=True)):
            notes.append(f"the tie on {target} now reads {new_target}")
        new_ties[new_target] = spec.model_copy(update={
            "terms": [(p, float(c)) for p, c in sources]})
    return held, new_ties, free, notes


def carry_state_constraints(state, moves: dict[str, tuple[str | None, float]],
                            found: list[Diagnostic]) -> None:
    """:func:`carry_constraints` on a ``RefinementState``'s registers, in place.

    A stored node carries its holds, user ties and free paths against the DOF
    numbering of the structure it recorded; when that structure's site merges,
    they follow it.  What is dropped is named in the site's
    ``SITE_TWINS_MERGED`` message in ``found``, replaced in the list.
    """
    for site in sorted({path.rsplit(".dof.", 1)[0] for path in moves}):
        site_moves = {p: m for p, m in moves.items()
                      if p.rsplit(".dof.", 1)[0] == site}
        holds, ties, free, notes = carry_constraints(
            site_moves, holds=state.holds, ties=state.ties,
            free_paths=state.free_paths)
        state.holds, state.ties, state.free_paths = holds, ties, free
        for n, d in enumerate(found):
            if notes and d.code == "SITE_TWINS_MERGED" and d.where == [site]:
                found[n] = d.model_copy(update={
                    "message": d.message + " Constraints: " + "; ".join(notes) + "."})


def _same_site(sg, a: np.ndarray, b: np.ndarray) -> bool:
    """Whether ``b`` is an image of ``a`` under the group, within the merge's reach.

    Grouped at :data:`~.symmetry.TWIN_COORD_TOL` per coordinate, the reach the
    merge itself moves a site by: an unmerged model puts co-occupants that
    close at one place, and a fit moves them apart by that much unless they
    are tied (#1014, round 5).
    """
    for image in expand_positions(sg, a):
        d = np.asarray(image, dtype=np.float64) - b
        if np.all(np.abs(d - np.round(d)) <= TWIN_COORD_TOL * (1.0 + 1e-9)):
            return True
    return False


def applied_twin_merges(sg, cell, xyzs: Sequence[np.ndarray | None],
                        occs: Sequence[float]
                        ) -> tuple[dict[int, TwinMerge], dict[int, TwinMerge]]:
    """Which sites' coinciding images the merge acts on, and which it leaves as stored.

    ``xyzs[j]`` is site j's stated position, ``None`` for a site that takes no
    part (a rigid-body atom); ``occs[j]`` its occupancy.  Returns
    ``(applied, kept)``, each ``{j: TwinMerge}``.  One gate at every boundary,
    readers included (maintainer's ruling, #1014 round 5): where the occupancy
    at the site's position, summed over every atom there with each × (images
    before / images after), is above 1, the unmerged model puts more than one
    atom at one place and the merge is arithmetic.  At most 1 the stated
    numbers read both as one atom off its position and as a split pair of
    part-atoms (#1088): that site is *kept*, and the caller says both readings.
    The sum is over the atoms sharing the position (Fe 0.5 and Mn 0.5 on one
    site is 1 per position, doubled by the collapse), never per atom.  GSAS-II
    drops an image only within 2e-4 fractional, FullProf and BGMN not at all,
    TOPAS only on request.
    """
    found: dict[int, TwinMerge] = {}
    for j, xyz in enumerate(xyzs):
        if xyz is None:
            continue
        try:
            merge = site_twin_merge(sg, cell, xyz)
        except ValueError:
            continue             # an orbit refusal speaks at compile
        if merge is not None:
            found[j] = merge

    def position_of(j: int) -> np.ndarray | None:
        """Where atom j sits as the merge would leave it, for sharing."""
        if j in found:
            return found[j].position
        xyz = xyzs[j]
        if xyz is None:
            return None
        try:
            return np.asarray(site_orbit(sg, xyz).position)
        except ValueError:
            return None

    def per_position(j: int) -> float:
        here = found[j].position
        total = 0.0
        for k in range(len(xyzs)):
            if k != j:
                other = position_of(k)
                if other is None or not _same_site(sg, here, other):
                    continue
            ratio = found[k].before / found[k].after if k in found else 1.0
            total += occs[k] * ratio
        return total

    applied: dict[int, TwinMerge] = {}
    kept: dict[int, TwinMerge] = {}
    for j, merge in found.items():
        if round(per_position(j), 6) <= 1.0:
            kept[j] = merge
        else:
            applied[j] = merge
    return applied, kept


def merge_site_twins(structure: Structure, *,
                     diagnostics: list[Diagnostic] | None = None,
                     source: str | None = None) -> Structure:
    """``structure`` with every site whose own images coincide moved onto its position.

    A site whose special position lies within
    :data:`~.symmetry.TWIN_COORD_TOL` of its coordinates, per coordinate, is one
    atom counted twice; it is moved to the special position its orbit collapses
    to, and one ``SITE_TWINS_MERGED`` warning per site is appended to
    ``diagnostics``.  A split site, a site already on its position and a
    rigid-body atom (the body's pose writes it; a body across a symmetry
    element is the body's own question, #876) are left alone.  Returns the
    argument itself when nothing moved, and never mutates it.

    A moved site is also made fit for its new position: coordinates the
    position fixes lose ``vary``, and an anisotropic tensor is projected onto
    the allowed patterns, each said in the message (otherwise the parameter
    table refuses the merged model, #1014).  The coordinate DOFs of a site that
    gains symmetry renumber; :func:`numbering_moves` reads that off two
    structures, for :func:`carry_constraints`.

    Which sites merge is :func:`applied_twin_merges`'s one gate: a site whose
    occupancy summed over the atoms at its position, each × (images before /
    images after), is at most 1 is **left as stored** and ``SITE_TWINS_KEPT``
    gives both readings; above 1 the merge is arithmetic and happens, with the
    stated occupancy kept.

    ``source`` prefixes the message (a file path, as the readers' messages do).

    The rule and its references are :func:`~.symmetry.site_twin_merge`'s:
    International Tables for Crystallography vol. A (Wyckoff positions) and
    Grosse-Kunstleve & Adams (2002), Acta Cryst. A58, 60.
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
        stated = {j: np.array([a.x.value, a.y.value, a.z.value])
                  for j, a in enumerate(atoms)}
        applied, kept = applied_twin_merges(
            sg, cell,
            [None if a.label in bodied else stated[j] for j, a in enumerate(atoms)],
            [a.occ.value for a in atoms])
        found = {**applied, **kept}

        moved_any = False
        for j, merge in found.items():
            atom = atoms[j]
            xyz = stated[j]
            position = [float(v) for v in merge.position]
            if j in kept:
                if diagnostics is not None:
                    message, suggestion = _kept_message(
                        atom, phase.name, source, xyz, merge, position)
                    diagnostics.append(Diagnostic(
                        level="warning", code="SITE_TWINS_KEPT",
                        where=[f"phases.{i}.atoms.{j}"], value=merge.gap,
                        message=message, suggestion=suggestion))
                continue
            notes: list[str] = []
            atoms[j] = atom.model_copy(update=_fixed_by_symmetry(
                atom, sg, np.array(position), notes))
            moved_any = True
            if diagnostics is not None:
                content = _content_change(atom.occ.value, merge)
                diagnostics.append(Diagnostic(
                    level="warning", code="SITE_TWINS_MERGED",
                    where=[f"phases.{i}.atoms.{j}"], value=merge.gap,
                    message=(
                        f"{source + ': ' if source else ''}site "
                        f"{atom.label!r} of phase {phase.name!r} was given at "
                        f"{[round(float(v), 6) for v in xyz]}, where it puts "
                        f"{merge.before} positions in the cell in pairs "
                        f"{merge.gap:.2g} Å apart; it was moved onto the "
                        f"special position {[round(v, 6) for v in position]}, "
                        f"{merge.after} positions, with its occupancy unchanged. "
                        f"{content}" + "".join(" " + n for n in notes)),
                    suggestion=(
                        "check the coordinate against its source: a special "
                        "position stated a few 1e-5 off (a hand edit, a "
                        "rounded project file) is the usual cause. "
                        + f"To keep a genuinely displaced atom, state "
                        f"it more than {_num(TWIN_COORD_TOL)} (fractional) "
                        f"from the special position.")))
        if moved_any:
            # model_copy skips validation on purpose: the move is the repair,
            # and an assignment would re-run every validator of the phase
            phases[i] = phase.model_copy(update={"atoms": atoms})
            changed = True
    if not changed:
        return structure
    return structure.model_copy(update={"phases": phases})
