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

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import NamedTuple

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
    site_stabilizer_indices,
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


#: :func:`_content_change`'s sentence: its numbers can carry a decimal point.
_CONTENT_SENTENCE = re.compile(r"Atoms per cell \(multiplicity × occupancy\): .*? = \S+ → .*? = \S+?\.(?= |$)")


def message_notes(message: str) -> str:
    """What a ``SITE_TWINS_MERGED`` message says after its atoms-per-cell sentence.

    The coordinates released and the tensor projected, each as its own sentence,
    with their leading space; ``""`` if there are none.  For a reader that
    rewrites the head of the message and must keep what the merge said about
    making the site fit its position (#1014 round 7, item 3).
    """
    m = _CONTENT_SENTENCE.search(message)
    return message[m.end():] if m else ""


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


class DofMove(NamedTuple):
    """Where one coordinate DOF of a site goes when the site's symmetry changes.

    ``path`` is the new DOF whose direction is parallel to the old one, with
    ``scale`` = s such that old direction = s × new, so a value θ on the old
    DOF is s·θ on the new one and a coefficient c on it is c/s; ``None`` where
    no new direction is parallel.  ``linked`` names every new DOF the old one
    shares a direction with (:func:`_linked`), each with its direction in
    (x, y, z): the parallel one, or, where the position couples coordinates,
    as (x, 2x, z) in P 6₃/mmc does, the coupled direction that moves this one
    (#1014, round 6).  A hold follows ``linked``; a tie and a value need the
    single direction ``path``.  ``direction`` is the old DOF's own, in
    (x, y, z), for the message.

    ``linked`` and ``direction`` default to ``()``, which means *not computed*,
    not an answer: the carry reads an empty ``linked`` as "the position fixes
    this direction", so a hand-built ``DofMove`` that leaves it out drops a hold
    in silence.  :func:`_dof_moves` is the only writer and always fills both.
    """

    path: str | None
    scale: float
    linked: tuple[tuple[str, tuple[int, ...]], ...] = ()
    direction: tuple[int, ...] = ()


def _expansion(basis: np.ndarray, v: np.ndarray) -> np.ndarray | None:
    """The coefficients c with ``v`` = Σₖ cₖ·basisₖ, or ``None`` outside their span."""
    if len(basis) == 0:
        return None
    b = np.asarray(basis, dtype=np.float64).T
    c = np.linalg.lstsq(b, np.asarray(v, dtype=np.float64), rcond=None)[0]
    return c if np.allclose(b @ c, v, atol=1e-9) else None


def _linked(old_basis: np.ndarray, new_basis: np.ndarray) -> set[tuple[int, int]]:
    """The (old k, new j) DOF pairs that share a direction.

    New direction j and old direction k are linked where moving along one
    moves along the other: j written in the old directions uses k (a site
    gaining symmetry, whose new directions lie in the old span), or k written
    in the new directions uses j (a site losing it).  A parallel pair is the
    one-to-one case.  On PbSO₄'s y = ¼ mirror, x and z each link to one new
    DOF and y to none: the position fixes it.  On (x, 2x, z) in P 6₃/mmc,
    the new direction [1, 2, 0] is old x + 2 × old y, so both old x and old y
    link to it: the position couples them.
    """
    pairs: set[tuple[int, int]] = set()
    for j, n in enumerate(new_basis):
        c = _expansion(old_basis, n)
        if c is not None:
            pairs.update((k, j) for k, ck in enumerate(c) if abs(ck) > 1e-9)
    for k, b in enumerate(old_basis):
        a = _expansion(new_basis, b)
        if a is not None:
            pairs.update((k, j) for j, aj in enumerate(a) if abs(aj) > 1e-9)
    return pairs


