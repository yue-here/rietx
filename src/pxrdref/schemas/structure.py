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

    @model_validator(mode="after")
    def _nonempty(self) -> "Phase":
        if not self.atoms:
            raise ValueError(f"phase {self.name!r} has no atoms")
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
