"""Common schema primitives: the refinable :class:`Parameter` and provenance.

The ``Parameter`` model (``value``/``vary``/``min``/``max``) follows the
design popularised by *lmfit* (BSD-3-Clause); no lmfit code is used, only the
interface convention.  See ``ATTRIBUTION.md``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType
from typing import Annotated, ClassVar, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, model_validator

from .._nearmiss import check_choice, did_you_mean

#: Data-contract version of the pydantic schemas (``Capabilities.schema_version``).
#: Any change a consumer could observe bumps the last component by one, and
#: its note in ``docs/contracts/schema.md`` says what changed — no
#: classification, no digest (WP-1117).
#: The number moves once per release cycle.  The first change after a release
#: bumps it, and each later change before the next release adds its own line
#: under that number, so a PR rebased onto a ``main`` already bumped keeps
#: ``main``'s number.  Decided 2026-10-15, after six concurrent PRs had
#: renumbered one another after every merge.
SCHEMA_VERSION = "0.62"

#: Intensity model.  ``rietveld`` computes |F|² from the structure; ``lebail``
#: partitions the observed intensity among reflections by an iterated
#: fixed-point (the intensities are *not* free parameters); ``pawley`` puts the
#: same per-hkl intensities *into* the least-squares parameter vector (Pawley,
#: 1981), so they carry esds and overlapped groups need explicit conditioning.
#: Defined here rather than in ``model.forward`` so the schemas can name it
#: without importing the forward model (which imports the schemas).
Mode = Literal["rietveld", "lebail", "pawley"]


def check_mode(mode: object) -> None:
    """Refuse a ``mode`` outside :data:`Mode`, before any work (WP-2302).

    ``Mode`` is a ``Literal``, which nothing checks at a call: a misspelt mode
    used to raise a pydantic error about an internal schema after most of a
    fit.  Every public call taking ``mode`` calls this on entry.
    """
    check_choice("mode", mode, get_args(Mode))


@lru_cache(maxsize=None)
def _nested_field_paths(cls: type, name: str) -> tuple[str, ...]:
    """``field.name`` for every *singular* nested schema of ``cls`` holding ``name``.

    Derived from the live annotations rather than listed, for the reason
    ``tests/api_surface.py`` gives one rank up: a hand-written map of "misses
    people have made" cannot notice a field added tomorrow, and this is a hint
    whose whole value is being right about where the number actually is.

    Optional blocks are searched too, and are the reason the answer is a tuple:
    ``n_points`` is on both ``Statistics`` and ``DataSupport`` (WP-1071's whole
    point — they count different things), so naming both is the honest reply.
    Cached per (class, name) because the miss happens on a hot-ish path:
    pydantic probes absent attributes during copy and serialization.
    """
    out: list[str] = []
    for field, info in cls.model_fields.items():
        for candidate in getattr(info.annotation, "__args__", (info.annotation,)):
            if (isinstance(candidate, type) and issubclass(candidate, Base)
                    and name in candidate.model_fields):
                out.append(f"{field}.{name}")
    return tuple(out)


class Base(BaseModel):
    """Base for every rietx schema.

    ``extra="forbid"`` makes unknown fields a loud error, which gives agents an
    actionable message instead of a silently dropped key.

    A wrong attribute name is answered with the right one wherever one can be
    found (WP-1302): a name that lives on a nested block gets that block's
    path (``result.rwp`` → "it is ``result.statistics.rwp``"), a typo of an
    own field gets the closest match, and a small schema with neither lists
    its fields outright. This complements, and does not replace, pydantic's
    own ``AttributeError`` for dunders, private attributes and ``model_extra``.
    """

    # ser_json_inf_nan="strings": ±inf bounds serialize as "Infinity" (valid
    # strict JSON, unlike the default null) and coerce back to float on load.
    model_config = ConfigDict(extra="forbid", validate_assignment=True,
                              ser_json_inf_nan="strings")

    #: Example variable name a subclass wants its nested-path hints prefixed
    #: with (``"result"`` → ``result.statistics.rwp``). ``None`` (the default)
    #: prints the bare field path — most schemas have no canonical call-site
    #: name, and inventing one would be a hint that lies half the time.
    _attr_hint_name: ClassVar[str | None] = None

    #: Above this many fields, an unresolved miss with no close match does not
    #: try to list them all — the list would be longer than the error.
    _ATTR_HINT_FIELD_CAP: ClassVar[int] = 12

    def __getattr__(self, name: str):
        """A pointer, not an alias — see :func:`_nested_field_paths`.

        Order: pydantic's own machinery first (dunders, private attributes,
        ``model_extra`` — none of these is ever a typo); then a *declared but
        unset* own field (only reachable through ``model_construct`` skipping
        a required field, most often a model validator probing a sibling
        mid-assignment — never a typo, so it gets its own message rather than
        the closest-match one, which would otherwise trivially "suggest"
        itself); then a nested block that carries this name; then the closest
        own-field match (:mod:`rietx._nearmiss`); then, for a small schema,
        every field name; otherwise the plain pydantic-shaped message
        untouched, so a caller matching on ``"no attribute 'x'"`` keeps
        working.
        """
        try:
            return super().__getattr__(name)
        except AttributeError:
            pass
        plain = f"{type(self).__name__!r} object has no attribute {name!r}"
        if name.startswith("_"):
            raise AttributeError(plain)
        if name in type(self).model_fields:
            raise AttributeError(
                f"{plain}; {name!r} is declared on {type(self).__name__} "
                "but was never given a value")
        where = _nested_field_paths(type(self), name)
        if where:
            prefix = type(self)._attr_hint_name
            paths = [f"{prefix}.{p}" if prefix else p for p in where]
            raise AttributeError(
                f"{type(self).__name__} has no {name!r} — it is "
                + " or ".join(paths)
                + ". The top level carries what this schema declares; a value "
                  "computed about it lives in the block that computed it.")
        hint = did_you_mean(name, type(self).model_fields)
        if hint:
            raise AttributeError(f"{plain}; {hint}")
        fields = list(type(self).model_fields)
        if len(fields) <= type(self)._ATTR_HINT_FIELD_CAP:
            raise AttributeError(f"{plain}; its fields are {fields}")
        raise AttributeError(plain)

    def __repr_args__(self):
        """Pydantic's fields, with every long sequence shown as a count and a
        range (WP-1544).

        This is the one place a long array is kept out of a repr, and so out of
        ``str``, ``print``, a traceback and a notebook cell's text, since
        pydantic's ``__str__`` is its repr. A pattern's repr was 1.4 MB.
        """
        from .._display import summarise
        for name, value in super().__repr_args__():
            yield name, summarise(value)

    def __str__(self) -> str:
        """An indented field tree, one line per parameter (WP-1544).

        ``repr`` stays pydantic's one line, for logs and debugging; ``str`` and
        ``print`` are for reading. A schema with a designed view (a result's
        termination view) overrides this.
        """
        from .._display import tree
        return tree(self)

    def _repr_pretty_(self, p, cycle) -> None:
        """IPython's text: the same as ``print``, so a notebook cell and a
        terminal agree."""
        p.text(f"{type(self).__name__}(...)" if cycle else str(self))


class Parameter(Base):
    """A single refinable scalar.

    Attributes
    ----------
    value:
        Current value in the unit given by ``unit``.
    vary:
        Whether the parameter is free in the least-squares problem.
    min, max:
        Inclusive bounds passed to the bounded minimiser, which refines the
        value in these units (WP-1938).  A ``transform`` written before
        schema 0.46 is folded into them on read
        (:func:`legacy_transform_bounds`).
    stderr:
        Estimated standard deviation, filled in by the refinement.
    """

    value: float
    vary: bool = False
    min: float = -math.inf
    max: float = math.inf
    unit: str | None = None
    stderr: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _drop_expr(cls, data: object) -> object:
        """Read a stored ``"expr": null`` as nothing (WP-1964).

        The field left the schema at 0.61.  It only ever held ``None``, any
        other value having raised, and every parameter written before carries
        that ``null``, so a file opens unchanged.  A formula is declared where
        it is evaluated: ``ParametricEquation(basis="expression")`` in a joint
        fit, never a field on the parameter it sets.
        """
        if not isinstance(data, dict) or "expr" not in data:
            return data
        if data["expr"] is not None:
            raise ValueError(
                "Parameter.expr was removed at schema 0.61 and only ever held None: "
                "a formula is declared as rx.ParametricEquation(basis='expression', "
                "expression=...) in a joint fit")
        data = dict(data)
        del data["expr"]
        return data

    @model_validator(mode="before")
    @classmethod
    def _fold_transform(cls, data: object) -> object:
        """Read a stored or passed ``transform`` as the bounds it enforced.

        The field left the schema at 0.46 (WP-1938), as
        ``Instrument._migrate_v1_2_background_peaks`` handles a vanished field.
        Every project, history line and ``.rxt`` written before carries it, and
        so does python written against it, so both open unchanged in meaning:
        the table had already built each declared transform as this box.  The
        bound it sets counts as stated, so a declared range does not replace
        it.  A field whose declared floor is above zero (a hump's width,
        March ``r``, Caglioti ``w``) raises a ``min`` of 0 to that floor at
        read, as it does for any caller's.
        """
        if not isinstance(data, dict) or "transform" not in data:
            return data
        data = dict(data)
        kind = data.pop("transform")
        if kind == "identity":
            return data
        try:
            lo = float(data.get("min", -math.inf))
            hi = float(data.get("max", math.inf))
        except (TypeError, ValueError):
            return data  # the field's own validation names the bad bound
        data["min"], new_hi = legacy_transform_bounds(kind, lo, hi)
        if new_hi != hi:
            data["max"] = new_hi
        return data

    @model_validator(mode="after")
    def _check_bounds(self) -> "Parameter":
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must not exceed max ({self.max})")
        if not (self.min <= self.value <= self.max):
            raise ValueError(
                f"value {self.value} lies outside bounds [{self.min}, {self.max}]"
            )
        return self

    @classmethod
    def positive(cls, value: float, *, vary: bool = False, unit: str | None = None,
                 max: float = math.inf) -> "Parameter":
        """A parameter bounded below at zero."""
        return cls(value=value, vary=vary, min=0.0, max=max, unit=unit)


def P(value: float, **kw) -> Parameter:  # noqa: N802 - deliberate short helper
    """Shorthand constructor used throughout the default instrument presets."""
    return Parameter(value=value, **kw)


def legacy_transform_bounds(kind: str, lo: float, hi: float) -> tuple[float, float]:
    """The box a ``transform`` written before schema 0.46 enforced (WP-1938).

    softplus and exp kept a value above zero and logit inside (0, 1), whatever
    ``lo`` and ``hi`` said.  Refined in physical units, each is that box.  The
    one map from the old word to bounds: ``Parameter``'s read validator and the
    ``.rxt`` parser's legacy flag words both call it.
    """
    if kind == "identity":
        return lo, hi
    if kind in ("softplus", "exp"):
        return max(lo, 0.0), hi
    if kind == "logit":
        return max(lo, 0.0), min(hi, 1.0)
    raise ValueError(
        f"unknown transform {kind!r}: a stored transform is one of identity, "
        "softplus, exp or logit, and since schema 0.46 it is read as bounds")


def refuse_retired_scope(paths, where: str, error: type[Exception] = ValueError) -> None:
    """Raise when a caller's path or glob uses the joint fit's ``hist.`` scope.

    WP-2305 renamed a joint fit's per-pattern scope ``hist.N.`` to
    ``pattern.N.``.  A stored value under the old name fails loudly anyway,
    but a glob does not: ``"hist.*.instrument.*"`` matches nothing and frees
    nothing, and the fit returns a plausible answer (DESIGN Rule 4).  No stored
    document holds a joint path, since a joint fit keeps no history or project,
    so this refuses at the call rather than migrating text at a read point.
    ``where`` names the call, and ``error`` lets a lookup raise ``KeyError``.
    """
    old = [p for p in paths if isinstance(p, str) and p.startswith("hist.")]
    if old:
        raise error(
            f"{where}: {old[0]!r} uses the joint fit's 'hist.' scope, renamed in "
            f"v1.13; write {'pattern.' + old[0][len('hist.'):]!r}")


#: What a bare ``Parameter`` holds for each attribute a field's declared
#: default can carry.  In a document written before a class inherited
#: (:class:`_InheritsDeclaredDefaults`), an attribute holding this value is the
#: only trace an omission left once it was serialized.
BARE_PARAMETER_ATTRS: dict[str, object] = {
    "min": -math.inf, "max": math.inf, "unit": None}


#: The pydantic validation context a reader of a **stored document** passes,
#: at each reader :data:`rietx.schemas.migrate.STORED_DOCUMENT_READ_POINTS`
#: names.  A field a release made required is filled there with the
#: placeholder its old default held, and raises everywhere else: old files
#: open, old code does not (``HumpComponent.position``, WP-2013).  Read only
#: through :func:`reading_stored_document`.
STORED_DOCUMENT = MappingProxyType({"stored_document": True})


def reading_stored_document(info) -> bool:
    """Whether this validation is a stored document's read (:data:`STORED_DOCUMENT`)."""
    context = info.context
    return isinstance(context, Mapping) and bool(context.get("stored_document"))


