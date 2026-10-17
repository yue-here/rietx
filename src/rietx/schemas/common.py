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
#: The number moves once per release cycle.  The first change after a release
#: bumps it, and each later change before the next release adds its own line
#: under that number, so a PR rebased onto a ``main`` already bumped keeps
#: ``main``'s number.  Decided 2026-10-15, after six concurrent PRs had
#: renumbered one another after every merge.
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
#: 0.32 → 0.33 (WP-1320): ``FractionProfile`` and ``FractionProfilePoint``
#: (``schemas/fraction.py``), the answer ``Refinement.profile_fraction``
#: returns — every weight fraction of one phase the pattern admits along its
#: width, beside the QPA rather than inside it.  Additive: no existing model
#: gains or loses a field and every stored document loads unchanged, but a
#: new answer type is a new shape a consumer parses, which since WP-1117 is
#: the whole test.
#: 0.33 → 0.34 (WP-1468): ``Atom.disorder_assembly`` and
#: ``Atom.disorder_group``, the CIF core dictionary's two disorder items as
#: strings.  Additive and defaulted to ``None``, an ordered site, which is the
#: honest empty state and the bit-identical one: a structure that declares
#: none serializes apart from the new nulls, and refines, exactly as before.
#: No forward model reads them; the structure viewer does.
#: 0.34 → 0.35 (WP-1321, issues #204 and #209): every class whose
#: ``Parameter`` fields declare a range in their ``default_factory`` now does
#: what ``Atom`` has done since 0.17 — ``Phase``, ``PreferredOrientation``,
#: ``AnisoU``, ``Moment``, ``StephensStrain`` and eleven instrument classes
#: (:class:`_InheritsDeclaredDefaults`).  A caller's own ``Parameter``
#: inherits the ``min``/``max``/``unit`` it left out, and the ``transform``
#: together with the bounds that transform enforces.  No field changed shape;
#: the 0.16 → 0.17 shape again, stated in the direction it bites.  **Legal
#: constructions shrank**: ``ProfileTCHZ(u=Parameter(value=1.576))``, storable
#: before, raises naming ``ProfileTCHZ.coarse``.  **One grew**: a
#: ``PeakComponent`` width leaving ``max`` unset takes the declared box rather
#: than being refused.  **What moves without a refusal is the
#: parameterisation**: ``Phase(scale=Parameter(value=5e-3, vary=True))`` is
#: softplus from zero, where it was an unbounded identity, so a fit built that
#: way walks a different path to its answer.  **Documents already written are
#: repaired at read** where they carry the defect
#: (``RefinementTree.load``, ``DECLARED_RANGE_RESTORED``), gated on the
#: version each node was written under, which is why this bump is
#: load-bearing.  That needs ``HistoryNode.schema_version``, additive and
#: defaulted to ``None`` (a node written before it, read at its header's
#: version): the header stamps a log's creation, and a node appended to an
#: old log by this release would otherwise be read as old.  A log whose
#: header says 0.35 or later is never walked.
#: 0.35 → 0.36 (WP-1469, issue #481): ``SeriesEntry.rwp_fence`` — the Rwp
#: limit the chain's fence set at the pattern, so the verdict on a kept
#: attempt still above it (``SEQUENTIAL_RWP_OUTLIER``) is read off the entry —
#: and ``SeriesResult.discontinuities`` (``list[SeriesStep]``), the pair each
#: ``SEQUENTIAL_DISCONTINUITY`` names in prose.  Both additive and defaulted to
#: ``None``, the rule of 0.25 → 0.26: a series from before this may have had
#: an outlier or a flagged step, so an empty default would claim what nobody
#: checked.  Opened, it reports neither code's new half, which is true — no
#: fence recorded one.
#: 0.36 → 0.37 (WP-1343): ``Phase.magnetic_lor_size`` and
#: ``Phase.magnetic_lor_strain``, the magnetic component's own extra
#: Lorentzian size (1/cosθ) and strain (tanθ) broadening in deg 2θ
#: (``min = 0.0``, softplus, default 0.0, refused non-zero or free on a phase
#: with no ``magnetic_symmetry``).  Both are exactly off at that default, so
#: every document written before loads unchanged and no fit's number moves;
#: what a consumer notices is two new keys in every serialized phase, two new
#: parameter paths on a phase that declares a magnetic structure, and the
#: reflection table's new ``component`` column.  WP-1469 took 0.36 first, and
#: its sibling WP-1329 took 0.38 on top of this.
#: 0.37 → 0.38 (WP-1329): ``SeriesEntry.magnetic``, the moment along a
#: series — WP-1327's ``MomentEvidence`` rows per pattern of a sequential
#: refinement.  Before it, a magnetic series handed back a signed
#: ``phases.i.atoms.j.moment.dof0`` row in ``parameters`` and *none* of the
#: evidence that stops it being misread: ``supported``, the esd the ratio is
#: against, the direction the powder could not determine, the dipole
#: approximation in force.  Written by ``sequential._chain`` from the same
#: ``report.magnetic.analyse_moments`` a single-pattern report uses, keyed on
#: ``MomentEvidence.path`` (already stored since WP-1327).  Additive and
#: defaulted to an empty list, which is the honest empty state and the
#: bit-identical one: a series whose phases declare no moment serializes
#: exactly as before apart from that list, and no number any fit produces
#: moves.  ``MagneticTrajectory``/``MagneticOnset`` are *derived* views over it
#: and are stored nowhere.  WP-1343 took 0.37 first.
#: 0.38 → 0.39 (issue #599): ``StageResult.moment_flat_axes`` and
#: ``StageResult.moment_turned`` — the flat rotation axis of every three-DOF
#: moment site whose azimuth a stage held as a flat combination of its two
#: angles, and which of those sites the stage turned onto the axis's meridian
#: first.  The record the report's moment note is a projection of (review of
#: #624, item 2): the turn changes the direction a fit reports, so it ships
#: with a field stating it.  Additive and defaulted to empty, which is every
#: fit without such a site; a document written before loads unchanged.
#: 0.39 → 0.40 (WP-1534): ``StageResult.scale_b_held`` — per phase whose
#: displacement parameters a stage held because the fitted range cannot
#: separate them from the phase's scale, the column separation measured.
#: Additive, and defaulted to ``None`` rather than empty, the 0.25 → 0.26 rule:
#: a stored result from before this may have walked that ridge (issue #204's
#: did), so an empty default would say "looked, nothing held" of a fit nobody
#: looked at.  Both single-histogram runners now write a mapping on every
#: stage; the joint runner does not ask, and leaves ``None``.
#: 0.40 → 0.41 (WP-1323): ``PlanSpec.lebail_passes``, the cap on Le Bail passes.
#: Additive and defaulted to 1, the single run every earlier plan made; an older
#: build refuses a document carrying it (``extra="forbid"``), which is the point
#: of the bump.
#: 0.41 → 0.42 (#788): ``RefinementState.free_declared``, whether a node's
#: ``free_paths`` is a declaration or "nothing declared yet" (the models' own
#: ``vary`` flags then are the free set).  Additive and defaulted to ``False``,
#: the reading every earlier document had, so an old tree loads unchanged; an
#: older build refuses a document carrying it (``extra="forbid"``).
#: 0.42 → 0.43 (WP-1805): ``Phase.rigid_bodies``, a list of ``RigidBody``
#: (template, origin, orientation quaternion) over the phase's own atoms.
#: Additive and defaulted to empty, which builds exactly the table every
#: earlier document built; an older build refuses a document carrying a body.
#: 0.43 → 0.44 (WP-1930): ``StageResult.seeded``, each row a stage lifted
#: before solving and the value it started at, and ``.floor_unseeded``, the
#: freed rows left on their softplus floor for want of a seed size.  Additive,
#: and defaulted to ``None``, the 0.25 → 0.26 rule: a stored result from
#: before this may have freed a row on its floor (issue #832's did), so an
#: empty default would say "looked, nothing seeded" of a fit nobody looked at.
#: All three runners write both on every stage.
#: 0.44 → 0.45 (WP-1808): ``RigidBody.torsions``, named-bond torsions inside
#: a body (axis, declared moved set, the angle record).  Additive and defaulted to
#: empty, a body without one building exactly the 0.44 table.
#: 0.45 → 0.46 (WP-1938): two fields leave.  ``Parameter.transform`` goes
#: because every parameter is now refined in its own units, with its bounds
#: passed to the driver as a box.  A stored or passed ``transform`` is folded
#: into the bounds it enforced by a ``mode="before"`` validator on
#: ``Parameter`` (:func:`legacy_transform_bounds`): softplus and exp become
#: ``min ≥ 0``, logit also ``max ≤ 1``.  ``StageResult.floor_unseeded`` (0.44)
#: goes with WP-1930's floor seed, and a before-validator on ``StageResult``
#: drops a stored one.  Every document written before opens unchanged in
#: meaning, since the table already built each declared transform as that box.
#: A document written here carries neither key, and an older build reads it as
#: all-identity with the same bounds.
#: 0.46 → 0.47 (WP-1931): ``BackgroundSelection.diagnostics``, the findings a
#: selector carries beside its scan (``BACKGROUND_ORDER_AT_CAP``).  Additive and
#: defaulted to empty, the reading every earlier selection had.
#: 0.47 → 0.48 (WP-1929): ``ParameterInterval`` and ``ParameterIntervalPoint``
#: (``schemas/interval.py``), the answer ``Refinement.profile_interval``
#: returns — the profile-likelihood interval for one refined parameter,
#: one-sided for a row on its bound.  Additive, the 0.32 → 0.33 shape: no
#: existing model gains or loses a field, but a new answer type is a new shape
#: a consumer parses.
#: 0.48 → 0.49 (WP-1929): ``StageResult.moment_angle_tests``, a list of
#: ``MomentAngleTest``, each round of the stationary-angle test the stage's
#: covariance ran.  Additive and defaulted to ``None``, the 0.25 → 0.26 rule:
#: a stored result from before ran no test, so an empty list would claim one.
#: ``ParameterInterval.stderr`` becomes ``float | None``: an angle the test
#: left out of the covariance has a profile interval and no esd.  Every
#: earlier document opens unchanged; an older build refuses one carrying the
#: new field, or an interval whose ``stderr`` is ``None``.
#: 0.49 → 0.50 (WP-1809): ``TetherRestraint`` and ``AntiBumpRestraint`` join
#: the ``Restraint`` union, and ``RestraintRow.kind`` gains ``"tether"`` and
#: ``"anti_bump"``.  Additive: no existing document carries either.
#: 0.50 → 0.51 (WP-1317): ``SeriesResult.relative_paths`` and
#: ``.angle_paths``, the paths a run's models make steps and angles, so a
#: judgement across patterns made outside the run (``moved_paths``) skips and
#: wraps what the fences do.  Additive and defaulted to ``None``, "not
#: recorded", the 0.25 → 0.26 rule; ``SequentialRefinement.fit`` writes both
#: on every result, the backward chain's included.
#: 0.51 → 0.52 (WP-1912): ``Phase.floating_origin``, ``"hold"`` making the
#: parameter table hold one coordinate DOF along each direction a polar
#: group's origin floats in, and ``ParameterRow.origin_axis``, the direction a
#: row so held fixes.  Additive and defaulted to ``None``: exactly off, the
#: table every earlier document built.  An older build refuses a document
#: carrying either key.
#: 0.52 → 0.53 (yue-here/rietx issue #193, the time-of-flight readers and
#: axis): ``PatternData.two_theta`` becomes ``list[float] | None`` beside a new
#: ``PatternData.tof`` (µs), exactly one of the two set; ``Instrument.source``
#: gains a third arm, ``TOFSource`` (``kind="neutron_tof"``: DIFC/DIFA/TZERO/
#: DIFB, the bank angle, ``ProfileTOF`` and ``IncidentSpectrum``).  Not purely additive: a
#: consumer that read ``two_theta`` as always present must now ask
#: ``PatternData.axis``.  Every stored document loads unchanged — each has a
#: ``two_theta`` — and a 2θ pattern serializes apart from the new nulls, and
#: refines, exactly as before.  A ``neutron_tof`` source is read and never
#: refined in this build.
#: 0.53 → 0.54 (WP-1912): ``Phase.floating_origin`` gains ``"centroid"``, the
#: restraint of Flack & Schwarzenbach (1988) on a weighted centroid of the
#: phase's sites in place of a hold on one.  Additive: no existing document
#: carries the value, and an older build refuses one that does.
#: 0.54 → 0.55 (WP-1325): ``RefinementResult.parametric``, a list of
#: ``ParametricCoefficient`` — the coefficients of a joint fit's parametric
#: declarations, in user units at each declaration's reference — beside the
#: two declaration models ``CoordinateTable`` and ``ParametricTie``
#: (``schemas/parametric.py``) the joint path now takes.  Additive and
#: defaulted to ``None``, "nothing declared", which every earlier result is;
#: an older build refuses a result carrying the field.
#: 0.55 → 0.56 (WP-1325): ``RefinementResult.parametric_form``, one
#: ``ParametricFormTest`` per parametric declaration — whether the data
#: rejects the declared form, by a score test at the answer.  Additive and
#: defaulted to ``None``, as ``parametric`` is; an older build refuses a
#: result carrying the field.
#: 0.56 → 0.57 (WP-1960): ``Phase.texture``, a ``SphericalHarmonicTexture``
#: (an even ``order`` and a name → ``Parameter`` map of coefficients), and
#: ``RefinementResult.texture``, one ``PhaseTexture`` per textured phase.
#: Additive and defaulted to ``None`` and empty, so every stored document
#: loads and refines as before; an older build refuses either.
#: 0.57 → 0.58 (WP-1810): ``RigidBody.riding``, the body atoms that are riding
#: hydrogens, and the CIF ``_atom_site_refinement_flags_posn`` /
#: ``_atom_site_calc_flag`` columns a phase with a body now writes.  Additive.
#: 0.58 → 0.59 (WP-1325): ``RefinedParameter.equations``, the parametric
#: equations whose coefficients set a row; ``ParametricFormTest.n_subset``,
#: the subset's size beside the patterns tested; ``ParametricFormTest``'s
#: ``dof``/``statistic``/``cut`` moved into two ``ParametricFormReading``s,
#: ``tied`` and ``others_freed``, each with a ``p_value``;
#: ``RefinementResult.parametric_equations``, each equation as resolved with its
#: coefficients' covariance; ``RefinementResult.parametric_form_joint``, the
#: form test of every tested equation at once, ``None`` below two.
#: ``ParametricFormTest.rejected`` is the ``others_freed`` reading's verdict
#: where there is one, and ``ParametricFormTest.provisional_on`` names the
#: other rejected equations; every reading divides by χ²_red alone.
#: ``equations`` and ``parametric_equations`` default to
#: ``None``, "not recorded", so an older result opens and claims nothing; the
#: form-test fields are required and the old ones gone, ``parametric_form``
#: being unreleased.  The declaration model is ``ParametricEquation``, which
#: 1.9.0 called ``ParametricTie`` (no alias), and the field naming it is
#: ``equation`` on ``ParametricCoefficient``, ``ParametricFormTest`` and
#: ``RefinedParametricEquation``; ``ParametricCoefficient`` still reads the
#: 0.55 key ``tie``, so a 1.9.0 result opens and is written back as ``equation``.
#: ``ParametricValue``, built on demand and never stored, carries
#: ``provisional_on`` and ``joint_rejected`` beside ``form_rejected``.
#: 0.59, a second line in the 1.10.0 cycle (WP-1809): ``PlanarityRestraint``
#: joins the ``Restraint`` union, and ``RestraintRow.kind`` gains
#: ``"planarity"``.  Additive: no existing document carries either, and 1.9.0
#: refuses one that does.  The number does not move again inside a release
#: cycle (yue-here/rietx#991, decided 2026-10-15).
SCHEMA_VERSION = "0.59"

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
    stderr:
        Estimated standard deviation, filled in by the refinement.
    """

    value: float
    vary: bool = False
    min: float = -math.inf
    max: float = math.inf
    expr: str | None = None
    unit: str | None = None
    stderr: float | None = None

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


#: What a bare ``Parameter`` holds for each attribute a field's declared
#: default can carry.  In a document written before a class inherited
#: (:class:`_InheritsDeclaredDefaults`), an attribute holding this value is the
#: only trace an omission left once it was serialized.
BARE_PARAMETER_ATTRS: dict[str, object] = {
    "min": -math.inf, "max": math.inf, "unit": None}


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
    (``Atom.occ``: min 0, max 1.5; ``Phase.lor_size``: min 0, degrees) rather
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
    leaked the first field's range into the second.  ``data`` is copied once
    for the same reason (``model_validate`` may be handed the caller's dict).

    **The replacement is a ``Parameter``, never the merged dict**:
    ``validate_assignment=True`` re-runs this validator on every assignment to
    an already-built model, with ``data`` built from its current field values,
    so this branch fires for fields the assignment never touched; pydantic
    does not re-validate those, so a dict placed here would reach the model as
    a dict (measured on ``Atom`` after ``atom.aniso = AnisoU(...)``).

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

    @model_validator(mode="before")
    @classmethod
    def _inherit_declared_bounds(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        for name, info in cls.model_fields.items():
            if info.annotation is not Parameter or info.default_factory is None:
                continue
            if name not in data:
                continue  # omitted: default_factory already carries the range
            raw = data[name]
            if isinstance(raw, Parameter):
                present, base = raw.model_fields_set, raw.model_dump()
            elif isinstance(raw, dict):
                present, base = raw.keys(), raw
            else:
                continue  # not a shape that carries attribute presence
            if BARE_PARAMETER_ATTRS.keys() <= set(present):
                continue  # every attribute stated (every reload): nothing to inherit
            # an attribute left unset replaces the caller's object even where
            # the declared value is the one it holds anyway: one Parameter passed
            # to every atom's ``occ`` must become one Parameter per atom, or the
            # write-back leaves the last site's value in all of them (PR #206's
            # behaviour, kept).  Sharing *on purpose* states every attribute —
            # ``Harmonic.weight``'s default does, being its line's by reference
            fills = declared_fills(info.default_factory(), set(present))
            if not fills:
                continue
            try:
                data[name] = Parameter(**{**base, **fills})
            except ValueError as exc:
                try:
                    Parameter(**base)
                except ValueError:
                    raise exc from None  # broken without the fills too: not ours to name
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
        return data


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
        explanation is left out because it is the same for every finding; a
        notebook folds it under the headline.
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
