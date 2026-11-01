"""Interatomic distances and angles, with esds from the full covariance (WP-1072).

McCusker *et al.* (1999), *J. Appl. Cryst.* **32**, 36, names this twice.  §11
makes it one of the two "most important criteria for judging the quality of a
Rietveld refinement" — "Interatomic distances (both bonding and nonbonding)
should be reasonable, bond angles sensible" — and §10 says how the numbers
beside them must be computed: "The whole correlation matrix, not just the
diagonal elements, should be included in the calculation" of a derived
quantity's e.s.d.

Both halves are here.  The table is built at fit close because **the covariance
is never serialized** — it is read off the final Jacobian, the
:class:`~rietx.schemas.results.Identifiability` carrier argument — so a
distance's esd is measured here or lost.  A replayed or loaded result carries
what was stored, or ``None``; nothing downstream recomputes a diagonal-only
esd and calls it the answer.

**Reuse, not re-derivation.**  A bond distance is d = √(Δxᵀ·G·Δx) and an angle
is its arccos twin — exactly the soft restraints of :mod:`.restraints`, whose
``_bond_row_partials`` / ``_angle_row_partials`` already implement the
derivative chain through the coordinate DOFs' affine ties (p = C·θ + d,
WP-0301) *and* the six cell parameters.  So a geometry row **is** a restraint
row with σ = 1 and weight = 1, and its partials come from the function the
Jacobian itself uses.  :func:`~rietx.optimize.qpa.weight_fractions` is the
propagation precedent: J·Cov·Jᵀ with the diagonal-only number returned beside
it, so the difference §10 warns about is visible rather than asserted.

**What is listed.**  For each phase, every image of every atom within reach of
each asymmetric-unit atom, generated over that atom's *frozen* orbit ops (the
subsets :class:`~rietx.crystallography.structure_factor.PhaseSites` gave the
forward model — the geometry table and the structure factors count the same
orbits) crossed with a lattice shell wide enough for the cutoff.  A pair is a
**bond** when d ≤ r_cov(i) + r_cov(j) + :data:`BOND_SLACK_ANG` and a
**contact** otherwise, out to :data:`CONTACT_MAX_ANG`.

**Every asymmetric-unit atom gets its whole environment**, and nothing is
deduplicated against anything else.  A bond between two different sites
therefore appears twice, once from each end — which is *not* the CIF
convention, and is deliberate: the two directions are not the same list.  In
α-quartz Si has four O neighbours while each O has two Si (the relation is
4·3 = 2·6 over the two multiplicities), so a table listing only one direction
makes the other atom's coordination number unreadable without multiplicity
arithmetic — and coordination is exactly what §11 asks a reader to check.  The
CIF exporter drops one direction on its way out, where the audience is a
parser rather than a chemist.

The same reasoning settles the same-site case, which has no direction to drop:
x and S(x) and x and S⁻¹(x) are two *different* bonds that both touch x, so
both are listed, and the neighbour count is the coordination number.  Angles
are listed at each vertex over that vertex's complete bonded environment.
"""

from __future__ import annotations

import math

import gemmi
import numpy as np

from ..crystallography.symmetry import as_group, resolve_group
from ..params.derived import cartesian_frame
from .restraints import (
    _COS_CLAMP,
    _TORSION_SIN2_FLOOR,
    CompiledRestraints,
    _Angle,
    _Bond,
    _metric_g,
    _resolve_image,
    _Torsion,
    _torsion_defined,
    _torsion_geometry_np,
    _xyz_np,
    restraint_partials,
)

#: A pair is *bonded* when its distance is at most the sum of the two covalent
#: radii plus this slack, in Å.  The radii are gemmi's
#: ``gemmi.Element.covalent_r``, which reproduces Cordero *et al.* (2008),
#: *Dalton Trans.*, 2832 ("Covalent radii revisited") — checked against 30
#: single-valued entries of its Table 1, agreeing to < 5·10⁻³ Å throughout, so
#: the citation is a measurement rather than a remembered attribution.
#:
#: The slack is **not** a physical constant and is cited to nobody: 0.4 Å is
#: the tolerance bond-perception software conventionally allows, and it decides
#: which *loop* a row is listed in and nothing else — a pair past it is still
#: reported, as a contact.  It travels on ``GeometryTable.bond_slack`` so a
#: reader never has to guess which value produced a table.
BOND_SLACK_ANG = 0.40

#: A radius criterion is not evidence of a metal-metal bond, so a pair of two
#: metals (``gemmi.Element.is_metal``) is listed as a contact whatever its
#: distance.  Without this the covalent radii make α-Al₂O₃'s face- and
#: edge-sharing Al···Al pairs at 2.65 and 2.79 Å "bonds" — the sum plus the
#: slack is 2.82 Å — and every angle at an Al then carries them as arms.  The
#: distances are still reported; only the loop they land in changes.
DEMOTE_METAL_METAL = True

#: Non-bonded contacts are listed out to this distance, in Å.  McCusker §11
#: asks for "both bonding and nonbonding" distances without naming a range.
#: This is a **listing radius**, not a physical constant: 3.5 Å reaches the
#: second coordination sphere of the oxides and framework solids powder
#: Rietveld is usually about (ZnO's nearest Zn···Zn and O···O are both the
#: 3.25 Å a axis), and is short enough that the row count stays readable.  It
#: is recorded on the table, so a row can be read without guessing it.  It
#: bounds contacts only: the search reaches the longest pair the radii could
#: call a bond, so CsCl's 3.57 Å Cs–Cl is listed (WP-2002; a search stopping
#: here once dropped it with no note).
CONTACT_MAX_ANG = 3.5

#: Contacts kept per asymmetric-unit atom, nearest first.  Bonds and angles are
#: uncapped — chemistry bounds them — but the contact count grows with the
#: cutoff volume, and a table nobody can read is not evidence.  Whatever this
#: drops is counted in ``GeometryTable.notes``, never dropped in silence: a
#: firing cap is also the one thing that breaks the orbit-count relation the
#: search is checked with, since it can truncate one direction of a pair and
#: not the other.
MAX_CONTACTS_PER_ATOM = 24

