"""Crystal-structure schemas: ``Structure`` → ``Phase`` → ``Atom``.

Conventions
-----------
* Fractional coordinates; occupancies are site fractions in [0, 1].
* Atomic displacement: isotropic ``Biso`` in Å² with ``Biso = 8π² Uiso``
  (International Tables C) by default, or an optional anisotropic ``AnisoU``
  block per atom carrying the CIF U^ij tensor (Å²).
* The structure-factor sum runs over the symmetry orbit of each listed atom
  (asymmetric-unit atoms only should be listed), with reflection multiplicity
  applied to |F|² — the standard Rietveld formulation (Rietveld, 1969,
  J. Appl. Cryst. 2, 65).
"""

from __future__ import annotations

import functools
import math
from collections.abc import Sequence

from pydantic import Field, field_validator, model_validator

from .common import Base, Parameter

#: the lower bound below which ``params.transforms.internal_bounds`` treats a
#: softplus parameter as *unbounded* below, which is what lets its physical
#: value underflow to exactly zero
_SOFTPLUS_FLOOR = 1e-12

#: March coefficient bounds.  r = 1 is the identity, r < 1 / r > 1 map to
#: platy / needle habit (the mapping flips between reflection and transmission
#: geometry — see :mod:`rietx.model.preferred_orientation`), and a value
#: outside this range describes a texture no powder mount produces.  The floor
#: is what makes the softplus bound reachable at all: see
#: :class:`PreferredOrientation`.  Measured on a 90 wt % NaCl mixture where r
#: underflowed to zero: the stall went away *and* the fit improved, Rwp 30.8 %
#: → 13.2 % (WP-1028 §(e)).
MARCH_R_MIN = 0.15
MARCH_R_MAX = 6.0

def _op_key(op) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """One symmetry operation as an exact hashable key, modulo a lattice shift.

    gemmi stores both parts scaled by ``Op.DEN`` (24), so the rotation is an
    exact integer 3×3 and the translation an exact integer triple; reducing the
    translation modulo ``DEN`` is what makes ``x,y,z`` and ``x+1,y,z`` the same
    operation, which they are.  Used to compare operation lists and to test
    closure under composition without ever comparing floats.
    """
    return (tuple(int(v) for row in op.rot for v in row),
            tuple(int(v) % op.DEN for v in op.tran))


@functools.lru_cache(maxsize=64)
def _operation_list_refusal(xyz: tuple[str, ...],
                            space_group: str | None) -> str | None:
    """Why an operation list is refused, after ``"phase 'name'"``; else ``None``.

    ``Phase._operations_are_a_group``'s arithmetic, cached on the list and the
    plain symbol it must agree with (``None`` for a bracketed label, which
    claims no agreement).  The closure test composes every pair, 36 864 gemmi
    products for ``F d -3 m:2``'s 192 operations, and ``validate_assignment``
    reruns the validator on every assignment to any ``Phase`` field and every
    history load; the answer is a function of these two arguments alone, so
    it is computed once per list rather than once per assignment.
    """
    import gemmi

    ops = [gemmi.Op(s) for s in xyz]
    listed = {_op_key(op) for op in ops}
    if _op_key(gemmi.Op("x,y,z")) not in listed:
        return (f": symmetry_operations has {len(ops)} operation(s) and the "
                f"identity 'x,y,z' is not one of them, so the list is not a "
                f"group and the atoms listed are not in their own orbits")
    for a in ops:
        for b in ops:
            if _op_key(a * b) not in listed:
                return (f": symmetry_operations is not closed under "
                        f"composition — {a.triplet()!r} times "
                        f"{b.triplet()!r} is {(a * b).triplet()!r}, which is "
                        f"not in the list (modulo a lattice translation). A "
                        f"partial operation list gives partial site orbits, "
                        f"so |F|² would be wrong by a factor with nothing to "
                        f"show it")
    if space_group is None:
        return None
    from ..crystallography.symmetry import get_spacegroup

    try:
        symbol_ops = {_op_key(op)
                      for op in get_spacegroup(space_group).operations()}
    except ValueError as exc:
        return (f": space_group {space_group!r} is neither a symbol this "
                f"package resolves nor a bracketed label ({exc}). A phase "
                f"carrying symmetry_operations still needs a label: the "
                f"symbol the list agrees with, or the closest type in "
                f"brackets")
    if symbol_ops != listed:
        missing = len(symbol_ops - listed)
        extra = len(listed - symbol_ops)
        return (f" declares {len(listed)} symmetry_operations and the space "
                f"group {space_group!r}, which generates {len(symbol_ops)} — "
                f"and they are not the same group: {missing} of the symbol's "
                f"operations are missing from the list and {extra} of the "
                f"list's are not in the symbol. The site orbits and the "
                f"systematic absences would differ between the two, so this "
                f"is refused rather than resolved. If the symbol is only the "
                f"closest *type* — which is what a doubled cell does to a "
                f"glide, turning its half into a quarter no symbol carries — "
                f"say so by bracketing the label, as in "
                f"'{space_group} [unnamed in this cell]'")
    return None


#: Species of the mandatory dummy atom a Le Bail-only phase carries
#: (:func:`lebail_scaffold`).  Carbon because its K edge (284 eV) is nowhere near
#: any laboratory or ordinary synchrotron wavelength, so ``dispersion.resolve`` —
#: on by default since v1.0 — can never refuse it, and because the choice is
#: inert: ``_run_stage`` force-fixes every ``.atoms.`` path in lebail mode, so the
#: atom sets the *starting* per-hkl intensities and nothing else.
#:
#: Here rather than in :mod:`rietx.indexing.workflow`, which owned it first, only
#: because the scaffold moved: a cell typed into the GUI reaches it without
#: indexing (WP-1206).  That module re-exports the name.
DUMMY_SPECIES = "C"


class Cell(Base):
    """Unit-cell lengths (Å) and angles (degrees).

    Crystal-system constraints (e.g. cubic ``a=b=c``, α=β=γ=90°) are enforced
    by the parameter-vector compiler from the space group, not stored here.

    The six parameters carry no physical bounds of their own (``min=-inf,
    max=inf`` by default, like every other bare ``Parameter`` field) — the
    cell-window / tie-window machinery in :mod:`rietx.params.vector`
    (``cell_window``, ``freeze_cell_windows``, ``_tie_windows``) reads an
    infinite stored bound as *no claim made* and this is deliberately left
    that way (issue #283's own discussion; a schema default here is a design
    decision for that machinery, not a local fix).  A degenerate cell reached
    by an unbounded search is refused by
    :func:`~rietx.crystallography.lattice.d_spacings` and neutralised by the
    solver's own guard instead (``CELL_DEGENERATE_PROBE``).
    """

    a: Parameter
    b: Parameter
    c: Parameter
    alpha: Parameter
    beta: Parameter
    gamma: Parameter

    @classmethod
    def cubic(cls, a: float, *, vary: bool = False) -> "Cell":
        return cls(
            a=Parameter(value=a, vary=vary),
            b=Parameter(value=a),
            c=Parameter(value=a),
            alpha=Parameter(value=90.0),
            beta=Parameter(value=90.0),
            gamma=Parameter(value=90.0),
        )

    def lengths_angles(self) -> tuple[float, float, float, float, float, float]:
        return (self.a.value, self.b.value, self.c.value,
                self.alpha.value, self.beta.value, self.gamma.value)


