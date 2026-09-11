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

import math
from collections.abc import Sequence

from pydantic import Field, model_validator

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


class Phase(Base):
    """A crystalline phase: symmetry, cell, atoms, scale, sample broadening."""

    name: str
    space_group: str  # Hermann-Mauguin symbol or number-as-string, resolved via gemmi
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
    # Soft observational restraints (bond lengths, bond angles, value targets).
    # Empty default ⇒ exactly off: a phase declaring none is bit-identical to
    # one without the field.  Each contributes a √weight·(computed − target)/σ
    # residual row (model/restraints.py) kept in the covariance but excluded
    # from Rwp/Durbin-Watson/Bérar-Lelann.  Rietveld-mode only (Le Bail/Pawley
    # do not compute structural coordinates for a bond/angle to differentiate).
    restraints: list[Restraint] = Field(default_factory=list)

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