#: Phases with more asymmetric-unit atoms than this are skipped, and said in
#: ``GeometryTable.notes`` to be skipped.  The search is O(n²·m·shell³) and
#: runs at fit close, where a minute spent on a table is a minute stolen from
#: the refinement.
MAX_ASYM_ATOMS = 200

#: Torsions kept per asymmetric-unit atom B (the central bond's first atom),
#: in the table's chain order: B's bonds B–C nearest first, then A and D
#: nearest first.  Like :data:`MAX_CONTACTS_PER_ATOM` this bounds a
#: **listing**, not a measurement: a torsion's esd is its own row's J·Cov·Jᵀ
#: and does not depend on which other rows are listed, so the cap only decides
#: how many rows a reader is handed.  Whatever it drops is counted in
#: ``GeometryTable.notes``, and :meth:`~rietx.Refinement.geometry` answers any
#: chain by name, capped or not.  36 is the most a tetravalent chain can give,
#: (4 − 1)·(4 − 1) chains about each of B's four bonds, so every chain of a
#: molecule built from atoms of up to four bonds is listed whole; a densely
#: bonded inorganic phase reaches it (LaB₆'s La has 24 B neighbours and 4 374
#: chains), where a torsion is rarely the quantity anyone reads.
MAX_TORSIONS_PER_ATOM = 36

#: A CIF symmetry code ``n_klm`` encodes each lattice translation as one digit
#: offset by 5, so it can express shifts in −4…+4 only.  An image needing more
#: (reachable only when a stored fractional coordinate sits several cells out)
#: carries ``None`` here and ``?`` in the exported loop; the distance and its
#: esd are unaffected.
SYMMETRY_CODE_MAX_SHIFT = 4

#: A variance this small a fraction of its own quadratic form's absolute terms
#: is cancellation, not a measurement, and the esd is reported as absent.
#: **This is a floating-point floor, not a threshold on the physics.**  A
#: symmetry-constrained quantity has *exactly* zero variance — rutile's
#: O–Ti–O angle stays at 90° however the one free DOF moves — but its partials
#: against the individual x, y, z entries are not zero, so gᵀ·Cov·g reaches
#: zero by cancelling terms and lands on roundoff.  Left alone that prints as
#: ``90.00000000000(43)``, an uncertainty of 4·10⁻¹² degrees quoted with a
#: straight face.  The test is self-scaling (var against Σ|terms|, so it means
#: the same for a 2 Å distance and a 180° angle) and sits four orders above
#: fp64's own epsilon and five below the smallest esd a powder refinement
#: produces.
VARIANCE_CANCELLATION_FLOOR = 1e-12

#: How close to 0° or 180° an angle may come and still carry an esd, in
#: degrees — **derived** from the clamp :mod:`.restraints` applies to cos θ,
#: not chosen, so the two cannot drift apart.  Inside it the partials that come
#: back are the clamp's rather than the geometry's, and the linearisation
#: J·Cov·Jᵀ rests on is invalid anyway: a straight angle is a stationary point
#: of the coordinates (it can only bend one way), so it has no first-order
#: variance to propagate.  The angle itself is still exact — only its esd is
#: withheld.
ANGLE_LINEARISATION_LIMIT_DEG = math.degrees(math.acos(_COS_CLAMP))

#: an image closer than this (Å²) to the reference atom is the atom itself
_COINCIDENT_D2 = 1e-6

_CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")
_XYZ = ("x", "y", "z")


# ----------------------------------------------------------------------
# neighbour generation
# ----------------------------------------------------------------------
def _shell(g: np.ndarray, cutoff: float) -> np.ndarray:
    """Integer lattice shifts covering ``cutoff`` around a centred image.

    The perpendicular spacing of the (100) planes is 1/√(G\\*₁₁), so a cutoff
    of ``c`` reaches ``ceil(c·√(G*₁₁))`` cells along **a**, and likewise for
    **b** and **c**; the extra cell absorbs the ≤ ½-cell offset left by
    centring each image on the reference atom.
    """
    gstar = np.linalg.inv(g)
    reach = [int(math.ceil(cutoff * math.sqrt(gstar[k, k]))) + 1 for k in range(3)]
    grids = np.meshgrid(*[np.arange(-r, r + 1) for r in reach], indexing="ij")
    return np.stack([grid.ravel() for grid in grids], axis=1).astype(np.float64)


def symmetry_operations(space_group) -> list[str]:
    """The ``x,y,z`` triplets of ``space_group``, in gemmi's listing order.

    A symmetry code is an index into a listed order, so it means nothing
    without one: every CIF structure block writes this loop
    (:func:`~rietx.io.cif.blocks.write_structure_block`), rather than leaving a
    reader to re-derive the order from the Hermann-Mauguin symbol and hope it
    matches.
    """
    return [op.triplet() for op in _op_list(space_group)]


def _op_list(space_group):
    """The operations of a symbol or a group object, in the listing order.

    ``_group_arrays`` is the one authority for that order (see
    ``symmetry._op_list_from_xyz`` for why a group carrying its own list must
    keep the caller's), so a symmetry code written by the CIF exporter and the
    (R, t) pair the bond search matched it against cannot come from two
    different orderings.
    """
    from ..crystallography.symmetry import _group_arrays, group_key

    return _group_arrays(group_key(as_group(space_group)))[0]


def _symop_table(space_group) -> list[tuple[np.ndarray, np.ndarray]]:
    """(R, t) of every operation of ``space_group``, in the same order."""
    return [(np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN,
             np.array(op.tran, dtype=np.float64) / gemmi.Op.DEN)
            for op in _op_list(space_group)]


def _symop_index(symops, rot: np.ndarray, tran: np.ndarray) -> int | None:
    """Index of ``(rot, tran)`` in the space group's operation list, or None.

    Exact comparison is right here: both sides come from the same gemmi ops
    divided by the same ``Op.DEN``, so the frozen orbit subset holds bit-equal
    copies of the listed operations rather than reconstructions of them.
    """
    for idx, (r, t) in enumerate(symops):
        if np.array_equal(r, rot) and np.array_equal(t, tran):
            return idx
    return None