class AnisoU(Base):
    """Anisotropic displacement tensor in the CIF U^ij convention (Å²).

    The Debye-Waller factor is T(h) = exp(−2π² Σ_ij U^ij h_i h_j a*_i a*_j)
    — the ``_atom_site_aniso_U_ij`` definition, so these are exactly the
    numbers a CIF carries.  Conversions to U*, U_cart and U_eq, and the
    positive-definiteness test, live in ``crystallography.adp``.

    Components refine through site-symmetry-allowed *patterns*, not one by
    one: :class:`~rietx.params.vector.ParameterTable` ties each component to
    ``phases.i.atoms.j.adp.k`` DOFs derived from
    ``crystallography.wyckoff.adp_basis``.  Setting ``vary=True`` on any
    component frees all of the site's allowed patterns; ``min``/``max`` on a
    component are inert (the DOFs are unbounded — positive-definiteness is
    enforced by a diagnostic, not by box bounds, because the physical
    constraint couples all six components).
    """

    u11: Parameter
    u22: Parameter
    u33: Parameter
    u12: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="A^2"))
    u13: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="A^2"))
    u23: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="A^2"))

    def values(self) -> tuple[float, float, float, float, float, float]:
        """(U11, U22, U33, U12, U13, U23) — the order used everywhere."""
        return (self.u11.value, self.u22.value, self.u33.value,
                self.u12.value, self.u13.value, self.u23.value)

    @classmethod
    def from_values(cls, u6, *, vary: bool = False) -> "AnisoU":
        return cls(**{n: Parameter(value=float(v), vary=vary, unit="A^2")
                      for n, v in zip(("u11", "u22", "u33", "u12", "u13", "u23"),
                                      u6, strict=True)})

    @classmethod
    def isotropic(cls, uiso: float, cell: "Cell", *, vary: bool = False) -> "AnisoU":
        """The tensor equivalent to an isotropic Uiso in *this* cell.

        Not Uiso·δ_ij except when the reciprocal axes are orthogonal — see
        ``crystallography.adp.isotropic_u6``.
        """
        from ..crystallography.adp import isotropic_u6

        return cls.from_values(isotropic_u6(uiso, cell.lengths_angles()), vary=vary)


class PreferredOrientation(Base):
    """Single-axis March-Dollase preferred-orientation correction (Dollase 1986).

    Multiplies each reflection's intensity by the March factor averaged over
    the reflection's symmetry orbit; ``axis`` is the crystallographic direction
    of preferred alignment given as **integer hkl indices** (a reciprocal-
    lattice / plane-normal direction, the convention GSAS-II and FullProf use),
    and ``r`` is the refinable March coefficient.  The physics and the
    r < 1 / r > 1 → platy / needle mapping (which flips between reflection and
    transmission geometry) live in :mod:`rietx.model.preferred_orientation`.

    ``r`` is softplus-bounded strictly positive (a hard zero bound stalls TRF)
    and **defaults to 1.0, vary=False** — r ≡ 1 is exactly the no-correction
    case, so a phase carrying this block but not refining it is bit-identical
    to one without it.

    **The strictness is a promise softplus alone does not keep** (WP-1028
    §(e)).  ``min=0.0`` maps to an internal bound of −∞ (``internal_bounds``
    treats any lower bound at or under 1e-12 as absent), and ``log(1+e^u)``
    underflows to *exactly* 0.0 below u ≈ −745.  The March factor divides by
    r, so the residual becomes inf/NaN, nothing raises, and TRF grinds its
    whole budget on garbage — measured, a 3-second stage that had not
    returned after ten minutes.  So the bound is :data:`MARCH_R_MIN`, which
    makes the internal bound finite and the underflow unreachable.  It is
    physics, not a fudge: r = 1 is the identity, and a March coefficient
    outside 0.15-6 describes a texture no powder mount produces.
    """

    axis: tuple[int, int, int]
    r: Parameter = Field(
        default_factory=lambda: Parameter(value=1.0, vary=False, min=MARCH_R_MIN,
                                          max=MARCH_R_MAX, transform="softplus")
    )

    @model_validator(mode="after")
    def _axis_nonzero(self) -> "PreferredOrientation":
        if all(h == 0 for h in self.axis):
            raise ValueError("preferred-orientation axis (0,0,0) has no direction")
        return self

    @model_validator(mode="after")
    def _r_bound_is_reachable(self) -> "PreferredOrientation":
        """Repair a lower bound that softplus cannot actually enforce.

        Only fires on a bound *at or below* the softplus floor — the value
        that promises "strictly positive" and delivers zero.  Any positive
        bound a caller chose is left alone, because a positive bound already
        maps to a finite internal one and the underflow cannot happen.  This
        exists because the broken bound outlives the default: a JSON project
        or a history node written before this fix carries ``min: 0.0``
        explicitly, and would deserialize straight back into the stall.
        """
        if self.r.min <= _SOFTPLUS_FLOOR:
            self.r.min = MARCH_R_MIN
        if not math.isfinite(self.r.max):
            self.r.max = MARCH_R_MAX
        self.r.value = min(max(self.r.value, self.r.min), self.r.max)
        return self


def _s() -> Parameter:
    return Parameter(value=0.0, unit="1e-12 A^-4")


class StephensStrain(Base):
    """Anisotropic strain broadening coefficients S_HKL (Stephens, 1999).

    The variance of M = 1/d² across the crystallites is a homogeneous quartic
    in the Miller indices, σ²(M) = 10⁻¹²·Σ S_HKL h^H k^K l^L, which turns into
    an **hkl-dependent** Lorentzian width Λ(hkl)·tanθ — the physics, the units
    (S_HKL in 10⁻¹² Å⁻⁴) and the FWHM-not-σ convention are all documented in
    :mod:`rietx.crystallography.stephens`, which also derives the
    Laue-allowed subspace.

    Like :class:`AnisoU`, the components refine through symmetry-allowed
    *patterns* rather than one by one: ``ParameterTable`` ties them to
    ``phases.i.strain.k`` DOFs and the values are **absolute**
    (S = Σₖ θₖ·Bₖ), so the lattice symmetry is enforced exactly and a set of
    coefficients outside the allowed subspace is an error, not something to
    silently symmetrise.  ``min``/``max`` on a component are inert: σ²(M) ≥ 0
    couples all fifteen, so positivity is a diagnostic
    (``STEPHENS_STRAIN_NOT_POSITIVE``), not a box.

    Build one with :meth:`isotropic` — all-zero coefficients are the exact
    no-broadening identity, but they sit at the √ cusp of the width law where
    the derivative is unbounded, so refining from there is rejected.
    """

    s400: Parameter = Field(default_factory=_s)
    s310: Parameter = Field(default_factory=_s)
    s301: Parameter = Field(default_factory=_s)
    s220: Parameter = Field(default_factory=_s)
    s211: Parameter = Field(default_factory=_s)
    s202: Parameter = Field(default_factory=_s)
    s130: Parameter = Field(default_factory=_s)
    s121: Parameter = Field(default_factory=_s)
    s112: Parameter = Field(default_factory=_s)
    s103: Parameter = Field(default_factory=_s)
    s040: Parameter = Field(default_factory=_s)
    s031: Parameter = Field(default_factory=_s)
    s022: Parameter = Field(default_factory=_s)
    s013: Parameter = Field(default_factory=_s)
    s004: Parameter = Field(default_factory=_s)

    def values(self) -> tuple[float, ...]:
        """The fifteen coefficients in ``crystallography.stephens.S_NAMES`` order."""
        from ..crystallography.stephens import S_NAMES

        return tuple(getattr(self, n).value for n in S_NAMES)

    @classmethod
    def from_values(cls, s15, *, vary: bool = False) -> "StephensStrain":
        from ..crystallography.stephens import S_NAMES

        return cls(**{n: Parameter(value=float(v), vary=vary, unit="1e-12 A^-4")
                      for n, v in zip(S_NAMES, s15, strict=True)})

    @classmethod
    def isotropic(cls, microstrain: float, cell: "Cell", *, vary: bool = True
                  ) -> "StephensStrain":
        """The coefficients giving σ(M)/M ≡ ``microstrain``·10⁻⁶ for every hkl.

        M² is a Laue invariant in any group, so this point lies *exactly* in
        the allowed subspace whatever the symmetry — the rank-4 analogue of
        :meth:`AnisoU.isotropic`.  ``microstrain`` is ΔM/M = 2·Δd/d in ppm;
        1000 (0.1 % in ΔM/M) is a reasonable start for a broadened lab pattern.
        Defaults to ``vary=True``: an isotropic block that never refines is
        just a clumsy spelling of ``lor_strain``.
        """
        from ..crystallography.stephens import isotropic_coefficients

        return cls.from_values(
            isotropic_coefficients(cell.lengths_angles(), microstrain), vary=vary)


