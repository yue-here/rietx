"""Space-group symmetry via gemmi: operators, absences, unique hkl generation.

gemmi (MPL-2.0, used as a dependency) owns the symbol → operators mapping, the
systematic-absence test, and centring information.  Reflection multiplicities
are computed here by explicit orbit counting under the **Laue** group (the
point group of the diffraction pattern, i.e. the crystal point group plus
inversion), so ±h are always merged into one orbit.

**Merging ±h is exact with or without anomalous scattering, but for two
different reasons — do not "fix" it when dispersion is on.**  Without f″,
|F(h)|² = |F(−h)|² (Friedel's law) and the two are literally the same number.
With f″ they differ in a non-centrosymmetric group, but a powder cannot
separate them either way: d(h) = d(−h), so the pair lands in one peak and what
the peak measures is the *orbit average*.  ``structure_factor`` returns exactly
that average in closed form (⟨|F|²⟩ = |A|² + |B|², see its module docstring),
which is why one representative per Laue orbit remains the correct — not the
approximate — thing to enumerate here.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field

import gemmi
import numpy as np

from ..schemas.common import Diagnostic
from .lattice import d_spacings, two_theta_deg

#: ceiling on the (2h+1)(2k+1)(2l+1) enumeration grid ``generate_reflections``
#: may allocate — ~30M points is ≈ 1 GB of transient int64, far above any
#: physical powder problem (a 100 Å cell at d_min = 1 Å needs 8.1e6) and far
#: below the PiB-scale grids a collapsed cell implies
MAX_HKL_GRID_POINTS = 30_000_000

#: transient element budget for the orbit-image stack in
#: ``generate_reflections`` — the hkl loop it replaced was O(1) in memory, so
#: the vectorised form chunks to stay bounded.  ~24M int64 ≈ 200 MB, which every
#: physical case here fits in one chunk (the largest measured is 11k hkl × 8
#: images × 3 = 265k).
_ORBIT_CHUNK_ELEMENTS = 24_000_000


def get_spacegroup(symbol: str) -> gemmi.SpaceGroup:
    """Resolve an H-M symbol (or IT number given as a string) via gemmi."""
    sg = gemmi.find_spacegroup_by_name(symbol)
    if sg is None:
        try:
            sg = gemmi.find_spacegroup_by_number(int(symbol))
        except (ValueError, TypeError):
            sg = None
    if sg is None:
        raise ValueError(f"unknown space group symbol: {symbol!r}")
    return sg


# ---------------------------------------------------------------------------
# a group given by its operations rather than by a symbol
# ---------------------------------------------------------------------------
#: The bracketed-label form.  A ``Phase.space_group`` ending in ``[...]`` is a
#: **label**, not a resolvable symbol: it says "no Hermann-Mauguin symbol names
#: this group in this cell", and the group itself is then
#: ``Phase.symmetry_operations``.  The text before the bracket is the closest
#: standard *type* (what spglib identifies the operation list as, which is a
#: statement about the type and not about the setting) and the text inside says
#: why the symbol is not enough — usually the cell.
_LABEL = re.compile(r"^(?P<symbol>.*?)\s*\[(?P<note>[^\]]+)\]$")


def split_group_label(text: str) -> tuple[str, str] | None:
    """``("P m 1 1", "unnamed in 2a,b,a+c")`` for a bracketed label, else ``None``.

    The one authority for the bracket convention, so the schema validator, the
    supercell builder and the CIF writer cannot spell it three ways.
    """
    m = _LABEL.match(str(text).strip())
    if m is None:
        return None
    return m.group("symbol").strip(), m.group("note").strip()


def refuse_operation_list(phase, fmt: str) -> None:
    """Refuse, by name, a phase whose group only its operation list states.

    For a writer whose format states a phase's group as a symbol and nothing
    else.  A bracketed label is not one (:func:`split_group_label`), and
    without this the refusal read "unknown space group symbol" — true, and no
    help.  A plain symbol beside a list is the same group and passes.
    """
    if (phase.symmetry_operations is not None
            and split_group_label(phase.space_group) is not None):
        raise ValueError(
            f"phase {phase.name!r} cannot be written to {fmt}: its group is "
            f"its own list of {len(phase.symmetry_operations)} "
            f"symmetry_operations under the bracketed label "
            f"{phase.space_group!r}, which says no Hermann-Mauguin symbol "
            f"generates it, and {fmt} states a group only as a symbol. A CIF "
            f"(Structure.to_cif) carries the list")


def unnamed_label(closest: str | None, note: str) -> str:
    """The bracketed label for a group no symbol reproduces in its cell."""
    head = (closest or "").strip()
    return f"{head} [{note}]" if head else f"[{note}]"


@functools.lru_cache(maxsize=256)
def _op_list_from_xyz(xyz: tuple[str, ...]) -> tuple[gemmi.Op, ...]:
    """The operations of an explicit ``x,y,z`` list, **in the given order**.

    Order is load-bearing and gemmi's ``GroupOps`` does not preserve it: built
    from a flat 192-operation list it re-splits the group into 48 coset
    representatives times 4 centrings and picks *different* representatives
    (measured on ``F d -3 m:2``: the 18th operation comes back as ``y,z,x``
    where the table has ``y,z+1/2,x+1/2``, the same operation times a
    centring), so the product it iterates is a permutation of what went in.
    Orbit images are listed in operation order and
    ``structure_factor.select_orbit_ops`` freezes that order onto the compiled
    model, so a permutation reorders the structure-factor sum and changes the
    last bits of every intensity.  Keeping the caller's order is what makes a
    phase carrying the operation list of a *named* group predict bit-identically
    to the same phase carrying only the symbol.
    """
    if not xyz:
        raise ValueError("symmetry_operations: the list is empty; a group has "
                         "at least the identity in it")
    try:
        return tuple(gemmi.Op(str(s)) for s in xyz)
    except (RuntimeError, ValueError) as exc:
        raise ValueError(
            f"symmetry_operations: {exc} — an operation is an 'x,y,z'-style "
            f"triplet such as 'x,y,z' or '-x+1/2,y,z+1/4'") from exc


@functools.lru_cache(maxsize=256)
def _ops_from_xyz(xyz: tuple[str, ...]) -> gemmi.GroupOps:
    """gemmi's group object for an explicit list — for absences and epsilon.

    The *set* is what a systematic-absence or epsilon-factor test reads, so the
    reordering :func:`_op_list_from_xyz` warns about is harmless here; anything
    that reads the operations one by one must use that function instead.
    """
    return gemmi.GroupOps(list(_op_list_from_xyz(xyz)))


@functools.lru_cache(maxsize=256)
def _closest_type(xyz: tuple[str, ...]) -> gemmi.SpaceGroup | None:
    """The tabulated group with this operation list's rotations and centring.

    gemmi's ``derive_symmorphic`` drops every operation's translation part but
    keeps the centring, so what comes back has the **same point group and the
    same lattice** as the given list and differs from it only in the screw and
    glide translations — the very things a doubled cell turns into quarters.
    Every symmorphic group is tabulated, so this resolves for any operation
    list that is a space group at all, and it is what makes the metric
    constraints of an unnamed group knowable: ``cell_constraints`` reads only
    the crystal system, the ``R``-axes extension and the monoclinic unique
    axis, and all three are properties of the point group and the lattice.

    **Two tries, and the second is the one the real cases need.**  A child
    group carries the *parent's* lattice translation — the nuclear structure is
    still periodic on it; only the magnetic or displacive order is not — and a
    half translation along one axis is no tabulated Bravais centring, so gemmi
    reads it as a centring it cannot name and the symmorphic lookup returns
    nothing.  Measured on Ba₂FeSbSe₅'s S3(a,b) child in 2a,b,a+c: the
    operations are {x,y,z; x+½,y,z; x,−y+½,z; x+½,−y+½,z}, the symmorphic
    derivation keeps the (½,0,0) "centring", and ``find_spacegroup_by_ops``
    gives ``None``.  Dropping to the bare **point group on a P lattice** then
    resolves it as ``P 1 m 1`` — monoclinic, unique axis b, which is what the
    child cell is.  That second try is safe for the three keys
    :func:`cell_constraints` reads: a centring changes neither the crystal
    system nor the monoclinic unique axis, and the one setting where the
    lattice *is* load-bearing — trigonal on rhombohedral axes, ``ext == "R"`` —
    is named by the **first** try, because an R centring is tabulated.

    ``None`` only when even the point group does not resolve, which means the
    list is not a crystallographic group in this setting — a caller error
    rather than a naming problem.
    """
    ops = _ops_from_xyz(xyz)
    found = gemmi.find_spacegroup_by_ops(ops.derive_symmorphic())
    if found is not None:
        return found
    seen: dict[tuple[int, ...], gemmi.Op] = {}
    for op in ops:
        bare = gemmi.Op("x,y,z")
        bare.rot = [list(row) for row in op.rot]
        bare.tran = [0, 0, 0]
        seen.setdefault(tuple(v for row in op.rot for v in row), bare)
    return gemmi.find_spacegroup_by_ops(gemmi.GroupOps(list(seen.values())))


@dataclass(frozen=True)
class OperatorGroup:
    """A space group stated as its operation list, under a label.

    **Why this exists.**  A parent operation whose translation along a doubled
    axis is a half becomes a *quarter* in the child cell, and no Hermann-Mauguin
    symbol in any tabulated setting has a quarter in its operation list.  Such a
    group is a perfectly good space group of that cell — it has orbits, site
    multiplicities and systematic absences like any other — and the only thing
    it lacks is a name.  Before this class the package could only store a
    symbol, so the honest answer was a refusal
    (``magnetic.supercell.resolve_child_group``, which now states it); with it the
    answer is the operation list plus a label that says the symbol does not
    generate it.

    ``label`` is what :attr:`~rietx.schemas.structure.Phase.space_group` holds —
    the bracketed form :func:`unnamed_label` builds.  ``xyz`` is the operation
    list, in the caller's order, because a CIF symmetry code is an index into a
    listed order and the order therefore has to survive a round trip.

    The gemmi-shaped surface (:meth:`operations`, :meth:`xhm`, :attr:`hm`,
    :attr:`ext`, :meth:`crystal_system_str`, :meth:`monoclinic_unique_axis`) is
    what every consumer in this package already asks a ``gemmi.SpaceGroup``
    for, so :func:`resolve_group` can hand either object to any of them.  The
    four *naming* members delegate to :attr:`closest_type` and the reason they
    may is the one :func:`_closest_type` states: the symmorphic derivation has
    this list's point group and lattice exactly.
    """

    label: str
    xyz: tuple[str, ...]

    def operations(self) -> gemmi.GroupOps:
        return _ops_from_xyz(self.xyz)

    def xhm(self) -> str:
        return self.label

    @property
    def closest_type(self) -> gemmi.SpaceGroup:
        """The symmorphic group with the same point group and lattice."""
        found = _closest_type(self.xyz)
        if found is None:
            raise ValueError(
                f"the operation list of {self.label!r} ({len(self.xyz)} "
                f"operations) has no symmorphic space group in gemmi's table, "
                f"so it is not a crystallographic group in this setting and "
                f"neither its crystal system nor its cell constraints are "
                f"defined. Check the list: {', '.join(self.xyz[:4])}...")
        return found

    @property
    def hm(self) -> str:
        return self.closest_type.hm

    @property
    def ext(self) -> str:
        return self.closest_type.ext

    @property
    def number(self) -> int:
        """The *closest type's* IT number — a type, never this group's name."""
        return int(self.closest_type.number)

    def crystal_system_str(self) -> str:
        return self.closest_type.crystal_system_str()

    def monoclinic_unique_axis(self) -> str:
        return self.closest_type.monoclinic_unique_axis()

    def is_centrosymmetric(self) -> bool:
        return bool(self.operations().is_centrosymmetric())

    def centring_type(self) -> str:
        return str(self.operations().find_centering())


def resolve_group(space_group: str,
                  operations=None) -> gemmi.SpaceGroup | OperatorGroup:
    """The group a phase means: its operation list when it carries one.

    **The one place the choice is made.**  Every consumer of a phase's symmetry
    — orbit expansion, site multiplicity, systematic absences, reflection
    generation and multiplicity, the structure factor's frozen operation
    subsets, the Wyckoff constraint bases, the cell ties, the bond/angle symop
    table, ZMV, the CIF writer — calls this rather than
    :func:`get_spacegroup`, so a phase whose group has no symbol reaches all of
    them with the same operations and none of them can silently fall back on
    the label.

    ``operations`` ``None`` (every phase written before this field existed) is
    exactly the old path: ``get_spacegroup(space_group)``, same object, same
    cache, same numbers.
    """
    if operations is None:
        return get_spacegroup(space_group)
    return OperatorGroup(label=str(space_group),
                         xyz=tuple(str(s) for s in operations))


def as_group(spec) -> gemmi.SpaceGroup | OperatorGroup:
    """A symbol string, or a group object, as a group object.

    The adapter that lets the symbol-taking functions in this module
    (:func:`generate_reflections`, :func:`reflection_orbits`) also take what
    :func:`resolve_group` returns, without every call site branching.
    """
    if isinstance(spec, str):
        return get_spacegroup(spec)
    return spec


def group_key(sg) -> tuple[str, tuple[str, ...]]:
    """A hashable identity for a group, for the operation-array cache."""
    if isinstance(sg, OperatorGroup):
        return ("ops", sg.xyz)
    return ("hm", (sg.xhm(),))


@functools.lru_cache(maxsize=1)
def _settings_by_hm() -> dict[str, tuple[str, ...]]:
    """H-M symbols the tables hold more than one setting for, in table order.

    Built from gemmi rather than listed, so it cannot drift out of date; on
    the bundled tables it is **40** symbols, the origin-choice pairs
    (``:1``/``:2``) plus the rhombohedral groups' axis choices (``:H``/``:R``).
    """
    by_hm: dict[str, list[str]] = {}
    for sg in gemmi.spacegroup_table():
        held = by_hm.setdefault(sg.hm, [])
        if sg.xhm() not in held:
            held.append(sg.xhm())
    return {hm: tuple(v) for hm, v in by_hm.items() if len(v) > 1}


def setting_alternatives(symbol: str) -> tuple[str, tuple[str, ...]]:
    """The setting a **bare** symbol resolves to, and the ones it passed over.

    Returns ``("", ())`` when the caller named a setting (the symbol carries a
    ``:`` suffix) or when the tables hold only one — so the CIF and TOPAS
    routes, which both carry a setting, stay silent: ``cif.py`` prefers gemmi's
    own reading of the file, and the ``.inp`` reader maps TOPAS's trailing
    ``Z`` to ``:2`` (WP-1118).

    A bare symbol is not an error and this does not make it one — gemmi's
    choice of the first setting has to be made and is defensible.  What it
    cannot be is invisible.  ``F d -3 m`` resolves to ``:1``, and spinel
    coordinates from a paper are almost always origin choice 2, where the 8a
    and 16d multiplicities **swap**: A at (⅛,⅛,⅛) counts 16 under ``:1``
    against 8 under ``:2``, B at (½,½,½) the reverse, so a hand-built phase
    gives A₂BO₄ where AB₂O₄ was meant — wrong ``element_counts``, wrong ZMV,
    wrong weight fractions, and a fit that converges anyway (issue #217).
    """
    if ":" in symbol:
        return "", ()
    sg = get_spacegroup(symbol)
    settings = _settings_by_hm().get(sg.hm, ())
    if len(settings) < 2:
        return "", ()
    taken = sg.xhm()
    return taken, tuple(s for s in settings if s != taken)


#: Denominator every space-group translation is an exact multiple of, which is
#: what lets a stated operator be compared with a tabulated one by integers
#: rather than by tolerance.
_TRANSLATION_DEN = 12


def operator_key(rotation, translation) -> tuple:
    """One symmetry operation as integers, for comparing two operator lists.

    ``rotation`` is a 3×3 integer matrix and ``translation`` a fractional
    triple.  The translation is reduced modulo 1 and expressed in twelfths,
    which every space-group translation is an exact multiple of, so two
    spellings of one operation (``0.25`` against ``1/4``, ``-1/4`` against
    ``3/4``) give the same key and no tolerance is involved.
    """
    rot = np.asarray(rotation, dtype=np.float64)
    tran = np.asarray(translation, dtype=np.float64)
    return (tuple(np.rint(rot).astype(int).ravel().tolist()),
            tuple(int(round(v * _TRANSLATION_DEN)) % _TRANSLATION_DEN
                  for v in tran.ravel()))


def operator_keys(sg: gemmi.SpaceGroup) -> frozenset[tuple]:
    """The tabulated operations of ``sg`` as :func:`operator_key` keys."""
    return frozenset(
        operator_key(np.asarray(op.rot, dtype=np.float64) / op.DEN,
                     np.asarray(op.tran, dtype=np.float64) / op.DEN)
        for op in sg.operations())


def setting_from_operators(symbol: str, operators) -> str | None:
    """The setting of ``symbol`` whose operations are exactly ``operators``.

    ``operators`` is an iterable of :func:`operator_key` keys — the full group,
    centring and inversion already expanded.  Returns the extended H-M symbol of
    the single setting that matches, or ``None`` when none does or when the
    symbol resolves to only one setting anyway (nothing to choose).

    **This is what a format that states its operators is for.**  A bare
    ``F d -3 m`` is two different groups and the symbol cannot say which, but a
    file that also writes the operations has already said it, and reading them
    is not a convention to be trusted but an equality to be checked.  GSAS-II
    writes them (``SGData['SGOps']``), and 4 of the 46 phases in its public
    tutorial corpus state a bare two-setting symbol whose operators are origin
    choice 2 — where gemmi's reading of the symbol alone is choice 1 (WP-1118).
    """
    taken, others = setting_alternatives(symbol)
    if not others:
        return None
    stated = frozenset(operators)
    matches = [s for s in (taken, *others) if operator_keys(get_spacegroup(s)) == stated]
    return matches[0] if len(matches) == 1 else None


#: Largest deviation of a symmetry-fixed cell angle from its exact value that
#: :func:`cell_constraints` accepts, in degrees.  Chosen by consequence, not by
#: float tolerance: at 1e-3° the worst-case d-spacing bias is **8.3 ppm**
#: (measured on a=5, b=6, c=7 Å over h0l/hk l reflections; the coupling is
#: linear, 825 ppm at 0.1°), an order of magnitude under the tightest cell
#: assertion in the acceptance suite — SRM 660c's a = 4.15678 ± 2e-4 Å, i.e.
#: 48 ppm.  And it clears, by a **measured 7e10 ×**, the round-off an indexing
#: candidate arrives with: ``refine_candidate`` solves A..F *inside* the symmetry
#: subspace, so the derived angles come back within 1.4e-14° of exactly 90/120
#: across all five constrained systems.  That matters because
#: ``validate_by_lebail`` builds a ``ParameterTable`` from every candidate — a
#: tolerance anywhere near the conversion noise would make the indexer refuse its
#: own answers.
SYMMETRY_ANGLE_TOL_DEG = 1e-3

#: The exact angle a hexagonal/trigonal γ takes on hexagonal axes.
_GAMMA_HEX = 120.0


@dataclass(frozen=True)
class CellConstraints:
    """Which cell parameters a space-group **setting** leaves free.

    ``ties`` maps a dependent cell parameter to the one it equals (``"b" → "a"``,
    and on rhombohedral axes ``"beta" → "alpha"`` as well); ``fixed_angles`` maps
    an angle to the value its symmetry *demands*, in degrees.  Everything not
    named in either is refinable.

    **The crystal system is not enough** — the setting is, and three of them
    disagree with the system alone (WP-1036):

    * monoclinic has three unique-axis choices, and gemmi knows which
      (:meth:`gemmi.SpaceGroup.monoclinic_unique_axis`).  Assuming ``b`` inverts
      the answer on a ``c``-unique symbol: γ, the one angle the setting leaves
      free, gets held, and β, which symmetry fixes at 90°, is left to refine.
    * an R lattice on **rhombohedral** axes (``sg.ext == 'R'``) needs
      a = b = c and α = β = γ, not the hexagonal-axes ``b ← a`` with c free.
      ``read_small_structure`` picks the setting from the *cell*, so a bare
      ``R -3 c`` over a rhombohedral cell arrives here as ``R -3 c:R`` — no
      non-standard symbol required.
    * the ``:1``/``:2`` extensions on cubic, tetragonal and orthorhombic groups
      are origin choices and do not touch the metric, which is why only ``'R'``
      is tested for.

    **A degrees-of-freedom count cannot check any of this.** Both monoclinic
    subspaces have four free parameters and both trigonal ones have two; the
    wrong table has the right dimension and the wrong subspace, exactly as the
    transposed-rotation trap did one rank up (see
    :func:`~rietx.indexing.qspace.metric_basis`).  The test that does check it
    asserts the *true* metric of each setting lies in the span the constraints
    describe — ``tests/test_wyckoff.py`` runs it over gemmi's whole table.

    The values in ``fixed_angles`` are **new knowledge**: nothing else in this
    package knows a hexagonal γ "should be" 120°.  They live here so that no
    call site can open-code them.
    """

    ties: dict[str, str]
    fixed_angles: dict[str, float]


def cell_constraints(sg: gemmi.SpaceGroup) -> CellConstraints:
    """Cell ties and symmetry-fixed angles for one space-group **setting**.

    Raises ``ValueError`` naming the symbol and the setting if the group is one
    this package cannot serve.  See :class:`CellConstraints` for why the crystal
    system alone is the wrong key.
    """
    system = sg.crystal_system_str()
    right = {"alpha": 90.0, "beta": 90.0, "gamma": 90.0}
    if system == "cubic":
        return CellConstraints({"b": "a", "c": "a"}, right)
    if system == "tetragonal":
        return CellConstraints({"b": "a"}, right)
    if system == "hexagonal":
        return CellConstraints({"b": "a"}, right | {"gamma": _GAMMA_HEX})
    if system == "orthorhombic":
        return CellConstraints({}, right)
    if system == "triclinic":
        return CellConstraints({}, {})
    if system == "trigonal":
        if sg.ext == "R":  # rhombohedral axes: one length, one angle
            return CellConstraints({"b": "a", "c": "a", "beta": "alpha",
                                    "gamma": "alpha"}, {})
        return CellConstraints({"b": "a"}, right | {"gamma": _GAMMA_HEX})
    if system == "monoclinic":
        axis = sg.monoclinic_unique_axis()
        free = {"a": "alpha", "b": "beta", "c": "gamma"}.get(axis)
        if free is None:
            raise ValueError(
                f"space group {sg.xhm()!r}: monoclinic with unique axis "
                f"{axis!r}, which is not one of a, b, c — this package cannot "
                f"decide which angle its symmetry fixes")
        return CellConstraints({}, {k: v for k, v in right.items() if k != free})
    raise ValueError(
        f"space group {sg.xhm()!r}: crystal system {system!r} has no cell-tie "
        f"rule in this package")


def check_cell_angles(sg: gemmi.SpaceGroup,
                      angles: dict[str, float]) -> None:
    """Raise if a symmetry-fixed angle disagrees with the value symmetry demands.

    ``angles`` maps ``"alpha"``/``"beta"``/``"gamma"`` to the stored value in
    degrees.  Tolerance is :data:`SYMMETRY_ANGLE_TOL_DEG`.

    **Refusing, rather than normalising, is the deliberate choice** (WP-1036).
    A fixed angle is *held at its stored value*, so before this check a
    monoclinic β = 93.2° survived under an orthorhombic symbol and every
    d-spacing was computed from it — silently, because nothing in the package
    knew what the angle should have been.  Normalising it instead would move a
    number the user supplied, and the one place this is called from
    (``ParameterTable``) has no diagnostics channel to report a model edit
    through; an invisible edit to a stored cell is worse than a refusal.

    Putting the check on that hot path is safe for a reason worth stating: a
    symmetry-fixed angle is **locked**, so it cannot drift while a fit runs.
    The table is rebuilt at every stage boundary and on every ``set_vary`` /
    ``set_values``, but the answer here is the same at each rebuild — a
    refinement that starts can never fail this mid-flight.
    """
    for name, target in cell_constraints(sg).fixed_angles.items():
        value = angles[name]
        if abs(value - target) > SYMMETRY_ANGLE_TOL_DEG:
            raise ValueError(
                f"space group {sg.xhm()!r} fixes {name} at {target}° by "
                f"symmetry, but the cell stores {value}° — off by "
                f"{value - target:+.6g}°, {SYMMETRY_ANGLE_TOL_DEG}° allowed. "
                f"Correct the cell, or use a space group whose symmetry leaves "
                f"{name} free.")


#: The cell parameters, in the order every surface in this package writes them.
CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")


def free_cell_names(sg: gemmi.SpaceGroup) -> tuple[str, ...]:
    """Which cell parameters a setting leaves free, in :data:`CELL_NAMES` order.

    The complement of :class:`CellConstraints` — everything neither tied to
    another edge nor held at an angle symmetry demands.  Two for a hexagonal
    setting, one for a cubic one, four for a monoclinic one.
    """
    cons = cell_constraints(sg)
    determined = set(cons.ties) | set(cons.fixed_angles)
    return tuple(name for name in CELL_NAMES if name not in determined)


def complete_cell(sg: gemmi.SpaceGroup,
                  values: dict[str, float]) -> dict[str, float]:
    """The whole cell from the parameters the setting leaves free.

    ``values`` carries the :func:`free_cell_names` of ``sg`` and nothing else;
    the tied edges and the symmetry-fixed angles are filled in from
    :func:`cell_constraints`.  This is the constrained-cell shape TOPAS's
    ``Tetragonal(a, c)`` / ``Rhombohedral(a, al)`` macros take (concept only —
    that code is closed), and it is WP-1014's rule about coordinates one
    parameter family over: the editor offers the degrees of freedom, so a
    violation is **unrepresentable rather than refused**.

    A parameter the symmetry determines is refused rather than checked against
    what symmetry demands, and refused rather than quietly ignored.  Checking
    would need a tolerance on a *length* — a constant nothing else in this
    package needs, chosen from nothing — while ignoring is what the old
    six-number route did: under ``P 4/m m m`` a typed ``b`` was tied away by
    ``ParameterTable`` and the number the user read back was never the one they
    entered.  The message names the source instead, so the refusal says what to
    send.
    """
    cons = cell_constraints(sg)
    free = free_cell_names(sg)
    unknown = sorted(set(values) - set(CELL_NAMES))
    if unknown:
        raise ValueError(f"not cell parameters: {', '.join(unknown)}; "
                         f"the cell is {', '.join(CELL_NAMES)}")
    for name in sorted(set(values) - set(free)):
        if name in cons.ties:
            raise ValueError(
                f"space group {sg.xhm()!r} ties {name} to {cons.ties[name]}, so "
                f"{name} is not yours to give — send {', '.join(free)}")
        raise ValueError(
            f"space group {sg.xhm()!r} fixes {name} at "
            f"{cons.fixed_angles[name]:g}° by symmetry, so {name} is not yours "
            f"to give — send {', '.join(free)}")
    missing = [name for name in free if name not in values]
    if missing:
        raise ValueError(f"space group {sg.xhm()!r} leaves "
                         f"{', '.join(free)} free; missing {', '.join(missing)}")
    cell = {name: float(values[name]) for name in free}
    cell.update({name: cell[source] for name, source in cons.ties.items()})
    cell.update(cons.fixed_angles)
    return {name: cell[name] for name in CELL_NAMES}


def rotation_matrices(sg) -> np.ndarray:
    """Integer rotation parts of all symmetry operations, shape (M, 3, 3).

    gemmi stores rotations scaled by Op.DEN (=24).  ``sg`` is a
    ``gemmi.SpaceGroup`` or an :class:`OperatorGroup`; the rows come from
    :func:`_group_arrays`, so they are in the same order as the orbit images
    and, for a tabulated symbol, element for element what this function
    returned before it took either.
    """
    return np.array(_group_arrays(group_key(sg))[1])


#: Default tolerance, in fractional coordinates, for "this operation fixes this
#: site".  A structure whose coordinates are quoted to five decimals — the
#: ICSD's usual precision — can miss an exact relation such as y = 2x by 1e-4,
#: which is why the boundary sits here rather than at roundoff.
SITE_TOL = 1e-4

#: Relative slack making the :data:`SITE_TOL` comparison **inclusive**.  A
#: five-decimal file lands on the boundary *exactly*: the deviation computed
#: from ICSD 18318's B11 site is ``1.0000000000000286e-04`` and from its B16
#: ``9.999999999998899e-05`` — the same nominal 1e-4, on opposite sides of a
#: strict ``<``.  Which side a coordinate falls on is then decided by binary
#: rounding rather than by crystallography, so a deviation *at* the tolerance
#: counts as within it (issue #215).
_SITE_TOL_SLACK = 1e-9

#: Tolerance at which two images of an *already snapped* position count as the
#: same orbit member.  Coincidence after the snap is exact to roundoff, so this
#: is a float-equality threshold and never a crystallographic judgement — the
#: judgement is all in :data:`SITE_TOL`, one step earlier.
_COINCIDENCE_TOL = 1e-9

#: Below this the snap did nothing and ``SiteOrbit.shift`` reports 0.0.  A site
#: already *on* its special position still averages to itself only to within an
#: ulp or two — h·x/h is not exactly x unless h is a power of two — and a
#: report of that is a report of arithmetic, not of the structure.  The floor
#: sits seven orders under :data:`SITE_TOL`, so nothing a file could mean is
#: swallowed by it.
_SNAP_NOISE = 1e-12


def _op_arrays(op: gemmi.Op) -> tuple[np.ndarray, np.ndarray]:
    """(R, t) of one gemmi operation as float64; gemmi scales both by Op.DEN."""
    return (np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN,
            np.array(op.tran, dtype=np.float64) / gemmi.Op.DEN)


@functools.lru_cache(maxsize=64)
def _group_arrays(key: tuple[str, tuple[str, ...]]
                  ) -> tuple[tuple[gemmi.Op, ...], np.ndarray, np.ndarray]:
    """Operations of one group with their (R, t) already in float64.

    Rebuilding them per call is what :func:`site_orbit` spent most of its time
    on — it walks the operation list three times, and a 192-operation group
    costs 0.78 ms a walk, so a 48-site cubic phase paid 0.76 s every time
    ``snap_diagnostics`` ran.  The arrays are exactly what :func:`_op_arrays`
    returns and are never written to, so the cache changes no number.

    ``key`` is :func:`group_key`'s: the xhm symbol for a tabulated group and
    the explicit operation list for an :class:`OperatorGroup`, so the two
    cannot collide and a phase carrying its own list is cached like any other.
    """
    kind, payload = key
    ops = (_op_list_from_xyz(payload) if kind == "ops"
           else tuple(get_spacegroup(payload[0]).operations()))
    pairs = [_op_arrays(op) for op in ops]
    rot = np.array([r for r, _ in pairs], dtype=np.float64)
    tran = np.array([t for _, t in pairs], dtype=np.float64)
    rot.flags.writeable = False
    tran.flags.writeable = False
    return ops, rot, tran


@dataclass(frozen=True)
class SiteOrbit:
    """The orbit of one fractional position, derived from its stabiliser.

    A site multiplicity is a group-theoretic fact — |G| / |stabiliser| — and
    not a count of how many images survived a pairwise comparison.  This class
    is the one authority for it: :func:`expand_orbit` reads the images with
    their rotations,
    :func:`~rietx.crystallography.structure_factor.select_orbit_ops` the
    operation subset frozen onto the compiled model, and
    :func:`~rietx.crystallography.wyckoff.stabilizer_rotations` the stabiliser
    itself, so the forward model, the Wyckoff constraints and QPA can no longer
    disagree about how many atoms a site puts in the cell.

    Attributes
    ----------
    position : (3,) float — the given position **snapped** onto the special
        position its stabiliser defines, wrapped into [0,1).  The snap is the
        Reynolds average over the stabiliser, so it moves the coordinate only
        along directions the site symmetry forbids, and never further than the
        deviation it removes.  On a general position it is the input,
        bit-identical.
    shift : float — the largest periodic component of ``position − xyz``; 0.0
        when nothing moved.
    multiplicity : int — |G| / |stabilizer|, always a divisor of |G|.
    stabilizer : (h,3,3) int — rotation parts of the operations fixing the
        site.  Translations are dropped because a displacement or a tensor
        transforms without them (see ``wyckoff.py``).
    rot, tran : (m,3,3) float, (m,3) float — one operation per left coset of
        the stabiliser, in gemmi's own order, so each generates a *distinct*
        orbit image.
    images : (m,3) float — those images of ``position``, wrapped into [0,1).
    """

    position: np.ndarray
    shift: float
    multiplicity: int
    stabilizer: np.ndarray
    rot: np.ndarray
    tran: np.ndarray
    images: np.ndarray


def site_orbit(sg: gemmi.SpaceGroup, xyz: np.ndarray, *,
               tol: float = SITE_TOL) -> SiteOrbit:
    """Stabiliser, snapped position, multiplicity and orbit images of one site.

    A site multiplicity is |G| / |G_x| with G_x the site-symmetry group
    (International Tables for Crystallography Vol. A, Hahn ed., 2005,
    sect. 8.3.2), so it always divides the group order.  Snapping a coordinate
    onto the special position its stabiliser defines follows cctbx
    (Grosse-Kunstleve & Adams, 2002, J. Appl. Cryst. 35, 477), which derives
    the site symmetry the same way rather than counting coincidences.

    Four steps, in this order because each depends on the one before:

    1. **Candidates.** The operations with R·x + t ≡ x (mod 1) to within
       ``tol``, inclusive of the boundary (:data:`_SITE_TOL_SLACK`).
    2. **Snap.** Their Reynolds average, each image taken on the lattice branch
       nearest x.  Every term is within ``tol`` of x, so the average is too;
       when the candidates are a group it is exactly a fixed point of every one
       of them.
    3. **Stabiliser.** The operations fixing the *snapped* position, to
       roundoff.  This — not step 1 — is the stabiliser, and it is a genuine
       subgroup because the exact stabiliser of a point always is.  Step 1's
       set need not be one: a coordinate jittered off a cubic ¼¼¼ site can
       satisfy some members of its site symmetry within ``tol`` and miss
       others, and averaging over that set is a projection, not a claim.  When
       the snap buys nothing — the stabiliser comes back trivial — the
       caller's own numbers are kept and the shift is zero.
    4. **Cosets.** The distinct images of the snapped position, and the first
       operation reaching each.  Two operations give the same image iff they
       share a left coset of the stabiliser, so by orbit-stabiliser the count
       is |G| / |stabiliser| and cannot depend on the order gemmi yields
       operations in.

    A greedy pairwise dedup — what this replaced — has neither property: the
    comparison is not transitive, so the partition follows the operation order,
    and nothing forces the count to divide |G|.  Perturbing an 18h site of
    ``R -3 m:H`` off its y = 2x relation by ±1e-4 returned orbits of 22 and 30
    under a group of order 36 (issue #215), and one such site put 327 boron
    atoms in a cell that holds 315 — 3.8 % carried silently into ZMV and every
    ``weight_percent``, while the fit converged.

    Raises ``ValueError`` prefixed ``ORBIT_NOT_A_MULTIPLICITY`` when the count
    is not |G| / |stabiliser|.  Steps 3 and 4 make that unreachable — they
    measure one point's own stabiliser and one point's own orbit — which is
    exactly why the guard is kept: it is the invariant, and an invariant nobody
    can currently break is the one worth asserting.
    """
    ops, all_rot, all_tran = _group_arrays(group_key(sg))
    order = len(ops)
    x = np.asarray(xyz, dtype=np.float64).reshape(3)

    def fixing(p: np.ndarray, bound: float) -> list[int]:
        d = all_rot @ p + all_tran - p
        d -= np.round(d)
        return list(np.flatnonzero(np.all(np.abs(d) <= bound, axis=1)))

    candidates = fixing(x, tol * (1.0 + _SITE_TOL_SLACK))
    if len(candidates) == 1:
        snapped, shift = x, 0.0          # general position: no arithmetic at all
    else:
        p = all_rot[candidates] @ x + all_tran[candidates]
        p -= np.round(p - x)             # each image on the branch nearest x
        snapped = p.mean(axis=0)
        delta = snapped - x
        shift = float(np.max(np.abs(delta - np.round(delta))))
        if shift <= _SNAP_NOISE:
            snapped, shift = x, 0.0      # already on it; the average is noise

    stab_ops = fixing(snapped, _COINCIDENCE_TOL)
    if len(stab_ops) == 1 and shift:
        # the projection landed nowhere special: keep the caller's numbers, and
        # re-measure the stabiliser *there*, since x can be fixed exactly by an
        # operation the projected point is not — leaving the stabiliser stale
        # would report the wrong site symmetry and trip the guard below
        snapped, shift = x, 0.0
        stab_ops = fixing(snapped, _COINCIDENCE_TOL)
    coincide = min(tol, _COINCIDENCE_TOL)
    images: list[np.ndarray] = []
    keep: list[int] = []
    for i in range(order):
        p = (all_rot[i] @ snapped + all_tran[i]) % 1.0
        for q in images:
            diff = np.abs(p - q)
            if np.all(np.minimum(diff, 1.0 - diff) <= coincide):
                break
        else:
            images.append(p)
            keep.append(i)

    multiplicity = len(images)
    if multiplicity * len(stab_ops) != order:
        raise ValueError(
            f"ORBIT_NOT_A_MULTIPLICITY: site "
            f"{np.array2string(x, precision=6)} in {sg.xhm()!r} expands to "
            f"{multiplicity} images against a stabiliser of order "
            f"{len(stab_ops)} in a group of order {order}; a multiplicity is "
            f"|G|/|stabiliser| and must divide |G|. Tolerance {tol:g} admitted "
            f"operations that are not a subgroup — the coordinates are not "
            f"consistent with this space group's setting")

    return SiteOrbit(
        position=snapped % 1.0,
        shift=shift,
        multiplicity=multiplicity,
        stabilizer=np.rint(all_rot[stab_ops]).astype(np.int64),
        rot=np.array(all_rot[keep]),
        tran=np.array(all_tran[keep]),
        images=np.asarray(images),
    )


def expand_orbit(sg: gemmi.SpaceGroup, xyz: np.ndarray, *, tol: float = SITE_TOL
                 ) -> list[tuple[np.ndarray, np.ndarray]]:
    """Orbit of one fractional position, **with the rotation that produced each image**.

    Returns ``(position, R)`` pairs — the position wrapped into [0,1) and the
    fractional-space rotation part of the operation that generated it.  The
    rotation is what a caller needs when the site carries something that
    *transforms* rather than merely moves: a displacement ellipsoid is
    U\\* → R·U\\*·Rᵀ (see ``adp.py``), so an image drawn with the parent's tensor
    is drawn wrong in every non-orthogonal setting.

    One operation per left coset of the stabiliser (:func:`site_orbit`), so a
    special position keeps the first operation that reached it and "the first"
    is well defined: the operations giving one image are exactly a coset, and
    any of the stabiliser's members leaves the site's own tensor invariant.
    That was the *claim* of the greedy version this replaced, and it did not
    hold at the tolerance boundary, where the merged set was not a coset.
    """
    orbit = site_orbit(sg, xyz, tol=tol)
    return [(orbit.images[i], orbit.rot[i]) for i in range(orbit.multiplicity)]


def expand_positions(sg: gemmi.SpaceGroup, xyz: np.ndarray, *, tol: float = SITE_TOL
                     ) -> list[np.ndarray]:
    """Orbit of one fractional position under the space group.

    Returns the distinct equivalent positions (each wrapped into [0,1)); the
    orbit length is the site multiplicity, |G| / |stabiliser| — see
    :func:`site_orbit` for why that is a derivation and not a count.
    """
    return [p for p, _ in expand_orbit(sg, xyz, tol=tol)]


#: How many snapped sites a ``SITE_SNAPPED_TO_SPECIAL_POSITION`` message names
#: before it says "and N more".  ``where`` still carries every one of them.
_SNAP_MESSAGE_SITES = 4


def snap_diagnostics(sg: gemmi.SpaceGroup, sites, *, source: str,
                     prefix: str, tol: float = SITE_TOL) -> list[Diagnostic]:
    """``SITE_SNAPPED_TO_SPECIAL_POSITION`` for the sites whose orbit needed one.

    ``sites`` is an iterable of ``(label, (x, y, z))`` in model order; ``source``
    names where the coordinates came from, and ``prefix`` is the dot-path of the
    phase (``"phases.0"``) whose atoms they are.

    A site within ``tol`` of a special position but not on it is expanded at the
    snapped position, so its multiplicity is the special one — which is what the
    file's own ``_atom_site_symmetry_multiplicity`` says, and what its density
    implies.  The stored coordinate is **not** rewritten: the deviation is the
    caller's number and may be real, and the fit is unharmed either way, but it
    decides how many atoms the site puts in the cell and therefore ZMV and every
    weight fraction, so it cannot be decided in silence (issue #215).

    Empty when nothing moved, which is every structure whose sites sit on their
    special positions exactly.
    """
    moved: list[tuple[str, float, int, str]] = []
    for j, (label, xyz) in enumerate(sites):
        try:
            orbit = site_orbit(sg, np.asarray(xyz, dtype=np.float64), tol=tol)
        except ValueError as exc:
            # a reader's refusal must name the file it read (io/CLAUDE.md); the
            # orbit guard knows the site and the group but not where they came
            # from, and this is the only place that does
            raise ValueError(f"site {label!r} in {source}: {exc}") from exc
        if orbit.shift:
            moved.append((label, orbit.shift, orbit.multiplicity,
                          f"{prefix}.atoms.{j}"))
    if not moved:
        return []
    named = ", ".join(f"{lbl} ({shift:.1e} → multiplicity {m})"
                      for lbl, shift, m, _ in moved[:_SNAP_MESSAGE_SITES])
    if len(moved) > _SNAP_MESSAGE_SITES:
        named += f", and {len(moved) - _SNAP_MESSAGE_SITES} more"
    worst = max(shift for _, shift, _, _ in moved)
    return [Diagnostic(
        level="warning", code="SITE_SNAPPED_TO_SPECIAL_POSITION",
        where=[path for *_, path in moved],
        message=(f"{len(moved)} site(s) in {source} sit within {tol:g} of a "
                 f"special position of {sg.xhm()!r} without being on it, and "
                 f"were expanded at it: {named}. Largest shift {worst:.2e} in "
                 f"fractional coordinates"),
        suggestion="the stored coordinates are unchanged and the fit is "
                   "unaffected, but the multiplicity is the special one — it "
                   "is what decides how many atoms the site puts in the cell, "
                   "hence ZMV and every weight fraction. Check these sites "
                   "against the source's own multiplicities: if they agree, "
                   "nothing is wrong and the coordinates are simply rounded; "
                   "if they disagree, the coordinates and the space group are "
                   "telling you different things",
    )]


def setting_diagnostics(symbol: str, *, source: str, where: list[str],
                        cell=None, sites=None) -> list[Diagnostic]:
    """``SPACE_GROUP_SETTING_ASSUMED`` for a bare symbol the tables hold twice.

    ``source`` names what the symbol belongs to and opens the message (``"phase
    'spinel'"`` from a fit, ``"spinel.gpx: phase 'CuCr2O4'"`` from a reader);
    ``where`` is the dot-path the report hangs on.  ``cell`` and ``sites`` are
    optional — a caller that has them gets the composition each setting implies,
    which is the discriminator the reader recognises (issue #217).  ``sites`` is
    an iterable of ``(species, x, y, z, occupancy)``.

    **One builder, because a reader and a fit report the same fact.**  A `.EXP`
    or a `.inp` states a symbol and nothing else, so the setting is assumed at
    *read* and saying so there is the point of the report (issue #101); a
    hand-built ``Phase`` reaches the same silence with no file involved, and
    ``refine.py`` catches that one.  A format that states its operators is a
    different case entirely and does not come here — it is read, by
    :func:`setting_from_operators`, and there is nothing to assume.

    Empty when the symbol names its setting, when the tables hold only one, or
    when the caller already pinned it.

    **The composition is quoted only where it separates the settings.**  It
    usually does, which is why it leads: spinel's A and B multiplicities swap,
    so ``F d -3 m:1`` reads AB₂O₄ as A₂BO₄.  Where the swapping sites carry the
    *same* species it separates nothing — hausmannite Mn₃O₄ under ``I 41/a m
    d`` is Mn₁₂O₁₆ either way, measured on the GSAS-II corpus — and quoting one
    formula twice reads as evidence that the choice does not matter.  It does:
    the two Mn sites exchange multiplicities (8c/4b against 4a/8d), so the
    message falls back to the multiplicities themselves and the suggestion stops
    claiming a ZMV that has not moved (WP-1118).
    """
    taken, others = setting_alternatives(symbol)
    if not others:
        return []
    # An origin choice keeps the axes, so one coordinate list means something
    # under each setting and the compositions are comparable — that comparison
    # is the whole point.  ``:H`` against ``:R`` changes the axes themselves, so
    # the cell and the coordinates belong to one of the two and reading them
    # under the other is arithmetic, not a composition: calcite's hexagonal
    # 6/6/18 came back as 2/12/12.
    same_axes = not any(s.rsplit(":", 1)[-1] in ("H", "R")
                        for s in (taken, *others))
    settings = (taken, *others)
    # materialised once: the rows are walked twice below, and a caller passing a
    # generator would leave the second pass reading an exhausted one — an empty
    # multiplicity list rather than an error
    rows = [] if sites is None else [(s, x, y, z, occ)
                                     for s, x, y, z, occ in sites]
    formulas: list[str] = []
    if cell is not None and rows and same_axes:
        # here rather than at module scope: ``optimize.qpa`` is built on this
        # module, so the composition a report quotes is fetched when a report is
        # built and never on the way in
        from ..optimize.qpa import phase_zmv
        for setting in settings:
            try:
                counts = phase_zmv(setting, tuple(cell), rows).element_counts
            except (ValueError, KeyError):
                formulas = []
                break
            formulas.append(" ".join(f"{s}{c:g}"
                                     for s, c in sorted(counts.items())))

    separated = len(set(formulas)) > 1
    multiplicities: dict[str, str] = {}
    if formulas and not separated:
        for setting in settings:
            sg = get_spacegroup(setting)
            multiplicities[setting] = ", ".join(
                str(len(expand_positions(sg, np.asarray(row[1:4],
                                                        dtype=np.float64))))
                for row in rows)

    if separated:
        detail = "; ".join(f"{s} → {f}" for s, f in zip(settings, formulas))
        body = f"Cell contents each setting implies: {detail}"
        closing = ("The site multiplicities differ between settings, so the "
                   "choice changes ZMV and every weight fraction while leaving "
                   "Rwp alone")
    elif multiplicities:
        detail = "; ".join(f"{s} → {m}" for s, m in multiplicities.items())
        body = (f"Both settings imply the same cell contents ({formulas[0]}), "
                f"so the composition does not separate them — the site "
                f"multiplicities do: {detail}")
        closing = ("The sites exchange multiplicities between settings without "
                   "changing the cell contents, so ZMV and the weight fractions "
                   "cannot tell you which is right — what moves is which site "
                   "carries which multiplicity, and with it the calculated "
                   "pattern")
    else:
        detail = (f"{taken}, against {', '.join(others)}"
                  + ("" if same_axes else " — hexagonal against rhombohedral "
                     "axes, so the cell and the coordinates belong to one of "
                     "them and no composition compares the two"))
        body = f"The alternatives are {detail}"
        closing = ("The site multiplicities differ between settings, so the "
                   "choice changes ZMV and every weight fraction while leaving "
                   "Rwp alone")

    return [Diagnostic(
        level="warning", code="SPACE_GROUP_SETTING_ASSUMED", where=list(where),
        message=(f"{source} names space group {symbol!r}, which the tables hold "
                 f"in {1 + len(others)} settings; it was resolved to {taken}. "
                 + body),
        suggestion=("if that is the setting you meant, nothing is wrong — write "
                    f"it into the symbol ({taken!r}) to say so. If it is not, "
                    "the coordinates belong to another setting: name it instead "
                    f"({', '.join(repr(s) for s in others)}). " + closing),
    )]


@dataclass
class ReflectionSet:
    """Unique reflections in a d-range, frozen for one refinement stage.

    Attributes
    ----------
    hkl : (N, 3) int array — one representative per orbit.  For a satellite row
        (WP-1326) this is the **parent** reciprocal-lattice vector H, and the
        scattering vector the peak sits at is :attr:`index`, H + m·k.
    multiplicity : (N,) int — orbit size under the Laue group (Friedel incl.).
    d : (N,) float — d-spacings at the cell used for generation.
    satellite_order : (N,) int or None — the m of Q = H + m·k, 0 on a nuclear
        row.  ``None`` — every purely nuclear set — is not the same as an
        all-zero array: it is what makes :attr:`index` return ``hkl`` itself,
        so a phase without a propagation vector reaches every consumer with
        the identical array object it always did.
    propagation_vector : (3,) float or None — k in fractional coordinates of
        the conventional reciprocal cell, carried beside the orders so
        :attr:`index` can be rebuilt from what is stored.
    """

    hkl: np.ndarray
    multiplicity: np.ndarray
    d: np.ndarray
    spacegroup: str = ""
    #: The explicit ``x,y,z`` list when :attr:`spacegroup` is a *label* rather
    #: than a symbol (:class:`OperatorGroup`), else ``None`` — so a consumer
    #: that needs the group again (``report.strain``'s Stephens basis) can
    #: rebuild it with :func:`resolve_group` instead of re-resolving a label
    #: that names no tabulated group.  ``None`` for every set generated before
    #: this field existed, which is every set from a symbol.
    operations: tuple[str, ...] | None = None
    extra: dict = field(default_factory=dict)
    satellite_order: np.ndarray | None = None
    propagation_vector: tuple[float, float, float] | None = None

    def __len__(self) -> int:
        return len(self.hkl)

    @property
    def index(self) -> np.ndarray:
        """(N, 3) — the reciprocal-space index each row's peak sits at.

        ``hkl`` for a nuclear row, H + m·k for a satellite; the array is
        integer when nothing in the set is a satellite and float otherwise.
        **Everything that computes a position, a d-spacing or a width reads
        this**, and everything that identifies a reflection — the structure
        factor's op subsets, the March-Dollase orbit, a stored per-hkl
        intensity — reads ``hkl`` and ``satellite_order`` instead.  The split
        is what keeps a satellite an integer object in the record while its
        peak sits at a rational index (WP-1326).
        """
        if self.satellite_order is None:
            return self.hkl
        k = np.asarray(self.propagation_vector, dtype=np.float64)
        return (self.hkl.astype(np.float64)
                + self.satellite_order[:, None].astype(np.float64) * k)

    @property
    def is_satellite(self) -> np.ndarray:
        """(N,) bool — which rows are satellites; all-False when none are."""
        if self.satellite_order is None:
            return np.zeros(len(self.hkl), dtype=bool)
        return self.satellite_order != 0

    @property
    def hklm(self) -> np.ndarray:
        """(N, 4) int — (H, m) per row, m = 0 on a nuclear row.

        What **identifies** a reflection wherever one is named to a reader (a
        tick label, a diagnostic's ``where``): the parent H alone does not,
        since H + k and H − k share it and a satellite of (0, 0, 0) is not the
        origin.  Render one row with :func:`reflection_label` or
        :func:`reflection_label_row`.
        """
        h = np.asarray(self.hkl, dtype=np.int64).reshape(-1, 3)
        m = (np.zeros(len(h), dtype=np.int64) if self.satellite_order is None
             else np.asarray(self.satellite_order, dtype=np.int64))
        return np.column_stack([h, m])

    def two_theta(self, cell: tuple[float, float, float, float, float, float],
                  wavelength: float) -> np.ndarray:
        d = d_spacings(self.index, *cell)
        return two_theta_deg(d, wavelength)


def reflection_label_row(hklm) -> list[int]:
    """``[h, k, l]`` for a nuclear row, ``[h, k, l, m]`` for a satellite.

    The row a ``tick_hkl`` list carries (WP-1438, WP-1326): three integers
    exactly as before wherever there is no propagation vector, and the order m
    appended where there is, so the satellites H + k and H − k are two labels
    and neither reads as its parent.  A renderer that spells only three-index
    rows shows a four-index one as unlabelled rather than as the wrong
    reflection.
    """
    h, k, el, m = (int(v) for v in hklm)
    return [h, k, el] if m == 0 else [h, k, el, m]


def reflection_label(hklm) -> str:
    """``"(1, 0, 0)"`` for a nuclear row, ``"(0, 0, 0)+k"`` for a satellite.

    The nuclear spelling is ``str`` of the index tuple, byte for byte what a
    diagnostic printed before WP-1326; a satellite appends its order as
    ``+k``/``-k`` (``+2k`` beyond the first order).
    """
    h, k, el, m = (int(v) for v in hklm)
    base = str((h, k, el))
    if m == 0:
        return base
    mag = "" if abs(m) == 1 else str(abs(m))
    return f"{base}{'+' if m > 0 else '-'}{mag}k"


def reflection_orbits(sg_symbol: str, hkl_reps: np.ndarray) -> list[np.ndarray]:
    """Distinct symmetry+Friedel equivalents of each representative reflection.

    Returns one ``(m_k, 3)`` integer array per row of ``hkl_reps``, listing the
    Laue-group orbit (Friedel mates included) — the same set ``generate_reflections``
    counts to get the multiplicity, so ``len(orbit) == multiplicity``.  The
    reciprocal-space action is the **transposed** rotation (see the comment in
    ``generate_reflections``); this is the frozen discrete object the
    March-Dollase correction averages over, computed once per stage.
    """
    rots = rotation_matrices(as_group(sg_symbol))
    rot_int = np.rint(np.transpose(rots, (0, 2, 1))).astype(np.int64)
    orbits: list[np.ndarray] = []
    for h in np.asarray(hkl_reps, dtype=np.int64):
        images = np.einsum("mij,j->mi", rot_int, h)
        images = np.vstack([images, -images])  # Friedel mates
        uniq = sorted({tuple(map(int, im)) for im in images})
        orbits.append(np.array(uniq, dtype=np.int64))
    return orbits


def generate_reflections(sg_symbol: str,
                         cell: tuple[float, float, float, float, float, float],
                         wavelength: float,
                         two_theta_max: float,
                         two_theta_min: float = 0.0,
                         *, apply_absences: bool = True) -> ReflectionSet:
    """Enumerate the symmetry-unique, absence-allowed reflections in range.

    Strategy: enumerate all integer hkl in the sphere d ≥ d_min =
    λ/(2 sin(θ_max)), drop systematic absences (gemmi), group the survivors
    into Laue-group orbits (including Friedel mates), and keep one
    representative per orbit with its orbit size as the multiplicity.

    ``apply_absences=False`` keeps every systematically absent orbit —
    **centring absences included**, since gemmi's one absence test is where the
    centring condition lives too — with the parent's Laue multiplicities.  A
    caller that wants the lattice rather than every integer hkl applies the
    centring itself.  Its one caller is
    ``crystallography.magnetic.scattering.magnetic_reflections``: a k = 0
    magnetic space group generally drops the parent's glide and screw
    operations, so it puts intensity exactly on the reflections a glide or
    screw absence removes, and those rows have to exist for the peak to be
    computed at all (WP-1327; WP-1326 measured it on Cr₂WO₆).  **The default is
    unchanged**, so every existing caller enumerates the same list in the same
    order and every number it produces is bit-identical.
    """
    sg = as_group(sg_symbol)
    ops = sg.operations()

    d_min = wavelength / (2.0 * np.sin(np.radians(two_theta_max / 2.0)))
    a, b, c = cell[0], cell[1], cell[2]
    hmax = int(np.floor(a / d_min)) + 1
    kmax = int(np.floor(b / d_min)) + 1
    lmax = int(np.floor(c / d_min)) + 1

    # refuse before allocating: a collapsed or mis-scaled cell (or a
    # wavelength typed in the wrong unit) implies index ranges whose grid
    # would be petabytes — measured 63747 × 63747 × 81527 = 2.35 PiB on a
    # real external CIF (WP-1028 §(b)), which killed the process instead of
    # naming the cause
    n_grid = (2 * hmax + 1) * (2 * kmax + 1) * (2 * lmax + 1)
    if n_grid > MAX_HKL_GRID_POINTS:
        raise ValueError(
            f"refusing to enumerate reflections for cell a={a:g}, b={b:g}, "
            f"c={c:g} Å at d_min={d_min:.4g} Å (λ={wavelength:g} Å, "
            f"2θ_max={two_theta_max:g}°): index ranges ±{hmax}, ±{kmax}, "
            f"±{lmax} span {n_grid:.2e} grid points "
            f"(limit {MAX_HKL_GRID_POINTS:.0e}). A cell this large relative "
            f"to d_min usually means a collapsed or mis-scaled cell, or a "
            f"wavelength/2θ range implying an unphysical resolution.")

    rng_h = np.arange(-hmax, hmax + 1)
    rng_k = np.arange(-kmax, kmax + 1)
    rng_l = np.arange(-lmax, lmax + 1)
    H, K, L = np.meshgrid(rng_h, rng_k, rng_l, indexing="ij")
    hkl = np.column_stack([H.ravel(), K.ravel(), L.ravel()]).astype(np.int64)
    hkl = hkl[~np.all(hkl == 0, axis=1)]

    d = d_spacings(hkl, *cell)
    keep = d >= d_min * 0.999
    if two_theta_min > 0.0:
        d_max = wavelength / (2.0 * np.sin(np.radians(max(two_theta_min, 1e-3) / 2.0)))
        keep &= d <= d_max * 1.001
    hkl, d = hkl[keep], d[keep]

    # systematic absences via gemmi GroupOps (vectorised where available)
    if apply_absences:
        try:
            absent = np.asarray(ops.systematic_absences(hkl), dtype=bool)
        except (AttributeError, TypeError):
            absent = np.array(
                [ops.is_systematically_absent(list(map(int, h))) for h in hkl])
        hkl, d = hkl[~absent], d[~absent]

    # Laue-group orbits.  A real-space operation x' = Rx + t acts on Miller
    # indices (column form) as h' = Rᵀ h; the orbit therefore uses the
    # transposed rotations.  ({Rᵀ} ≠ {R} as a set outside cubic/orthogonal
    # settings — e.g. trigonal threefold axes — so the transpose matters.)
    # Friedel mates ±h are merged.  Exact with or without anomalous
    # scattering — the powder measures the ±h average and structure_factor
    # returns it in closed form; see the module docstring.
    rots = rotation_matrices(sg)
    rot_int = np.rint(np.transpose(rots, (0, 2, 1))).astype(np.int64)
    # One einsum over every (operation, hkl) pair rather than one per hkl.  The
    # per-hkl form spent ~11 µs of numpy dispatch on three-element arrays, which
    # is the whole cost at this size: this is 14-34× faster and returns the same
    # arrays element for element, checked against the loop over all 564 gemmi
    # settings, not merely over a few systems (the reason to check every one is
    # the Rᵀ trap in this module's docstring — a wrong action keeps the orbit
    # *count* right in every crystal system).
    # Lexicographic order on (h, k, l) is numeric order on a mixed-radix
    # encoding, so "largest image" becomes an integer max along the image axis.
    # ``base`` bounds every image component — |Rᵀh|_∞ ≤ max row sum of |Rᵀ| times
    # |h|_∞ — and is computed once so codes stay comparable across the chunks
    # below.
    # a range that admits no reflection is a legitimate answer, not an error —
    # the per-hkl loop simply did not execute, and ``max`` on the empty stack
    # would raise
    base = (int(np.abs(rot_int).sum(axis=2).max())
            * (int(np.abs(hkl).max()) if len(hkl) else 0) + 1)
    radix = 2 * base + 1
    # The (2m, n, 3) image stack is the one array here that is not O(n): 48
    # operations over a million surviving hkl would be gigabytes, where the
    # per-hkl loop was O(1).  rep_code and n_distinct are per-hkl, so chunking
    # over hkl is exact and bounds the transient at CHUNK × 2m × 3 int64.
    chunk = max(1, _ORBIT_CHUNK_ELEMENTS // max(6 * len(rot_int), 1))
    rep_parts: list[np.ndarray] = []
    mult_parts: list[np.ndarray] = []
    for start in range(0, len(hkl), chunk):
        block = hkl[start:start + chunk]
        images = np.einsum("mij,nj->mni", rot_int, block)
        images = np.concatenate([images, -images], axis=0)  # Friedel
        code = (((images[..., 0] + base) * radix
                 + (images[..., 1] + base)) * radix
                + images[..., 2] + base)
        rep_parts.append(code.max(axis=0))
        # multiplicity is the count of *distinct* images, which a special
        # position makes smaller than the operation count — sort each orbit's
        # codes and count the changes rather than building a set per hkl
        ordered = np.sort(code, axis=0)
        mult_parts.append(1 + (np.diff(ordered, axis=0) != 0).sum(axis=0))
    rep_code = np.concatenate(rep_parts) if rep_parts else np.empty(0, dtype=np.int64)
    n_distinct = (np.concatenate(mult_parts) if mult_parts
                  else np.empty(0, dtype=np.int64))
    # one row per orbit, in the order the orbits are first met, as the loop did
    keep = np.sort(np.unique(rep_code, return_index=True)[1])
    sel = rep_code[keep]
    reps = np.stack([(sel // (radix * radix)) - base,
                     ((sel // radix) % radix) - base,
                     (sel % radix) - base], axis=1).astype(np.int64)
    mult = n_distinct[keep].astype(np.int64)
    d_reps = d_spacings(reps, *cell)
    sort = np.argsort(-d_reps)  # ascending 2θ = descending d
    return ReflectionSet(hkl=reps[sort], multiplicity=mult[sort], d=d_reps[sort],
                         spacegroup=sg.xhm(),
                         operations=(sg.xyz if isinstance(sg, OperatorGroup)
                                     else None))