def _symmetry_code(index: int | None, shift: np.ndarray) -> str | None:
    """CIF ``n_klm`` code for operation ``index`` plus lattice ``shift``."""
    if index is None:
        return None
    n = [int(round(float(v))) for v in shift]
    if any(abs(v) > SYMMETRY_CODE_MAX_SHIFT for v in n):
        return None
    if index == 0 and not any(n):
        return "."
    return f"{index + 1}_{5 + n[0]}{5 + n[1]}{5 + n[2]}"


def _code_of(symops, rot: np.ndarray, tran: np.ndarray) -> str | None:
    """CIF code of the image ``rot·x + tran``, ``tran`` holding any shift.

    For a composed image (the far end of a torsion, the image of an image):
    the rotation is matched exactly (integer entries), and the translation is
    split into the listed operation's part, in [0, 1), and a lattice shift.
    """
    shift = np.floor(tran + 1e-9)
    frac = tran - shift
    for idx, (r, t) in enumerate(symops):
        if np.array_equal(r, rot) and np.allclose(t, frac, atol=1e-9):
            return _symmetry_code(idx, shift)
    return None


def _neighbours(sites, values, ip: int, i: int, g: np.ndarray,
                shifts: np.ndarray, cutoff: float) -> list[tuple]:
    """``(j, R, t, n, d)`` for every image within ``cutoff`` of atom ``i``.

    Vectorised over (orbit op × lattice shift) per neighbour site, because the
    scalar loop is O(n²·m·shell³) and this runs at fit close.  Each image is
    first centred on the reference atom (``round(x_i − image)``), so ``shifts``
    only has to cover the cutoff rather than wherever the stored coordinates
    happen to sit.
    """
    x_i = _xyz_np(values, ip, i)
    out = []
    for j in range(sites.n_asym):
        ops_r, ops_t = sites.ops[j]
        x_j = _xyz_np(values, ip, j)
        img0 = np.einsum("mab,b->ma", ops_r, x_j) + ops_t          # (m, 3)
        base = np.round(x_i - img0)                                # (m, 3)
        dx = (img0 + base)[:, None, :] + shifts[None, :, :] - x_i  # (m, s, 3)
        d2 = np.einsum("msa,ab,msb->ms", dx, g, dx)
        for m, s in np.argwhere((d2 > _COINCIDENT_D2) & (d2 <= cutoff * cutoff)):
            out.append((j, ops_r[m], ops_t[m], base[m] + shifts[s],
                        math.sqrt(float(d2[m, s]))))
    out.sort(key=lambda row: row[4])
    return out


# ----------------------------------------------------------------------
# per-phase assembly
# ----------------------------------------------------------------------
def _element(species: str) -> gemmi.Element:
    """The element behind a scattering species (``"Zn2+"`` → Zn).

    ``crystallography.species.element_symbol`` is the one parser — it already
    rejects the symbols gemmi maps to its placeholder element, and a covalent
    radius of 1.0 Å for a mis-parsed species would silently reclassify every
    one of its contacts.
    """
    from ..crystallography.species import element_symbol

    return gemmi.Element(element_symbol(species))


def _angle_degrees(item: _Angle, values: dict) -> float:
    """The angle at ``item``'s vertex, stable at 0° and 180°.

    ``restraints._angle_value_np`` clamps cos θ just inside [−1, 1] because a
    restraint's derivative goes as 1/sin θ there; that is right for a residual
    row and wrong for a reported number — it turns fluorite's linear F–Ca–F
    into 179.997°.  The half-angle form θ = 2·atan2(‖û − v̂‖, ‖û + v̂‖) (Kahan)
    needs no clamp and is exact at both ends, with the norms taken in the
    direct metric because the arms are fractional.
    """
    ip = item.phase
    g = _metric_g(tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_NAMES))
    u = item.Ri @ _xyz_np(values, ip, item.i) + item.ti + item.ni \
        - _xyz_np(values, ip, item.j)
    v = item.Rk @ _xyz_np(values, ip, item.k) + item.tk + item.nk \
        - _xyz_np(values, ip, item.j)

    def norm(w):
        return math.sqrt(max(float(w @ (g @ w)), 0.0))

    nu, nv = norm(u), norm(v)
    if nu <= 0.0 or nv <= 0.0:
        return float("nan")
    uh, vh = u / nu, v / nv
    return math.degrees(2.0 * math.atan2(norm(uh - vh), norm(uh + vh)))


def _phase_items(phase, sites, values, ip: int, notes: list[str]):
    """``(labels, bonds, contacts, angles)`` descriptors for one phase.

    Bonds and contacts are ``(reference atom, neighbour entry)`` pairs; an
    angle is ``(vertex, entry, entry)``.  An entry carries what the ``_Bond``
    and ``_Angle`` items built from it cannot: the distance, and the symmetry
    code of the image.
    """
    cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_NAMES)
    g = _metric_g(cell)
    symops = _symop_table(resolve_group(phase.space_group,
                                        phase.symmetry_operations))
    elements = [_element(a.species) for a in phase.atoms]
    radii = [float(e.covalent_r) for e in elements]
    metal = [bool(e.is_metal) for e in elements]
    labels = [a.label for a in phase.atoms]
    # the longest pair the radii could call a bond, past the contact radius
    # for heavy atoms (Cs: 2.44 Å)
    longest = max(radii, default=0.0)

    bonds, contacts, angles = [], [], []
    bonded_of: list[list] = []
    dropped = 0
    for i in range(sites.n_asym):
        bonded, near = [], []
        # sized per atom, so a light atom beside a heavy one searches the
        # contact radius's shell rather than the heavy atom's
        reach = max(CONTACT_MAX_ANG, radii[i] + longest + BOND_SLACK_ANG)
        for j, rot, tran, shift, d in _neighbours(sites, values, ip, i, g,
                                                  _shell(g, reach), reach):
            entry = (j, rot, tran, shift, d,
                     _symmetry_code(_symop_index(symops, rot, tran), shift))
            if (d <= radii[i] + radii[j] + BOND_SLACK_ANG
                    and not (DEMOTE_METAL_METAL and metal[i] and metal[j])):
                bonded.append(entry)
            elif d <= CONTACT_MAX_ANG:
                near.append(entry)
        if len(near) > MAX_CONTACTS_PER_ATOM:
            dropped += len(near) - MAX_CONTACTS_PER_ATOM
            near = near[:MAX_CONTACTS_PER_ATOM]
        bonded_of.append(bonded)
        bonds.extend((i, e) for e in bonded)
        contacts.extend((i, e) for e in near)
        for a in range(len(bonded)):
            for b in range(a + 1, len(bonded)):
                angles.append((i, bonded[a], bonded[b]))
    if dropped:
        notes.append(f"{phase.name}: {dropped} contact(s) beyond the nearest "
                     f"{MAX_CONTACTS_PER_ATOM} per atom are not listed")
    torsions = _torsion_chains(phase, ip, values, bonded_of, symops, notes)
    return labels, bonds, contacts, angles, torsions