#: A moment this small is *at the floor*: the direction of a moment of this
#: length is not a fact about the sample, and |F_m|² ∝ m² makes its Jacobian
#: column vanish with it.  A moment block whose modulus sits here is held and
#: reported unsupported (WP-1327, the shape WP-1301 uses for a phase the data
#: cannot see).  0.001 μ_B is three orders below the smallest ordered moment a
#: powder measurement resolves and two below the esd of a good one, so it is a
#: floor rather than a threshold anyone could argue about.
MOMENT_FLOOR_MU_B = 1e-3


class Moment(Base):
    """A magnetic moment on a site, in crystal-axis components (μ_B).

    The components are the magCIF ``_atom_site_moment.crystalaxis_*``
    convention (COMCIFS ``magnetic_dic``): "a right-handed basis of **unit
    vectors** parallel to the unit-cell basis vectors".  That basis is oblique
    whenever the cell is, so |m| is √(mᵀ·G·m) with G the unit-vector metric and
    **not** √(Σmᵢ²) — on hexagonal axes the moment (1, 1, 0) is 1 μ_B, not √2
    (``crystallography.magnetic.operators.moment_magnitude``).

    **The components are not the refined parameters.**  A moment refines
    through ``phases.i.atoms.j.moment.dof<k>`` — a modulus and, where the site
    symmetry allows a direction to move at all, one or two angles inside the
    allowed subspace — because a direction a powder average cannot determine
    has to be a *column* something can name (Shirane, 1959; WP-1327).  These
    three are written back from those DOFs at the end of a stage, carry
    ``vary`` as the *intent* that frees the DOFs, and their ``stderr`` stays
    ``None``: the esd of this block lives on the modulus, which is the quantity
    the data measures.

    ``ion`` is the magnetic form-factor key — ``"Cr3+"``, ``"Ho3+"`` — and is
    **not** ``Atom.species``: the nuclear scattering length is keyed by
    nuclide and the form factor by oxidation state, and an ion the table does
    not carry is refused by name rather than mapped to a neighbour.  ``g`` is
    the Landé factor; ``None`` means the spin-only 2 for a 3d/4d ion and is
    **refused** for a 4f/5f one, where the ⟨j₂⟩ term does not vanish
    (``crystallography.magnetic.form_factor``).
    """

    crystalaxis_x: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="mu_B"))
    crystalaxis_y: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="mu_B"))
    crystalaxis_z: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="mu_B"))
    ion: str
    g: float | None = None

    def values(self) -> tuple[float, float, float]:
        """The three crystal-axis components, in the CIF tag order."""
        return (self.crystalaxis_x.value, self.crystalaxis_y.value,
                self.crystalaxis_z.value)

    @property
    def vary(self) -> bool:
        """Whether any component asks for the block to refine."""
        return any(getattr(self, n).vary for n in MOMENT_COMPONENTS)

    @classmethod
    def from_values(cls, components, ion: str, *, g: float | None = None,
                    vary: bool = False) -> "Moment":
        """A block from three crystal-axis components in μ_B."""
        mx, my, mz = (float(c) for c in components)
        return cls(
            crystalaxis_x=Parameter(value=mx, vary=vary, unit="mu_B"),
            crystalaxis_y=Parameter(value=my, vary=vary, unit="mu_B"),
            crystalaxis_z=Parameter(value=mz, vary=vary, unit="mu_B"),
            ion=ion, g=g)


#: The three component field names, in the magCIF tag order.  Named once
#: because the parameter table, the write-back and the exporters all walk them
#: and a fourth spelling of the same list is a fourth place to forget one.
MOMENT_COMPONENTS = ("crystalaxis_x", "crystalaxis_y", "crystalaxis_z")