def _dof_moves(old_basis: np.ndarray, new_basis: np.ndarray, prefix: str,
               new_prefix: str | None = None) -> dict[str, DofMove]:
    """Where each coordinate DOF of a site goes when the site's symmetry changes.

    ``phases.i.atoms.j.dof.k`` is the k-th direction the site symmetry allows,
    so a site that moves onto a special position renumbers them: PbSO₄'s O5 has
    x, y, z as DOFs 0-2 on the general position and x, z as DOFs 0-1 on the
    y = ¼ mirror, where ``dof.1`` is z (#1014, round 4).  Each old DOF's
    :class:`DofMove` names its parallel new DOF, if any, and every new DOF it
    is linked to (:func:`_linked`).
    """
    pairs = _linked(old_basis, new_basis)
    new_site = new_prefix or prefix
    moves: dict[str, DofMove] = {}
    for k, old in enumerate(old_basis):
        old = np.asarray(old, dtype=np.float64)
        target, scale = None, 1.0
        for j, new in enumerate(new_basis):
            new = np.asarray(new, dtype=np.float64)
            s = float(old @ new) / float(new @ new)
            if np.allclose(old, s * new, atol=1e-9):
                target, scale = f"{new_site}.dof.{j}", s
                break
        linked = tuple((f"{new_site}.dof.{j}", tuple(int(v) for v in new_basis[j]))
                       for j in range(len(new_basis)) if (k, j) in pairs)
        moves[f"{prefix}.dof.{k}"] = DofMove(target, scale, linked,
                                             tuple(int(v) for v in old_basis[k]))
    return moves


@dataclass(frozen=True)
class CoordinateSnapshot:
    """What :func:`numbering_moves` reads of a structure: its groups, labels and coordinates.

    A caller that must look at the structure *before* a write (``_write_back``,
    once per stage) takes this instead of deep-copying the whole structure,
    which cost more than the carry it served (#1014 round 6, item 4).
    """

    phases: tuple[tuple[str, object, tuple[str, ...], np.ndarray], ...]


class NumberingMoves(dict):
    """:func:`numbering_moves`' result: ``{old DOF path: DofMove}``.

    The keys read the *old* structure's atom numbering, the diagnostics a caller
    reports read the new one's, and the two differ whenever an atom was inserted
    or removed ahead of the site (#1014 round 7, item 2).  ``sites`` maps each
    old site path (``phases.i.atoms.j``) to its path in the new structure.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sites: dict[str, str] = {}

    def new_site(self, old_site: str) -> str:
        """The new structure's path of the site that was ``old_site``."""
        return self.sites.get(old_site, old_site)


def coordinate_snapshot(structure: Structure) -> CoordinateSnapshot:
    """The coordinates and the labels, groups and operation lists they are read against."""
    return CoordinateSnapshot(tuple(
        (p.space_group, p.symmetry_operations, tuple(a.label for a in p.atoms),
         np.array([[a.x.value, a.y.value, a.z.value] for a in p.atoms],
                  dtype=np.float64).reshape(-1, 3))
        for p in structure.phases))


def numbering_moves(old: Structure | CoordinateSnapshot,
                    new: Structure | CoordinateSnapshot
                    ) -> NumberingMoves:
    """Where each coordinate DOF of ``old`` goes in ``new``, wherever a site's DOFs differ.

    The one reading of "this structure's DOF numbering changed", whatever
    changed it: a merge, a coordinate a fit landed within 5e-5 of a mirror
    (which :func:`~.symmetry.site_orbit` already counts as special, so no
    merge fires), a value ``set_values`` wrote, an edit that moved a site off
    its position.  A holder of a hold, tie, free path or stored path applies it
    with :func:`carry_constraints`, so the carry does not depend on which route
    moved the site (#1014 round 5, items 2-6).  Phases are matched by position
    and atoms by label (see :func:`_matched_atoms`), so a structure edited to
    add or rename an atom keeps the carry for the others; a phase whose group
    changed is a different model and is left to the caller's own
    reconciliation.

    An atom whose coordinates did not move is not looked at, and one that did
    costs the site's stabiliser (:func:`~.symmetry.site_stabilizer_indices`,
    no orbit) at the two positions: the same operations fixing both is the
    same DOF numbering, whatever else moved.
    """
    old = old if isinstance(old, CoordinateSnapshot) else coordinate_snapshot(old)
    new = new if isinstance(new, CoordinateSnapshot) else coordinate_snapshot(new)
    moves = NumberingMoves()
    for i, (po, pn) in enumerate(zip(old.phases, new.phases, strict=False)):
        (go, _, lo, xo_all), (gn, ops_n, ln, xn_all) = po, pn
        if go != gn:
            continue
        pairs = [(jo, jn) for jo, jn in _matched_atoms(lo, ln)
                 if not np.array_equal(xo_all[jo], xn_all[jn])]
        if not pairs:
            continue
        try:
            sg = resolve_group(gn, ops_n)
        except (ValueError, RuntimeError):
            continue
        for jo, jn in pairs:
            xo, xn = xo_all[jo], xn_all[jn]
            if site_stabilizer_indices(sg, xo) == site_stabilizer_indices(sg, xn):
                continue
            try:
                bo = coordinate_basis(stabilizer_rotations(sg, xo))
                bn = coordinate_basis(stabilizer_rotations(sg, xn))
            except ValueError:
                continue
            if len(bo) == len(bn) and np.array_equal(np.asarray(bo), np.asarray(bn)):
                continue
            moves.update(_dof_moves(bo, bn, f"phases.{i}.atoms.{jo}",
                                    f"phases.{i}.atoms.{jn}"))
            moves.sites[f"phases.{i}.atoms.{jo}"] = f"phases.{i}.atoms.{jn}"
    return moves


