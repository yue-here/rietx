"""Common schema primitives: the refinable :class:`Parameter` and provenance.

The ``Parameter`` model (``value``/``vary``/``min``/``max``/``expr``) follows the
design popularised by *lmfit* (BSD-3-Clause); no lmfit code is used, only the
interface convention.  See ``ATTRIBUTION.md``.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .._nearmiss import did_you_mean

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
#: 0.6 → 0.7 (PR #108): constant-wavelength neutron support, three observable
#: changes landing together because they are one feature and one PR.
#: (a) ``NeutronSource`` added as a second arm of the ``Instrument.source``
#: discriminated union (``kind="neutron_cw"``), so a consumer that switched
#: exhaustively on ``kind`` now has a case it has never seen, and
#: ``Capabilities.radiations`` / ``RadiationCapability`` are a new field on a
#: response arm.
#: (b) ``Source.harmonics`` / ``NeutronSource.harmonics`` — a list of
#: ``Harmonic`` blocks declaring the λ/n components a monochromator does not
#: filter out.  A consumer notices the new key in every serialized source, and
#: that a **neutron** source carrying a harmonic reports more than one entry in
#: ``source.lines``, since the λ/n lines are *derived* there rather than stored.
#: Empty is the default; a non-empty list is refused outright on an X-ray source
#: (``Source.harmonics_supported``).
#: (c) ``EmissionLine.wavelength`` and ``NeutronSource.wavelength`` are a
#: :class:`Parameter` rather than a ``float``, so a serialized source carries a
#: nested object where it carried a number and the parameter table gains an
#: ``instrument.source.lines.N.wavelength`` row.  Both still *accept* a bare
#: number and default to ``vary=False``.
#: Nothing existing changes meaning, every pre-0.7 document validates unchanged,
#: and a fit that declares no harmonic and frees no wavelength is bit-identical.
#: One bump rather than three: the ladder counts *observable releases*, and
#: these three reach a consumer in the same one.
#: 0.7 → 0.8 (WP-1202): ``ParameterRow.help_key`` added, naming the help-corpus
#: family that describes the path (``rietx.help``).  Additive and defaulted, and
#: it bumps for the reason 0.6 → 0.7 did: a new key on a response arm is
#: something a consumer notices.  ``None`` is a real answer here (no family
#: claims the path) rather than an unfilled default, because
#: ``Refinement.parameters`` fills it for every caller.
#: 0.8 → 0.9 (WP-1207): ``Structure.phases`` may be **empty**.  Nothing gains a
#: field and every document written before validates unchanged, but the set of
#: legal documents grew and that is what a consumer notices: code that read a
#: serialized structure and indexed ``phases[0]``, or counted phases to size an
#: answer, now has a case it has never seen.  The agent envelope's ``NO_PHASES``
#: rides with it as a fourth ``ERROR_CODES`` member.  One bump for the pair —
#: the ladder counts observable releases, and they reach a consumer in the same
#: one.
#: 0.9 → 0.10 (additive background peaks): ``Instrument.extra_components`` (a new
#: declared block) and ``RefinementResult.n_extra_components`` (a new field on a
#: result).  Additive and defaulted — the empty list and ``None`` reproduce a
#: pre-feature document byte for byte — but both are noticeable to a consumer,
#: which since WP-1117 is the whole test (the ``Identifiability`` docstring is
#: the sentence that first talked a reader out of this bump).
#: 0.10 → 0.11 (WP-1301): ``StageResult.held`` and ``StageResult.released`` —
#: the structural parameters of a phase the data could not see, held for the
#: stage rather than refined down a flat direction, and the subset the same
#: stage let go again.  Additive and defaulted, and the empty lists are the
#: honest answer for every fit with no unsupported phase (they are written on
#: every stage, so an empty one means "nothing was held", not "nobody looked").
#: A consumer notices, which is the whole test: a parameter the plan freed can
#: now come back unrefined, and these two fields are where it says so.
#: 0.11 → 0.12 (WP-1303): the **agent envelope is gone** — ``rietx.agent``, its
#: request union (``RefineRequest`` and the four peers), its response arms
#: (``AgentSuccess``/``AgentFailure``), the ``ERROR_CODES`` grammar and the
#: exported JSON Schemas.  Every other bump on this ladder was additive; this
#: one removes models a consumer could have been parsing, which is why it moves
#: the string rather than riding along with a release note.  Nothing that
#: *computes* moved: the answer types the envelope wrapped
#: (``RefinementResult``, ``FitReport``, ``SeriesResult``, ``IndexingResult``,
#: ``SuggestionResult``) are untouched and still serialize byte for byte, so a
#: caller that dumps ``Refinement.fit``'s result gets what the ``result`` arm
#: carried.  ``Capabilities.features`` loses ``agent_json`` with it.
#: 0.12 → 0.13 (WP-1304): ``Capabilities`` gains ``skill_path``, the directory
#: of the agent skill this build carries (``None`` where it carries none).
#: Additive, and a client that ignores the field is unaffected — but the field
#: list of that model *is* the contract a client reads to decide what it may
#: ask for, which is the argument for moving the string rather than letting a
#: new arm ride along silently.
#: 0.13 → 0.14 (WP-1305): ``CandidateGroup.delta_bic`` — what ``suggest``'s
#: ranking never said, whether the predicted gain pays for the parameter.
#: **Required, not defaulted**: 0.0 on a model-selection field reads as "no
#: preference", which is the defaulted-``False`` lie WP-1076 named, so a
#: document written before this field does not load rather than loading with an
#: answer nobody computed.
#: 0.14 → 0.15 (WP-1131): ``RefinementResult.microstructure`` — the four
#: profile coefficients read as a coherent domain size and a Δd/d, with esds.
#: Additive and defaulted to an empty list, which is the honest empty state
#: here (a result built without a compiled model measured no wavelength and can
#: read no size), but it is a new field a consumer enumerates, so it bumps.
#: ``PhaseMicrostructure.scherrer_k`` inside it is **required**: a size scales
#: linearly in K, so a defaulted 0.0 would be an answer about a constant nobody
#: chose (WP-1076; WP-1305's ``delta_bic`` took the same decision).
#: 0.15 → 0.16 (WP-1119): ``RefinementState.variables`` and
#: ``NodeAction.variables``/``removed_variables`` — named variables, a caller's
#: own ``Parameter`` outside the model tree that other parameters follow by
#: affine tie.  Additive and defaulted to empty, which is the honest empty state
#: (a refinement that declared none), but a variable is the one piece of
#: refinement state with **no** model field behind it: ``apply_to_models`` has
#: nothing to write it to, so the document is its only source of truth and a
#: node that dropped it would restore ties pointing at a parameter that is gone.
#: The field it reuses is ``Parameter`` itself rather than a new type, which is
#: what makes a variable and the model parameter it replaces produce the
#: identical table ``Entry``.
#: 0.16 → 0.17 (issue #204): ``Atom.occ``/``biso`` now inherit their field's
#: declared bounds and unit onto a caller-supplied ``Parameter`` that omitted
#: them, rather than silently falling back to ``Parameter``'s own bare
#: (-inf, inf, no unit). No field gained or changed shape — this is the
#: 0.4 → 0.5 shape, a behaviour change rather than a field-list one — but
#: **the set of legal ``Atom`` constructions shrank**, the opposite direction
#: from every earlier entry here: a bare ``Parameter(value=-165.0)`` for
#: ``biso``, storable before this change, now raises ``ValidationError``.
#: WP-1117 made the only question whether a consumer could notice, and a
#: construction that used to succeed and now doesn't is exactly that.
#: **Already-written documents are unaffected.** A persisted ``Atom`` always
#: serializes ``min``/``max``/``unit`` explicitly, so on load
#: ``model_fields_set`` (or, for the raw dict, its keys) is already complete,
#: nothing is inherited, and every stored value — including one this
#: validator would now refuse at construction, e.g. that same -165 A^2 Biso
#: — deserializes and validates exactly as before. The break is to
#: *construction*, not to *documents* (issue #209 is the read-time follow-up
#: that leaves open whether such an already-persisted value should also be
#: repaired).
#: 0.17 → 0.18 (WP-1102): ``Instrument.background_peaks`` became
#: ``extra_components``, a list of the discriminated union
#: :data:`~rietx.schemas.instrument.ExtraComponent` whose one member today is
#: ``HumpComponent`` (v1.2's ``BackgroundPeak``, plus a ``kind`` field);
#: ``RefinementResult.n_background_peaks`` became ``n_extra_components``.  A
#: **rename**, which every earlier entry here avoided, so it is stated in the
#: direction it breaks: **old documents open and old code does not.** A v1.2
#: project, history tree or ``.rxt`` is read by
#: :mod:`rietx.schemas.migrate` — the field *and* the dot-paths, because those
#: fail differently and only one of them fails loudly — while assigning
#: ``instrument.background_peaks`` in code raises under ``extra="forbid"``.
#: The path half is the reason the migration exists at all: a stored plan glob
#: under the old spelling loads clean and then matches nothing, which stops
#: refining a declared hump in silence.
#: 0.19 → 0.20 (issue #283): ``StageResult.n_degenerate_cell_probes`` — the
#: count of degenerate-cell trial points a stage's search reached (zero or
#: negative direct-metric-tensor determinant, refused by name from
#: ``crystallography.lattice.d_spacings`` as ``DegenerateCellError``) and the
#: solver-side guard (``optimize.least_squares._DegenerateCellGuard``) pushed
#: back out before the reported values were ever computed from one.
#: Additive and defaulted to 0, the honest empty state for a fit whose search
#: never left the physical cell, but it is a new field on every stage result
#: a consumer enumerates — bump per observable change (the precedent is
#: 0.8 → 0.9, where ``Structure.phases`` being allowed empty grew the set of
#: legal documents with no field added at all; a new field is squarely that,
#: and more so).  Surfaced beside it, not instead of it, as the ``info``-level
#: ``CELL_DEGENERATE_PROBE`` diagnostic: the guard already contained the
#: excursion before it reached the caller, so however often an underdetermined
#: cell stage reaches this, nothing about the reported values is in question.
#: 0.20 → 0.21 (WP-1309): ``BackgroundFixedPlusChebyshev`` grew ``scale`` (the
#: multiplier TOPAS's ``bkg_file("f.xy", @, s)`` has), ``fixed_sigma`` (the
#: curve's own counting statistics) and ``fixed_source`` (where the curve came
#: from).  Three new fields on a union member a consumer enumerates, so the same
#: rule as 0.19 → 0.20.  **No document changes meaning**: all three default to
#: the state the member was in — a scale of 1.0 held, no esds, no provenance —
#: so a stored instrument opens and refines exactly as it did.  What does change
#: without a stored field is that every plan preset frees
#: ``instrument.background.*``, which now reaches the scale; the v1.4 record's
#: break list has that half.
#: 0.21 → 0.22 (WP-1438): ``RefinementResult.tick_hkl`` and
#: ``HistogramResult.tick_hkl`` — which reflection each entry of ``ticks`` is,
#: as the orbit representative ``h k l``, paired with the positions by index.
#: Additive and defaulted to ``{}``, and the same rule as 0.19 → 0.20: a new
#: field on a result a consumer enumerates bumps the version whether or not any
#: stored document changes meaning.  **None does** — a result written before
#: this opens with the mapping empty, which is the honest empty state rather
#: than a claim, and the three pages that draw ticks fall back to hovering the
#: 2θ they always did.
#: The field is a *companion*, not a change of shape: ``ticks`` keeps its
#: ``dict[str, list[float]]``, because its four readers want positions and none
#: of them wants this.  A phase is **absent** from ``tick_hkl`` rather than
#: empty where there is nothing to say, which is the case for the reserved
#: declared-peaks key: a peak given by centre has no Miller index, and ``[]``
#: there would claim it had none of its own.
#: 0.22 → 0.23 (issue #375): ``SeriesResult.failures``
#: (``list[SeriesFailure]``) and ``.n_failed`` — a pattern
#: ``SequentialRefinement.fit``'s new ``on_error`` policy caught rather than
#: letting crash the whole chain.  Additive and defaulted to ``[]``/``0``, the
#: same rule as 0.19 → 0.20: a stored series from before this opens with no
#: failures recorded, which is the honest statement that this field did not
#: exist yet, never a claim that every pattern fit — the default policy is
#: still ``on_error="raise"``, unchanged behaviour, so no existing chain's
#: reported entries move.
#: 0.23 → 0.24 (issue #211): ``StageResult.blocked_by_hold`` — the paths a
#: stage's ``turn_on`` matched and a caller's ``Refinement.hold`` kept fixed,
#: and ``RefinementState.holds``/``NodeAction.held``/``.unheld``, the register
#: a checkout restores it from.  Additive and defaulted to ``[]``, the same
#: rule as 0.19 → 0.20: a stored result from before this opens with nothing
#: blocked, which is true of it — no hold could be declared, so no plan's glob
#: was ever refused.
#: 0.24 → 0.25 (WP-1333, issue #224): ``SeriesEntry.rungs_raised`` — the rungs
#: of a pattern's escalation ladder whose fit raised rather than returned, now
#: that a raised rung escalates like a diverged one instead of abandoning the
#: pattern.  Additive and defaulted to ``{}``, the same rule as 0.19 → 0.20: a
#: stored series from before this opens with no rung raised, which is true of
#: it — a raise then ended the pattern, so no entry could carry one.
#: 0.25 → 0.26 (WP-1414, issue #265): ``StageResult.unknown_paths`` — the
#: literal ``turn_on`` paths naming no parameter of the model — and
#: ``StageResult.unreached_histograms``, per histogram of a joint fit the globs
#: that reached another histogram and none of its rows.  Additive, the rule of
#: 0.19 → 0.20, and defaulted to ``None`` rather than empty, unlike 0.24's
#: ``blocked_by_hold`` or 0.25's ``rungs_raised``: no hold could exist before
#: its field, and no rung could raise and survive, so an empty default was
#: true of every older document there, while a typo'd literal freed nothing in
#: silence long before this one.  A stored result from before this opens with
#: ``None``, "nobody looked", and every runner now writes a value (WP-1076's
#: rule).
#: 0.26 → 0.27 (issue #270): ``CandidateGroup.delta_bic_raw_n`` and
#: ``SuggestionResult.n_effective`` — ``CandidateGroup.delta_bic`` is now
#: charged at N/f² (the probe residual's rows over its squared Bérar-Lelann
#: factor) and the raw-N figure rides beside it.  Additive and defaulted to
#: ``None``, the same rule as 0.19 → 0.20.
#: 0.27 → 0.28 (WP-1327): two additive fields, both defaulted to ``None``,
#: which is the honest empty state and the bit-identical one — a phase that
#: declares neither serializes apart from the new nulls, and refines, exactly
#: as before.  ``Atom.moment`` (crystal-axis components in μ_B, the magCIF
#: ``_atom_site_moment.crystalaxis_*`` convention, with the ion and the Landé
#: g the dipole form factor needs) and ``Phase.magnetic_symmetry`` (the magCIF
#: operator and centring loops with their time-reversal signs, the BNS/OG
#: symbol as metadata).
#: 0.28 → 0.29 (WP-1454): ``BackgroundPSpline.air_scatter`` is
#: ``Parameter | None`` and defaults to ``None``, which is no 1/(2θ) term at
#: all rather than one at zero.  Not additive: a stored ``null`` does not load
#: before this.  A document from before it carries the old default, a
#: ``Parameter`` at 0, and opens with that term declared, so it refines as it
#: did; setting the field to ``None`` is what drops it.  In the same step
#: ``BackgroundPSpline.lambda_units`` (``"dimensionless"`` default,
#: ``"intensity"`` the old rows): a document from before it has no such key,
#: so its stored λ opens as the new pure number and its penalty changes.  That
#: is deliberate rather than defaulted, because the old λ's meaning moved with
#: the intensity unit and no stored value says which unit it was chosen in;
#: ``lambda_units="intensity"`` refits it as before.
#: 0.29 → 0.30 (WP-1327, the operation-list phase split out of PR #433):
#: ``Phase.symmetry_operations``, the phase's own ``x,y,z`` operation list,
#: defaulted to ``None`` — the honest empty state and the bit-identical one:
#: a phase that declares none serializes apart from the new null, and refines,
#: exactly as before.  Written for the distortion-mode track's M-1 rung and for
#: a k ≠ 0 magnetic supercell, where a parent glide's ½ along a doubled axis
#: is a ¼ in the child and no symbol carries it.  What a consumer notices
#: beyond the null is that ``space_group`` may then be a bracketed *label*,
#: and that a bracketed label with no list, or a plain symbol that does not
#: generate the list, is refused.  0.30 → 0.31 (WP-1327, the k ≠ 0 route):
#: ``MagneticSymmetry.propagation_vector_parent``, the parent's k recorded on
#: a magnetic supercell ``magnetic.supercell.magnetic_supercell`` builds,
#: defaulted to ``None``.
#: 0.31 → 0.32 (WP-1326): ``Phase.propagation_vector`` — a commensurate k on
#: the nuclear cell, which adds satellites at Q = H ± k to the phase's frozen
#: reflection list — and ``ReflectionState.satellite_order``, the m that makes
#: (H, m) the key a Le Bail/Pawley intensity is restored on.  Both additive and
#: both defaulted to ``None``, which is the honest empty state *and* the
#: bit-identical one: a phase that declares no k serializes exactly as before
#: apart from the new null, and its reflection list, its intensities and every
#: number the fit produces are unchanged.  One shape widens without a new
#: field: a satellite's ``tick_hkl`` row is ``[h, k, l, m]`` (H and its order),
#: since H alone does not identify it; a nuclear row keeps its three.  0.31 is
#: the magnetic supercell's (#477), which landed first; this is the rung after
#: it.
SCHEMA_VERSION = "0.32"

TransformKind = Literal["identity", "softplus", "exp", "logit"]

#: Intensity model.  ``rietveld`` computes |F|² from the structure; ``lebail``
#: partitions the observed intensity among reflections by an iterated
#: fixed-point (the intensities are *not* free parameters); ``pawley`` puts the
#: same per-hkl intensities *into* the least-squares parameter vector (Pawley,
#: 1981), so they carry esds and overlapped groups need explicit conditioning.
#: Defined here rather than in ``model.forward`` so the schemas can name it
#: without importing the forward model (which imports the schemas).
Mode = Literal["rietveld", "lebail", "pawley"]


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