class Atom(Base):
    """One site in the asymmetric unit.

    Displacement is isotropic (``biso``) unless ``aniso`` is set, which is an
    opt-in *per atom*: a structure may mix isotropic and anisotropic sites.
    When ``aniso`` is present it alone drives the Debye-Waller factor and
    ``biso`` becomes an inert record of the starting estimate — refining it
    would be a silently dead parameter, so that is rejected.

    ``species`` is validated at *compile*, not here (WP-1003, ratifying
    1014): an unknown symbol is a crystallography question the schema cannot
    answer, so the compile error is the authoritative refusal and the GUI's
    stricter up-front check is a deliberately earlier error on the human
    path, not a second contract.  Schema validation was declined **and is not
    cheap later** — refusing a previously-storable value is a breaking change
    under the hybrid rule, so any future tightening is a read-time diagnostic
    or a better compile error, never schema refusal.
    """

    label: str
    species: str  # scattering species, e.g. "La", "B", "Fe3+"
    x: Parameter
    y: Parameter
    z: Parameter
    occ: Parameter = Field(default_factory=lambda: Parameter(value=1.0, min=0.0, max=1.5))
    biso: Parameter = Field(default_factory=lambda: Parameter(value=0.5, min=0.0, max=25.0, unit="A^2"))
    aniso: AnisoU | None = None
    # Optional magnetic moment, opt-in per atom exactly as ``aniso`` is
    # (WP-1327).  ``None`` — the default — is exactly off: a phase whose atoms
    # declare none compiles, refines and reports as it did before this field
    # existed.  A moment needs ``Phase.magnetic_symmetry`` beside it, because
    # without an operator list there is no allowed subspace to refine in and
    # no way to propagate the moment over the site's orbit; that is checked on
    # the phase, which is the object that carries both.
    moment: Moment | None = None

    @model_validator(mode="before")
    @classmethod
    def _inherit_declared_bounds(cls, data: object) -> object:
        """Fill a caller-supplied Parameter's min/max/unit from the field's
        own declared default, wherever the caller left that attribute unset —
        **before** a ``Parameter`` is ever constructed for that field, so
        nothing about the caller's own object is read *or written*.

        ``occ``/``biso`` declare their physical range in a ``default_factory``
        (min=0, max=1.5 for occ; min=0, max=25, unit="A^2" for biso) rather
        than as a field constraint, so the range only ever applied when the
        field was omitted entirely — a caller supplying their own
        ``Parameter(value=..., vary=...)``, the natural way to set a starting
        value or hold one, silently got ``(-inf, +inf)`` and no unit instead
        (issue #204). Measured cost: a refined Biso of -165 A^2 and an
        81-point QPA error at unchanged Rwp, invisible at the call site.

        **The 25 A^2 ceiling is this package's own, and it is not common
        practice** (WP-1311, measured 2026-09-18).  FullProf's hard limits are
        opt-in, one user-supplied ``[LowLIMIT, HighLIMIT]`` line per parameter
        (its manual's "Hard limits for parameters"), and TOPAS's bounding
        constraints are declared per parameter in the input (Coelho, 2018);
        neither ships a default ceiling on a displacement parameter.  It has
        been here since v0.1 and the validator above is what made it bind a
        caller's own ``Parameter``, so it is kept rather than widened.  A
        specimen that genuinely runs hotter than 25 A^2 is served by supplying
        the bound explicitly --- ``Atom(..., biso=Parameter(value=8.0,
        vary=True, max=60.0))`` --- which wins over the declared one in either
        direction, by the rule two paragraphs down.

        Detected with ``model_fields_set`` (or, for a raw dict, its keys —
        the same "was this key present" question one representation down)
        rather than by comparing against ``Parameter``'s own bare defaults:
        an *explicit* ``min=-inf`` is indistinguishable from an omission by
        value alone, and must still win — an explicit bound always beats a
        declared one, in either direction.

        **A ``mode="after"`` validator was tried first and rejected.**
        Pydantic stores a passed-in ``Parameter`` *by reference*
        (``revalidate_instances="never"``), so ``getattr(self, name)`` in an
        after-validator hands back the caller's own object, not a copy; and
        ``Base``'s ``validate_assignment=True`` means the ``setattr`` that
        filled the missing attributes both wrote to that object and added the
        names to *its own* ``model_fields_set`` — the very signal the next
        ``Atom`` built from the same object would consult. Reusing one
        ``Parameter`` for two fields (a plausible pattern — "start both at
        the field default") leaked the first field's bounds and unit into
        the second, the same defect class as the one this validator exists to
        close, reopened through a different door. Filling the *raw* input
        before a ``Parameter`` object exists at all has no object to mutate:
        the replacement is a brand-new ``Parameter``, built from a dict of
        the caller's own values, never their instance. ``data`` itself is
        copied once up front for the same reason — ``model_validate`` may be
        handed the caller's own dict directly, unlike keyword construction
        where Python already built a fresh one.

        **Why the replacement is a ``Parameter``, not the merged dict
        itself**: ``validate_assignment=True`` (``Base``) re-runs *this*
        validator on every attribute assignment to an already-built
        ``Atom`` — ``atom.aniso = ...`` included — not only on the field
        being assigned, with ``data`` built from the model's current,
        already-valid field values. So this branch can fire for ``occ`` on
        an assignment that never touched it, wherever ``occ``'s own
        ``model_fields_set`` legitimately never grew a ``unit`` key (it was
        never given one because it never needed one — a bare ``Parameter``
        has no unit already). Pydantic does not re-run core validation on a
        field that is not itself the assignment target, so a bare ``dict``
        placed in ``data`` there reaches ``self.occ`` as a ``dict``, not a
        ``Parameter``, breaking every later ``.occ.value`` — measured via
        ``ParameterTable`` construction after ``atom.aniso = AnisoU(...)``.
        A real ``Parameter`` is a legal value however pydantic treats it.

        Generalised over every ``Parameter`` field on this class carrying a
        ``default_factory`` (today: ``occ`` and ``biso`` — not ``x``/``y``/
        ``z``, which are required with no factory and default to (-inf, inf)
        regardless, so they lose nothing), rather than naming the two fields,
        so a field added later the same way is covered without touching this
        validator. See ``test_every_bounds_carrying_atom_field_is_inherited``
        in ``tests/test_schemas.py``, which fails if a new such field is
        added and *not* covered by this loop.

        Inherits rather than refuses a bound-less ``Parameter``: requiring
        every caller to restate the physical range on every construction
        would break existing ones (the recipe and CIF readers already pass
        their own explicit bounds and are unaffected either way — checked
        against this repo's own call sites before landing this). If the
        caller's value falls outside the inherited bound,
        ``Parameter._check_bounds`` still raises once the merged dict is
        validated below — that is this fix doing its job, not a new refusal.

        A field's raw value may be a ``Parameter`` instance, a plain
        ``dict`` (the JSON-round-trip / ``model_validate`` shape), or absent
        entirely (the field omitted, where the ``default_factory`` already
        carries the declared bounds and there is nothing to fill). Anything
        else — ``None``, a bare number, a wrong type — is left untouched and
        falls through to whatever error normal field validation already
        raises for it; this validator only ever *adds* missing keys, never
        changes which construction is legal.
        """
        if not isinstance(data, dict):
            return data
        data = dict(data)
        for name, info in cls.model_fields.items():
            if info.annotation is not Parameter or info.default_factory is None:
                continue
            if name not in data:
                continue  # omitted: default_factory already carries the bounds
            raw = data[name]
            if isinstance(raw, Parameter):
                present = raw.model_fields_set
                base = raw.model_dump()
            elif isinstance(raw, dict):
                present = raw.keys()
                base = raw
            else:
                continue  # not a shape that carries min/max/unit presence
            missing = {"min", "max", "unit"} - set(present)
            if not missing:
                continue
            default = info.default_factory()
            fills = {attr: getattr(default, attr) for attr in missing}
            # A real Parameter, not the merged dict itself: validate_assignment
            # re-runs this validator on every attribute assignment to the
            # Atom (not only the field being assigned), with `data` built
            # from the model's *current*, already-validated field values —
            # so this branch also fires reassigning e.g. `atom.aniso = ...`
            # on an Atom whose `occ` has always been fine (model_fields_set
            # legitimately missing "unit", never given because it never
            # needed giving). Pydantic does not re-run core validation on a
            # field that is not itself being assigned, so a bare dict placed
            # here would reach `self.occ` as a dict, not a Parameter — it
            # must already be the right type.
            data[name] = Parameter(**{**base, **fills})
        return data

    @model_validator(mode="after")
    def _one_displacement_model(self) -> "Atom":
        if self.aniso is not None and self.biso.vary:
            raise ValueError(
                f"atom {self.label!r} has an anisotropic block, so biso does "
                "not enter the model; set biso.vary=False and vary the aniso "
                "components instead")
        return self


class BondRestraint(Base):
    """A soft restraint on the distance between two atoms of one phase.

    Contributes a single residual row √weight·(d − target)/sigma (Waser, 1963,
    Acta Cryst. 16, 1091 — least squares with observational restraints), so a
    known chemical distance can stabilise an under-determined coordinate
    without hard-constraining it.  ``atom_i``/``atom_j`` are **positional
    indices** into ``Phase.atoms`` (the dot-path convention everywhere).

    Distances obey periodic boundary conditions: the second atom is taken at
    the symmetry image ``R·x_j + t + n``.  ``op_index`` selects the rotation
    operation from the atom's frozen orbit subset (``PhaseSites.ops``) and
    ``translation`` the lattice shift ``n``; leaving ``op_index`` ``None``
    resolves the *minimum image* at the stage's compile-time coordinates and
    freezes that choice for the stage (frozen-per-stage discreteness — the
    positions still move smoothly, only the discrete op/translation is fixed).
    """

    atom_i: int
    atom_j: int
    target: float  # Å
    sigma: float = Field(gt=0.0)  # Å
    weight: float = Field(default=1.0, ge=0.0)
    op_index: int | None = None
    translation: tuple[int, int, int] = (0, 0, 0)