def _matched_atoms(lo: Sequence[str], ln: Sequence[str]) -> list[tuple[int, int]]:
    """(old index, new index) of the atoms two label lists both hold.

    The same list in the same order matches by position.  Otherwise (an atom
    appended, one renamed, one removed: the GUI's add-atom path) an atom is
    matched by its label where that label is unique in both phases; an atom
    with no such partner is a different atom and is left alone (#1014 round 6,
    item 2).
    """
    if list(lo) == list(ln):
        return [(j, j) for j in range(len(lo))]
    return [(lo.index(label), ln.index(label)) for label in lo
            if lo.count(label) == 1 and ln.count(label) == 1]


def _move(m) -> DofMove:
    """A move as :class:`DofMove`; a bare ``(path, scale)`` pair links its parallel DOF only."""
    if isinstance(m, DofMove):
        return m
    path, scale = m[0], m[1]
    return DofMove(path, scale, ((path, ()),) if path is not None else ())


def _along(linked) -> str:
    return " and ".join(f"{p} (along {list(v)} in x, y, z)" if v else p
                        for p, v in linked)


def _coords(v: Sequence[int]) -> str:
    """The coordinates a direction moves, as words: ``[1, 2, 0]`` → ``"x and y"``."""
    names = ["xyz"[i] for i, c in enumerate(v) if c]
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else "".join(names)


def _coupling(m: DofMove, targets) -> str:
    """Why a path on ``m``'s DOF now covers ``targets`` rather than one parallel DOF."""
    old = {i for i, c in enumerate(m.direction) if c}
    if len(targets) == 1 and {i for i, c in enumerate(targets[0][1]) if c} > old:
        return (f"the special position couples {_coords(targets[0][1])}, and this is "
                f"the one direction that moves {_coords(m.direction)}")
    return (f"the site's new position no longer couples {_coords(m.direction)}, and "
            f"each of these moves part of the direction it named")


def _carry_paths(moves: dict, paths: Iterable[str], what: str, notes: list[str], *,
                 free: bool = False) -> list[str]:
    """``paths`` (holds, or with ``free`` free paths) carried through ``moves``.

    A hold follows every new DOF its direction is linked to
    (:attr:`DofMove.linked`): on a parallel one it is the same hold renumbered,
    and where the position couples it with another coordinate, as
    (x, 2x, z) does x with y, the coupled direction is the only one that moves
    x, so holding x holds it (#1014, round 6).  A hold linked to nothing is on
    a direction the position fixes, and is dropped.  A free path frees a new
    DOF only where every old direction linked to it was free, so freeing x
    alone does not free the (x, 2x, z) direction, which moves y too.  Paths
    ``moves`` does not name (another site, a glob) pass unchanged.
    """
    paths = list(paths)
    out: list[str] = []
    if free:
        sources: dict[str, set[str]] = {}
        for old, m in moves.items():
            for new, _ in _move(m).linked:
                sources.setdefault(new, set()).add(old)
        given = set(paths)
    for path in paths:
        if path not in moves:
            if path not in out:
                out.append(path)
            continue
        m = _move(moves[path])
        targets = list(m.linked)
        if free:
            targets = [(p, v) for p, v in targets if sources[p] <= given]
        if not targets:
            if not m.linked:
                why = "the special position fixes that direction"
            else:
                why = (f"the special position couples it with a direction that was "
                       f"not free ({_along(m.linked)})")
            notes.append(f"the {what} on {path} was dropped: {why}")
            continue
        if m.path is not None and [p for p, _ in targets] == [m.path]:
            if m.path != path:
                notes.append(f"the {what} on {path} now reads {m.path}")
        else:
            notes.append(f"the {what} on {path} now covers {_along(targets)}: "
                         f"{_coupling(m, targets)}")
        for p, _ in targets:
            if p not in out:
                out.append(p)
    return out