def declared_fills(declared: Parameter, present) -> dict[str, object]:
    """The attributes a ``Parameter`` inherits from its field's declared default.

    ``present`` names the attributes the caller stated.  ``min``, ``max`` and
    ``unit`` are inherited one by one wherever the caller left them out, the
    rule PR #206 set for ``Atom`` (issue #204): an explicit bound always wins,
    in either direction, and only a true omission inherits.  **One rule, two
    readers**: construction (a key absent from the caller's input) and the
    history reader's repair (an attribute holding the bare value in a document
    written before its class inherited) ask the same question with a different
    notion of absence, and neither restates it.
    """
    return {attr: getattr(declared, attr) for attr in ("min", "max", "unit")
            if attr not in present}


class _InheritsDeclaredDefaults(Base):
    """A schema whose ``Parameter`` fields declare a range: a caller's own
    ``Parameter`` inherits what it left out.

    A field declares its physical range and unit in its ``default_factory``
    (``Atom.occ``: min 0; ``Phase.lor_size``: min 0, degrees) rather
    than as a field constraint, so before this the range applied only when the
    field was omitted entirely.  A caller supplying
    ``Parameter(value=..., vary=...)`` — the natural way to set a start or hold
    one — silently got ``(-inf, inf)`` and no unit instead (issue #204: a refined Biso of −165 Å² and an 81-point QPA error
    at unchanged Rwp, invisible at the call site).  PR #206 closed it for
    ``Atom``; WP-1321 audited every other class carrying such a field and
    moved the validator here, so a class opts in by inheriting and a field
    added later is covered without naming it.  The sort, field by field, is in
    ``docs/wp/1321-persisted-bounds-repair.md``; every class
    ``tests/test_schemas.py`` finds with a declared attribute inherits this or
    is excluded there with a reason.

    ``_declared_since`` is the :data:`SCHEMA_VERSION` from which the class
    inherits.  Before it, an explicit bare attribute and an omission were the
    same thing, so a stored bare attribute in a document written earlier is
    read as an omission and repaired at read
    (:func:`rietx.history.tree.declared_range_repairs`); from it on, an
    explicit ``min=-inf`` is a choice and wins.

    **Filled before any ``Parameter`` exists for the field**, so nothing about
    the caller's own object is read *or written*.  PR #206 first tried a
    ``mode="after"`` validator: pydantic stores a passed-in ``Parameter`` by
    reference, and ``Base``'s ``validate_assignment=True`` meant the
    ``setattr`` that filled the gaps wrote to the caller's object and grew
    *its own* ``model_fields_set`` — so one ``Parameter`` reused for two fields
    leaked the first field's range into the second.  A dict is read and never
    written, for the same reason (``model_validate`` may be handed the
    caller's dict).

    **Construction and assignment each have a seam, and both call
    :meth:`_inherit_declared`** (WP-2088).  Construction's is the
    ``model_validator(mode="before")``.  Assignment's is ``__setattr__``,
    because a model validator's output for the assigned field never lands:
    pydantic validates that field from the value it was handed.  So until
    WP-2088, ``phase.lor_size = Parameter(value=0.01, vary=True)`` landed at
    ``(-inf, inf)`` with no unit, while the same ``Parameter`` handed to the
    constructor inherited the range.  Measured 2026-11-07, 70 of the 72
    declared fields lost their range on assignment.  A
    ``field_validator("*", mode="before")`` would be one seam for both, but
    pydantic refuses a before validator on a discriminator field, and
    ``Source.kind`` is one.

    **On assignment the model validator returns ``data`` untouched.**
    pydantic re-runs it with ``data`` built from the model's current field
    values, and it does not re-validate the fields the assignment never
    touched, so whatever the validator returns for them lands as it is.  A
    dict landed as a dict (measured on ``Atom`` after
    ``atom.aniso = AnisoU(...)``).  A fresh ``Parameter`` replaced every
    default whose declaration leaves ``max`` unset, so after
    ``phase.lor_size = ...`` the object a caller held as ``phase.gauss_size``
    was no longer the model's, and a change made to it reached nothing
    (WP-2088's code review).  ``info.field_name`` names the assigned field on
    that pass and is ``None`` on construction, which is how the validator
    tells the two apart.

    Detected with ``model_fields_set`` (for a raw dict, its keys) rather than
    by comparing with the bare defaults, since an explicit ``min=-inf`` is
    indistinguishable from an omission by value alone and must still win.
    Anything but a ``Parameter`` or a dict — ``None``, a bare number — is left
    to the field's own validation, so this only ever *adds* missing keys.  A
    value outside the inherited range raises here, naming the field and the
    two escapes, rather than as ``Parameter``'s anonymous bounds error.
    """

    _declared_since: ClassVar[str] = "0.35"
    #: A class-specific way out, appended to the out-of-range refusal.
    _declared_escape: ClassVar[str] = ""
    #: An opt-in ``Parameter | None`` field has no default to carry its range,
    #: so it names one here (``Phase.extinction``, WP-1944): field name → a
    #: factory for the ``Parameter`` whose range and unit a declaration inherits.
    _declared_optional: ClassVar[dict] = {}

    @classmethod
    def _declared_default(cls, name: str):
        """The factory whose ``Parameter`` carries field ``name``'s declared
        range, or ``None`` where the field declares none.  One answer for
        construction and for the history reader's repair."""
        info = cls.model_fields[name]
        if info.annotation is Parameter and info.default_factory is not None:
            return info.default_factory
        return cls._declared_optional.get(name)

    @model_validator(mode="before")
    @classmethod
    def _inherit_declared_bounds(cls, data: object, info: ValidationInfo) -> object:
        """Construction's half of the seam: each field handed in inherits."""
        if not isinstance(data, dict) or info.field_name is not None:
            return data  # an assignment's pass: ``__setattr__`` has filled it
        return {name: cls._inherit_declared(name, raw) if name in cls.model_fields
                else raw for name, raw in data.items()}

    def __setattr__(self, name: str, value: object) -> None:
        """Assignment's half of the seam (WP-2088): the value inherits first."""
        cls = type(self)
        if name in cls.model_fields:
            try:
                value = cls._inherit_declared(name, value)
            except ValidationError:
                pass  # broken without the fills too: validating the value raises it
            except ValueError as exc:
                raise ValidationError.from_exception_data(cls.__name__, [{
                    "type": "value_error", "loc": (name,), "input": value,
                    "ctx": {"error": exc}}]) from None
        super().__setattr__(name, value)

    @classmethod
    def _inherit_declared(cls, name: str, raw: object) -> object:
        """``raw``, handed to field ``name``, with what it left out of the
        field's declared range and unit filled in."""
        factory = cls._declared_default(name)
        if factory is None:
            return raw
        if isinstance(raw, Parameter):
            present, base = raw.model_fields_set, raw.model_dump()
        elif isinstance(raw, dict):
            present, base = raw.keys(), raw
        else:
            return raw  # not a shape that carries attribute presence
        if BARE_PARAMETER_ATTRS.keys() <= set(present):
            return raw  # every attribute stated (every reload): nothing to inherit
        # an attribute left unset replaces the caller's object even where
        # the declared value is the one it holds anyway: one Parameter passed
        # to every atom's ``occ`` must become one Parameter per atom, or the
        # write-back leaves the last site's value in all of them (PR #206's
        # behaviour, kept).  Sharing *on purpose* states every attribute —
        # ``Harmonic.weight``'s default does, being its line's by reference
        fills = declared_fills(factory(), set(present))
        # ``model_validate``, not ``Parameter(**...)``: a dict with a non-string
        # key raises pydantic's error rather than a bare TypeError
        try:
            return Parameter.model_validate({**base, **fills})
        except ValidationError as exc:
            try:
                Parameter.model_validate(base)
            except ValidationError as own:
                # broken without the fills too: not ours to name, and the
                # caller's own error quotes the input they wrote, not ours
                raise own from None
            value = base.get("value")
            # a JSON-mode dict spells an infinite bound "-Infinity"
            lo = float(fills.get("min", base.get("min", -math.inf)))
            hi = float(fills.get("max", base.get("max", math.inf)))
            what = (f"bounds [{lo}, {hi}] are empty: one is yours and the other "
                    f"is the one this field declares" if lo > hi else
                    f"value {value!r} lies outside bounds [{lo}, {hi}], the "
                    f"range this field declares")
            raise ValueError(
                f"{cls.__name__}.{name}: {what}, which a "
                f"Parameter leaving min or max unset inherits (issue #204). "
                f"State the range you mean on the Parameter itself, e.g. "
                f"Parameter(value={value!r}, min=..., max=...)"
                + (f", or {cls._declared_escape}" if cls._declared_escape else "")
            ) from exc


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
    """A structured, actionable message produced by the engine.

    Three texts, each written once (WP-1985).  ``message`` is the observation:
    one sentence on what this case found, carrying its numbers.  ``suggestion``
    is the action: one sentence on what to do next.  :attr:`explanation` is
    what the code means and why it fires.  It is the same for every finding,
    so it is looked up by ``code`` in :data:`rietx.help.DIAGNOSTIC_HELP` and
    never stored.
    """

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

    def __str__(self) -> str:
        """The one text form every printed view uses, after rustc's.

        ``warning[CODE]: message`` heads it, then ``at:`` with the paths and
        ``help:`` with the suggestion, each indented on its own line.  The
        explanation is left out because it is the same for every finding
        (WP-1985).  A notebook form prints it as ``means:`` under ``help:``
        (:func:`rietx._display.diagnostic_lines`).
        """
        lines = [f"{self.level}[{self.code}]: {self.message}"]
        if self.where:
            lines.append(f"  at: {', '.join(self.where)}")
        if self.suggestion:
            lines.append(f"  help: {self.suggestion}")
        return "\n".join(lines)

    @property
    def explanation(self) -> str | None:
        """What ``code`` means, from :func:`rietx.help.explain`.

        ``None`` for a code this build does not describe, such as one read
        from a file a different version wrote.
        """
        from ..help import explain

        entry = explain(self.code)
        return None if entry is None else entry.description

    @property
    def view(self) -> str | None:
        """The rendered view that shows this finding, from
        :data:`rietx.help.DIAGNOSTIC_VIEW_OF` (WP-1133).

        A name in :data:`rietx.help.DIAGNOSTIC_VIEWS`, such as
        ``"plot_for_vlm.residual"``.  ``None`` where no view has been checked
        for the code, which is most codes.  The pointer is a name and never an image, so the caller
        decides whether to draw it.
        """
        from ..help import DIAGNOSTIC_VIEW_OF

        return DIAGNOSTIC_VIEW_OF.get(self.code)