class AngleRestraint(Base):
    """A soft restraint on the i–j–k bond angle (vertex = the **middle** atom
    ``atom_j``), contributing √weight·(angle − target_deg)/sigma degrees.

    The angle is formed by u = x_i' − x_j and v = x_k' − x_j, where x_i' and
    x_k' are the (optionally symmetry-imaged) neighbour positions and x_j the
    vertex atom, taken at its base position.  Each neighbour carries its own
    PBC selection (``op_index_i``/``translation_i`` and
    ``op_index_k``/``translation_k``), resolved to the minimum image at compile
    time when the op index is ``None``, exactly as :class:`BondRestraint`.
    Angles near 0°/180° are ill-conditioned (cos θ is clamped just inside
    [−1, 1] before ``arccos``) and are not a supported target.
    """

    atom_i: int
    atom_j: int  # vertex
    atom_k: int
    target_deg: float
    sigma: float = Field(gt=0.0)  # degrees
    weight: float = Field(default=1.0, ge=0.0)
    op_index_i: int | None = None
    translation_i: tuple[int, int, int] = (0, 0, 0)
    op_index_k: int | None = None
    translation_k: tuple[int, int, int] = (0, 0, 0)


class ValueRestraint(Base):
    """A soft restraint pulling a single parameter toward ``target``.

    ``path`` is any dot-path in the model tree (e.g. ``phases.0.atoms.1.occ``);
    the row is √weight·(value − target)/sigma, linear in the physical value.
    """

    path: str
    target: float
    sigma: float = Field(gt=0.0)
    weight: float = Field(default=1.0, ge=0.0)


#: A soft observational restraint on one phase — a bond length, a bond angle,
#: or a single parameter value.  Each contributes one residual row that is kept
#: in the covariance (JᵀJ) but excluded from Rwp/Durbin-Watson/Bérar-Lelann
#: (they are soft observations, not data — the standard Rietveld convention).
Restraint = BondRestraint | AngleRestraint | ValueRestraint