def _carry_tie(moves: dict, target: str, spec: TieSpec) -> tuple[str | None, TieSpec | None, str]:
    """One tie through ``moves``: its new target and spec, or ``None`` and the reason.

    A DOF value is a displacement along the DOF's direction, so with old
    direction = s × new a value θ on the old DOF is s·θ on the new one
    (:class:`DofMove`).  The tie θₜ = Σ cᵢ·θᵢ + k then reads
    s_t·θₜ = Σ (s_t·cᵢ/sᵢ)·(sᵢ·θᵢ) + s_t·k on the new DOFs: each coefficient
    takes the target's scale over its source's, and the constant the target's
    (#1014, round 6).  ``_nullspace_int`` scales every basis vector to coprime
    integers with its first nonzero entry positive, so two parallel ones are
    equal and every s is 1 today
    (``test_parallel_basis_vectors_are_equal_so_every_dof_scale_is_one``); this
    is the arithmetic for the day that changes.  A tie needs one direction per
    path, so a target or source the position fixes or couples drops it.
    """
    def one(path: str) -> tuple[str | None, float, DofMove | None]:
        if path not in moves:
            return path, 1.0, None
        m = _move(moves[path])
        return m.path, m.scale, m

    new_target, s_t, m_t = one(target)
    sources = [(one(p), c) for p, c in spec.terms]
    lost = [m for path, _, m in [(new_target, s_t, m_t), *(o for o, _ in sources)]
            if path is None]
    if lost:
        why = ("coupled with another by the special position, and a tie needs "
               "a single direction" if any(m.linked for m in lost)
               else "fixed by the special position")
        return None, None, f"the tie on {target} was dropped: a direction it uses is {why}"
    terms = [(p, float(s_t * c / s)) for (p, s, _), c in sources]
    note = ""
    if new_target != target or any(p != q for (p, _), (q, _) in
                                   zip(terms, spec.terms, strict=True)):
        note = f"the tie on {target} now reads {new_target}"
    return new_target, spec.model_copy(update={
        "terms": terms, "const": float(s_t * spec.const)}), note


def carry_constraints(moves: dict[str, DofMove], *,
                      holds: Iterable[str] = (),
                      ties: dict[str, TieSpec] | None = None,
                      free_paths: Iterable[str] = ()
                      ) -> tuple[list[str], dict[str, TieSpec], list[str], list[str]]:
    """``holds``, user ``ties`` and ``free_paths`` carried through a DOF renumbering.

    ``moves`` is what :func:`numbering_moves` returns, for one site.  A hold
    follows its direction, onto the coupled direction where the position
    couples it with another coordinate, and is dropped where the position fixes
    it; a free path follows only onto a direction every coordinate it moves was
    free on (:func:`_carry_paths`).  A tie is carried only if its target and
    every source keep a single direction, its coefficients and constant
    rescaled (:func:`_carry_tie`); otherwise it is dropped (a source that moved
    would otherwise change meaning in silence).  Returns
    ``(holds, ties, free_paths, notes)``, ``notes`` naming each thing dropped
    and each hold or tie that now sits on a different DOF.
    """
    notes: list[str] = []
    held = _carry_paths(moves, holds, "hold", notes)
    free = _carry_paths(moves, free_paths, "free path", notes, free=True)
    new_ties: dict[str, TieSpec] = {}
    for target, spec in (ties or {}).items():
        new_target, new_spec, note = _carry_tie(moves, target, spec)
        if note:
            notes.append(note)
        if new_target is not None:
            new_ties[new_target] = new_spec
    return held, new_ties, free, notes


