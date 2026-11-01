"""The magnetic structure factor of a powder reflection, and its Laue-orbit average.

For a reflection at Q (FullProf manual eqs 3.47-3.50; Halpern & Johnson, 1939,
*Phys. Rev.* **55**, 898, for the interaction vector):

    F_m(Q) = p · Σ_j occ_j · f_j(s) · T_j · Σ_s ε_s·det(R_s)·R_s·m_j
                                            · exp(2πi Q·(R_s x_j + t_s))
    I_mag ∝ ⟨ |F_m|² − |Q̂·F_m|² ⟩          p = γr₀/2 = 0.2695×10⁻¹² cm / μ_B

s runs over the magnetic operators, ε_s = ±1 is the operator's time-reversal
sign, and det(R_s)·R_s is the action on an *axial* vector.  Only the component
of F_m perpendicular to Q scatters, which is the ``− |Q̂·F_m|²``.

**Three things this expression is easy to get wrong, and what stops each.**

*The axial action.*  hkl transforms by Rᵀ, a tensor by R·U·Rᵀ, and a moment by
det(R)·R with ε on top.  The transposed set is a group too, so a dimension
count passes with the wrong action in every crystal system; the guard is a
*span* test on a known moment, and it lives one module over in
:func:`~rietx.crystallography.magnetic.operators.in_span`.  Nothing here builds
a second axial action: the per-operation matrices are M-5's
``MagneticOperator.moment_matrix()``, resolved onto the **nuclear** operation
subset so the magnetic orbit and the nuclear one are literally the same
positions.

*The orbit average.*  |F_⊥|² is **not** constant over the nuclear Laue orbit of
Q, because the moment direction breaks the Laue symmetry.  "One representative
times the multiplicity" — which is right for |F_N|² — is wrong here, and it is
wrong in a way that only shows on a non-collinear or low-symmetry structure, so
it survives a cubic test.  This module therefore takes the average over the
whole orbit (Friedel mates included), the same shape ``structure_factors_
squared`` takes for the ±h average under dispersion, and the same frozen
``orbit_layout`` the March-Dollase correction already averages over.  After
that average a cubic collinear structure's intensity is independent of the
moment direction (Shirane, 1959, *Acta Cryst.* **12**, 282) — which is a
*result* here, measured to fp64 in the tests, not an assumption.

*The units.*  p = 2.695 fm per μ_B and a Sears b in fm, so p·m and b are the
same unit and |F_m|² adds to |F_N|² under **one** scale.  A separate magnetic
scale is the easiest route to a plausible fit and a wrong moment, and it is not
offered.

**What is frozen per stage** (:class:`MagneticSites`): the operation subset and
its ε·det(R)·R matrices, the form-factor coefficients, g, and the moment frame.
What moves with θ: the coordinates, the occupancies, the Debye-Waller factors,
the cell (hence the crystal-axis→Cartesian matrix and Q̂), and the moment DOFs.
That is the same split ``PhaseSites.f_anom`` takes one module over.

References
----------
* Halpern, O. & Johnson, M. H. (1939). *Phys. Rev.* **55**, 898 — the magnetic
  interaction vector.
* Shirane, G. (1959). *Acta Cryst.* **12**, 282 — what a powder average
  determines of a moment direction.
* Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
  manual's eqs 3.47-3.54 are the form above.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import gemmi
import numpy as np

from ..adp import cartesian_basis
from ..symmetry import SITE_TOL, ReflectionSet, as_group, generate_reflections
from .form_factor import approximation_name, j0, j2, resolve_g
from .moments import moment_frame, moment_from_dofs

#: p = γ·r₀/2, the magnetic scattering length of one Bohr magneton, in **fm**
#: — the unit ``crystallography.neutron``'s Sears table gives b in, which is
#: what lets |F_m|² and |F_N|² share one scale (issue #257 A6 iv).  0.2695 ×
#: 10⁻¹² cm is 2.695 fm; the two spellings are the same number and the fm one
#: is the one this package computes in.
P_MAGNETIC_FM = 2.695

#: The source kinds whose histograms carry the magnetic term, and the ones that
#: do not.  One table, two readers: ``model.forward.magnetic_wanted`` dispatches
#: on it (and refuses a kind in neither set by name), and
#: ``capabilities.RadiationCapability.magnetic_scattering`` is derived from it,
#: so the arm a client reads cannot disagree with what the forward model does.
#: A neutron couples to the magnetization density through its own moment; an
#: X-ray of a laboratory or ordinary synchrotron experiment does not, to many
#: orders of magnitude.
MAGNETIC_SOURCE_KINDS = frozenset({"neutron_cw"})
NON_MAGNETIC_SOURCE_KINDS = frozenset({"xray_cw"})


@dataclass
class MagneticSites:
    """Frozen magnetic data for one phase, beside :class:`PhaseSites`.

    ``mom_mat[j]`` is ``(m_j, 3, 3)``: for each operation of atom ``j``'s
    frozen nuclear subset, the axial action ε·det(R)·R that carries the
    asymmetric-unit moment onto that image.  Resolved by matching the nuclear
    operation's (R, t mod 1) against the magnetic group, so image *k* of the
    magnetic model is image *k* of the nuclear one — not a parallel orbit that
    could drift out of correspondence.

    ``carries[j]`` says whether atom ``j`` has a moment at all; a phase may mix
    magnetic and non-magnetic sites, and the non-magnetic ones contribute
    nothing to F_m while still contributing to F_N.
    """

    mom_mat: list[np.ndarray | None]
    #: the *nuclear* operation subsets, ``PhaseSites.ops`` — carried by
    #: reference rather than copied, so image k here is image k there by
    #: construction and no correspondence has to be maintained
    ops: list[tuple[np.ndarray, np.ndarray]]
    frames: list[np.ndarray | None]
    ions: list[str | None]
    g_factors: list[float | None]
    #: per-atom name of the approximation in force, for the report
    approximations: list[str | None]
    #: (n_asym,) bool, ``carries[j] == (mom_mat[j] is not None)``
    carries: list[bool] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.carries:
            self.carries = [m is not None for m in self.mom_mat]

    @property
    def n_asym(self) -> int:
        return len(self.mom_mat)

    def n_dofs(self, j: int) -> int:
        frame = self.frames[j]
        return 0 if frame is None else len(frame)

    def named_approximations(self) -> dict[str, str]:
        """``{ion: approximation}`` for every magnetic species of the phase."""
        return {ion: name for ion, name in zip(self.ions, self.approximations,
                                               strict=True)
                if ion is not None and name is not None}


def compile_magnetic_sites(phase, ops) -> MagneticSites | None:
    """Freeze the per-atom magnetic data for one stage, or ``None`` if there is none.

    ``ops`` is ``PhaseSites.ops`` — the *nuclear* operation subsets, already
    chosen so each site's orbit images appear exactly once.  Every one of those
    images must be reachable by an operation of the magnetic group, and the
    axial matrix stored for it is that operation's ε·det(R)·R (M-5's
    ``MagneticOperator.moment_matrix``, never a second implementation).

    **The match is on the image, not on the operation**, and that is what lets
    a magnetic space group with *fewer* rotations than the nuclear one be
    stated at all — the case every cubic collinear antiferromagnet is.  There
    the magnetic order picks out one axis, its magnetic group is a tetragonal
    or rhombohedral subgroup of the cubic parent, and the crystal breaks into
    domains; each nuclear image still gets one moment, because the magnetic
    group's orbit of the site still covers the nuclear orbit.  The domain
    average is then the Laue-orbit average this module already takes —
    measured by the isotropy rung (M-7 arm F): the domain sum over a complete
    shell is a constant multiple of the single-domain sum, to 1e-9 relative.

    Where the magnetic orbit is genuinely *smaller* than the nuclear one, some
    nuclear atoms have no moment the stated group determines, and that is
    refused by name: the structure has to be stated in the magnetic space
    group's own asymmetric unit, which is what a magCIF gives.
    """
    if phase.magnetic_symmetry is None:
        return None
    if not any(a.moment is not None for a in phase.atoms):
        return None
    group = phase.magnetic_symmetry.group()
    cell = phase.cell.lengths_angles()
    mom_mat: list[np.ndarray | None] = []
    frames: list[np.ndarray | None] = []
    ions: list[str | None] = []
    gs: list[float | None] = []
    names: list[str | None] = []
    for j, atom in enumerate(phase.atoms):
        if atom.moment is None:
            mom_mat.append(None)
            frames.append(None)
            ions.append(None)
            gs.append(None)
            names.append(None)
            continue
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        rot, tran = ops[j]
        mom_mat.append(_axial_matrices(group, xyz, rot, tran,
                                       phase.name, atom.label))
        frames.append(moment_frame(group.allowed_moment_basis(xyz), cell))
        ions.append(atom.moment.ion)
        gs.append(resolve_g(atom.moment.ion, atom.moment.g))
        names.append(approximation_name(atom.moment.ion, atom.moment.g))
    return MagneticSites(mom_mat=mom_mat, ops=list(ops), frames=frames,
                         ions=ions, g_factors=gs, approximations=names)


#: |RᵀGR − G| / max|G| above which a magnetic operation is not a symmetry of
#: the cell.  Every consistent phase measured on issue #597 sits at ≤ 1e-16
#: and the wrong-setting ones at 0.43-0.52; 1e-3 (≈ 0.06° on an angle) leaves
#: room for a cell copied from a file to a few decimals.
METRIC_TOL = 1e-3
#: fractional-coordinate tolerance for matching an image to an atom of the
#: compiled structure.  Looser than ``SITE_TOL``: two atoms the magnetic group
#: relates may be listed separately in a file at four decimals.
INVARIANCE_POS_TOL = 1e-3
#: moment tolerance for the same match, μ_B, relative to max(1, |m|)
INVARIANCE_MOMENT_TOL = 1e-3


def group_symmetry_violations(phase, ops) -> list[str]:
    """Why the declared magnetic group is not a symmetry of ``phase``, or ``[]``.

    A magnetic space group is a symmetry *of the structure it decorates*: its
    operations must map the lattice onto itself and the compiled set of atoms
    — every nuclear image of every atom, with its species, occupancy, B and,
    on a moment carrier, the moment ``mom_mat`` assigns it — onto itself, with
    the axial action ε·det(R)·R on the moment.  :func:`_axial_matrices` asks
    only the converse (every nuclear image is reached by *some* magnetic
    operation, first match wins), and that is satisfied by a group that is not
    a symmetry at all: a type-IV group by number beside the symbol of its
    unprimed operations (the anti-translated atom does not exist), a BNS
    number beside a nuclear group in the other origin choice (the moments come
    out of a different group), a b-unique group on a c-unique cell (issue
    #597).  Each compiles a different structure from the one the group
    describes, with no diagnostic.

    Two predicates, both needed:

    1. **lattice metric** RᵀGR = G for every operation.  Catches the
       wrong-setting cell even when every atom sits where the wrong operation
       happens to map it onto itself (a magnetic atom alone on an inversion
       centre);
    2. **structure invariance** of the compiled set, above.

    Not "every magnetic operation with ε dropped is a nuclear operation": the
    supercell builder lists the anti-translated copies as independent sites
    under the parent's group, which fails that test on every phase it builds
    and is right.

    ``ops`` is ``PhaseSites.ops``.  Returns at most a handful of messages
    (the first few violations, then a count); an image no magnetic operation
    reaches is :func:`_axial_matrices`' refusal, not this one's.
    """
    group = phase.magnetic_symmetry.group()
    cell = phase.cell.lengths_angles()
    basis = np.asarray(cartesian_basis(*cell), dtype=np.float64)
    metric = basis.T @ basis
    scale = float(np.max(np.abs(metric)))
    all_ops = group.all_operations()
    out: list[str] = []
    for op in all_ops:
        r = np.asarray(op.rotation, dtype=np.float64)
        dev = float(np.max(np.abs(r.T @ metric @ r - metric))) / scale
        if dev > METRIC_TOL:
            out.append(
                f"the operation {op.xyz()} does not map the cell "
                f"{tuple(round(v, 4) for v in cell)} onto itself "
                f"(|RᵀGR − G|/|G| = {dev:.2g}), so the group is in a "
                f"different setting from the cell")
            return out
    # the compiled structure: one row per nuclear image of every atom
    pos, owner, mom = [], [], []
    for j, atom in enumerate(phase.atoms):
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        rot, tran = ops[j]
        rot = np.asarray(rot, dtype=np.float64)
        tran = np.asarray(tran, dtype=np.float64)
        images = (np.einsum("mij,j->mi", rot, xyz) + tran) % 1.0
        if atom.moment is not None:
            try:
                mats = _axial_matrices(group, xyz, rot, tran, phase.name,
                                       atom.label)
            except ValueError:
                return out          # compile refuses this one by name
            moments = mats @ np.asarray(atom.moment.values(), dtype=np.float64)
        else:
            moments = np.full((len(images), 3), np.nan)
        pos.append(images)
        mom.append(moments)
        owner.extend([j] * len(images))
    pos = np.concatenate(pos)
    mom = np.concatenate(mom)
    owner = np.asarray(owner)
    keys = [(a.species, a.occ.value, a.biso.value) for a in phase.atoms]
    species = np.array([[ka[0] == kb[0] for kb in keys] for ka in keys])
    same = np.array([[ka[0] == kb[0] and abs(ka[1] - kb[1]) <= 1e-4
                      and abs(ka[2] - kb[2]) <= 1e-4 for kb in keys]
                     for ka in keys])[owner][:, owner]          # (n, n)
    species = species[owner][:, owner]
    carries = ~np.isnan(mom[:, 0])
    m_tol = INVARIANCE_MOMENT_TOL * np.maximum(
        1.0, np.linalg.norm(np.where(carries[:, None], mom, 0.0), axis=1))
    n_bad = 0
    block = 256
    for op in all_ops:
        r = np.asarray(op.rotation, dtype=np.float64)
        t = np.array([float(c) for c in op.translation])
        moved = (pos @ r.T + t) % 1.0
        moved_m = mom @ op.moment_matrix().T
        for lo in range(0, len(pos), block):
            sl = slice(lo, lo + block)
            delta = np.abs(moved[sl, None, :] - pos[None, :, :])
            at = np.all(np.minimum(delta, 1.0 - delta) <= INVARIANCE_POS_TOL,
                        axis=2)
            near = at & same[sl]
            dist = np.linalg.norm(mom[None, :, :] - moved_m[sl, None, :], axis=2)
            good_m = near & carries[None, :] & (dist <= m_tol[sl, None])
            ok = np.where(carries[sl], good_m.any(axis=1), near.any(axis=1))
            for i in lo + np.flatnonzero(~ok):
                n_bad += 1
                if len(out) >= 3:
                    continue
                hits = np.flatnonzero(near[i - lo])
                if hits.size == 0:
                    other = np.flatnonzero(at[i - lo] & species[i])
                    problem = ("there is no such atom in the structure"
                               if other.size == 0 else
                               f"the {phase.atoms[owner[other[0]]].label!r} "
                               f"there has another occupancy or B")
                else:
                    h = hits[0]
                    have = (np.round(mom[h], 3).tolist() if carries[h]
                            else "no moment")
                    problem = (f"the group puts the moment "
                               f"{np.round(moved_m[i], 3).tolist()} μ_B there "
                               f"where the structure has {have}")
                atom = phase.atoms[owner[i]]
                out.append(
                    f"{op.xyz()} sends the image of {atom.label!r} "
                    f"({atom.species}) at {np.round(pos[i], 4).tolist()} to "
                    f"{np.round(moved[i], 4).tolist()}, and {problem}")
    if n_bad > len(out):
        out.append(f"... {n_bad} (image, operation) pairs in all")
    return out


def check_group_is_structure_symmetry(phase) -> None:
    """Raise ``ValueError`` naming why the magnetic group is not a symmetry.

    The refusal :func:`group_symmetry_violations` describes, for a phase with
    moments and a ``magnetic_symmetry``; anything else returns.

    Runs where a **statement** enters: the readers (magCIF, TOPAS, FullProf)
    and ``Refinement.__init__``.  Never as a ``Phase`` validator and never at
    compile: atoms the group relates but the caller listed separately (the
    supercell builder's anti-translated copies, explicit copies in a file) move
    apart once their B, occupancy or coordinates are freed, so a refined phase
    is not a statement and must still validate and read back (review of #620).
    """
    if phase.magnetic_symmetry is None:
        return
    if not any(a.moment is not None for a in phase.atoms):
        return
    from ..structure_factor import select_orbit_ops
    from ..symmetry import resolve_group

    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    ops = [select_orbit_ops(sg, np.array([a.x.value, a.y.value, a.z.value]))
           for a in phase.atoms]
    problems = group_symmetry_violations(phase, ops)
    if not problems:
        return
    raise ValueError(
        f"phase {phase.name!r}: the declared magnetic symmetry is not a "
        f"symmetry of the structure it decorates (space group "
        f"{phase.space_group!r}, cell and atoms as stated): "
        + "; ".join(problems)
        + ". A magnetic space group has to map the lattice and every atom, "
        "with its moment, onto itself, or the forward model computes a "
        "different structure from the one the group describes. Usual causes: "
        "a type-IV group (anti-translation) by number beside the nuclear "
        "group of its unprimed operations — state the nuclear group with the "
        "translation in Phase.symmetry_operations, or list the translated "
        "atoms explicitly; a BNS number whose default setting (origin choice, "
        "cell choice, unique axis) is not the nuclear group's — pick the "
        "matching setting with operators.database_settings() and "
        "magnetic_group(..., hall_number=...), or give the operator list in "
        "the nuclear setting")


def _axial_matrices(group, xyz, rot, tran, phase_name, label) -> np.ndarray:
    """``(m, 3, 3)`` ε·det(R)·R, one per nuclear image of the site.

    Several magnetic operations may reach one image — the site's magnetic
    stabiliser — and using any one of them is correct for a *general*
    position: they all carry the moment to the same place, because that is
    exactly what makes the moment lie in the site's allowed subspace, which
    the schema has already checked.  On a **special** position this is not
    true of every matching operation individually — a stabiliser element
    whose axial matrix disagrees with the identity there is exactly what
    forces a moment component to zero (:func:`~.operators.
    allowed_moment_basis`) — but it is still true of the group's own
    identity operation, which always matches an atom's own (k=0, itself)
    image and is what this function must pick for that image. So "any one
    match" is really "the *first* match", by convention, not "any of them
    interchangeably" — see the note below on why that is safe.

    **Order (small-fixes-20260917, item 1).** "The first match" used to mean
    "whichever operation ``group.all_operations()`` happens to iterate to
    first" — a property of that tuple's *order*. Two callers that built the
    same group from the same operation *set* enumerated in a different
    order (``_candidate_group``'s seed dict, or ``_close_operations``'s
    closure-discovery order, both in ``isotropy.py``) used to get back a
    ``MagneticGroup`` whose ``all_operations()`` iterated in a different
    order, and Q23 measured this reach exactly this function: reordering
    could pick a different first match — and so a different sign — for an
    image with more than one stabiliser (measured on
    ``test_epsilon_bookkeeping.py::test_moment_path_is_clean_by_design``
    with an unordered ``set()`` in ``_close_operations``). This is now moot:
    ``operators.MagneticGroup.from_operations`` sorts canonically by
    ``(rotation, translation, time_reversal)`` before choosing coset
    representatives, so ``all_operations()`` is bit-identical for any input
    order of the same set, and "the first match" is now a property of the
    *image*, never of the caller's enumeration order (see
    ``tests/test_operator_order_independence.py``, which checks this
    end to end through ``compile_magnetic_sites``).
    """
    ops_all = group.all_operations()
    images = [op.act_on_site(xyz) for op in ops_all]
    mats = np.empty((len(rot), 3, 3), dtype=np.float64)
    for k, (r, t) in enumerate(zip(rot, tran, strict=True)):
        # wrapped like ``act_on_site``'s images: unwrapped, a coordinate one
        # cell or more away gives δ in (1, 2), where 1 − δ is negative and
        # "matches" every operation, so the first one won and an
        # anti-translated image got the untranslated moment (issue #597, the
        # shifted-origin supercell statements)
        want = (np.asarray(r, dtype=np.float64) @ xyz
                + np.asarray(t, dtype=np.float64)) % 1.0
        for op, image in zip(ops_all, images, strict=True):
            delta = np.abs(image - want)
            if np.all(np.minimum(delta, 1.0 - delta) <= SITE_TOL):
                mats[k] = op.moment_matrix()
                break
        else:
            raise ValueError(
                f"phase {phase_name!r} atom {label!r}: the nuclear space group "
                f"puts an image of this site at "
                f"{np.round(want % 1.0, 4).tolist()}, and no operation of the "
                f"declared magnetic symmetry sends the site there — so the "
                f"stated group does not determine a moment for that atom. "
                f"State the structure in the magnetic space group's own "
                f"asymmetric unit (and, for a k != 0 structure, in its "
                f"magnetic supercell), which is what a magCIF from MAGNDATA, "
                f"ISODISTORT or k-SUBGROUPSMAG already gives you")
    return mats


# ---------------------------------------------------------------------------
# the reflections a magnetic space group needs and a nuclear one does not
# ---------------------------------------------------------------------------
def magnetic_reflections(sg_symbol,
                         cell: tuple[float, float, float, float, float, float],
                         wavelength: float, two_theta_max: float,
                         two_theta_min: float = 0.0, *,
                         magnetic_group=None) -> ReflectionSet:
    """The reciprocal-lattice points the **nuclear** structure factor forbids.

    A k = 0 magnetic structure puts intensity exactly where the parent's glide
    and screw operations kill the nuclear structure factor, because its
    magnetic space group generally does not carry those operations — WP-1326
    measured it on Cr₂WO₆, whose two strongest 4 K residual peaks are the
    systematically absent (0 0 1) and (1 0 2).  Those reflections are **not in
    the nuclear reflection list at all**, so a magnetic phase needs them added
    or its strongest peaks are simply not computed.

    **A row is kept where the magnetic group's own lattice lets some member
    of its Laue orbit scatter.**  A pure translation (t, ε) of the magnetic
    group — an operation whose rotation is the identity — gives
    F_m(h) = ε·e^{2πi h·t}·F_m(h), so |F_m(h)|² is identically zero unless
    e^{2πi h·t} = ε: h·t ∈ ℤ for an ordinary translation, h·t ∈ ℤ + ½ for an
    anti-translation (the black-white lattices of the type-IV groups; Litvin,
    2013, *Magnetic Group Tables*, IUCr, § 1.3 on the BNS lattice types).  A
    row is a whole Laue orbit of the **parent**, and its intensity is the
    orbit average, so it is kept when **any** member hR of that orbit passes
    every such condition.  Two cases make the per-member test necessary, and
    a test on the parent's centrings alone wrong:

    * the magnetic lattice can be **primitive inside a centred parent** — a
      zone-boundary k such as (1, 0, 0) of an F or I lattice, stated in the
      parent's conventional cell with an integer k.  The parent's centrings
      are then not translations of the magnetic group at all, neither plain
      nor primed (the atoms they relate are reached by operations with a
      rotation), and the magnetic intensity sits on exactly the rows those
      centrings forbid;
    * a translation the magnetic group keeps need not be invariant under the
      parent's point group: (½, ½, 0) kept and (0, ½, ½), (½, 0, ½) primed is
      the fcc type-I antiferromagnet, and the orbit of (1 0 2) holds members
      that pass (h + k even) and members that fail.  Testing the
      representative alone dropped or kept the whole orbit by which member
      ``generate_reflections`` happened to list.

    ``magnetic_group=None`` applies every parent centring, the ordinary case;
    there the condition is the same for every member of an orbit, because a
    group's centring set is invariant under its own point group.

    Glide and screw absences are not applied.  The Laue multiplicity is the
    parent group's, because that is what makes two reflections coincide in a
    powder pattern; the fact that the *magnetic* symmetry is lower is exactly
    why the intensity is an orbit average rather than one representative's
    value.

    Magnetic absences are not applied either, and are not needed: |F_m|² is
    identically zero where the magnetic group forbids the reflection, so the
    extinction comes out of the arithmetic instead of a second table.
    """
    everything = generate_reflections(sg_symbol, cell, wavelength,
                                      two_theta_max=two_theta_max,
                                      two_theta_min=two_theta_min,
                                      apply_absences=False)
    allowed = generate_reflections(sg_symbol, cell, wavelength,
                                   two_theta_max=two_theta_max,
                                   two_theta_min=two_theta_min)
    keep = {tuple(map(int, h)) for h in allowed.hkl}
    mask = np.array([tuple(map(int, h)) not in keep for h in everything.hkl],
                    dtype=bool)
    if magnetic_group is None:
        centrings = applied_centrings(as_group(sg_symbol))
        if len(centrings) and len(everything):
            # h·t for every centring t, in 1/DEN units: integral iff divisible
            phase = everything.hkl.astype(np.int64) @ centrings.T
            mask &= np.all(phase % gemmi.Op.DEN == 0, axis=1)
    elif len(everything):
        mask &= lattice_allows_orbit(everything.hkl, as_group(sg_symbol),
                                     magnetic_group)
    return ReflectionSet(hkl=everything.hkl[mask],
                         multiplicity=everything.multiplicity[mask],
                         d=everything.d[mask],
                         spacegroup=everything.spacegroup,
                         operations=everything.operations)


def lattice_allows_orbit(hkl, group, magnetic_group) -> np.ndarray:
    """``(N,)`` bool — whether some member of each row's Laue orbit can scatter magnetically.

    ``hkl`` are representatives of Laue orbits of ``group`` (the parent); a
    member is h·R for each rotation R of the parent.  A member passes when,
    for every pure translation (t, ε) of ``magnetic_group``,
    e^{2πi h·t} = ε (:func:`magnetic_reflections` has the derivation).  All
    arithmetic is in gemmi's 1/``Op.DEN`` units, so the test is exact.
    """
    den = gemmi.Op.DEN
    identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    shifts, signs = [], []
    for op in magnetic_group.all_operations():
        if op.rotation != identity:
            continue
        t = tuple(int(round(float(c) * den)) % den for c in op.translation)
        if not any(t):
            continue
        shifts.append(t)
        signs.append(op.time_reversal)
    h = np.asarray(hkl, dtype=np.int64)
    if not shifts:
        return np.ones(len(h), dtype=bool)
    rotations = np.unique(np.array([np.asarray(op.rot, dtype=np.int64) // den
                                    for op in group.operations()]), axis=0)
    members = np.einsum("nj,rjk->nrk", h, rotations)          # (N, R, 3): h·R
    phase = (members @ np.array(shifts, dtype=np.int64).T) % den   # (N, R, m)
    want = np.where(np.array(signs) == 1, 0, den // 2)         # (m,)
    return np.any(np.all(phase == want, axis=2), axis=1)


def applied_centrings(group) -> np.ndarray:
    """``(n, 3)`` int — the parent's non-trivial centrings a nuclear-lattice row must obey.

    In gemmi's 1/``Op.DEN`` units: every centring translation of ``group``
    except the identity.  A magnetic group's own lattice, primed or
    anti-centred, is not read here; :func:`lattice_allows_orbit` applies it.
    """
    den = gemmi.Op.DEN
    kept = [tuple(int(c) % den for c in t)
            for t in group.operations().cen_ops]
    kept = [t for t in kept if any(t)]
    return np.array(kept, dtype=np.int64).reshape(-1, 3)


def merge_magnetic(nuclear: ReflectionSet, extra: ReflectionSet
                   ) -> tuple[ReflectionSet, np.ndarray]:
    """One reflection list carrying both, and the (N,) 1/0 nuclear mask.

    The same merge WP-1326 makes for satellites and for the same reason: every
    consumer downstream — the frozen windows, the FCJ node counts, the Le Bail
    partition, the Pawley block, the tick list, the observation count — is
    written over "the phase's reflections", and a magnetically-allowed lattice
    point is one of those.  What distinguishes them is the mask, which is
    **exact** rather than a tolerance: on those rows the nuclear structure
    factor is identically zero by the glide or screw condition, so masking it
    is the arithmetic the symmetry already implies and not an approximation.

    ``operations`` rides along with ``spacegroup`` onto the merged set: a phase
    whose group has no Hermann-Mauguin symbol carries it as an explicit
    operation list under a bracketed *label*, and a set holding the label
    without the list cannot be resolved by anything reading it back
    (``report.strain``, ``report.texture``).
    """
    if len(extra) == 0:
        return nuclear, np.ones(len(nuclear), dtype=np.float64)
    hkl = np.concatenate([nuclear.hkl.astype(np.int64), extra.hkl.astype(np.int64)])
    mult = np.concatenate([nuclear.multiplicity, extra.multiplicity])
    d = np.concatenate([nuclear.d, extra.d])
    nuc = np.concatenate([np.ones(len(nuclear)), np.zeros(len(extra))])
    sort = np.argsort(-d, kind="stable")
    merged = ReflectionSet(hkl=hkl[sort], multiplicity=mult[sort], d=d[sort],
                           spacegroup=nuclear.spacegroup,
                           operations=nuclear.operations,
                           extra=dict(nuclear.extra))
    return merged, nuc[sort].astype(np.float64)


# ---------------------------------------------------------------------------
# the structure factor
# ---------------------------------------------------------------------------
def reciprocal_cartesian_basis(cell) -> np.ndarray:
    """M⁻ᵀ — the matrix taking integer hkl to a Cartesian reciprocal vector.

    The same Cartesian frame ``moment_to_cartesian`` puts a moment in
    (``adp.cartesian_basis``'s Cholesky convention), because the perpendicular
    projection below takes an angle between the two and an angle needs one
    frame.  Only the *direction* of Q is used, so the 2π convention does not
    enter.
    """
    return np.linalg.inv(np.asarray(cartesian_basis(*cell), dtype=np.float64)).T


def magnetic_f2(members, seg, counts, stol, msites: MagneticSites, cell,
                xyz, occ, biso, dofs: list[np.ndarray]):
    """``(N,)`` p²·⟨|F_⊥|²⟩ in fm², the orbit average over each reflection's Laue orbit.

    ``members`` (M_total, 3), ``seg`` (M_total,) and ``counts`` (N,) are the
    frozen orbit layout (``model.preferred_orientation.orbit_layout``) — every
    reflection's symmetry equivalents, Friedel mates included, stacked and
    segmented.  ``stol`` is (N,) s = sinθ/λ = 1/2d, the same argument the
    nuclear structure factor evaluates its form factors at.  ``dofs[j]`` is atom
    ``j``'s moment DOF vector, or an empty array where it carries no moment.

    Adds to ⟨|F_N|²⟩ directly: both are in fm², so the phase's one scale
    multiplies both.

    **Host numpy, deliberately.**  Two pieces of this are not expressible on a
    traced backend as the package's ``xp`` protocol stands — the Cholesky
    factorisation behind the Cartesian frame, and the crystal-axis→Cartesian
    solve — and rather than approximate either by freezing it against a cell
    that is still refining, the traced twin **declines by name**
    (``backend.traced.make_traced_residual``) and jax/torch fall back to the
    host path for a magnetic phase.  The numpy answer is exact, and so is
    the Jacobian column for a moment modulus: analytic since WP-1327's last
    task (:func:`d_magnetic_f2_d_dofs`,
    ``optimize.least_squares._moment_column``).  An angle column, and a split
    draw with extinction evaluated, take the peak chain's re-run of the
    forward model.
    """
    m_hkl = np.asarray(members, dtype=np.float64)
    seg_i = np.asarray(seg, dtype=np.int64)
    n = len(counts)
    stol_mem = np.asarray(stol, dtype=np.float64)[seg_i]              # (M_total,)

    cart = _crystalaxis_to_cartesian(cell)                      # (3, 3)
    total = np.zeros((len(seg_i), 3), dtype=np.complex128)
    for j in range(msites.n_asym):
        if not msites.carries[j]:
            continue
        m_crystal = moment_from_dofs(msites.frames[j], dofs[j])          # (3,)
        images = np.asarray(msites.mom_mat[j]) @ m_crystal               # (m, 3)
        m_cart = images @ cart.T                                         # (m, 3)
        rot, tran = msites.ops[j]
        positions = np.asarray(rot) @ np.asarray(xyz[j], dtype=np.float64) \
            + np.asarray(tran, dtype=np.float64)                         # (m, 3)
        phase = np.exp(2.0j * np.pi * (positions @ m_hkl.T))             # (m, M)
        amp = (float(occ[j]) * _form_factor(msites, j, stol_mem)
               * np.exp(-float(biso[j]) * stol_mem * stol_mem))                # (M,)
        contrib = np.einsum("km,kc->mc", phase, m_cart.astype(np.complex128))
        total = total + amp[:, None] * contrib

    q = m_hkl @ reciprocal_cartesian_basis(cell).T                       # (M, 3)
    qhat = q / np.sqrt((q * q).sum(axis=1))[:, None]
    # only the component of F_m perpendicular to Q scatters (Halpern & Johnson
    # 1939): |F_⊥|² = |F|² − |Q̂·F|², and F is complex, so the subtracted term
    # is the squared modulus of a complex projection and not (Q̂·Re F)²
    parallel = (qhat.astype(np.complex128) * total).sum(axis=1)          # (M,)
    f2 = (np.real(total * np.conj(total)).sum(axis=1)
          - np.real(parallel * np.conj(parallel)))
    summed = np.zeros(n, dtype=np.float64)
    np.add.at(summed, seg_i, f2)
    return (P_MAGNETIC_FM ** 2) * summed / np.asarray(counts, dtype=np.float64)


def d_magnetic_f2_d_dofs(members, seg, counts, stol, msites: MagneticSites,
                         cell, xyz, occ, biso, dofs: list[np.ndarray]
                         ) -> dict[tuple[int, int], np.ndarray]:
    """``{(j, k): (N,)}`` — ∂(p²·⟨|F_⊥|²⟩)/∂ moment DOF k of atom j, analytic.

    The arguments are :func:`magnetic_f2`'s, and so is the arithmetic up to
    the point where a moment enters.  F is **linear** in every site's moment
    (the form factor, the Debye-Waller factor, the phases and the axial
    matrices do not depend on it), and a DOF moves its own site's moment
    only, through :func:`~.moments.d_moment_d_dofs`.  So ∂F/∂d is the forward
    orbit sum of that one atom with m replaced by ∂m/∂d.  The perpendicular
    projection P = I − Q̂Q̂ᵀ is real, symmetric and idempotent, so

        ∂|F_⊥|²/∂d = 2·Re[(P·F)ᴴ · ∂F/∂d]

    with no ∂P term, Q̂ being a function of h and the cell alone (Halpern &
    Johnson, 1939, *Phys. Rev.* **55**, 898; the Wirtinger form of a real
    quadratic in a complex vector, Brandwood, 1983, *IEE Proc. F* **130**, 11).  Averaged over the
    same frozen Laue orbit as the forward model and multiplied by p².  The
    derivation, with the exact oracles the tests hold it to, is WP-1327's
    analytic-branch entry (PR #1206).

    Every carrying atom's DOFs are returned in one call, because the
    projected total F_⊥ is the expensive half and is shared by all of them.
    """
    from .moments import d_moment_d_dofs

    m_hkl = np.asarray(members, dtype=np.float64)
    seg_i = np.asarray(seg, dtype=np.int64)
    n = len(counts)
    stol_mem = np.asarray(stol, dtype=np.float64)[seg_i]
    cart = _crystalaxis_to_cartesian(cell)
    total = np.zeros((len(seg_i), 3), dtype=np.complex128)
    per_atom = {}
    for j in range(msites.n_asym):
        if not msites.carries[j]:
            continue
        m_crystal = moment_from_dofs(msites.frames[j], dofs[j])
        mats = np.asarray(msites.mom_mat[j])                             # (m, 3, 3)
        m_cart = (mats @ m_crystal) @ cart.T                             # (m, 3)
        rot, tran = msites.ops[j]
        positions = np.asarray(rot) @ np.asarray(xyz[j], dtype=np.float64) \
            + np.asarray(tran, dtype=np.float64)
        phase = np.exp(2.0j * np.pi * (positions @ m_hkl.T))             # (m, M)
        amp = (float(occ[j]) * _form_factor(msites, j, stol_mem)
               * np.exp(-float(biso[j]) * stol_mem * stol_mem))
        total = total + amp[:, None] * np.einsum(
            "km,kc->mc", phase, m_cart.astype(np.complex128))
        per_atom[j] = (mats, phase, amp)

    q = m_hkl @ reciprocal_cartesian_basis(cell).T
    qhat = q / np.sqrt((q * q).sum(axis=1))[:, None]
    perp = total - qhat * (qhat.astype(np.complex128) * total).sum(axis=1)[:, None]
    perp_conj = np.conj(perp)
    norm = (P_MAGNETIC_FM ** 2) / np.asarray(counts, dtype=np.float64)
    out: dict[tuple[int, int], np.ndarray] = {}
    for j, (mats, phase, amp) in per_atom.items():
        dm = d_moment_d_dofs(msites.frames[j], dofs[j])                  # (n, 3)
        dm_cart = np.einsum("kab,nb->kna", mats, dm) @ cart.T            # (m, n, 3)
        d_f = amp[:, None, None] * np.einsum(
            "km,knc->mnc", phase, dm_cart.astype(np.complex128))         # (M, n, 3)
        d_f2 = 2.0 * np.real(np.einsum("mc,mnc->mn", perp_conj, d_f))    # (M, n)
        for k in range(d_f2.shape[1]):
            summed = np.zeros(n, dtype=np.float64)
            np.add.at(summed, seg_i, d_f2[:, k])
            out[(j, k)] = norm * summed
    return out


def _form_factor(msites: MagneticSites, j: int, stol):
    """f_j(s) for the atom's ion and g, evaluated on the member-shaped ``stol``.

    Through :func:`~.form_factor.j0`/:func:`~.form_factor.j2`, the one
    evaluator of the table: they dispatch an ion to whichever stored form
    carries it (Brown's or Lisher & Forsyth's), which a local evaluation of
    :func:`~.form_factor.coefficients` could not.
    """
    ion = msites.ions[j]
    g = msites.g_factors[j]
    f = np.asarray(j0(ion, stol), dtype=np.float64)
    weight = 2.0 / g - 1.0
    if weight == 0.0:
        return f
    return f + weight * np.asarray(j2(ion, stol), dtype=np.float64)


def _crystalaxis_to_cartesian(cell) -> np.ndarray:
    """M·diag(1/a, 1/b, 1/c) — one authority with ``operators.moment_to_cartesian``."""
    from .operators import _crystalaxis_to_cartesian_matrix

    return _crystalaxis_to_cartesian_matrix(cell)


def magnetic_orbit(group, xyz, moment, *, tol: float = SITE_TOL):
    """The site's magnetic orbit — positions and the moment carried on each.

    A thin re-export of M-5's ``MagneticGroup.site_orbit`` so that a caller who
    wants the orbit for a *report* does not have to know which module owns the
    axial action.  Nothing in the forward model uses it: there the orbit comes
    from the nuclear operation subset, so that the magnetic and the nuclear
    images are the same array of positions.
    """
    return group.site_orbit(xyz, moment, tol=tol)