class MagneticSymmetry(Base):
    """A magnetic (Shubnikov) space group as the two magCIF loops that state it.

    ``operations`` is ``_space_group_symop_magn_operation.xyz`` — xyz strings
    each carrying a time-reversal sign, ``"-x,-y,z,-1"`` — and ``centerings``
    is ``_space_group_symop_magn_centering.xyz``, the (anti)centring
    translations with the identity in it.  **This is the stored form**: no
    Shubnikov symbol is resolved by rietx, because no dependency here parses
    one and every route a user has to a magnetic structure (MAGNDATA,
    ISODISTORT, k-SUBGROUPSMAG, a magCIF from any of them) already emits the
    operator list.

    ``bns_number`` and ``symbol`` are **metadata**, carried through and never
    used to derive anything — the operators are the model
    (``planning`` D-4).  A UNI/BNS/OG *number* is nonetheless accepted as an
    alternative **input**: pass an ``int`` or a number string in place of the
    block and it is resolved through spglib's database by
    ``crystallography.magnetic.operators.magnetic_group`` (issue #257 A4),
    which fills all four fields.  What is stored is still the operator list.

    A commensurate k ≠ 0 structure is stated in its **magnetic supercell**
    with the parent's k recorded in ``propagation_vector_parent``: that is what
    magCIF itself does, and it is what lets one reflection list and one scale
    serve the nuclear and the magnetic contribution.  It is a *record* of
    provenance, never a propagation vector that generates reflections (that is
    WP-1326's route, which a moment model refuses:
    :func:`refuse_moment_model_with_k`).
    """

    operations: list[str]
    centerings: list[str] = Field(default_factory=lambda: ["x,y,z,+1"])
    bns_number: str | None = None
    og_number: str | None = None
    uni_number: int | None = None
    symbol: str | None = None
    setting: str | None = None
    #: k of the parent cell this supercell was built from, as three rational
    #: strings — a record of provenance for the report, never used to generate
    #: a reflection (the supercell's own reflections are the satellites).
    #: Written by ``magnetic.supercell.magnetic_supercell``.
    propagation_vector_parent: tuple[str, str, str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_a_number(cls, value):
        """A UNI/BNS/OG number in place of the block resolves to one (A4).

        ``magnetic_symmetry=136`` (UNI), ``"136.499"`` (BNS) or
        ``"136.7.1159"`` (OG) all become the same operator list with the
        database's own metadata attached, which is the input a user who has a
        *number* rather than a magCIF actually has.  Anything else is passed
        through to normal validation.
        """
        if isinstance(value, (int, str)) and not isinstance(value, bool):
            from ..crystallography.magnetic.operators import magnetic_group

            group = magnetic_group(value)
            ops, cent = group.xyz_strings()
            return {
                "operations": list(ops), "centerings": list(cent),
                "bns_number": group.bns_number, "og_number": group.og_number,
                "uni_number": group.uni_number, "setting": group.setting,
            }
        return value

    @model_validator(mode="after")
    def _is_a_group(self) -> "MagneticSymmetry":
        """Refuse a list that is not closed, or has no identity (M-5's guard).

        Parsing here rather than at compile is the opposite of the choice
        ``Atom.species`` makes, and deliberately so: an operator list is *not*
        a crystallography question the schema cannot answer — closure is
        arithmetic on the strings themselves, it needs no cell, no atoms and no
        wavelength, and a list that is not a group is not a magnetic space
        group under any later interpretation.  The cost is one import.
        """
        from ..crystallography.magnetic.operators import MagneticGroup

        if not self.operations:
            raise ValueError(
                "magnetic_symmetry.operations is empty; a magnetic space "
                "group is stated by its operator list and the identity "
                "'x,y,z,+1' is the least of it")
        try:
            MagneticGroup.from_xyz(self.operations, self.centerings)
        except ValueError as exc:
            raise ValueError(f"magnetic_symmetry: {exc}") from exc
        return self

    def group(self):
        """The :class:`~rietx.crystallography.magnetic.operators.MagneticGroup`."""
        from ..crystallography.magnetic.operators import MagneticGroup

        return MagneticGroup.from_xyz(
            self.operations, self.centerings,
            setting=self.setting or "as given", uni_number=self.uni_number,
            bns_number=self.bns_number, og_number=self.og_number)


#: Field names on :class:`Phase` that constitute a **moment model** — a
#: magnetic space group with moments on the sites.  The two descriptions of a
#: commensurate magnetic structure — a propagation vector on the nuclear cell
#: (WP-1326) and a magnetic space group with moments — must not both sit on
#: one phase, and :func:`refuse_moment_model_with_k` is the refusal that
#: enforces it, called from :meth:`Phase._k_is_usable`.  It was written and
#: tested by WP-1327 before ``Phase.propagation_vector`` existed, so that
#: adding the field was one call rather than a rule someone had to remember.
#: ``Atom.moment`` is not listed and does not need to be: a moment without a
#: magnetic symmetry is refused on its own (:meth:`Phase._moments_are_stateable`),
#: so a phase carrying any moment carries this field too.
MOMENT_MODEL_FIELDS: tuple[str, ...] = ("magnetic_symmetry",)


def refuse_moment_model_with_k(phase_name: str, present: Sequence[str]) -> None:
    """Raise when a phase declares both a propagation vector and a moment model.

    ``present`` is the moment-model fields the phase actually carries.  A
    commensurate magnetic structure can be described either by a propagation
    vector on the nuclear cell (this rung's hypothesis tool, no moments) or by
    a magnetic space group with moments in the magnetic supercell (WP-1327,
    the shape GSAS-II uses).  Both on one phase is not a richer model: it is
    the same physics stated twice with nothing to reconcile the two, so it is
    refused rather than silently letting one win.
    """
    if present:
        raise ValueError(
            f"phase {phase_name!r} declares a propagation vector and a moment "
            f"model ({', '.join(sorted(present))}) at once. A commensurate "
            "magnetic structure is described either by k on the nuclear cell "
            "— satellites, no moments, the hypothesis test — or by a magnetic "
            "space group with moments; the two say the same thing and nothing "
            "reconciles them. Drop propagation_vector to refine the moments, "
            "or drop the moment model to test the k")


class Phase(Base):
    """A crystalline phase: symmetry, cell, atoms, scale, sample broadening."""

    name: str
    space_group: str  # Hermann-Mauguin symbol or number-as-string, resolved via gemmi
    # The phase's symmetry operations as ``x,y,z`` triplets, when the phase
    # carries them explicitly instead of leaving them to be resolved from
    # ``space_group``.  ``None`` — the default, and every phase written before
    # this field existed — is exactly the old behaviour: gemmi resolves the
    # symbol and every consumer reads the operations from it.
    #
    # **Why a phase may need to carry them.**  A parent operation whose
    # translation along a doubled axis is a half becomes a *quarter* in the
    # child cell, and no Hermann-Mauguin symbol in any tabulated setting has a
    # quarter in its operation list.  The child group is a perfectly good space
    # group of that cell — orbits, site multiplicities and systematic absences
    # all defined — and the only thing it lacks is a name.  Without this field
    # the only honest answer to such a child is a refusal; with it the answer
    # is the list.
    #
    # **The rule for ``space_group`` beside it**, and it is a rule about
    # *labels*.  When the list is present ``space_group`` is a label, and one
    # of two kinds:
    #
    # * **bracketed** — ``"P m 1 1 [unnamed in 2a,b,a+c]"``.  The bracket is
    #   the marker that says "this symbol does not generate this group": the
    #   text before it is the closest standard *type* and no agreement with the
    #   list is claimed or checked.  A bracketed label **requires** the list
    #   (there would otherwise be nothing to fall back on), and the list is
    #   then the whole of the phase's symmetry.
    # * **a plain symbol** — the list must then be *exactly* the operations
    #   that symbol generates, and a disagreement is refused rather than
    #   resolved in either direction.  A redundant-but-verified list is what
    #   lets a caller state a group two ways and be told when the two are not
    #   the same group; silently preferring one of them is how a fit ends up
    #   with the wrong absences under a right-looking symbol.
    #
    # Stored canonically (gemmi's own triplet spelling, duplicates dropped) so
    # a JSON round trip is bit-identical, and **in the caller's order**,
    # because a CIF symmetry code is an index into a listed order.
    symmetry_operations: list[str] | None = None
    cell: Cell
    atoms: list[Atom]
    scale: Parameter = Field(
        default_factory=lambda: Parameter(value=1.0, vary=False, min=0.0, transform="softplus")
    )
    # Secondary-extinction coefficient (Sabine model, model/extinction.py).
    # Attenuates the strong low-angle reflections of a well-crystallised
    # sample: each reflection's integrated intensity is multiplied by
    # E(hkl) = E_B·sin²θ + E_L·cos²θ with a dimensionless x ∝ ext·|F|²·(λ/V)².
    # ext = 0 ⇒ E ≡ 1 exactly (off by default), so it is opt-in and never
    # perturbs a structure that does not free it.  Softplus-bounded positive
    # (a hard zero bound stalls TRF; the staged plan seeds it off zero).
    extinction: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, vary=False, min=0.0, transform="softplus")
    )
    # Optional single-axis March-Dollase preferred-orientation correction
    # (model/preferred_orientation.py).  None ⇒ no correction; a block with the
    # default r = 1 is also exactly the identity, so it is opt-in and never
    # perturbs a phase that does not free r.  The axis is fixed integer hkl; only
    # r enters the least-squares fit.
    preferred_orientation: PreferredOrientation | None = None
    # Sample contribution to Lorentzian width (deg 2θ units, see profiles.caglioti):
    # size term varies as 1/cosθ (Scherrer), strain term as tanθ.  Lorentzian
    # FWHMs add under convolution, so these stack on the instrument X, Y.
    lor_size: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="deg", transform="softplus")
    )
    lor_strain: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="deg", transform="softplus")
    )
    # Sample contribution to Gaussian *variance* (deg² 2θ; variances add under
    # convolution): size term varies as 1/cos²θ (GSAS's P), strain term as
    # tan²θ (stacks on the instrument Caglioti U).  Together with lor_size /
    # lor_strain this is the instrument ⊕ sample profile split: calibrate
    # U V W X Y on a standard, freeze them, then refine only these four.
    gauss_size: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="deg^2", transform="softplus")
    )
    gauss_strain: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="deg^2", transform="softplus")
    )
    # Optional Stephens (1999) anisotropic strain broadening: an hkl-dependent
    # Lorentzian width Λ(hkl)·tanθ replacing the isotropic lor_strain·tanθ.
    # None ⇒ no correction, and all-zero coefficients are exactly the identity
    # too, so it is opt-in and never perturbs a phase that does not use it.
    # The isotropic direction of the S subspace *is* the lor_strain column
    # (identically, not merely correlated), so declaring a block locks
    # lor_strain — the same bargain Atom.aniso strikes with biso.
    microstrain: StephensStrain | None = None
    # Physical particle radius in micrometres, used only by the Brindley
    # microabsorption correction of QPA weight fractions (Brindley 1945).
    # There is no way to obtain it from the pattern: profile broadening
    # measures the *coherent domain* size, which is smaller than (and
    # unrelated to) the particle Brindley's absorption path runs through —
    # conflating the two is a classic error.  Supply it from a micrograph or
    # a particle-size analysis; leave None (the default) for no correction.
    # Not a Parameter on purpose: it must never enter the least-squares fit.
    particle_radius_um: float | None = Field(default=None, gt=0.0)
    # Commensurate propagation vector k, in fractional coordinates of the
    # *conventional* reciprocal cell — the basis a CIF, a Bilbao page and
    # ``_parent_propagation_vector`` all speak.  Declaring one adds satellite
    # reflections at Q = H ± k to the phase's frozen reflection list
    # (``crystallography/satellites.py``): Le Bail and Pawley extract intensity
    # on them and a Rietveld stage contributes exactly zero there, so a user
    # with unindexed low-angle intensity in a neutron pattern can test the
    # magnetic hypothesis **without stating a single moment** (WP-1326).
    #
    # Stored as three rational *strings* (``"0"``, ``"1/2"``, ``"1/3"``), not
    # floats, and that is the point: k is exact, the ± k equivalence test and
    # the satellite enumeration are integer arithmetic, and a float would put a
    # tolerance where none belongs.  Any spelling a caller finds natural — an
    # int, a ``Fraction``, ``"1/2"``, or a float that *is* a small rational —
    # arrives through the validator below and is stored canonically, so a JSON
    # round-trip is bit-identical.  ``None`` (the default) is exactly off: a
    # phase declaring none compiles to the reflection list it always did.
    propagation_vector: tuple[str, str, str] | None = None
    # The phase's magnetic space group, as the magCIF operator and centring
    # loops (WP-1327).  ``None`` — the default — is exactly off, and it is the
    # only state in which an atom of this phase may carry no ``moment``:
    # declaring one is what gives a moment an allowed subspace to refine in
    # and an orbit to be propagated over.  Refused beside
    # ``propagation_vector`` (:data:`MOMENT_MODEL_FIELDS`): a commensurate
    # magnetic structure is described *either* by k on the nuclear cell with
    # no moments, *or* by a magnetic space group with moments in the magnetic
    # supercell (``crystallography.magnetic.supercell.magnetic_supercell``),
    # and both at once is the same physics stated twice.
    #
    # A UNI/BNS/OG number is accepted here in place of the block and resolved
    # through spglib (issue #257 A4); what is stored is always the operator
    # list, because that is the object the refinement uses and the symbol is
    # metadata.
    magnetic_symmetry: MagneticSymmetry | None = None
    # Soft observational restraints (bond lengths, bond angles, value targets).
    # Empty default ⇒ exactly off: a phase declaring none is bit-identical to
    # one without the field.  Each contributes a √weight·(computed − target)/σ
    # residual row (model/restraints.py) kept in the covariance but excluded
    # from Rwp/Durbin-Watson/Bérar-Lelann.  Rietveld-mode only (Le Bail/Pawley
    # do not compute structural coordinates for a bond/angle to differentiate).
    restraints: list[Restraint] = Field(default_factory=list)

    @field_validator("symmetry_operations", mode="before")
    @classmethod
    def _canonical_operations(cls, value):
        """Normalise the operation list to gemmi's own triplet spelling.

        ``"-X+1/2, Y, Z+1/4"`` and ``"-x+1/2,y,z+1/4"`` are the same operation
        and must store as the same string, or two callers who wrote the same
        group differently store different documents and a JSON round trip is
        not bit-identical.  Duplicates are dropped (a list built by composing
        generators repeats the identity) and the caller's order is kept, for
        the reason the field comment gives.  Whether the list is a *group* —
        and whether it agrees with the symbol — needs the symbol and is
        checked in :meth:`_operations_are_a_group` below.
        """
        if value is None:
            return None
        import gemmi

        if isinstance(value, str):
            raise ValueError(
                f"symmetry_operations must be a list of 'x,y,z' triplets, not "
                f"the single string {value!r}")
        out: list[str] = []
        for entry in value:
            try:
                op = gemmi.Op(str(entry).strip())
                # **The translation is wrapped into [0,1).**  ``x+3/2,y,z`` and
                # ``x+1/2,y,z`` are the same operation and must store as the
                # same string; gemmi's ``triplet()`` prints what it was given.
                # gemmi's own tabulated operations already lie in the window,
                # so this touches nothing when the list came from a symbol —
                # which is what keeps the bit-identity property.
                op.tran = [int(v) % op.DEN for v in op.tran]
                triplet = op.triplet()
            except (RuntimeError, ValueError) as exc:
                raise ValueError(
                    f"symmetry_operations: {entry!r} is not an 'x,y,z'-style "
                    f"symmetry operation ({exc}). One operation per entry, as "
                    f"in 'x,y,z' or '-x+1/2,y,z+1/4'") from exc
            if triplet not in out:
                out.append(triplet)
        if not out:
            raise ValueError(
                "symmetry_operations is an empty list. A group has at least "
                "the identity in it; leave the field None to resolve the "
                "operations from space_group instead")
        return out

    @model_validator(mode="after")
    def _operations_are_a_group(self) -> "Phase":
        """Refuse a list that is not a group, and one that fights its symbol.

        Three refusals, and each of them is a fit that would otherwise run and
        be wrong:

        1. **Not a group** — a list missing the identity, or not closed under
           composition, has no orbits worth the name: the structure-factor sum
           would run over a partial orbit and every |F|² would be wrong by a
           factor nobody could see. Checked by composing every pair and asking
           whether the product is in the list, modulo a lattice translation.
        2. **A plain symbol that does not generate the list.** The phase then
           states its symmetry twice and the two statements disagree; which of
           them the absences and the site multiplicities should come from is
           not this schema's call. Bracket the label to say the symbol is only
           the closest type (:func:`~rietx.crystallography.symmetry.unnamed_label`).
        3. **A bracketed label with no list.** The bracket *is* the claim that
           the symbol does not name the group, so without the list there is
           nothing left to be the group.
        """
        from ..crystallography.symmetry import split_group_label

        bracket = split_group_label(self.space_group)
        if self.symmetry_operations is None:
            if bracket is not None:
                raise ValueError(
                    f"phase {self.name!r} names space group "
                    f"{self.space_group!r}, whose bracketed form says no "
                    f"Hermann-Mauguin symbol generates this group in this "
                    f"cell — and declares no symmetry_operations, so nothing "
                    f"is left to be the group. State the operation list, or "
                    f"drop the bracket and name a symbol that does generate "
                    f"the symmetry")
            return self
        refusal = _operation_list_refusal(
            tuple(self.symmetry_operations),
            None if bracket is not None else self.space_group)
        if refusal is not None:
            raise ValueError(f"phase {self.name!r}{refusal}")
        return self

    @field_validator("propagation_vector", mode="before")
    @classmethod
    def _canonical_k(cls, value):
        """Normalise any accepted spelling of k to three rational strings.

        Validation of what the *vector* means — commensurate, and not a
        reciprocal-lattice vector of this phase's symmetry — needs the space
        group and therefore happens in :meth:`_k_is_usable` below.  This step
        only fixes the storage: ``Fraction``s, ints, ``"1/2"`` strings and
        floats that are exactly a small rational all become the same three
        strings, so two callers who spelled the same vector differently store
        the same document.
        """
        if value is None:
            return None
        from ..crystallography.satellites import as_propagation_vector

        return tuple(str(c) for c in as_propagation_vector(value))

    @model_validator(mode="after")
    def _k_is_usable(self) -> "Phase":
        """Refuse a k this phase's symmetry cannot carry, and a moment model.

        Two refusals, and neither can be made by the field validator above.
        **k = 0** — a k that is a reciprocal-lattice vector of *this* group,
        which is a centring-aware test — would put every satellite on a
        nuclear line and duplicate the reflection list exactly; the message
        (``crystallography.satellites.check_propagation_vector``) says what to
        do instead.  And a **moment model declared beside k**: the two
        descriptions of a commensurate magnetic structure — a propagation
        vector on the nuclear cell, and a magnetic space group with moments —
        must not both be declared on one phase, because they say the same
        thing twice and nothing reconciles them
        (:func:`refuse_moment_model_with_k`).
        """
        if self.propagation_vector is None:
            return self
        from ..crystallography.satellites import check_propagation_vector

        try:
            check_propagation_vector(self.space_group, self.propagation_vector)
        except ValueError as exc:
            raise ValueError(f"phase {self.name!r}: {exc}") from exc
        refuse_moment_model_with_k(
            self.name, [f for f in MOMENT_MODEL_FIELDS
                        if getattr(self, f, None) is not None])
        return self

    @model_validator(mode="after")
    def _moments_are_stateable(self) -> "Phase":
        """Refuse a moment the stated magnetic symmetry cannot carry.

        Five refusals, all of them arithmetic on what this object already
        holds — no cell, no wavelength, no data — which is why they are here
        and not at compile (the opposite of ``Atom.species``, whose answer
        needs a scattering table).

        1. A moment with no ``magnetic_symmetry``: there is no allowed
           subspace to refine in and no orbit to propagate over.
        2. A moment **outside** the site's allowed subspace.  The subspace is
           ∩ ker(ε·det(R)·R − I) over the site's magnetic stabiliser
           (``crystallography.magnetic.operators.allowed_moment_basis``), and
           the test is :func:`~rietx.crystallography.magnetic.operators.in_span`
           — a *span* test, never a dimension count, because the transposed
           action is a group too and gives the same dimension in every crystal
           system (measured: R and Rᵀ differ only inside space groups
           149-194).
        3. A moment on an **anisotropic** site.  The magnetic orbit sum needs
           the per-image Debye-Waller factor at each Laue-orbit member, which
           is a shape this rung does not build; refused by name rather than
           quietly evaluated with the isotropic factor.
        4. A moment **free at exactly zero**.  |F_m|² ∝ m², so the Jacobian
           column vanishes there and the parameter is dead — the same trap
           :meth:`StephensStrain` refuses for the all-zero S block, and the
           same fix: start from a physical estimate.
        5. An ``ion`` the form-factor table does not carry, or a 4f/5f ion
           with no ``g``.
        """
        moments = [(j, a) for j, a in enumerate(self.atoms) if a.moment is not None]
        if not moments:
            return self
        if self.magnetic_symmetry is None:
            labels = ", ".join(repr(a.label) for _, a in moments)
            raise ValueError(
                f"phase {self.name!r}: {labels} carr{'ies' if len(moments) == 1 else 'y'} "
                f"a moment but the phase declares no magnetic_symmetry. A "
                f"moment is only meaningful under a magnetic space group: it "
                f"is the operator list that says which directions the site "
                f"allows and how the moment propagates over the orbit. State "
                f"it as the magCIF operator loop, or as a UNI/BNS/OG number")
        from ..crystallography.magnetic.form_factor import coefficients, resolve_g
        from ..crystallography.magnetic.operators import in_span

        group = self.magnetic_symmetry.group()
        for j, atom in moments:
            where = f"phase {self.name!r} atom {j} ({atom.label!r})"
            if atom.aniso is not None:
                raise ValueError(
                    f"{where} carries both an anisotropic displacement block "
                    f"and a moment. The magnetic orbit sum would need the "
                    f"per-image U^ij at every Laue-orbit member, which this "
                    f"version does not build; refine the site with biso while "
                    f"a moment is on it")
            m = atom.moment.values()
            xyz = (atom.x.value, atom.y.value, atom.z.value)
            basis = group.allowed_moment_basis(xyz)
            if not in_span(basis, m):
                allowed = ("no moment at all — the site symmetry forbids one"
                           if len(basis) == 0 else
                           f"only {[list(map(int, r)) for r in basis]} "
                           f"(crystal-axis directions)")
                raise ValueError(
                    f"{where}: the moment {list(m)} μ_B is not compatible with "
                    f"the magnetic symmetry, which allows {allowed} on this "
                    f"site. A moment outside the allowed subspace is not a "
                    f"starting guess to be symmetrised: it says the structure "
                    f"and the group disagree")
            if atom.moment.vary and not any(m):
                raise ValueError(
                    f"{where}: the moment is free and exactly zero. |F_m|² is "
                    f"proportional to m², so its Jacobian column vanishes at "
                    f"the origin and the parameter cannot move — seed a "
                    f"physical estimate (1-5 μ_B for a 3d ion) instead")
            try:
                coefficients(atom.moment.ion)
            except KeyError as exc:
                # pydantic wraps a ValueError into its own report and lets a
                # KeyError through raw, which would reach a caller as an
                # unhandled exception with no path in it
                raise ValueError(f"{where}: {exc.args[0]}") from exc
            try:
                resolve_g(atom.moment.ion, atom.moment.g)
            except ValueError as exc:
                raise ValueError(f"{where}: {exc}") from exc
        return self

    @model_validator(mode="after")
    def _nonempty(self) -> "Phase":
        if not self.atoms:
            raise ValueError(f"phase {self.name!r} has no atoms")
        return self

    @model_validator(mode="after")
    def _one_strain_model(self) -> "Phase":
        if self.microstrain is not None and self.lor_strain.vary:
            raise ValueError(
                f"phase {self.name!r} has a Stephens microstrain block, whose "
                "isotropic direction is the same residual column as "
                "lor_strain; refining both is exactly degenerate.  Set "
                "lor_strain.vary=False and refine the S_HKL patterns instead")
        return self

    @model_validator(mode="after")
    def _valid_restraints(self) -> "Phase":
        n = len(self.atoms)

        def check(idx: int, label: str) -> None:
            if not 0 <= idx < n:
                raise ValueError(
                    f"phase {self.name!r} restraint references {label}={idx}, "
                    f"but the phase has {n} atom(s) (indices 0..{n - 1})")

        for r in self.restraints:
            if isinstance(r, BondRestraint):
                check(r.atom_i, "atom_i")
                check(r.atom_j, "atom_j")
            elif isinstance(r, AngleRestraint):
                check(r.atom_i, "atom_i")
                check(r.atom_j, "atom_j")
                check(r.atom_k, "atom_k")
        return self


