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

from pydantic import Field, model_validator

from .common import Base, Parameter


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
            a=Parameter(value=a, vary=vary, min=0.1),
            b=Parameter(value=a, min=0.1),
            c=Parameter(value=a, min=0.1),
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
    one: :class:`~pxrdref.params.vector.ParameterTable` ties each component to
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
    transmission geometry) live in :mod:`pxrdref.model.preferred_orientation`.

    ``r`` is softplus-bounded strictly positive (a hard zero bound stalls TRF)
    and **defaults to 1.0, vary=False** — r ≡ 1 is exactly the no-correction
    case, so a phase carrying this block but not refining it is bit-identical
    to one without it.
    """

    axis: tuple[int, int, int]
    r: Parameter = Field(
        default_factory=lambda: Parameter(value=1.0, vary=False, min=0.0, transform="softplus")
    )

    @model_validator(mode="after")
    def _axis_nonzero(self) -> "PreferredOrientation":
        if all(h == 0 for h in self.axis):
            raise ValueError("preferred-orientation axis (0,0,0) has no direction")
        return self


class Atom(Base):
    """One site in the asymmetric unit.

    Displacement is isotropic (``biso``) unless ``aniso`` is set, which is an
    opt-in *per atom*: a structure may mix isotropic and anisotropic sites.
    When ``aniso`` is present it alone drives the Debye-Waller factor and
    ``biso`` becomes an inert record of the starting estimate — refining it
    would be a silently dead parameter, so that is rejected.
    """

    label: str
    species: str  # scattering species, e.g. "La", "B", "Fe3+"
    x: Parameter
    y: Parameter
    z: Parameter
    occ: Parameter = Field(default_factory=lambda: Parameter(value=1.0, min=0.0, max=1.5))
    biso: Parameter = Field(default_factory=lambda: Parameter(value=0.5, min=0.0, max=25.0, unit="A^2"))
    aniso: AnisoU | None = None

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
    """One or more phases refined against the same pattern(s)."""

    phases: list[Phase]

    @model_validator(mode="after")
    def _nonempty(self) -> "Structure":
        if not self.phases:
            raise ValueError("structure has no phases")
        return self

    @classmethod
    def from_cif(cls, path: str, *, phase_name: str | None = None,
                 aniso: bool = False) -> "Structure":
        from ..crystallography.cif import structure_from_cif

        return structure_from_cif(path, phase_name=phase_name, aniso=aniso)

    def to_cif(self, path: str) -> None:
        from ..crystallography.cif import structure_to_cif

        structure_to_cif(self, path)
