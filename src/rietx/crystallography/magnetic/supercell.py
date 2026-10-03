"""A commensurate k ≠ 0 magnetic structure, stated as a nuclear phase in its magnetic cell.

WP-1327 stores **one moment per atom of the nuclear asymmetric unit** and
propagates it over that site's magnetic orbit.  A commensurate k ≠ 0 structure
does not fit that shape in the *parent* cell: the moment is not periodic on the
parent lattice, so one nuclear orbit carries several different moments and there
is no field for the second.

The route out is the one magCIF itself takes.  A commensurate structure is
stated in its **magnetic supercell**: the child cell whose lattice is
{t : k·t ∈ ℤ}, in which the moment *is* periodic.  In that cell

* the nuclear structure is the parent's, repeated — every parent lattice
  translation that is no longer a child lattice translation carries a second
  copy of every atom, and those copies are **independent sites of the child**;
* the magnetic group's anti-translation is an **anti-centring** of the child
  cell, so the two copies carry opposite moments and no new field is needed;
* the extra reciprocal-lattice points of the child are the satellites at
  Q = H ± k, and they arrive in the phase's own reflection list rather than as
  a second frozen set — which is what lets **one** scale serve the nuclear and
  the magnetic contribution.

So this module is a *restatement*, not a new physics term.  What it must not
get wrong is the bookkeeping, and the three things that would go wrong silently
are asserted rather than argued:

1. **A parent site counted twice.**  The child atom list is built by orbit
   partition — every position in the child cell belongs to exactly one child
   orbit and each orbit contributes exactly one asymmetric atom — and the
   partition is checked to cover the whole set exactly once.
2. **The child's nuclear space group not being the symbol it is given.**  The
   parent group carried through the cell transform generally contains
   operations that no Hermann-Mauguin symbol reproduces *in the child cell*
   (a ½ translation along a doubled axis becomes ¼, which is in no standard
   operation list).  :func:`magnetic_supercell` therefore checks that the
   symbol's operations, times the child's lattice cosets, reproduce the
   transformed group exactly — and when they do not, the child phase carries
   its **own operation list** under a bracketed label
   (:func:`resolve_child_group`, ``Phase.symmetry_operations``, #448) so that
   every orbit, multiplicity and absence still comes from the operations.  It
   used to refuse there, which was right while a phase could only store a
   symbol and cost the whole S3(a,b) direction of Ba₂FeSbSe₅; the check is
   unchanged and only the answer to "no symbol" is different.  A
   ``CHILD_GROUP_UNNAMED`` info diagnostic on
   :attr:`SupercellStatement.diagnostics` says which operations the symbol got
   wrong.
3. **A superlattice reflection with nuclear intensity on it.**  A doubled cell
   holding the parent's atoms twice has |F_N|² identically zero at every
   reciprocal-lattice point the parent does not have, by the phase sum, and
   that is a *test* (``tests/test_magnetic_supercell.py``) rather than a
   comment.

**Scope.** Commensurate k with 2k in the reciprocal lattice — the same fence
WP-1326 and :func:`~.isotropy.candidates` carry — because that is where the
child lattice has index 2 and one anti-translation.  A k of higher denominator
needs a larger child cell and is not handled here; an incommensurate k has no
child cell at all.

**The anti-centring has to be tied, not only seeded.**  The two cosets of one
parent site are independent *sites* of the child, so their moment DOFs are
independent columns of the fit — and one combination of those columns is the
**ferromagnetic** mode the declared group forbids.  Seeding the pair
antiparallel (which :func:`magnetic_supercell` does, by propagating one seed
over the group's own orbit) states the candidate correctly but does not keep a
refinement inside it: nothing in the fit stops the pair drifting off
antiparallel.  :func:`anti_translation_ties` is therefore part of the statement,
not an option: it returns the affine ties for
:meth:`rietx.Refinement.tie` that spend that freedom the way the symmetry
already spends it.  They *are* affine, and the reason is structural — an
(anti)centring's axial action is ±**I** rather than a rotation, which is
exactly the case modulus-and-angles carries linearly.
:func:`anti_translation_residual` is the check that they were applied, and the
number to quote beside any moment refined from a supercell statement.

This is **not** a change to moment cardinality: it does not let one nuclear
orbit carry two independent moments, it makes two nuclear orbits carry one.
That is enough for a commensurate k with 2k ∈ L*, where the child's magnetic
asymmetric unit is the parent's; a larger child cell would need the field.

References
----------
* Perez-Mato, J. M., Gallego, S. V., Tasci, E. S., Elcoro, L., de la Flor, G. &
  Aroyo, M. I. (2015). *Annu. Rev. Mater. Res.* **45**, 217 — magnetic
  symmetry, the magnetic supercell and MAGNDATA's stored form.
* Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006).
  *J. Appl. Cryst.* **39**, 607 — parent + irrep + direction → structure, the
  workflow :func:`~.isotropy.candidates` comes from.
* Hahn, T., ed. (2005). *International Tables for Crystallography, Vol. A* —
  sect. 5.1 for the (P, p) convention this module's transforms are written in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

from ...schemas.common import Diagnostic, Parameter
from ...schemas.structure import (
    Atom,
    Cell,
    MagneticSymmetry,
    Moment,
    Phase,
)
from ..symmetry import (
    SITE_TOL,
    OperatorGroup,
    cell_constraints,
    expand_positions,
    get_spacegroup,
    resolve_group,
    unnamed_label,
)
from . import isotropy as _isotropy
from .moments import tilted_seed
from .operators import MagneticGroup, format_transform
from .scattering import check_group_is_structure_symmetry

__all__ = [
    "ChildGroup",
    "SupercellStatement",
    "anti_translation_residual",
    "anti_translation_ties",
    "child_basis",
    "lattice_cosets",
    "magnetic_supercell",
]

#: How close two fractional coordinates must be to be the same site.  The
#: nuclear side's tolerance, deliberately: the child positions are the parent's
#: pushed through an exact rational transform, so nothing here is looser than
#: what ``site_orbit`` already accepts.
CHILD_SITE_TOL = SITE_TOL


@dataclass(frozen=True)
class SupercellStatement:
    """The nuclear phase in the magnetic cell, and how it was reached.

    ``phase`` is a complete :class:`~rietx.schemas.structure.Phase`: the child
    cell, the child's nuclear space-group symbol, one atom per child orbit, the
    magnetic space group as WP-1327's operator list **in that cell** with the
    anti-translation in its centring loop, and a moment on every atom the group
    puts one on.  It compiles and refines like any other magnetic phase — the
    whole point of the restatement.

    ``site_map[i]`` is ``(parent atom index, coset index)`` for child atom
    ``i``: which parent site it came from and which parent lattice coset put it
    there.  It is what lets a report say "Co1 and Co1′ are the two halves of
    one parent orbit" rather than leaving a reader to match coordinates.
    """

    phase: Phase
    transform: str
    index: int
    parent_space_group: str
    child_space_group: str
    group: MagneticGroup
    site_map: tuple[tuple[int, int], ...]
    k: tuple[str, str, str] | None
    #: Whether a Hermann-Mauguin symbol generates the child's nuclear group in
    #: the child cell.  ``False`` means ``phase.space_group`` is the bracketed
    #: *label* and ``phase.symmetry_operations`` is the group — the case that
    #: used to be a refusal (#448, ``resolve_child_group``).  A caller
    #: reporting the child group should print the label either way and read
    #: this only when it wants to say *why* the label looks the way it does.
    child_group_named: bool = True
    #: Info diagnostics about the statement itself, ``CHILD_GROUP_UNNAMED``
    #: among them.  Empty for every statement whose child group has a symbol,
    #: so a caller that ignores the field sees exactly what it saw before.
    #: Each ``where`` is a path **relative to** :attr:`phase` (``space_group``,
    #: not ``phases.0.space_group``): the statement cannot know which index its
    #: phase will take in a structure, so a caller placing it at index ``i``
    #: prefixes ``phases.i.``.
    diagnostics: tuple[Diagnostic, ...] = ()
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def volume_ratio(self) -> int:
        """|det P| — how many parent cells the child cell holds."""
        return self.index

    def parent_reflection(self, hkl_parent) -> np.ndarray:
        """The child index of a parent reflection: h_child = Pᵀ·h_parent."""
        p = _matrix_of(self._cache.setdefault("basis", _parse_basis(self.transform)))
        return np.rint(p.T @ np.asarray(hkl_parent, dtype=np.float64)).astype(np.int64)


# ---------------------------------------------------------------------------
# the cell
# ---------------------------------------------------------------------------
def _matrix_of(basis) -> np.ndarray:
    return np.array([[float(v) for v in row] for row in basis], dtype=np.float64)


def _parse_basis(transform: str):
    from .operators import parse_transform

    p, _shift = parse_transform(transform)
    return p


def child_basis(space_group, k) -> tuple[tuple[Fraction, ...], ...]:
    """P for the magnetic cell of ``k``, **without** the shortest-basis reduction.

    :func:`~.isotropy.magnetic_cell` reduces the basis so that spglib can
    identify a magnetic group in a cell no tabulated setting looks like — the
    right choice there, because nothing in :func:`~.isotropy.candidates` needs
    the cell to be *conventional*.  Here it is the wrong one: a reduced
    hexagonal supercell comes out with γ = 60°, and the nuclear operations of a
    hexagonal Hermann-Mauguin symbol are written for γ = 120°.  A phase whose
    ``space_group`` symbol does not generate its own operations is the silent
    failure this module exists to avoid.

    So the basis is the unreduced one: the parent's primitive basis with the
    one vector that carries ε = −1 doubled, and every other ε = −1 vector
    shifted by it.  For a primitive parent that is the obvious doubling of one
    axis; for a centred one it is a primitive cell of the magnetic lattice, and
    the caller is told so by the symbol check in :func:`magnetic_supercell`.

    When two or more primitive vectors carry ε = −1 (a k = (½,½,0)-type
    doubling) the recipe names one of them as the doubled pivot; the same
    lattice has other primitive bases, and in some of them a mm2/4mm child is
    conventional where here it is not.  This rung does not choose between
    them: the pivot is the first ε = −1 vector, and a child whose group then
    has no expressible metric is refused by :func:`magnetic_supercell` with
    :func:`_unnamed_child`'s full text rather than restated in a cell picked
    for it.
    """
    sg = _isotropy._irreps._resolve(space_group)
    kk = _isotropy.as_kvector(k)
    # the scope fence, and the coset list, are magnetic_cell's — asked rather
    # than re-derived, so there is one authority on what k this rung admits
    cell = _isotropy.magnetic_cell(sg, kk)
    if not cell.doubled:
        return cell.basis
    prim = _isotropy._irreps.primitive_basis(sg)
    signs = [_isotropy._translation_sign(kk, row) for row in prim]
    anti_indices = [i for i, s in enumerate(signs) if s < 0]
    pivot = anti_indices[0]
    anti = prim[pivot]
    rows: list[tuple[Fraction, ...]] = []
    for i, row in enumerate(prim):
        if i == pivot:
            rows.append(tuple(2 * Fraction(c) for c in row))
        elif signs[i] < 0:
            rows.append(tuple(Fraction(c) + Fraction(a) for c, a in zip(row, anti)))
        else:
            rows.append(tuple(Fraction(c) for c in row))
    return _rows_to_columns(rows)


def _rows_to_columns(rows) -> tuple[tuple[Fraction, ...], ...]:
    """Three basis-vector rows as the (P, p)-convention matrix (columns)."""
    return tuple(tuple(rows[j][i] for j in range(3)) for i in range(3))


def _transform_string(basis) -> str:
    return format_transform([list(row) for row in basis],
                            (Fraction(0), Fraction(0), Fraction(0)))


def _child_lattice(parent_cell, basis) -> np.ndarray:
    """The child cell's lattice vectors as **rows**, in Å.

    ``adp.cartesian_basis`` returns the direct lattice vectors as *columns* of
    M with MᵀM = G, so the row-vector matrix is Mᵀ; (a′,b′,c′) = (a,b,c)·P then
    makes the child's row matrix Pᵀ·Mᵀ.  Getting that transpose wrong produces
    a cell with the right volume and the wrong angles, which is exactly the
    kind of error a volume check does not catch — so the cell parameters below
    come from the **metric** instead, and this function exists only for
    spglib, which wants a lattice and not a metric.
    """
    from ..adp import cartesian_basis

    rows = np.asarray(cartesian_basis(*parent_cell), dtype=np.float64).T
    return _matrix_of(basis).T @ rows


def _child_cell_parameters(parent_cell, basis) -> tuple[float, ...]:
    """(a, b, c, α, β, γ) of the child cell, from the parent's metric and P.

    G′ = Pᵀ·G·P exactly — no Cartesian frame, no Cholesky, so a right angle
    stays a right angle to the last bit.  The *cosine* is then snapped onto the
    exact values a lattice symmetry can force (0, ±½): a hexagonal γ comes out
    of ``arccos(-0.5000000000000001)`` as 119.999999999999986, and a cell whose
    γ is not 120 is a cell whose space-group constraint the refinement has to
    re-impose.  The snap is at 1e-12 on the cosine, far below any physical
    departure and far above the rounding it removes.
    """
    from ..adp import direct_metric_tensor

    p = _matrix_of(basis)
    g = p.T @ np.asarray(direct_metric_tensor(*parent_cell),
                         dtype=np.float64) @ p
    lengths = np.sqrt(np.diag(g))
    angles = []
    for i, j in ((1, 2), (0, 2), (0, 1)):
        cosine = float(g[i, j] / (lengths[i] * lengths[j]))
        for exact in (0.0, 0.5, -0.5):
            if abs(cosine - exact) <= 1e-12:
                cosine = exact
                break
        angles.append(float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))))
    return (float(lengths[0]), float(lengths[1]), float(lengths[2]), *angles)


# ---------------------------------------------------------------------------
# the group
# ---------------------------------------------------------------------------
def _nuclear_operations(group: MagneticGroup) -> set[tuple]:
    """The group's operations with the time-reversal sign dropped.

    A magnetic operation {R | t, ε} moves the *nucleus* by {R | t} whatever ε
    is, so this is the nuclear space group of the child structure — including
    the anti-translation, which as a nuclear operation is an ordinary lattice
    translation and is a symmetry of the nuclear structure.
    """
    return {(tuple(map(tuple, op.rotation)),
             tuple(Fraction(v) % 1 for v in op.translation))
            for op in group.all_operations()}


def _nuclear_group_of(space_group, symmetry_operations=None) -> MagneticGroup:
    """A space group as a **colourless** :class:`MagneticGroup`, ε = +1 throughout.

    Not a grey group: 1' is not in it, so it is the nuclear group and nothing
    more.  It exists only to be handed to ``MagneticGroup.transformed``, whose
    lattice completion is what supplies the child cell's extra translation —
    that method is the one piece of operator algebra in the package that knows
    how to enlarge a cell, and writing a second one here for the nuclear case
    would be the drift this module's docstring is written against.

    ``symmetry_operations`` is a phase's own explicit operator list
    (``Phase.symmetry_operations``), for the case ``space_group`` is a
    bracketed, unnamed label: :func:`~..symmetry.resolve_group`
    reads the operators directly rather than resolving the label through
    gemmi, exactly as every other consumer of a phase's own group already
    does.  ``None`` (every call before this parameter existed) is bit-
    identical to the old ``get_spacegroup(symbol)`` path.
    """
    from .operators import MagneticOperator

    sg = resolve_group(space_group, symmetry_operations)
    operations = []
    for op in sg.operations():
        rot = [[int(round(v / op.DEN)) for v in row] for row in op.rot]
        tran = [Fraction(int(v), op.DEN) for v in op.tran]
        operations.append(MagneticOperator.build(rot, tran, 1))
    return MagneticGroup.from_operations(operations, setting=str(space_group))


def _settings_of(symbol: str) -> tuple[str, ...]:
    """Every tabulated setting of the space-group *type* ``symbol`` names.

    The identified symbol first, then its axis-permutation and origin-choice
    siblings in table order, so a group that is expressible in exactly one of
    them is found and one that is expressible in none is refused with the count.
    """
    import gemmi

    try:
        number = get_spacegroup(symbol).number
    except (ValueError, RuntimeError):
        return (symbol,)
    out = [get_spacegroup(symbol).xhm()]
    for sg in gemmi.spacegroup_table():
        if sg.number == number and sg.xhm() not in out:
            out.append(sg.xhm())
    return tuple(out)


def _colourless(group: MagneticGroup) -> MagneticGroup:
    """The magnetic group with every time-reversal sign set to +1.

    The nuclear part of a magnetic space group: {R | t} for every {R | t, ε} in
    it.  Used by ``nuclear_group="magnetic"`` — see
    :func:`magnetic_supercell` for when that is the only correct choice.
    """
    from .operators import MagneticOperator

    return MagneticGroup.from_operations([
        MagneticOperator.build([[int(v) for v in row] for row in op.rotation],
                               list(op.translation), 1)
        for op in group.all_operations()], setting=group.setting)


def _symbol_operations(symbol: str) -> set[tuple]:
    """The operations a Hermann-Mauguin symbol generates, as exact rationals."""
    sg = get_spacegroup(symbol)
    out = set()
    for op in sg.operations():
        rot = tuple(tuple(int(round(v / op.DEN)) for v in row) for row in op.rot)
        tran = tuple(Fraction(int(v), op.DEN) % 1 for v in op.tran)
        out.add((rot, tran))
    return out


def _identify_child_space_group(group: MagneticGroup, lattice) -> str | None:
    """spglib's identification of the child's **nuclear** group, or ``None``.

    The magnetic identification is :func:`~.operators.identify`'s and lives on
    the group; what is wanted
    here is the plain space-group type of the same operation list with ε
    dropped, because that is the symbol :class:`Phase` stores and the symbol
    ``generate_reflections`` resolves.
    """
    import spglib

    ops = sorted(_nuclear_operations(group))
    rotations = np.array([o[0] for o in ops], dtype="intc")
    translations = np.array([[float(v) for v in o[1]] for o in ops],
                            dtype="double")
    try:
        found = spglib.get_spacegroup_type_from_symmetry(
            rotations, translations, lattice=np.asarray(lattice, dtype="double"))
    except Exception:                       # pragma: no cover - spglib refusal
        return None
    if not found:
        return None
    symbol = found.get("international_short") or found.get("international")
    if not symbol:
        return None
    # spglib writes screw axes with an underscore (``P2_1/m``, ``P4_2/mnm``);
    # rietx's resolver and gemmi's table spell them without one (``P21/m``).
    # Pnma at k = (1/2, 0, 1/2) is the case: the child comes back as 'P2_1/m'
    # and every candidate is a P 1 21/m 1 supercell
    # (tests/test_magnetic_supercell.py::
    # test_pnma_half_zero_half_states_in_the_magnetic_nuclear_group).
    return str(symbol).replace("_", "")


def _cosets(group: MagneticGroup, symbol: str) -> tuple[tuple[Fraction, ...], ...]:
    """The pure translations of the child group that the symbol does not carry."""
    symbol_ops = _symbol_operations(symbol)
    identity = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))
    out = []
    for rot, tran in sorted(_nuclear_operations(group)):
        if rot == identity and (rot, tran) not in symbol_ops:
            out.append(tran)
    return tuple(out)


@dataclass(frozen=True)
class ChildGroup:
    """The child cell's nuclear group, named or not.

    ``named`` is what a caller branches on.  When it is true, ``symbol`` is the
    Hermann-Mauguin symbol whose operations times ``cosets`` **are** the child
    group — the old contract, unchanged — and ``operations`` is ``None``, so
    the phase built from it is byte-identical to what this module built before.
    When it is false there is no such symbol (see
    :func:`resolve_child_group`), ``symbol`` is the closest standard *type*,
    ``label`` is the bracketed form that goes in
    :attr:`~rietx.schemas.structure.Phase.space_group`, ``operations`` is the
    child group's own ``x,y,z`` list — the phase's symmetry from then on — and
    ``reason`` is the diagnostic text saying which operations the symbol got
    wrong.

    ``label`` is the string to store either way, so a caller need not branch to
    build the phase.
    """

    named: bool
    symbol: str
    label: str
    cosets: tuple
    operations: tuple[str, ...] | None
    reason: str

    @property
    def group(self):
        """The group object every symmetry consumer should read."""
        from ..symmetry import resolve_group

        return resolve_group(self.label, self.operations)


def _child_triplets(group: MagneticGroup) -> tuple[str, ...]:
    """The child's **nuclear** operations as ``x,y,z`` triplets, deterministic.

    Sorted on the exact (rotation, translation) key, because the list is stored
    on a phase and serialized: two runs of the same statement must give the
    same document, and ``set`` iteration order would not.
    """
    import gemmi

    out = []
    for rot, tran in sorted(_nuclear_operations(group)):
        op = gemmi.Op("x,y,z")
        op.rot = [[int(v) * gemmi.Op.DEN for v in row] for row in rot]
        op.tran = [int(round(float(v) * gemmi.Op.DEN)) for v in tran]
        out.append(op.triplet())
    return tuple(out)


def _unnamed_child(group: MagneticGroup, head: str, transform: str,
                   detail: str) -> ChildGroup:
    """A :class:`ChildGroup` stated as its operation list — or the old refusal.

    **One thing an operation list cannot supply by itself: the cell metric
    constraints.**  A phase cannot even build a ``ParameterTable`` without
    them — ``symmetry.cell_constraints`` needs a crystal system, a monoclinic
    unique axis and the ``R``-axes flag — and for an operation list they come
    from the tabulated group sharing the list's point group and lattice
    (:attr:`~rietx.crystallography.symmetry.OperatorGroup.closest_type`).
    That orientation lookup fails for a child cell whose axes are not
    conventional for its own point group (a c- or n-glide group doubled along
    the glide's own translation), and there this function
    still refuses: deriving the constraints straight from the rotation set is
    the distortion-mode track's (WP-1419), not this rung's.  Refusing there is
    the right call on this tree: building the phase anyway would move the
    failure from this function to the first compile, where the message would
    be about a crystal system rather than about a cell transform.
    """
    triplets = _child_triplets(group)
    label = unnamed_label(head, f"unnamed in {transform.split(';')[0]}")
    probe = OperatorGroup(label=label, xyz=triplets)
    try:
        closest = probe.closest_type.xhm()
        cell_constraints(probe)
    except ValueError as exc:
        raise ValueError(
            f"magnetic_supercell(): the child cell {transform!r} carries the "
            f"parent's space group to an operation list that no "
            f"Hermann-Mauguin symbol reproduces in that cell — {detail}. "
            f"That happens when a parent operation's translation along the "
            f"doubled axis is a half, which becomes a quarter in the child "
            f"cell and appears in no standard operation list. A phase can "
            f"carry its own operation list (Phase.symmetry_operations) for "
            f"exactly this case, and that is what this function does "
            f"whenever it can — but not here: the list's own point group "
            f"and lattice name no tabulated group in this orientation "
            f"({exc}), so this cell's metric constraints are undefined and a "
            f"phase built on it would get the wrong site orbits and the wrong "
            f"systematic absences from a cell nothing constrains. State this "
            f"structure in the magnetic group's nuclear part "
            f"(nuclear_group='magnetic'), or restate it by hand in a cell "
            f"whose axes are conventional for the child point group."
        ) from exc
    constraint_source = (f"the closest standard type by point group and "
                         f"lattice ({closest!r})")
    return ChildGroup(
        named=False, symbol=head, label=label,
        cosets=((Fraction(0), Fraction(0), Fraction(0)),
                *_cosets_of_the_operation_list(group)),
        operations=triplets,
        reason=(
            f"{detail}. That happens when a parent operation's translation "
            f"along the doubled axis is a half, which becomes a quarter in the "
            f"child cell and appears in no standard operation list. The child "
            f"phase therefore carries its own {len(triplets)} symmetry "
            f"operations ({', '.join(triplets)}) and its space_group is the "
            f"label {label!r} — the site orbits, the site multiplicities and "
            f"the systematic absences all come from the operation list, and "
            f"the cell's metric constraints from {constraint_source}, so "
            f"nothing is guessed from the label. What is *not* available for "
            f"such a group is a Wyckoff letter and a setting-comparison "
            f"warning, both of which are properties of a tabulated setting"))


def resolve_child_group(group: MagneticGroup, symbol: str | None,
                        transform: str) -> ChildGroup:
    """The child's nuclear group as a symbol if one generates it, else as a list.

    **What this used to do, and why it changed.**  A parent operation carrying
    a ½ translation along the doubled axis becomes a ¼ in the child cell, and ¼
    appears in no standard operation list — so for such a parent there is *no*
    Hermann-Mauguin symbol that generates the child's nuclear group in the
    child's cell.  Until the operation-list phase (#448) a ``Phase`` could only
    store a symbol, so the
    only honest answer was a refusal: a phase whose symbol does not generate
    its own operations gets the wrong site orbits and the wrong systematic
    absences, and a fit on it converges anyway.  That refusal cost real work —
    Ba₂FeSbSe₅'s S3(a,b) direction could not be stated at all
    (``tests/test_operator_list_phase.py`` now builds it).

    A phase can now carry its own operation list
    (``Phase.symmetry_operations``), so the answer is the list plus a label
    that says the symbol is only the closest type.  Nothing is loosened: the
    check is the same set comparison it always was, and the *named* branch
    returns exactly what it returned before.  What changes is the unnamed
    branch, which now states the group instead of refusing to.
    """
    nuclear = _nuclear_operations(group)
    tried: list[str] = []
    detail = ""
    if symbol is None:
        # spglib named no type at all, which is the same fact one step earlier:
        # the setting is not one its tables recognise.  The label's leading
        # half is then whatever the operation list's own point group and
        # lattice are, which is what ``_unnamed_child`` looks up anyway.
        probe = OperatorGroup(label="", xyz=_child_triplets(group))
        try:
            head = probe.closest_type.xhm()
        except ValueError:
            head = ""
        return _unnamed_child(
            group, head, transform,
            "spglib identifies no nuclear space-group *type* for this "
            "operation list at all, so the setting is not one its tables "
            "recognise")
    # **Every setting of the identified type, not only its standard one.**
    # spglib identifies a *type*; which of its axis settings the child cell is
    # in is a separate fact, and the child cell's axes are whatever the
    # transform made them.  Mn₃O₄'s child group comes back as ``Pbcn`` (#60)
    # and the cell is in the ``bca`` setting, where the symbol is **Pbna** —
    # which is the symbol the GSAS-II tutorial names in prose.  Refusing on the
    # standard setting alone would refuse a statement that is perfectly
    # expressible one qualifier over.
    for resolved in _settings_of(symbol):
        tried.append(resolved)
        try:
            symbol_ops = _symbol_operations(resolved)
        except (ValueError, RuntimeError):
            continue
        cosets = ((Fraction(0), Fraction(0), Fraction(0)),
                  *_cosets(group, resolved))
        built = {(rot, tuple((t + c) % 1 for t, c in zip(tran, coset)))
                 for rot, tran in symbol_ops for coset in cosets}
        if built == nuclear:
            return ChildGroup(named=True, symbol=resolved, label=resolved,
                              cosets=cosets, operations=None, reason="")
        missing, extra = sorted(nuclear - built), sorted(built - nuclear)
        detail = (
            f"and none of its {len(tried)} setting(s) reproduces it — {resolved!r} "
            f"times the {len(cosets)} lattice coset(s) of this cell "
            f"{'omits ' + str(len(missing)) + ' of its operations' if missing else ''}"
            f"{' and ' if missing and extra else ''}"
            f"{'adds ' + str(len(extra)) + ' it does not have' if extra else ''}")
    if not detail:
        detail = (f"and rietx cannot resolve any setting of {symbol!r} to an "
                  f"operation list, which is the same fact one step earlier")
    return _unnamed_child(
        group, symbol, transform,
        f"spglib identifies the child's nuclear group as {symbol!r}, {detail}")


def _cosets_of_the_operation_list(group: MagneticGroup
                                  ) -> tuple[tuple[Fraction, ...], ...]:
    """The pure translations of the child group, for an unnamed one.

    The named branch takes these relative to the symbol's own operations
    (:func:`_cosets`); with no symbol there is nothing to subtract, so every
    pure translation but the identity is a coset representative.  Used only to
    fill :attr:`ChildGroup.cosets`, which callers read for its *length* — the
    number of parent cells the child holds under this group.
    """
    identity = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))
    zero = (Fraction(0), Fraction(0), Fraction(0))
    return tuple(tran for rot, tran in sorted(_nuclear_operations(group))
                 if rot == identity and tuple(tran) != zero)


def _sign_consistent_operations(cand, m_matrix, ops, *, tol: float = 1e-6
                                ) -> set[tuple]:
    r"""The subset of ``ops`` that is a symmetry of ``cand``'s own **signed**
    field, not only of its positions.

    ``_colourless`` drops which copy of a grey operation {R | t, ±1} a
    candidate's own isotropy subgroup actually carries, and every consumer of
    the *declared* nuclear group downstream — chiefly
    ``crystallography.structure_factor.py``'s ``select_orbit_ops``/
    ``_orbit_terms``, called through ``expand_positions`` — propagates a
    representative's mode vector to its orbit siblings by the bare rotation,
    which is only correct for the ε = +1 copy. For a candidate whose
    order-parameter direction is 1-dimensional (or whose components never
    split) that loss is harmless: every operation of the colourless group
    that moves a listed position at all turns out to carry the same, single
    character on every component.  Where it does not — an operation carrying
    ε = +1 on some free amplitudes and ε = −1 on others, as the child
    lattice's anti-translation and its products do for a displacive k ≠ 0
    mode — a single scalar ε cannot state it, and dropping the operation
    (rather than keeping it with a wrong assumed sign) is the only choice
    available to a group whose operators carry one ε each.  On the generic
    Pnma fixture of ``tests/test_operator_list_phase.py`` at k = (½, 0, ½)
    S3(a,b)'s group (built with the coset character ε(Δ), so it holds no
    ε = −1 pure translation) is the order-4 ``{x,y,z; x,-y+1/2,z;
    -x+1/2,y+1/2,-z; -x+1/2,-y,-z}``, all four of which this keeps;
    ``test_the_ba2fesbse5_s3ab_child_is_built_instead_of_refused`` pins it.

    ``cand`` is one of :mod:`.isotropy`'s ``MagneticCandidate`` objects
    (``kind="displacive"`` or ``"magnetic"`` — the test is the same shape for
    either; the axial-vs-polar distinction is already baked into
    ``cand.configurations`` by :func:`~.isotropy.order_parameter_space`, so
    this function never itself decides which action a component takes).
    ``m_matrix`` carries ``cand.positions``/``cand.configurations`` from the
    candidate's own cell into the cell ``ops`` is expressed in; one matrix
    carries both, because a mode vector is contravariant.

    An operation with no free amplitude to check (``cand.configurations`` has
    zero rows — an undistorted parent, or a direction with no free
    amplitude) is vacuously kept.  An operation whose image matches no listed
    position at all is dropped rather than kept, since an operation this rung
    cannot verify is not one it should trust.

    The identity is always kept, and the result always contains it, so
    :func:`~.operators.MagneticGroup.from_operations` never sees an empty
    list.  The result is a group (a product of two sign-consistent operations
    propagates ``cand``'s own field correctly twice in a row, hence once), and
    ``from_operations`` is the check that would catch it not being one — it
    raises on a set that does not close — so this function does not re-derive
    closure itself.
    """
    identity = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))
    if cand.configurations.shape[0] == 0:
        return set(ops)
    moved = np.asarray([m_matrix @ q for q in cand.positions], dtype=np.float64) % 1.0
    configs = np.asarray([[m_matrix @ v for v in row] for row in cand.configurations],
                        dtype=np.float64)
    kept: set[tuple] = set()
    for rot, tran in ops:
        if rot == identity and all(Fraction(v) == 0 for v in tran):
            kept.add((rot, tran))
            continue
        rmat = np.asarray(rot, dtype=np.float64)
        tvec = np.asarray([float(v) for v in tran], dtype=np.float64)
        ok = True
        for m in range(moved.shape[0]):
            image = (rmat @ moved[m] + tvec) % 1.0
            hits = [mm for mm in range(moved.shape[0])
                   if _same_site(moved[mm], image, tol=max(tol, CHILD_SITE_TOL))]
            if not hits:
                ok = False
                break
            target = configs[:, hits[0], :]
            predicted = np.einsum("ij,fj->fi", rmat, configs[:, m, :])
            if not np.allclose(predicted, target, atol=tol):
                ok = False
                break
        if ok:
            kept.add((rot, tran))
    return kept


def _group_from_nuclear_ops(ops) -> MagneticGroup:
    """A colourless :class:`MagneticGroup` from a set of nuclear (rot, tran) pairs.

    Every operation gets ε = +1: the input is a nuclear set, and
    :func:`magnetic_supercell` uses the result only as the child's nuclear
    group.
    """
    from .operators import MagneticOperator

    operators = [MagneticOperator.build(
        [[int(v) for v in row] for row in rot], list(tran), 1)
        for rot, tran in ops]
    return MagneticGroup.from_operations(operators)


# ---------------------------------------------------------------------------
# the atoms
# ---------------------------------------------------------------------------
def lattice_cosets(basis) -> tuple[tuple[int, int, int], ...]:
    """The integer lattice modulo the child lattice: |det P| coset representatives.

    **ℤ³/L_child, not L/L_child**, and the distinction is the difference between
    the right atom count and twice it for a centred parent.
    :func:`~rietx.crystallography.symmetry.expand_positions` returns a site's
    orbit in the *conventional* cell — the centring images already listed among
    them, because gemmi's operation list carries the centring — so what is left
    to add is the conventional cell's own translations modulo the child lattice,
    and there are exactly |det P| of those.  Adding L/L_child on top of an orbit
    that already contains the centring image counts every atom of a centred
    parent twice, and the child cell's volume ratio is the arithmetic that says
    so.

    Enumerated by class rather than by a fundamental-domain test, so a transform
    with negative entries — which is what a database setting routinely gives,
    to keep a frame right-handed — is handled without a sign convention.
    """
    inverse = _isotropy._fraction_inverse(basis)
    want = int(round(abs(np.linalg.det(_matrix_of(basis)))))
    seen: dict[tuple[int, ...], tuple[int, int, int]] = {}
    span = 1
    while len(seen) < want and span <= 8:
        # shortest first, and (0,0,0) first of all, so the identity coset is
        # always the representative of its own class and the list is the same
        # on two runs of the same stage
        box = [tuple(int(v) - span for v in n)
               for n in np.ndindex(2 * span + 1, 2 * span + 1, 2 * span + 1)]
        for vector in sorted(box, key=lambda v: (sum(c * c for c in v), v)):
            key = tuple(int(round(v * 720)) % 720
                        for v in (inverse @ np.array(vector, dtype=np.float64)) % 1.0)
            seen.setdefault(key, vector)
            if len(seen) == want:
                break
        span += 1
    if len(seen) != want:                    # pragma: no cover - |det P| <= 8^3
        raise ValueError(
            f"lattice_supercell(): found {len(seen)} integer lattice cosets of "
            f"the child lattice where |det P| = {want} demands that many")
    return tuple(seen.values())


def _child_positions(parent_phase, basis, shift, cosets):
    """Every atom of the child cell: ``(parent index, coset index, position)``.

    ``x_child = P⁻¹·(x_parent + n − p)`` with ``n`` a coset of ℤ³/L_child and
    ``p`` the origin shift of the transform.
    """
    from ..symmetry import resolve_group

    sg = resolve_group(parent_phase.space_group,
                       parent_phase.symmetry_operations)
    inverse = _isotropy._fraction_inverse(basis)
    origin = np.array([float(v) for v in shift], dtype=np.float64)
    out = []
    for j, atom in enumerate(parent_phase.atoms):
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value],
                       dtype=np.float64)
        for image in expand_positions(sg, xyz):
            for c, coset in enumerate(cosets):
                moved = inverse @ (image + np.array(coset, dtype=np.float64)
                                   - origin)
                out.append((j, c, moved % 1.0))
    return out


def _same_site(a, b, tol: float = CHILD_SITE_TOL) -> bool:
    # both wrapped: min(d, 1 - d) is negative for d > 1, which "matches"
    # anything, and a stated coordinate (x = -0.1) beside an image already
    # wrapped into [0, 1) (0.95) is exactly that
    d = np.abs(np.asarray(a) % 1.0 - np.asarray(b) % 1.0)
    return bool(np.all(np.minimum(d, 1.0 - d) <= tol))


def _partition_into_child_orbits(symbol, entries):
    """One representative per child orbit, with the entries it covers.

    Every position of the child cell must land in exactly one orbit: a position
    covered twice is a site counted twice in |F_N|², and one covered not at all
    is an atom missing from it.  Both are checked, because both are silent.

    ``symbol`` is a Hermann-Mauguin symbol or a group object — for an unnamed
    child (:class:`ChildGroup`) the partition has to run over the *operation
    list*, since the label generates nothing.  Running it over the symbol
    instead is exactly the error the old refusal existed to prevent: the child
    would get the symbol's orbits, which are a different partition of the same
    positions.
    """
    from ..symmetry import as_group

    sg = as_group(symbol)
    assigned = [False] * len(entries)
    groups: list[tuple[int, list[int]]] = []
    for i, (_j, _c, position) in enumerate(entries):
        if assigned[i]:
            continue
        orbit = expand_positions(sg, position)
        members = [n for n, (_pj, _pc, q) in enumerate(entries)
                   if any(_same_site(q, p) for p in orbit)]
        for n in members:
            if assigned[n]:
                raise ValueError(
                    f"magnetic_supercell(): the child position "
                    f"{np.array2string(entries[n][2], precision=5)} is in two "
                    f"orbits of {sg.xhm()!r}; the supercell atom list would count "
                    f"that site twice in |F_N|^2. This is a bug in the orbit "
                    f"partition, not a tolerance to widen")
            assigned[n] = True
        if len({entries[n][0] for n in members}) != 1:
            raise ValueError(
                f"magnetic_supercell(): one orbit of {sg.xhm()!r} in the child "
                f"cell joins atoms from more than one parent site "
                f"({sorted({entries[n][0] for n in members})}); the parent "
                f"structure's own symmetry is not a subgroup of the child's, "
                f"which means the cell transform is wrong")
        if len(members) != len(orbit):
            raise ValueError(
                f"magnetic_supercell(): the orbit of "
                f"{np.array2string(position, precision=5)} under {sg.xhm()!r} has "
                f"{len(orbit)} members but only {len(members)} of them are in "
                f"the child position list; the child cell does not hold a whole "
                f"orbit and |F_N|^2 would be short")
        groups.append((i, members))
    if not all(assigned):
        raise ValueError(
            "magnetic_supercell(): the orbit partition left "
            f"{assigned.count(False)} child positions unassigned")
    return groups


# ---------------------------------------------------------------------------
# the moments
# ---------------------------------------------------------------------------
def _seed_moments(group: MagneticGroup, positions, ions, magnitude: float,
                  cell):
    """A moment on every site the group allows one on, consistent by construction.

    One seed per **magnetic** orbit — the orbit of the group itself, which for
    a type IV group joins a site to its anti-translation image — propagated by
    ``MagneticGroup.site_orbit``.  So the antiparallel pattern the anti-centring
    demands is the *stated* structure rather than something a fit has to find,
    and ``Phase._moments_are_stateable`` accepts it for the same reason.

    The seed itself is :func:`~rietx.crystallography.magnetic.moments.
    tilted_seed` (WP-1418 stage (b)) rather than the whole magnitude on the
    allowed basis's first row alone: a rank ≥ 2 basis (a multi-copy irrep or a
    general/kernel direction) used to leave every other DOF starting at a
    stationary point of χ², the same shape ``Stage.distortion_seed`` exists
    to fix for a whole amplitude vector at A = 0 — see that function's
    docstring.

    cell is the **child** cell, and it is not optional: crystal-axis
    components are on unit vectors along the cell axes, so their modulus is
    √(mᵀ·G·m) with G the unit metric of *that* cell, and tilted_seed
    normalises in the metric it is handed.  In a unit cubic stand-in an oblique
    child got a seed of the wrong modulus (2.324 μ_B for magnitude=3 on a
    hexagonal child), and a rank ≥ 2 frame that is orthonormal in the wrong
    metric.  In the right one the frame is metric-orthonormal, so the tilt is
    geometric: the seed leaves row 0 at tan θ = SEED_TILT·√(rank − 1).
    """
    seeded: dict[int, np.ndarray] = {}
    for i, position in enumerate(positions):
        if i in seeded or ions[i] is None:
            continue
        basis = group.allowed_moment_basis(position)
        if len(basis) == 0:
            seeded[i] = np.zeros(3)
            continue
        seed = tilted_seed(basis, cell, magnitude)
        images, moments = group.site_orbit(position, seed)
        for image, moment in zip(images, moments):
            for n, q in enumerate(positions):
                if ions[n] is not None and n not in seeded and _same_site(q, image):
                    seeded[n] = np.asarray(moment, dtype=np.float64)
    return seeded


def anti_translation_residual(phase) -> float:
    """max |m(x) − ε·det(R)·R·m(x′)| over every operation of the phase's own group.

    A supercell statement puts the two cosets of a parent site on **independent**
    moment DOFs (module docstring, "The anti-centring has to be tied"), so a
    refinement can leave the magnetic space group it declares.  This is the
    distance it has travelled, in μ_B, and a report that quotes a refined moment
    from a supercell statement should quote this beside it: zero means the
    refined structure still has the symmetry it claims.

    The law tested is the axial-vector one, M(R·r + t) = ε·det(R)·R·M(r):
    Gallego, Tasci, de la Flor, Perez-Mato & Aroyo (2012), *J. Appl. Cryst.*
    **45**, 1236 (MAGNEXT), eq. (3), p. 1239.
    """
    group = phase.magnetic_symmetry.group()
    sites = [(np.array([a.x.value, a.y.value, a.z.value], dtype=np.float64),
              np.array(a.moment.values(), dtype=np.float64))
             for a in phase.atoms if a.moment is not None]
    worst = 0.0
    for position, moment in sites:
        for op in group.all_operations():
            image = op.act_on_site(position)
            carried = op.act_on_moment(moment)
            for q, m in sites:
                if _same_site(q, image):
                    worst = max(worst, float(np.max(np.abs(m - carried))))
    return worst


def anti_translation_ties(phase, ip: int = 0):
    """The affine ties that make the anti-centring a *constraint*, not a seed.

    Returns ``[(target_path, source_path, scale, offset)]`` for
    :meth:`rietx.Refinement.tie` (WP-1070).  Applying them removes exactly the
    freedom the magnetic space group already spends: without them a supercell
    statement carries two independent moment columns per parent site, one of
    which is a **ferromagnetic** mode the declared group forbids, and the fit
    will happily spend it.

    The relation is affine in the DOFs, and it is affine because the operation
    is a pure translation.  An (anti)centring is {1 | t, ε}, so its axial action
    is ε·det(I)·I = ±**I** — not a rotation — by the axial-vector law
    M(R·r + t) = ε·det(R)·R·M(r) of Gallego, Tasci, de la Flor, Perez-Mato &
    Aroyo (2012), *J. Appl. Cryst.* **45**, 1236 (MAGNEXT), eq. (3), p. 1239;
    and ±I is exactly the case the modulus-and-angles parameterisation carries
    linearly:

    ==== ================================================================
    dim  m′ = −m in DOFs
    ==== ================================================================
    1    μ′ = −μ                       (μ is signed for a line)
    2    μ′ = μ, φ′ = φ + π
    3    μ′ = μ, θ′ = π − θ, φ′ = φ + π
    ==== ================================================================

    and ε = +1 gives the identity in every dimension.  A pair related by a
    *rotational* operation is **not** emitted: those atoms are in one nuclear
    orbit already and WP-1327 propagates them through ``mom_mat``, so a tie
    there would be a second, weaker copy of a constraint the forward model
    already applies exactly.

    Ties are chained no deeper than one step — each image follows the first
    atom of its (anti)centring coset — because ``Refinement.tie`` refuses a
    tied source by name, and rightly.
    """
    group = phase.magnetic_symmetry.group()
    magnetic = [(j, a) for j, a in enumerate(phase.atoms) if a.moment is not None]
    positions = {j: np.array([a.x.value, a.y.value, a.z.value], dtype=np.float64)
                 for j, a in magnetic}
    dims = {j: len(group.allowed_moment_basis(positions[j])) for j, _a in magnetic}
    out: list[tuple[str, str, float, float]] = []
    tied: set[int] = set()
    for op in group.centerings:
        if not op.is_translation:                      # pragma: no cover - schema
            continue
        for j, _atom in magnetic:
            if j in tied:
                continue
            image = op.act_on_site(positions[j])
            if _same_site(image, positions[j]):
                continue
            target = next((n for n, _a in magnetic
                           if n not in tied and n != j
                           and _same_site(positions[n], image)), None)
            if target is None:
                continue
            n_dof = dims[j]
            if dims[target] != n_dof:                  # pragma: no cover - symmetry
                continue
            base = f"phases.{ip}.atoms.{target}.moment.dof"
            src = f"phases.{ip}.atoms.{j}.moment.dof"
            sign = float(op.time_reversal)
            if n_dof == 1:
                out.append((f"{base}0", f"{src}0", sign, 0.0))
            elif sign > 0:
                out.extend((f"{base}{k}", f"{src}{k}", 1.0, 0.0)
                           for k in range(n_dof))
            elif n_dof == 2:
                out.append((f"{base}0", f"{src}0", 1.0, 0.0))
                out.append((f"{base}1", f"{src}1", 1.0, float(np.pi)))
            else:
                out.append((f"{base}0", f"{src}0", 1.0, 0.0))
                out.append((f"{base}1", f"{src}1", -1.0, float(np.pi)))
                out.append((f"{base}2", f"{src}2", 1.0, float(np.pi)))
            tied.add(target)
    return out


def _refuse_a_contradicting_bns_number(group: MagneticGroup,
                                       bns_number: str | None) -> None:
    """Raise where a stated ``bns_number`` is not the group's own (#605).

    A BNS number labels a group's type, the same in every setting, so the
    child-cell operator list must identify as it.  The number is otherwise
    stored on the phase unchecked and re-exported beside operators that
    contradict it.  A group spglib cannot name in this cell is not checked.
    """
    if bns_number is None:
        return
    from .operators import identification

    found = identification(group).group_id
    if found is not None and found.bns_number != str(bns_number):
        raise ValueError(
            f"magnetic_supercell: bns_number {bns_number!r} is not the group "
            f"this statement carries, whose operators identify as BNS "
            f"{found.bns_number} (UNI {found.uni_number}). The operators are "
            f"what is refined and the number is their label, so a phase "
            f"carrying both would contradict itself; pass the matching "
            f"number, or none.")


# ---------------------------------------------------------------------------
# the statement
# ---------------------------------------------------------------------------
def magnetic_supercell(parent: Phase, candidate=None, *, group=None,
                       transform: str | None = None, k=None,
                       bns_number: str | None = None,
                       nuclear_group: str = "parent", magnetic_species=None,
                       ion: str | dict[str, str] | None = None,
                       g: float | dict[str, float] | None = None,
                       magnitude: float = 1.0,
                       vary: bool = True, name: str | None = None
                       ) -> SupercellStatement:
    r"""The nuclear phase of ``parent`` restated in the magnetic cell of a k.

    **Two ways in, and only the first goes through** :func:`~.isotropy.candidates`.

    ``candidate`` is one of :func:`~.isotropy.candidates`'
    :class:`~.isotropy.MagneticCandidate`
    objects — a magnetic space group with its cell and its k.  Only its
    ``group``, ``cell.k`` and ``bns_number`` are read: the moment *family* is
    not, because the family is derived per site from the group itself
    (``allowed_moment_basis``), which is what lets a parent with several
    magnetic sites be stated from one candidate.  The child cell is
    :func:`child_basis`'s, and ``candidates``' scope fence applies — 2k in the
    reciprocal lattice.

    ``group`` + ``transform`` is the other way, and it exists because that
    fence is ``candidates``' and not this module's.  It needs 2k ∈ L\* so that a
    lattice translation enters the order parameter with a phase of ±1 and an
    isotropy subgroup of the grey little group exists; **a supercell statement
    needs no such thing**.  It needs a child lattice, which every commensurate k
    has, and a magnetic space group in that cell, which a database or a
    k-SUBGROUPSMAG table supplies directly.  Mn₃O₄ on POWGEN is the case: parent
    I4₁/amd with k = (0, ½, 0), whose 2k = (0, 1, 0) is *not* a
    reciprocal-lattice vector of a body-centred lattice, so ``candidates``
    refuses it by name — and yet the structure is stated, and refined, in a,
    2b, c with a primitive lattice.  Pass the operator list in that cell and its
    (P, p) transform in ``transform_BNS_Pp_abc`` form; ``k`` is then a record
    for the report and nothing derives from it.  A ``bns_number`` passed with
    either way in is checked against the group's own and refused when it
    differs (#605).  The list has to be stated at
    the child origin the transform puts the atoms at (x_c = P⁻¹·(x − p)), i.e.
    restated by ``transformed`` under (I, −P⁻¹·p) when p is not zero: the same
    list at another origin is not a symmetry of the child structure, and the
    child phase is refused here, as it would be where it enters a fit
    (the magnetic-symmetry check, issue #597).

    ``nuclear_group`` chooses which group the child phase's ``space_group``
    states, and it is the one knob a caller can get wrong, so both settings and
    the reason for each are here.

    ``"parent"`` (the default) is the parent's own group carried through the
    transform: the right answer whenever the child lattice is invariant under
    the parent's point group, which is the k = (0,0,½)-in-P-lattice family and
    every type IV case.  The nuclear model then keeps every constraint the
    parent's symmetry puts on it.

    ``"magnetic"`` states the child phase under the **magnetic group's own
    nuclear part**, and it is not a convenience: for a k that lowers the crystal
    class there is no alternative.  Mn₃O₄ again: the child cell a, 2b, c breaks
    the tetragonal symmetry, so I4₁/amd's 4₁ screw does not map the child
    lattice onto itself and the parent group **is not a group of this cell at
    all** — ``"parent"`` refuses by name, from ``MagneticGroup.transformed``'s
    own integrality guard.  The largest subgroup of the parent that does
    preserve the child lattice is not describable by a Hermann-Mauguin symbol
    in it either (the body-centring becomes a quarter translation), which is the
    same obstruction the GSAS-II Magnetic-V tutorial states in prose: *"one has
    to describe the chemical structure in the doubled magnetic cell with the
    space group Pbna"*.  ``"magnetic"`` is that description.  What it costs is
    the parent's constraints on the *coordinates* — the child asymmetric unit is
    larger and its sites are independent — which is exactly why the tutorial
    calls the refinement unstable and why a caller should hold those coordinates
    rather than free them.  What it does **not** cost is the nuclear structure
    factor: every atom of the child cell is listed explicitly, so |F_N|² is the
    parent's to the last bit (``tests/test_magnetic_supercell.py``).

    ``magnetic_species`` is the species (or atom labels) that carry a moment;
    ``ion`` the magnetic form-factor key, either one string for all of them or
    a mapping from species to key.  ``g`` is that ion's Landé factor, mirroring
    ``ion``'s shape — one float for every moment, or a mapping keyed by the
    *parent's own atom label* (the same label ``ion``'s mapping form takes) —
    ``None`` (the default) leaves every moment's ``g`` unset, bit-identical to
    every call before this parameter grew a mapping form.  ``magnitude`` is
    the seed modulus in μ_B — a seed, not a claim.

    Every number in the returned phase is derived; nothing is copied from a
    published structure.  The parent's cell, coordinates, occupancies and
    displacement parameters come through unchanged, and the cell parameters are
    the parent's carried through P.
    """
    if (candidate is None) == (group is None):
        raise ValueError(
            "magnetic_supercell(): pass either one of isotropy.candidates' "
            "candidates or an "
            "explicit group with its transform, not both and not neither. The "
            "candidate route derives the child cell from k and is fenced at "
            "2k in the reciprocal lattice (candidates' scope); the explicit route "
            "takes the cell from the transform and has no such fence, because "
            "a child lattice exists for every commensurate k.")
    if nuclear_group not in ("parent", "magnetic"):
        raise ValueError(
            f"magnetic_supercell(): nuclear_group={nuclear_group!r} is not one "
            f"of 'parent' or 'magnetic'.")
    if group is not None and transform is None:
        raise ValueError(
            "magnetic_supercell(): an explicit group needs its transform. The "
            "operator list alone does not say which cell it is written in, and "
            "guessing would put the parent's atoms in the wrong cell with no "
            "sign that anything was wrong.")
    if any(a.aniso is not None for a in parent.atoms):
        raise ValueError(
            "magnetic_supercell(): an anisotropic displacement block is "
            "declared and this rung does not carry one into the child cell. "
            "U* transforms as R·U*·Rᵀ under the operation that produced an "
            "image, and the child sites are images of the parent's, so the "
            "tensors would have to be rotated rather than copied; copying them "
            "would be wrong in every non-orthogonal setting "
            "(crystallography/adp.py). Convert the sites to biso, or wait for "
            "the rung that carries the tensor.")

    # An unnamed (bracketed-label) parent used to be refused here by name.
    # ``child_basis``/``magnetic_cell``/``candidates`` all resolve their group
    # through ``_irreps._resolve``, which already accepts the ``OperatorGroup``
    # ``resolve_group`` builds from a phase's own operator list — no tabulated
    # space-group number is used anywhere in that chain — so the parent's group
    # is resolved once, from its operators when it has no name, and threaded
    # through instead of refusing before either derivation is tried.
    parent_group = resolve_group(parent.space_group, parent.symmetry_operations)
    if candidate is not None:
        basis = child_basis(parent_group, candidate.cell.k)
        origin = (Fraction(0), Fraction(0), Fraction(0))
        transform = format_transform([list(row) for row in basis], origin)
        k = candidate.cell.k
        bns_number = candidate.bns_number if bns_number is None else bns_number
        # the MSG in *this* cell.  The candidate's group is in magnetic_cell's
        # reduced cell, so it is carried across rather than rebuilt:
        # MagneticGroup.transformed takes (P, p) in the BNS sense and applies
        # the inverse map, so reaching a cell whose basis is M relative to the
        # current one means handing it M⁻¹ (isotropy.MagneticCell.
        # inverse_transform records the same direction).
        p_candidate = [[Fraction(v) for v in row] for row in candidate.cell.basis]
        step = _mat_mul(_isotropy._exact_inverse(p_candidate),
                        [[Fraction(v) for v in row] for row in basis])
        group = candidate.group.transformed(
            format_transform(_isotropy._exact_inverse(step),
                             (Fraction(0), Fraction(0), Fraction(0))))
    else:
        from .operators import parse_transform

        basis, origin = parse_transform(transform)
        transform = format_transform([list(row) for row in basis], origin)
    _refuse_a_contradicting_bns_number(group, bns_number)
    p_child = [[Fraction(v) for v in row] for row in basis]
    cosets = lattice_cosets(basis)
    parent_cell = parent.cell.lengths_angles()
    child_cell = _child_cell_parameters(parent_cell, basis)

    # The child's **nuclear** space group is the *parent's*, carried through the
    # same transform — not the magnetic candidate's, whose nuclear part is
    # generally smaller.  Ordering a moment lowers the magnetic symmetry and
    # leaves the nuclei exactly where they were, so the reflection list, the
    # site orbits and the systematic absences are all still the parent's.
    # Taking them from the candidate would give a different atom list for every
    # candidate of the same structure, which is the ranking measuring the wrong
    # thing.
    if nuclear_group == "parent":
        # ``transformed((Q, q))`` restates a group under x' = Q·x + q (its
        # docstring: W → Q·W·Q⁻¹, w → Q·w + (I − Q·W·Q⁻¹)·q), and
        # :func:`_child_positions` places the atoms at x_c = P⁻¹·(x − p) =
        # P⁻¹·x − P⁻¹·p.  So Q = P⁻¹ and q = −P⁻¹·p, **not** p: handing it the
        # parent-frame shift unchanged moves the group's origin by
        # (I − W')·(p + P⁻¹·p) against the atoms', which is a lattice vector
        # for some shifts and an orbit the child cannot hold for the rest.
        p_inverse = _isotropy._exact_inverse(p_child)
        child_origin = tuple(-v for v in _mat_vec(p_inverse, origin))
        nuclear = _nuclear_group_of(
            parent.space_group, parent.symmetry_operations).transformed(
            format_transform(p_inverse, child_origin))
    else:
        nuclear = _colourless(group)
        # **The little-group sign.**  A commensurate k != 0 little group is
        # generally grey: the same spatial operation {R | t} can carry
        # little-group character +1 on one component of a multi-dimensional
        # order-parameter direction and -1 on another. _colourless already
        # discarded that character above; here, for a candidate whose own
        # (positions, configurations) this rung can check against, the declared
        # group is reduced to the subgroup that is a symmetry of the
        # candidate's **signed** field, not only of its positions — so an
        # operation whose sign this rung cannot state correctly is excluded
        # rather than trusted with an implicit +1, and the sibling it used to
        # reach becomes its own explicit representative instead.  Gated on
        # ``kind == "displacive"``: the moment path's own consumer
        # (``magnetic.scattering.compile_magnetic_sites``) re-derives each
        # image's axial matrix from the *full*, non-colourless magnetic group
        # at compile time, one operation at a time, so it never trusts the
        # *declared* nuclear group's sign in the first place — reducing it too
        # would only add atoms no consumer needs.
        if candidate is not None and candidate.kind == "displacive":
            m_matrix = (_isotropy._fraction_inverse(basis)
                       @ _matrix_of(candidate.cell.basis))
            reduced_ops = _sign_consistent_operations(
                candidate, m_matrix, _nuclear_operations(nuclear))
            nuclear = _group_from_nuclear_ops(reduced_ops)
    # The group is exact rationals here and meets gemmi's integer-over-24
    # operations downstream (the orbit partition, the phase's own list), where
    # a 1/7 does not survive.  An origin shift is free to put one there, so it
    # is refused by name rather than left to surface as an orbit that "does
    # not fit" the child cell.
    off_grid = sorted({str(v) for op in nuclear.all_operations()
                       for v in op.translation if 24 % Fraction(v).denominator})
    if off_grid:
        raise ValueError(
            f"magnetic_supercell(): transform {transform!r} gives the child's "
            f"nuclear group translations {off_grid}, which are not multiples "
            f"of 1/24; symmetry operations are carried at that resolution "
            f"(gemmi's), so this origin cannot be stated. Choose an origin "
            f"shift in multiples of 1/24 — every tabulated origin choice is one")
    lattice = _child_lattice(parent_cell, basis)
    # ``None`` when spglib will not even name the *type* — no longer a refusal:
    # the type is the leading half of a label and the operation list is the
    # group either way, so what used to stop the statement now only shortens
    # its label (#448).
    symbol = _identify_child_space_group(nuclear, lattice)
    child_group = resolve_child_group(nuclear, symbol, transform)
    symbol = child_group.label
    diagnostics: tuple[Diagnostic, ...] = ()
    if not child_group.named:
        diagnostics = (Diagnostic(
            level="info", code="CHILD_GROUP_UNNAMED",
            where=["space_group"],
            message=f"magnetic_supercell(): {child_group.reason}",
            suggestion=(
                "nothing to fix — the statement is complete. Quote the child "
                "group as its operation list (or as the closest type with the "
                "cell beside it), not as the bracketed label's leading symbol, "
                "which names a different group. If a published assignment for "
                "this superstructure names a symbol, it is naming the type in "
                "another cell: check the transform before comparing"),
        ),)

    entries = _child_positions(parent, basis, origin, cosets)
    partition = _partition_into_child_orbits(child_group.group, entries)

    wanted = _species_map(parent, magnetic_species, ion)
    g_lookup = g if isinstance(g, dict) else None
    positions = [entries[rep][2] for rep, _members in partition]
    ions = [wanted.get(parent.atoms[entries[rep][0]].label) for rep, _ in partition]
    seeds = _seed_moments(group, positions, ions, magnitude, child_cell)
    _refuse_a_nuclear_orbit_the_magnetic_group_cannot_cover(
        child_group.group, group, positions, ions, nuclear_group)

    atoms: list[Atom] = []
    site_map: list[tuple[int, int]] = []
    counts: dict[str, int] = {}
    for n, (rep, _members) in enumerate(partition):
        j, coset, position = entries[rep]
        source = parent.atoms[j]
        counts[source.label] = counts.get(source.label, 0) + 1
        suffix = "" if len(
            [1 for r, _ in partition if entries[r][0] == j]) == 1 else \
            f"_{counts[source.label]}"
        moment = None
        seed = seeds.get(n)
        if ions[n] is not None and seed is not None and float(np.abs(seed).max()) > 0:
            g_n = g_lookup.get(source.label) if g_lookup is not None else g
            moment = Moment.from_values(tuple(float(v) for v in seed), ions[n],
                                        g=g_n, vary=vary)
        atoms.append(Atom(
            label=f"{source.label}{suffix}", species=source.species,
            x=Parameter(value=float(position[0])),
            y=Parameter(value=float(position[1])),
            z=Parameter(value=float(position[2])),
            occ=Parameter(value=source.occ.value),
            # the source's own bounds: a reader widens them to hold a file's
            # value (schemas.structure.biso_bounds), and the declared 0-25 Å²
            # a bare Parameter inherits would refuse that value here
            biso=Parameter(value=source.biso.value, min=source.biso.min,
                           max=source.biso.max), moment=moment))
        site_map.append((j, coset))

    ops, cent = group.xyz_strings()
    phase = Phase(
        name=name or f"{parent.name} ({transform})",
        space_group=symbol,
        symmetry_operations=(None if child_group.operations is None
                             else list(child_group.operations)),
        cell=Cell(a=Parameter(value=child_cell[0]), b=Parameter(value=child_cell[1]),
                  c=Parameter(value=child_cell[2]),
                  alpha=Parameter(value=child_cell[3]),
                  beta=Parameter(value=child_cell[4]),
                  gamma=Parameter(value=child_cell[5])),
        atoms=atoms,
        magnetic_symmetry=MagneticSymmetry(
            operations=list(ops), centerings=list(cent),
            bns_number=bns_number,
            # ``setting`` is the transform from this cell to the BNS standard
            # setting, which this builder does not derive; the parent -> child
            # transform it does know is a different map, and stays on the
            # statement (``SupercellStatement.transform``) and in the name (#610)
            setting=None,
            propagation_vector_parent=(None if k is None
                                       else tuple(str(c) for c in k))),
        scale=Parameter(value=parent.scale.value),
    )
    # the builder's own statement is judged here, once; a refined copy of it
    # is not (``check_group_is_structure_symmetry``)
    check_group_is_structure_symmetry(phase)
    return SupercellStatement(
        phase=phase, transform=transform, index=len(cosets),
        parent_space_group=parent.space_group, child_space_group=symbol,
        group=group, site_map=tuple(site_map),
        k=None if k is None else tuple(str(c) for c in k),
        child_group_named=child_group.named, diagnostics=diagnostics)


def _mat_mul(a, b):
    return [[sum(Fraction(a[i][t]) * Fraction(b[t][j]) for t in range(3))
             for j in range(3)] for i in range(3)]


def _mat_vec(a, v):
    return [sum(Fraction(a[i][t]) * Fraction(v[t]) for t in range(3))
            for i in range(3)]


def _refuse_a_nuclear_orbit_the_magnetic_group_cannot_cover(
        nuclear_group_object, group: MagneticGroup, positions, ions,
        nuclear_group: str) -> None:
    """Refuse, at build, a statement whose moments the compile would refuse.

    ``compile_magnetic_sites`` already refuses a child whose **nuclear** orbit
    of a magnetic site is larger than the group's magnetic orbit of it: some
    nuclear image then has no moment the stated group determines, and no
    tolerance makes one.  It refuses at *compile*, which was invisible while
    ``resolve_child_group`` refused every such child one step earlier for the
    unrelated reason that no symbol named it — and that earlier refusal is what
    ``strategy.magnetic._supercell`` reads to take the documented remedy
    (``nuclear_group="magnetic"``) by itself.  P2₁2₁2₁ at k = (½,0,0) is the
    case (``test_the_parent_route_is_refused_when_the_magnetic_orbit_is_smaller``):
    with the child stated as an operation list the build would succeed and the
    compile refuse, so a workflow that used to fall back would abstain instead.

    So the check moves here, where the remedy is still reachable.  It is the
    same arithmetic and the same verdict — nothing is loosened, and a statement
    that passes it compiles exactly as it did.
    """
    if nuclear_group != "parent":
        return
    for position, ion in zip(positions, ions):
        if ion is None:
            continue
        nuclear_images = expand_positions(nuclear_group_object, position)
        magnetic_images, _moments = group.site_orbit(position)
        for image in nuclear_images:
            if not any(_same_site(image, q) for q in magnetic_images):
                raise ValueError(
                    f"magnetic_supercell(): the child's nuclear space group "
                    f"puts an image of the site "
                    f"{np.array2string(np.asarray(position), precision=5)} at "
                    f"{np.array2string(np.asarray(image), precision=5)}, and "
                    f"no operation of the magnetic group sends the site there "
                    f"— so the stated group determines no moment for that "
                    f"atom and the child cannot carry one. The magnetic orbit "
                    f"({len(magnetic_images)} images) is smaller than the "
                    f"nuclear one ({len(nuclear_images)}), which is what "
                    f"nuclear_group='parent' means for a k that lowers the "
                    f"crystal class. State the child under the magnetic "
                    f"group's own nuclear part instead "
                    f"(nuclear_group='magnetic'), which is that group's own "
                    f"asymmetric unit and is what a magCIF from MAGNDATA, "
                    f"ISODISTORT or k-SUBGROUPSMAG gives you.")


def _species_map(parent: Phase, magnetic_species, ion) -> dict[str, str]:
    """``{atom label: form-factor ion}`` for the sites that carry a moment."""
    if magnetic_species is None:
        return {}
    wanted = {magnetic_species} if isinstance(magnetic_species, str) \
        else set(magnetic_species)
    out: dict[str, str] = {}
    for atom in parent.atoms:
        key = None
        if atom.species in wanted:
            key = atom.species
        elif atom.label in wanted:
            key = atom.species
        if key is None:
            continue
        if isinstance(ion, dict):
            resolved = ion.get(atom.species) or ion.get(atom.label)
        else:
            resolved = ion
        if resolved is None:
            raise ValueError(
                f"magnetic_supercell(): {atom.label!r} is asked to carry a "
                f"moment but no form-factor ion was given for it. The magnetic "
                f"form factor is keyed by oxidation state and the nuclear "
                f"scattering length by nuclide, so 'Mn' is not an answer: pass "
                f"ion='Mn2+' or a mapping.")
        out[atom.label] = resolved
    if not out:
        raise ValueError(
            f"magnetic_supercell(): none of {sorted(wanted)} is a species or a "
            f"label of {parent.name!r} (it has "
            f"{sorted({a.species for a in parent.atoms})}).")
    return out