class Structure(Base):
    """The phases refined against the same pattern(s) — possibly none.

    A declared cell (``structure.phases[i].cell.a.value``, in Å) rather than
    a fitted one — read a phase's refined cell off the *result*'s
    ``parameters`` rows or ``Refinement.parameters()``, never here.

    **Zero phases is legal, and it is a state rather than an oversight**
    (WP-1207): a pattern whose phase is not yet known.  Peak picking, indexing
    and the instrument and background parameters all work over one, which is
    what makes it worth holding — the audience least served by this package was
    the person with a pattern and no CIF, and every route out of that state
    (Adopt a candidate, type a cell) needs a project to arrive *in*.

    What it is not is refinable.  A phase reaches the pattern only through
    ``scale × |F|² × profile``, so with no phase there is nothing but the
    background to fit, and a plan run over one converges on it and reports
    ``converged`` — measured at Rwp 0.9637 on a pattern with 36 clear peaks.
    So the refusal lives on the verb, in :class:`~rietx.refine.NoPhasesError`,
    and never here: a validator would refuse the *state* along with the fit and
    take peak picking and indexing with it.

    ``Phase._nonempty`` is untouched and unrelated — a phase that exists still
    needs an atom, which is what makes a Le Bail scaffold's dummy atom
    mandatory rather than a convenience.
    """

    phases: list[Phase]

    @classmethod
    def from_cif(cls, path: str, *, phase_name: str | None = None,
                 aniso: bool = False, diagnostics: list | None = None,
                 ) -> "Structure":
        from ..crystallography.cif import structure_from_cif

        return structure_from_cif(path, phase_name=phase_name, aniso=aniso,
                                  diagnostics=diagnostics)

    def to_cif(self, path: str) -> None:
        from ..crystallography.cif import structure_to_cif

        structure_to_cif(self, path)


