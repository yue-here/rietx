"""Common schema primitives: the refinable :class:`Parameter` and provenance.

The ``Parameter`` model (``value``/``vary``/``min``/``max``/``expr``) follows the
design popularised by *lmfit* (BSD-3-Clause); no lmfit code is used, only the
interface convention.  See ``ATTRIBUTION.md``.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Data-contract version of the pydantic schemas (``Capabilities.schema_version``).
#: Any change a consumer could observe bumps the last component by one, and
#: the comment says what changed — no classification, no digest (WP-1117).
#: 0.1 → 0.2 (WP-1076): ``RefinedParameter.initial`` and
#: ``RefinementResult.correlation_warnings`` removed, both fields nothing wrote.
#: 0.2 → 0.3 (WP-1112): ``StageSpec.window_slack_deg`` added — a stage's
#: declared window capture slack in °2θ (``None`` → the compiled default).
#: 0.3 → 0.4 (WP-1113): ``StageSpec.ftol`` added — a stage's own termination
#: tolerance (``None`` → the solver default 1e-9).
#: 0.4 → 0.5 (WP-1123): ``PlanSpec.intermediate_ftol`` added and **defaulting
#: to 1e-6**, so a plan validated from a document that does not mention it now
#: stops its intermediate stages earlier than the same document did before;
#: ``StageResult.ftol`` and ``NodeAction.ftol``/``window_slack_deg`` added,
#: recording what a stage ran at.  The one entry so far whose default changes
#: an answer rather than only the field list — bounded at 0.03 esd on a single
#: fit — and ``intermediate_ftol=None`` restores the old schedule bit for bit.
#: 0.5 → 0.6 (PR #99): ``SeriesEntry.phase_agreement`` added — the per-phase
#: Bragg agreement each pattern's own result already carried, now surviving the
#: series boundary.  Additive and defaulted, and it bumps anyway: WP-1117 made
#: the only question whether a consumer could notice, and a new field on a
#: response arm is noticeable.
#: 0.6 → 0.7 (PR #108): ``NeutronSource`` added as a second arm of the
#: ``Instrument.source`` discriminated union (``kind="neutron_cw"``), so a
#: consumer that switched exhaustively on ``kind`` now has a case it has never
#: seen; ``Capabilities.radiations`` and the ``RadiationCapability`` it holds
#: added, which is a new field on a response arm.  Nothing existing changes
#: shape and every pre-0.7 document validates unchanged — the bump is for the
#: union arm, not for a migration.
#: 0.7 → 0.8 (PR #114): ``EmissionLine.wavelength`` and
#: ``NeutronSource.wavelength`` are a :class:`Parameter` rather than a
#: ``float``, so a serialized source carries a nested object where it carried a
#: number and the parameter table gains an
#: ``instrument.source.lines.N.wavelength`` row.  Both fields still *accept* a
#: bare number and default to ``vary=False``, so every pre-0.8 document
#: validates unchanged and every fit that frees no wavelength is bit-identical;
#: what a consumer can observe is the serialized shape and the new dot-path.
#: PR #112 is this entry's sibling on PR #108 and also claims 0.8 — deliberately,
#: so that whichever lands second conflicts here and is forced to renumber to 0.9
#: rather than merging cleanly into a ladder with a hole in it.
SCHEMA_VERSION = "0.8"

TransformKind = Literal["identity", "softplus", "exp", "logit"]

#: Intensity model.  ``rietveld`` computes |F|² from the structure; ``lebail``
#: partitions the observed intensity among reflections by an iterated
#: fixed-point (the intensities are *not* free parameters); ``pawley`` puts the
#: same per-hkl intensities *into* the least-squares parameter vector (Pawley,
#: 1981), so they carry esds and overlapped groups need explicit conditioning.
#: Defined here rather than in ``model.forward`` so the schemas can name it
#: without importing the forward model (which imports the schemas).
Mode = Literal["rietveld", "lebail", "pawley"]


class Base(BaseModel):
    """Base for every rietx schema.

    ``extra="forbid"`` makes unknown fields a loud error, which gives agents an
    actionable message instead of a silently dropped key.
    """

    # ser_json_inf_nan="strings": ±inf bounds serialize as "Infinity" (valid
    # strict JSON, unlike the default null) and coerce back to float on load.
    model_config = ConfigDict(extra="forbid", validate_assignment=True,
                              ser_json_inf_nan="strings")


class Parameter(Base):
    """A single refinable scalar.

    Attributes
    ----------
    value:
        Current value in the unit given by ``unit``.
    vary:
        Whether the parameter is free in the least-squares problem.
    min, max:
        Inclusive bounds passed to the bounded minimiser.
    expr:
        Reserved for nonlinear constraint expressions; **not implemented** —
        must be ``None``. The design (a tiny AST-whitelisted DSL emitted as
        backend ops, because asteval cannot run on autodiff tracers) is in
        DESIGN.md's "Parameter system"; linear/symmetry ties do not need it and
        go through the affine constraint block instead.

        **Kept deliberately** (WP-1110 item 5, decided 2026-08-21).  A declared
        field that can only ever raise is the shape WP-1076 removes, and this
        one was costed for removal: ``model_dump`` writes ``"expr": null`` into
        every persisted parameter, so under ``extra="forbid"`` it needs a
        ``mode="before"`` migration and ``SCHEMA_VERSION`` 0.2 → 0.3.  It stays
        because it is the carrier for the nonlinear half of WP-1119's named
        variables, whose linear half the affine block above already computes —
        removing it now would buy one bump and cost another to undo.
    transform:
        Reparameterisation used internally.  ``softplus`` maps an unbounded
        internal variable to a strictly positive physical value, which keeps
        the optimiser away from the hard lower bound of quantities such as peak
        widths and scale factors.
    stderr:
        Estimated standard deviation, filled in by the refinement.
    """

    value: float
    vary: bool = False
    min: float = -math.inf
    max: float = math.inf
    expr: str | None = None
    transform: TransformKind = "identity"
    unit: str | None = None
    stderr: float | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> "Parameter":
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must not exceed max ({self.max})")
        if not (self.min <= self.value <= self.max):
            raise ValueError(
                f"value {self.value} lies outside bounds [{self.min}, {self.max}]"
            )
        if self.expr is not None:
            raise ValueError(
                "Parameter.expr (nonlinear constraint expressions) is not "
                "implemented; set expr=None.  Symmetry and linear ties do not "
                "need it — they are applied as the affine constraint block in "
                "params/vector.py (crystal-system cell ties, Wyckoff coordinate "
                "DOFs, site-symmetry ADP patterns)."
            )
        return self

    @classmethod
    def positive(cls, value: float, *, vary: bool = False, unit: str | None = None,
                 max: float = math.inf) -> "Parameter":
        """A strictly positive parameter using the softplus reparameterisation."""
        return cls(value=value, vary=vary, min=0.0, max=max, transform="softplus",
                   unit=unit)


def P(value: float, **kw) -> Parameter:  # noqa: N802 - deliberate short helper
    """Shorthand constructor used throughout the default instrument presets."""
    return Parameter(value=value, **kw)


Fraction = Annotated[float, Field(ge=0.0, le=1.0)]


class Provenance(Base):
    """Everything needed to reproduce a result."""

    package_version: str
    schema_version: str = SCHEMA_VERSION
    backend: str = "numpy"
    dtype: str = "float64"
    #: which least-squares driver produced the values — "trf" (scipy, the
    #: reference) or "lm" (the bounded LM with constraint vocabulary, WP-0601).
    #: Provenance because the drivers differ in what they can enforce (the
    #: Stephens cone), not merely in how fast they converge.
    solver: str = "trf"
    #: version of the FitReport gates/vocabulary contract; the engines stamp
    #: the live ``report.schemas.THRESHOLDS_VERSION`` here (the default exists
    #: only for hand-built records and cannot be the constant itself — that
    #: would import the report package into the base schemas)
    report_thresholds_version: str = "0.1"
    created_utc: str | None = None
    notes: dict[str, str] = Field(default_factory=dict)


class Diagnostic(Base):
    """A structured, actionable message produced by the engine."""

    level: Literal["info", "warning", "error"]
    code: str
    message: str
    where: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    #: the headline number, where the diagnostic has one — ρ for a
    #: correlation, block R² for an absorption, the worst σ²(M) — so a client
    #: ranking or thresholding hits never parses ``message``.  ``None`` where
    #: there is no single number, which is not zero (WP-1003; the same
    #: absent-for-cause rule as ``GuardFinding.value``, its usual source).
    value: float | None = None