def _site_moves(moves: dict) -> Iterable[tuple[str, dict]]:
    """``moves`` split by site, as ``(old site path, its moves)``."""
    for site in sorted({path.rsplit(".dof.", 1)[0] for path in moves}):
        yield site, {p: m for p, m in moves.items()
                     if p.rsplit(".dof.", 1)[0] == site}


def carry_action_constraints(action, moves: dict[str, DofMove]) -> dict[str, list[str]]:
    """A recorded ``NodeAction``'s paths carried through a DOF renumbering, in place.

    A node records the paths its action named (a stage's ``turn_on``, a
    ``set_vary``'s ``turn_on``/``turn_off``, a ``set_value``'s ``values``, a
    ``set_hold``'s ``held``/``unheld``, a ``set_tie``'s ``ties``/``untied``)
    in the numbering of the state it acted on.  When a log is loaded and that
    site merges, the state's registers follow (:func:`carry_state_constraints`)
    and so must these, or a ``cherry_pick`` of a stage whose ``turn_on`` names
    y's ``dof.1`` frees z on the merged site (#1014, round 5).  A turn-on is
    carried as a free path and a turn-off, hold or release as a hold; a value
    is a displacement, s·θ on the new DOF, and is dropped with its DOF.
    Returns ``{new site path: notes}``.
    """
    out: dict[str, list[str]] = {}
    kind = action.kind
    for site, site_moves in _site_moves(moves):
        notes: list[str] = []
        action.turn_on = _carry_paths(site_moves, action.turn_on,
                                      f"recorded {kind}'s turn_on", notes, free=True)
        for field in ("turn_off", "held", "unheld"):
            setattr(action, field, _carry_paths(
                site_moves, getattr(action, field), f"recorded {kind}'s {field}", notes))
        values: dict[str, float] = {}
        for path, value in action.values.items():
            if path not in site_moves:
                values[path] = value
                continue
            m = _move(site_moves[path])
            if m.path is None:
                notes.append(f"the recorded {kind}'s value on {path} was dropped: the "
                             f"special position {'couples' if m.linked else 'fixes'} "
                             f"that direction")
                continue
            values[m.path] = m.scale * value
            if m.path != path:
                notes.append(f"the recorded {kind}'s value on {path} now reads {m.path}")
        action.values = values
        ties: dict[str, TieSpec] = {}
        for target, spec in action.ties.items():
            new_target, new_spec, note = _carry_tie(site_moves, target, spec)
            if note:
                notes.append(f"recorded {kind}: {note}")
            if new_target is not None:
                ties[new_target] = new_spec
        action.ties = ties
        untied: list[str] = []
        for path in action.untied:
            new = _move(site_moves[path]).path if path in site_moves else path
            if new is None:
                notes.append(f"the recorded {kind}'s untie of {path} was dropped: "
                             f"the special position takes that direction")
            elif new not in untied:
                untied.append(new)
        action.untied = untied
        if notes:
            new_site = moves.new_site(site) if isinstance(moves, NumberingMoves) else site
            out.setdefault(new_site, []).extend(notes)
    return out


def carry_state_constraints(state, moves: dict[str, DofMove],
                            found: list[Diagnostic]) -> None:
    """:func:`carry_constraints` on a ``RefinementState``'s registers, in place.

    A stored node carries its holds, user ties and free paths against the DOF
    numbering of the structure it recorded; when that structure's site merges,
    they follow it.  What is dropped is named in the site's
    ``SITE_TWINS_MERGED`` message in ``found``, replaced in the list.
    """
    for site, site_moves in _site_moves(moves):
        holds, ties, free, notes = carry_constraints(
            site_moves, holds=state.holds, ties=state.ties,
            free_paths=state.free_paths)
        state.holds, state.ties, state.free_paths = holds, ties, free
        new_site = moves.new_site(site) if isinstance(moves, NumberingMoves) else site
        for n, d in enumerate(found):
            if notes and d.code == "SITE_TWINS_MERGED" and d.where == [new_site]:
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
    table refuses the merged model, #1014).  The coordinate DOFs of a site whose
    symmetry changes renumber; :func:`numbering_moves` reads that off two
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