def lebail_scaffold(space_group: str, cell: Sequence[float], *,
                    name: str = "phase") -> Structure:
    """A single-phase :class:`Structure` carrying a cell and no structure.

    ``cell`` is the six numbers in ``a, b, c, alpha, beta, gamma`` order.  The
    result is what a Le Bail (or Pawley) fit needs and nothing more: the lattice
    decides where the peaks are, and the intensities are extracted rather than
    computed.

    **The dummy atom is mandatory, not a convenience.**  ``Phase._nonempty``
    raises on an empty atom list, and there is no structure here to list — that
    is the whole point.  So the phase carries one atom that contributes nothing:
    ``_run_stage`` force-fixes every ``.atoms.`` path, ``.scale`` and
    ``.source.lines.`` in lebail/pawley mode, which is also what keeps the
    parameter surface (WP-1004) from offering it for editing — it is reported
    ``mode_fixed``, not ``locked``.

    Two callers, one shape (WP-1206): the indexing panel's Adopt button, through
    :func:`rietx.indexing.workflow.structure_from_candidate`, which resolves the
    symbol from the candidate first; and a project typed from a cell, where the
    symbol and the free cell parameters are the whole of what a person supplies.
    Neither validates the symbol here — a ``Phase`` never has — so a caller that
    wants a refusal against a *field* resolves it itself
    (``crystallography.symmetry.get_spacegroup``).
    """
    a, b, c, alpha, beta, gamma = (float(v) for v in cell)
    return Structure(phases=[Phase(
        name=name, space_group=space_group,
        cell=Cell(a=Parameter(value=a), b=Parameter(value=b),
                  c=Parameter(value=c),
                  alpha=Parameter(value=alpha), beta=Parameter(value=beta),
                  gamma=Parameter(value=gamma)),
        atoms=[Atom(label="X", species=DUMMY_SPECIES,
                    x=Parameter(value=0.0), y=Parameter(value=0.0),
                    z=Parameter(value=0.0))])])