def _image(entry) -> tuple[np.ndarray, np.ndarray]:
    """(R, t + n) of a neighbour entry, the image as one affine map."""
    _j, rot, tran, shift, _d, _code = entry
    return rot, tran + shift


#: where :func:`_keys` puts its cell boundaries, as a fraction of a cell:
#: irrational, so no coordinate a CIF prints (a decimal) and none of its
#: images under a symmetry operation sits on one.  Rounding to the nearest
#: 1e-4 instead put 0.48775 (LaMnO₃'s O3 x) on a tie, two arithmetic paths to
#: one point fell either side of it, and four chains were counted twice.
_KEY_OFFSET = math.sqrt(2.0) - 1.0


def _keys(j, pos: np.ndarray) -> list[tuple]:
    """A position key per row of ``pos`` (fractional, 1e-4 cells) with its atom.

    Two images of one atom share a key exactly when they are the same point,
    so keys compare chains by where their atoms are rather than by which
    operation reached them.
    """
    js = [j] * len(pos) if np.isscalar(j) else list(j)
    cells = np.floor(np.asarray(pos) * 1e4 + _KEY_OFFSET).astype(np.int64)
    return [(jj, *row) for jj, row in zip(js, cells.tolist(), strict=True)]


def _cross_rows(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Row-wise u × v for (n, 3) arrays (``np.cross`` without its overhead)."""
    return np.stack([u[..., 1] * v[..., 2] - u[..., 2] * v[..., 1],
                     u[..., 2] * v[..., 0] - u[..., 0] * v[..., 2],
                     u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]], axis=-1)


def _bent_arms(arm: np.ndarray, axis: np.ndarray) -> np.ndarray:
    """Per row of ``arm``: whether the angle it makes with ``axis`` is bent.

    The test ``restraints._torsion_defined`` makes, |arm × axis|² against
    |arm|²·|axis|² at the clamp's sin² (and no zero arm), on Cartesian rows.
    """
    la = np.einsum("ka,ka->k", arm, arm)
    lx = float(axis @ axis)
    n = _cross_rows(arm, np.broadcast_to(axis, arm.shape))
    return (la > 0.0) & (lx > 0.0) & (np.einsum("ka,ka->k", n, n)
                                     > _TORSION_SIN2_FLOOR * la * lx)


def _torsion_chains(phase, ip: int, values, bonded_of, symops,
                    notes: list[str]) -> list[tuple]:
    """``(item, codes)`` for every torsion over bonded chains of one phase.

    B is an asymmetric-unit atom at its published position, C one of its
    bonded images, A another of B's, and D one of C's bonded neighbours
    carried to C's image (the composed map C∘D).  A torsion is not listed
    again from its other end: a chain whose reversal, carried by the inverse
    of C's map back to C's published position, was already listed is
    skipped.  Images related by an atom's own site symmetry are each listed,
    as the distances are.  A chain with a straight bond angle has no torsion,
    and a chain whose two ends coincide (a three-membered ring) none either;
    the first are counted in ``notes`` rather than listed, as is every torsion
    past :data:`MAX_TORSIONS_PER_ATOM` about one atom.

    Vectorised over A × D per central bond, since a densely bonded phase has
    thousands of chains (LaB₆: 4 566) and this runs at fit close.
    """
    eye, zero = np.eye(3), np.zeros(3)
    x = [_xyz_np(values, ip, j) for j in range(len(bonded_of))]
    amat = np.asarray(cartesian_frame(tuple(values[f"phases.{ip}.cell.{k}"]
                                            for k in _CELL_NAMES)), dtype=np.float64)
    # per atom: its bonded images' atoms, maps and positions, in table order
    nb_j = [[e[0] for e in around] for around in bonded_of]
    nb_map = [[_image(e) for e in around] for around in bonded_of]
    nb_pos = [np.array([r @ x[j] + t for j, (r, t) in zip(js, maps, strict=True)])
              .reshape(-1, 3) for js, maps in zip(nb_j, nb_map, strict=True)]
    seen: set[tuple] = set()
    out: list[tuple] = []
    over = straight = 0
    for b, around_b in enumerate(bonded_of):
        kept = 0
        if not around_b:
            continue
        key_b = _keys(b, x[b][None, :])[0]
        pos_a = nb_pos[b]
        keys_a = _keys(nb_j[b], pos_a)
        cart_b = amat @ x[b]
        arm_a = cart_b - pos_a @ amat.T                       # b₁ = B − A
        for ic, ec in enumerate(around_b):
            c = ec[0]
            if not bonded_of[c]:
                continue
            rc, tc = nb_map[b][ic]
            pos_c = pos_a[ic]
            key_c = keys_a[ic]
            rc_inv = np.linalg.inv(rc)
            pos_d = nb_pos[c] @ rc.T + tc                      # C's map on D
            keys_d = _keys(nb_j[c], pos_d)
            axis = amat @ pos_c - cart_b                       # b₂ = C − B
            arm_d = pos_d @ amat.T - amat @ pos_c              # b₃ = D − C
            bent_a = _bent_arms(arm_a, axis)
            bent_d = _bent_arms(arm_d, axis)
            # the reversal D–C–B–A carried back by C's inverse map
            back_d = _keys(nb_j[c], (pos_d - tc) @ rc_inv.T)
            back_c = _keys(c, x[c][None, :])[0]
            back_b = _keys(b, ((x[b] - tc) @ rc_inv.T)[None, :])[0]
            back_a = _keys(nb_j[b], (pos_a - tc) @ rc_inv.T)
            for ia, ea in enumerate(around_b):
                if ia == ic or keys_a[ia] == key_c:
                    continue
                for id_, ed in enumerate(bonded_of[c]):
                    if keys_d[id_] == key_b or keys_d[id_] == keys_a[ia]:
                        continue
                    key = (keys_a[ia], key_b, key_c, keys_d[id_])
                    if key in seen or (back_d[id_], back_c, back_b,
                                       back_a[ia]) in seen:
                        continue
                    seen.add(key)
                    if not (bent_a[ia] and bent_d[id_]):
                        straight += 1
                        continue
                    if kept >= MAX_TORSIONS_PER_ATOM:
                        over += 1
                        continue
                    kept += 1
                    ra, ta = nb_map[b][ia]
                    rd, td = nb_map[c][id_]
                    r_cd, t_cd = rc @ rd, rc @ td + tc
                    item = _Torsion(ip, [ea[0], b, c, ed[0]],
                                    [ra, eye, rc, r_cd], [ta, zero, tc, t_cd],
                                    [zero, zero, zero, zero], 0.0, 1.0, 1.0)
                    out.append((item, (ea[5], ".", ec[5],
                                       _code_of(symops, r_cd, t_cd))))
    if straight:
        notes.append(f"{phase.name}: {straight} bonded chain(s) with a straight "
                     "bond angle have no torsion and are not listed")
    if over:
        notes.append(f"{phase.name}: {over} torsion(s) beyond the first "
                     f"{MAX_TORSIONS_PER_ATOM} per atom are not listed")
    return out


def _bond_item(ip: int, i: int, entry) -> _Bond:
    j, rot, tran, shift, _d, _code = entry
    return _Bond(ip, i, j, rot, tran, shift, target=0.0, sigma=1.0, weight=1.0)


def _angle_item(ip: int, vertex: int, first, second) -> _Angle:
    ja, rot_a, tran_a, shift_a, _da, _ca = first
    jb, rot_b, tran_b, shift_b, _db, _cb = second
    return _Angle(ip, ja, vertex, jb, rot_a, tran_a, shift_a,
                  rot_b, tran_b, shift_b,
                  target_deg=0.0, sigma=1.0, weight=1.0)


# ----------------------------------------------------------------------
# esds: J·Cov·Jᵀ through the full covariance (McCusker §10)
# ----------------------------------------------------------------------
def _phase_paths(ip: int, n_atoms: int) -> list[str]:
    """Every table entry a distance or angle of phase ``ip`` can touch."""
    return ([f"phases.{ip}.atoms.{j}.{c}" for j in range(n_atoms) for c in _XYZ]
            + [f"phases.{ip}.cell.{k}" for k in _CELL_NAMES])


def _sigmas(items, values, table, ip: int, n_atoms: int, cov) -> list[tuple]:
    """``(σ_full, σ_diagonal)`` per item, or ``(None, None)`` without a covariance.

    σ² = gᵀ·Cov·g with g the row of ∂(value)/∂p over the phase's coordinate and
    cell entries — the same partials the Jacobian chains through the affine
    constraint block, so a coordinate refined as a site-symmetry DOF propagates
    through its tie rather than around it.

    ``cov`` is the pair (full, diagonal-only), both built by
    ``ParameterTable.physical_covariance`` — the second by handing it no
    correlation matrix, which is exactly §10's "just the diagonal elements".
    What is zeroed is the **refined parameters'** correlation, not the entry
    covariance: a crystal-system tie or a site-symmetry DOF is a constraint
    rather than a correlation, and dropping it would compare against a number
    nobody computes.  With uncorrelated parameters the two therefore agree
    exactly, which is what the test asserts.

    A row whose variance comes out zero — or only as far above zero as
    :data:`VARIANCE_CANCELLATION_FLOOR` allows — reports ``None``.  Either it
    touches nothing that was refined (every coordinate symmetry-fixed, the
    cell held: fluorite) or symmetry holds it fixed while its individual
    partials do not vanish (rutile's 90° O–Ti–O).  That is
    ``weight_fractions``' rule — an all-zero block is absence of information,
    never σ = 0 — with the cancelling case counted as the same thing, because
    it is.

    A fifth way to have no number arrived with WP-1110 item 14: a row drawing
    on an entry that was refined and **measured nothing**.  Its column is
    zeroed in ``Cov_free`` rather than carried as the infinity it is, since one
    infinity NaNs every product against a zero coefficient — so without the
    mask such a row reports the variance of its *other* sources and reads as a
    measurement.  A row whose partials touch nothing blind is unaffected, which
    is the case that matters: an unmeasured profile term must not cost a bond
    length its esd.
    """
    if not items:
        return []
    if cov is None:
        return [(None, None)] * len(items)
    cov_full, cov_diag, blind = cov
    compiled = CompiledRestraints(items=items)
    gross_rows = np.zeros((compiled.n_rows, len(table.entries)), dtype=np.float64)
    rows = restraint_partials(compiled, values, table, gross=gross_rows)
    cols = [table._paths[p] for p in _phase_paths(ip, n_atoms)]
    g = rows[:, cols]
    var_full = np.einsum("ra,ab,rb->r", g, cov_full, g)
    var_diag = np.einsum("ra,ab,rb->r", g, cov_diag, g)
    # the quadratic form's absolute terms, with a row's partials taken gross
    # (before two images of one atom cancel): a torsion fixed by symmetry has
    # roundoff for every net partial, and a floor scaled by those is roundoff
    # too.  Every other kind's gross row is |g|, the scale this always had.
    gross = gross_rows[:, cols]
    scale = np.einsum("ra,ab,rb->r", gross, np.abs(cov_full), gross)
    floor = VARIANCE_CANCELLATION_FLOOR * scale
    touches_blind = (np.abs(g[:, blind]) > 0.0).any(axis=1) if blind.any() \
        else np.zeros(len(items), dtype=bool)
    return [(None, None) if (b or f <= max(fl, 0.0)) else
            (math.sqrt(f), math.sqrt(max(float(d), 0.0)))
            for f, d, fl, b in zip(var_full, var_diag, floor, touches_blind,
                                   strict=True)]


def _covariance(table, theta, ip: int, n_atoms: int, stderr_internal,
                correlation):
    """``(full, diagonal-only, blind)`` over phase ``ip``'s entries, or None."""
    if stderr_internal is None:
        return None
    paths = _phase_paths(ip, n_atoms)
    return (table.physical_covariance(theta, stderr_internal, correlation, paths),
            table.physical_covariance(theta, stderr_internal, None, paths),
            table.unmeasured_rows(theta, stderr_internal,
                                  [table._paths[q] for q in paths]))


def _torsion_row(ip: int, labels, item: _Torsion, codes, values, sigma):
    from ..schemas.results import GeometryTorsion

    angle, _ = _torsion_geometry_np(item, values)
    a, b, c, d = item.atoms
    sig, sig_d = sigma
    return GeometryTorsion(
        phase_index=ip, atom_1=labels[a], atom_2=labels[b], atom_3=labels[c],
        atom_4=labels[d], atom_index_1=a, atom_index_2=b, atom_index_3=c,
        atom_index_4=d, angle=angle, stderr=sig, stderr_diagonal=sig_d,
        symmetry_1=codes[0], symmetry_2=codes[1], symmetry_3=codes[2],
        symmetry_4=codes[3])


def geometry_table(model, table, theta: np.ndarray, structure, *,
                   stderr_internal=None, correlation=None):
    """The converged model's distances, angles and torsions, or ``None``.

    ``None`` outside Rietveld mode, where the mandatory dummy atom of a Le Bail
    or Pawley phase is not a structure to measure — and ``None`` with no phase
    at all (WP-1207), for the same reason one rank up: an empty table reads as
    "the geometry was measured and this structure has no bonds", which is a
    claim about a structure that is not there.  Without ``stderr_internal``
    (a replay, an evaluate-only pass) the geometry is still reported and every
    esd is ``None`` — the values are recomputable from the model, the
    covariance is not.
    """
    if model.mode != "rietveld" or not model.phases:
        return None
    return geometry_from_sites([cp.sites for cp in model.phases], table, theta,
                               structure, stderr_internal=stderr_internal,
                               correlation=correlation)


def geometry_from_sites(sites_of, table, theta: np.ndarray, structure, *,
                        stderr_internal=None, correlation=None):
    """:func:`geometry_table` over each phase's frozen orbit subsets.

    ``sites_of[ip]`` is phase ``ip``'s :class:`~rietx.crystallography.
    structure_factor.PhaseSites`; a compiled model's when there is one, and
    ``compile_phase_sites`` of the phase where there is not
    (:meth:`~rietx.Refinement.geometry` with no live fit).
    """
    from ..schemas.results import GeometryAngle, GeometryDistance, GeometryTable

    values = table.decode(theta)
    notes: list[str] = []
    distances: list[GeometryDistance] = []
    angles: list[GeometryAngle] = []
    torsions: list = []
    for ip, sites in enumerate(sites_of):
        phase = structure.phases[ip]
        if sites.n_asym > MAX_ASYM_ATOMS:
            notes.append(f"{phase.name}: {sites.n_asym} asymmetric-unit atoms "
                         f"exceeds the {MAX_ASYM_ATOMS}-atom search limit; no "
                         "geometry listed for this phase")
            continue
        labels, bonds, contacts, angle_rows, torsion_rows = _phase_items(
            phase, sites, values, ip, notes)
        n_atoms = len(phase.atoms)
        cov = _covariance(table, theta, ip, n_atoms, stderr_internal, correlation)
        pairs = ([(i, e, True) for i, e in bonds]
                 + [(i, e, False) for i, e in contacts])
        pair_items = [_bond_item(ip, i, e) for i, e, _ in pairs]
        angle_items = [_angle_item(ip, v, a, b) for v, a, b in angle_rows]
        pair_sigma = _sigmas(pair_items, values, table, ip, n_atoms, cov)
        angle_sigma = _sigmas(angle_items, values, table, ip, n_atoms, cov)
        for (i, entry, is_bond), (sig, sig_d) in zip(pairs, pair_sigma,
                                                     strict=True):
            j, _rot, _tran, _shift, d, code = entry
            distances.append(GeometryDistance(
                phase_index=ip, atom_1=labels[i], atom_2=labels[j],
                atom_index_1=i, atom_index_2=j,
                distance=d, stderr=sig, stderr_diagonal=sig_d,
                symmetry_2=code, bonded=is_bond))
        for (v, a, b), item, (sig, sig_d) in zip(angle_rows, angle_items,
                                                 angle_sigma, strict=True):
            degrees = _angle_degrees(item, values)
            if min(degrees, 180.0 - degrees) < ANGLE_LINEARISATION_LIMIT_DEG:
                sig = sig_d = None
            angles.append(GeometryAngle(
                phase_index=ip, atom_1=labels[a[0]], atom_2=labels[v],
                atom_3=labels[b[0]], atom_index_1=a[0], atom_index_2=v,
                atom_index_3=b[0], angle=degrees,
                stderr=sig, stderr_diagonal=sig_d,
                symmetry_1=a[5], symmetry_3=b[5]))
        torsion_sigma = _sigmas([it for it, _ in torsion_rows], values, table,
                                ip, n_atoms, cov)
        for (item, codes), sigma in zip(torsion_rows, torsion_sigma, strict=True):
            torsions.append(_torsion_row(ip, labels, item, codes, values, sigma))
    return GeometryTable(distances=distances, angles=angles, torsions=torsions,
                         bond_slack=BOND_SLACK_ANG, contact_max=CONTACT_MAX_ANG,
                         notes=notes)


# ----------------------------------------------------------------------
# the cell volume (WP-1933)
# ----------------------------------------------------------------------
def _volume_and_gradient(a, b, c, alpha, beta, gamma) -> tuple[float, np.ndarray]:
    """V and ∂V/∂(a, b, c, α, β, γ), the angles in degrees.

    V = abc·√(1 − cos²α − cos²β − cos²γ + 2 cosα cosβ cosγ) (Giacovazzo et
    al. 2011, *Fundamentals of Crystallography*, 3rd ed., eq. 2.1).
    """
    ca, cb, cg = (math.cos(math.radians(x)) for x in (alpha, beta, gamma))
    root = math.sqrt(1.0 - ca * ca - cb * cb - cg * cg + 2.0 * ca * cb * cg)
    v = a * b * c * root
    per_degree = math.pi / 180.0
    # ∂root/∂α = sinα (cosα − cosβ cosγ) / root, and likewise for β and γ
    grad = np.array([
        v / a, v / b, v / c,
        *(a * b * c * math.sin(math.radians(x)) * (cx - cy * cz) / root * per_degree
          for x, cx, cy, cz in ((alpha, ca, cb, cg), (beta, cb, ca, cg),
                                (gamma, cg, ca, cb)))])
    return v, grad


def cell_volumes(table, theta: np.ndarray, structure, *,
                 stderr_internal=None, correlation=None):
    """Each phase's cell volume, its esd through the cell covariance.

    σ²(V) = gᵀ·Cov·g with g = ∂V/∂(a, b, c, α, β, γ), the covariance built by
    ``ParameterTable.physical_covariance`` over the six cell entries, so a tie
    (b ← a) and a correlation both reach it (McCusker et al. 1999 § 10).  An esd
    is ``None`` on the terms :func:`_sigmas` states: no covariance, nothing
    refined, a cancelling variance, or a source that measured nothing.  Every
    mode, since the cell of a Le Bail or Pawley fit is refined as surely as a
    Rietveld one's.
    """
    from ..schemas.results import CellVolume

    values = table.decode(theta)
    out = []
    for ip in range(len(structure.phases)):
        paths = [f"phases.{ip}.cell.{k}" for k in _CELL_NAMES]
        v, g = _volume_and_gradient(*(values[p] for p in paths))
        sig = sig_d = None
        if stderr_internal is not None:
            full = table.physical_covariance(theta, stderr_internal, correlation, paths)
            diag = table.physical_covariance(theta, stderr_internal, None, paths)
            blind = table.unmeasured_rows(theta, stderr_internal,
                                          [table._paths[q] for q in paths])
            var = float(g @ full @ g)
            floor = VARIANCE_CANCELLATION_FLOOR * float(np.abs(g) @ np.abs(full) @ np.abs(g))
            if not (np.abs(g[blind]) > 0.0).any() and var > max(floor, 0.0):
                sig = math.sqrt(var)
                sig_d = math.sqrt(max(float(g @ diag @ g), 0.0))
        out.append(CellVolume(phase_index=ip, volume=v, stderr=sig,
                              stderr_diagonal=sig_d))
    return out


# ----------------------------------------------------------------------
# a request: particular distances, angles and torsions (WP-1815)
# ----------------------------------------------------------------------
def _parse_code(code: str, symops, what: str) -> tuple[np.ndarray, np.ndarray]:
    """(R, t + n) of a CIF ``n_klm`` code (``.`` the identity), or raise."""
    if code == ".":
        return np.eye(3), np.zeros(3)
    parts = code.split("_")
    if (len(parts) != 2 or not parts[0].isdigit() or len(parts[1]) != 3
            or not parts[1].isdigit()):
        raise ValueError(f"{what}: symmetry code {code!r} is not of the CIF form "
                         "'n_klm' (operation n, lattice shift k-5, l-5, m-5)")
    n = int(parts[0])
    if not 1 <= n <= len(symops):
        raise ValueError(f"{what}: symmetry code {code!r} names operation {n}, "
                         f"but the space group lists {len(symops)}")
    rot, tran = symops[n - 1]
    return rot, tran + np.array([int(ch) - 5 for ch in parts[1]], dtype=np.float64)


def request_table(request, sites_of, table, theta: np.ndarray, structure, *,
                  stderr_internal=None, correlation=None):
    """The rows ``request`` names, as a :class:`GeometryTable`.

    Each atom is placed by its CIF code where one is given, and otherwise at
    the image nearest the atom it is measured from (``restraints.
    _resolve_image``, the minimum image a restraint takes): a distance's
    second atom from its first, an angle's two arms from the vertex, a
    torsion's B, C and D each from the atom before it.  The first atom of a
    distance or a torsion and an angle's vertex sit where they are stored
    unless coded.  esds are :func:`geometry_table`'s, through the same
    partials and the same floor, so a requested row the table also lists
    carries the same numbers.  A torsion whose chain has a straight bond
    angle has none, and is named in ``notes`` rather than listed.
    """
    from ..schemas.results import (
        GeometryAngle,
        GeometryDistance,
        GeometryRequest,
        GeometryTable,
    )

    if not isinstance(request, GeometryRequest):
        request = GeometryRequest.model_validate(request)
    ip = request.phase_index
    if not 0 <= ip < len(structure.phases):
        raise ValueError(f"geometry request names phase {ip}, but the structure "
                         f"has {len(structure.phases)} phase(s)")
    phase, sites = structure.phases[ip], sites_of[ip]
    values = table.decode(theta)
    cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_NAMES)
    g = _metric_g(cell)
    symops = _symop_table(resolve_group(phase.space_group,
                                        phase.symmetry_operations))
    labels = [a.label for a in phase.atoms]
    index = {}
    for j, lab in enumerate(labels):
        index.setdefault(lab, []).append(j)
    elements = [_element(a.species) for a in phase.atoms]
    radii = [float(e.covalent_r) for e in elements]
    metal = [bool(e.is_metal) for e in elements]
    x = [_xyz_np(values, ip, j) for j in range(len(labels))]

    def atom_of(ref, what: str) -> tuple[int, str | None]:
        lab, code = (ref, None) if isinstance(ref, str) else ref
        hits = index.get(lab, [])
        if len(hits) != 1:
            raise ValueError(
                f"{what}: phase {phase.name!r} has "
                f"{'no atom' if not hits else f'{len(hits)} atoms'} labelled {lab!r}")
        return hits[0], code

    def place(ref, reference, what: str):
        """(j, R, t + n, code) for one atom, relative to ``reference`` (a
        position) or at its stored site when ``reference`` is None."""
        j, code = atom_of(ref, what)
        if code is not None:
            rot, tran = _parse_code(code, symops, what)
            return j, rot, tran, code
        if reference is None:
            return j, np.eye(3), np.zeros(3), "."
        rot, tran, shift = _resolve_image(sites, j, reference, x[j], None,
                                          (0, 0, 0), g)
        return j, rot, tran + shift, _symmetry_code(_symop_index(symops, rot, tran),
                                                    shift)

    def relative(anchor, other):
        """``other``'s map seen from ``anchor``'s frame: anchor⁻¹ ∘ other."""
        _ja, ra, ta, _ca = anchor
        _jo, ro, to, _co = other
        inv = np.linalg.inv(ra)
        return inv @ ro, inv @ (to - ta)

    def pos(p):
        return p[1] @ x[p[0]] + p[2]

    n_atoms = len(phase.atoms)
    cov = _covariance(table, theta, ip, n_atoms, stderr_internal, correlation)
    notes: list[str] = []
    zero = np.zeros(3)

    pairs, pair_items = [], []
    for k, (r1, r2) in enumerate(request.distances):
        what = f"distance {k}"
        p1 = place(r1, None, what)
        p2 = place(r2, pos(p1), what)
        rot, tran = relative(p1, p2)
        pairs.append((p1, p2))
        pair_items.append(_Bond(ip, p1[0], p2[0], rot, tran, zero,
                                target=0.0, sigma=1.0, weight=1.0))
    distances = []
    for (p1, p2), item, (sig, sig_d) in zip(
            pairs, pair_items, _sigmas(pair_items, values, table, ip, n_atoms, cov),
            strict=True):
        i, j = p1[0], p2[0]
        d = math.sqrt(max(float((pos(p2) - pos(p1)) @ g @ (pos(p2) - pos(p1))), 0.0))
        distances.append(GeometryDistance(
            phase_index=ip, atom_1=labels[i], atom_2=labels[j], atom_index_1=i,
            atom_index_2=j, distance=d, stderr=sig, stderr_diagonal=sig_d,
            symmetry_1=p1[3] or "?", symmetry_2=p2[3],
            bonded=(d <= radii[i] + radii[j] + BOND_SLACK_ANG
                    and not (DEMOTE_METAL_METAL and metal[i] and metal[j]))))

    triples, angle_items = [], []
    for k, (r1, rv, r3) in enumerate(request.angles):
        what = f"angle {k}"
        pv = place(rv, None, what)
        p1 = place(r1, pos(pv), what)
        p3 = place(r3, pos(pv), what)
        (r_1, t_1), (r_3, t_3) = relative(pv, p1), relative(pv, p3)
        triples.append((p1, pv, p3))
        angle_items.append(_Angle(ip, p1[0], pv[0], p3[0], r_1, t_1, zero,
                                  r_3, t_3, zero, target_deg=0.0, sigma=1.0,
                                  weight=1.0))
    angles = []
    for (p1, pv, p3), item, (sig, sig_d) in zip(
            triples, angle_items,
            _sigmas(angle_items, values, table, ip, n_atoms, cov), strict=True):
        degrees = _angle_degrees(item, values)
        if min(degrees, 180.0 - degrees) < ANGLE_LINEARISATION_LIMIT_DEG:
            sig = sig_d = None
        angles.append(GeometryAngle(
            phase_index=ip, atom_1=labels[p1[0]], atom_2=labels[pv[0]],
            atom_3=labels[p3[0]], atom_index_1=p1[0], atom_index_2=pv[0],
            atom_index_3=p3[0], angle=degrees, stderr=sig, stderr_diagonal=sig_d,
            symmetry_1=p1[3], symmetry_2=pv[3] or "?", symmetry_3=p3[3]))

    torsion_rows = []
    for k, refs in enumerate(request.torsions):
        what = f"torsion {k}"
        placed = [place(refs[0], None, what)]
        for ref in refs[1:]:
            placed.append(place(ref, pos(placed[-1]), what))
        item = _Torsion(ip, [p[0] for p in placed], [p[1] for p in placed],
                        [p[2] for p in placed], [zero] * 4, 0.0, 1.0, 1.0)
        if not _torsion_defined(item, values):
            notes.append(f"{what} ({'-'.join(labels[p[0]] for p in placed)}): a "
                         "bond angle of the chain is straight, so it has no "
                         "torsion and is not listed")
            continue
        torsion_rows.append((item, tuple(p[3] for p in placed)))
    torsions = [
        _torsion_row(ip, labels, item, codes, values, sigma)
        for (item, codes), sigma in zip(
            torsion_rows,
            _sigmas([it for it, _ in torsion_rows], values, table, ip, n_atoms, cov),
            strict=True)]
    return GeometryTable(distances=distances, angles=angles, torsions=torsions,
                         bond_slack=BOND_SLACK_ANG, contact_max=CONTACT_MAX_ANG,
                         notes=notes)
