# Schema version history

One note per change to `SCHEMA_VERSION` (`rietx.schemas.common`), which `capabilities()` reports as
`schema_version`. The rule for when the number moves is the comment
above the constant. `tests/test_capabilities.py` fails when no note names the
constant's current value. These notes name removed things on purpose, so the
code-reference check does not read this directory.

0.1 → 0.2 (WP-1076): ``RefinedParameter.initial`` and
``RefinementResult.correlation_warnings`` removed, both fields nothing wrote.

0.2 → 0.3 (WP-1112): ``StageSpec.window_slack_deg`` added — a stage's
declared window capture slack in °2θ (``None`` → the compiled default).

0.3 → 0.4 (WP-1113): ``StageSpec.ftol`` added — a stage's own termination
tolerance (``None`` → the solver default 1e-9).

0.4 → 0.5 (WP-1123): ``PlanSpec.intermediate_ftol`` added and **defaulting
to 1e-6**, so a plan validated from a document that does not mention it now
stops its intermediate stages earlier than the same document did before;
``StageResult.ftol`` and ``NodeAction.ftol``/``window_slack_deg`` added,
recording what a stage ran at.  The one entry so far whose default changes
an answer rather than only the field list — bounded at 0.03 esd on a single
fit — and ``intermediate_ftol=None`` restores the old schedule bit for bit.

0.5 → 0.6 (PR #99): ``SeriesEntry.phase_agreement`` added — the per-phase
Bragg agreement each pattern's own result already carried, now surviving the
series boundary.  Additive and defaulted, and it bumps anyway: WP-1117 made
the only question whether a consumer could notice, and a new field on a
response arm is noticeable.

0.6 → 0.7 (PR #108): constant-wavelength neutron support, three observable
changes landing together because they are one feature and one PR.
(a) ``NeutronSource`` added as a second arm of the ``Instrument.source``
discriminated union (``kind="neutron_cw"``), so a consumer that switched
exhaustively on ``kind`` now has a case it has never seen, and
``Capabilities.radiations`` / ``RadiationCapability`` are a new field on a
response arm.
(b) ``Source.harmonics`` / ``NeutronSource.harmonics`` — a list of
``Harmonic`` blocks declaring the λ/n components a monochromator does not
filter out.  A consumer notices the new key in every serialized source, and
that a **neutron** source carrying a harmonic reports more than one entry in
``source.lines``, since the λ/n lines are *derived* there rather than stored.
Empty is the default; a non-empty list is refused outright on an X-ray source
(``Source.harmonics_supported``).
(c) ``EmissionLine.wavelength`` and ``NeutronSource.wavelength`` are a
:class:`Parameter` rather than a ``float``, so a serialized source carries a
nested object where it carried a number and the parameter table gains an
``instrument.source.lines.N.wavelength`` row.  Both still *accept* a bare
number and default to ``vary=False``.
Nothing existing changes meaning, every pre-0.7 document validates unchanged,
and a fit that declares no harmonic and frees no wavelength is bit-identical.
One bump rather than three: the ladder counts *observable releases*, and
these three reach a consumer in the same one.

0.7 → 0.8 (WP-1202): ``ParameterRow.help_key`` added, naming the help-corpus
family that describes the path (``rietx.help``).  Additive and defaulted, and
it bumps for the reason 0.6 → 0.7 did: a new key on a response arm is
something a consumer notices.  ``None`` is a real answer here (no family
claims the path) rather than an unfilled default, because
``Refinement.parameters`` fills it for every caller.

0.8 → 0.9 (WP-1207): ``Structure.phases`` may be **empty**.  Nothing gains a
field and every document written before validates unchanged, but the set of
legal documents grew and that is what a consumer notices: code that read a
serialized structure and indexed ``phases[0]``, or counted phases to size an
answer, now has a case it has never seen.  The agent envelope's ``NO_PHASES``
rides with it as a fourth ``ERROR_CODES`` member.  One bump for the pair —
the ladder counts observable releases, and they reach a consumer in the same
one.

0.9 → 0.10 (additive background peaks): ``Instrument.extra_components`` (a new
declared block) and ``RefinementResult.n_extra_components`` (a new field on a
result).  Additive and defaulted — the empty list and ``None`` reproduce a
pre-feature document byte for byte — but both are noticeable to a consumer,
which since WP-1117 is the whole test (the ``Identifiability`` docstring is
the sentence that first talked a reader out of this bump).

0.10 → 0.11 (WP-1301): ``StageResult.held`` and ``StageResult.released`` —
the structural parameters of a phase the data could not see, held for the
stage rather than refined down a flat direction, and the subset the same
stage let go again.  Additive and defaulted, and the empty lists are the
honest answer for every fit with no unsupported phase (they are written on
every stage, so an empty one means "nothing was held", not "nobody looked").
A consumer notices, which is the whole test: a parameter the plan freed can
now come back unrefined, and these two fields are where it says so.

0.11 → 0.12 (WP-1303): the **agent envelope is gone** — ``rietx.agent``, its
request union (``RefineRequest`` and the four peers), its response arms
(``AgentSuccess``/``AgentFailure``), the ``ERROR_CODES`` grammar and the
exported JSON Schemas.  Every other bump on this ladder was additive; this
one removes models a consumer could have been parsing, which is why it moves
the string rather than riding along with a release note.  Nothing that
*computes* moved: the answer types the envelope wrapped
(``RefinementResult``, ``FitReport``, ``SeriesResult``, ``IndexingResult``,
``SuggestionResult``) are untouched and still serialize byte for byte, so a
caller that dumps ``Refinement.fit``'s result gets what the ``result`` arm
carried.  ``Capabilities.features`` loses ``agent_json`` with it.

0.12 → 0.13 (WP-1304): ``Capabilities`` gains ``skill_path``, the directory
of the agent skill this build carries (``None`` where it carries none).
Additive, and a client that ignores the field is unaffected — but the field
list of that model *is* the contract a client reads to decide what it may
ask for, which is the argument for moving the string rather than letting a
new arm ride along silently.

0.13 → 0.14 (WP-1305): ``CandidateGroup.delta_bic`` — what ``suggest``'s
ranking never said, whether the predicted gain pays for the parameter.
**Required, not defaulted**: 0.0 on a model-selection field reads as "no
preference", which is the defaulted-``False`` lie WP-1076 named, so a
document written before this field does not load rather than loading with an
answer nobody computed.

0.14 → 0.15 (WP-1131): ``RefinementResult.microstructure`` — the four
profile coefficients read as a coherent domain size and a Δd/d, with esds.
Additive and defaulted to an empty list, which is the honest empty state
here (a result built without a compiled model measured no wavelength and can
read no size), but it is a new field a consumer enumerates, so it bumps.
``PhaseMicrostructure.scherrer_k`` inside it is **required**: a size scales
linearly in K, so a defaulted 0.0 would be an answer about a constant nobody
chose (WP-1076; WP-1305's ``delta_bic`` took the same decision).

0.15 → 0.16 (WP-1119): ``RefinementState.variables`` and
``NodeAction.variables``/``removed_variables`` — named variables, a caller's
own ``Parameter`` outside the model tree that other parameters follow by
affine tie.  Additive and defaulted to empty, which is the honest empty state
(a refinement that declared none), but a variable is the one piece of
refinement state with **no** model field behind it: ``apply_to_models`` has
nothing to write it to, so the document is its only source of truth and a
node that dropped it would restore ties pointing at a parameter that is gone.
The field it reuses is ``Parameter`` itself rather than a new type, which is
what makes a variable and the model parameter it replaces produce the
identical table ``Entry``.

0.16 → 0.17 (issue #204): ``Atom.occ``/``biso`` now inherit their field's
declared bounds and unit onto a caller-supplied ``Parameter`` that omitted
them, rather than silently falling back to ``Parameter``'s own bare
(-inf, inf, no unit). No field gained or changed shape — this is the
0.4 → 0.5 shape, a behaviour change rather than a field-list one — but
**the set of legal ``Atom`` constructions shrank**, the opposite direction
from every earlier entry here: a bare ``Parameter(value=-165.0)`` for
``biso``, storable before this change, now raises ``ValidationError``.
WP-1117 made the only question whether a consumer could notice, and a
construction that used to succeed and now doesn't is exactly that.
**Already-written documents are unaffected.** A persisted ``Atom`` always
serializes ``min``/``max``/``unit`` explicitly, so on load
``model_fields_set`` (or, for the raw dict, its keys) is already complete,
nothing is inherited, and every stored value — including one this
validator would now refuse at construction, e.g. that same -165 A^2 Biso
— deserializes and validates exactly as before. The break is to
*construction*, not to *documents* (issue #209 is the read-time follow-up
that leaves open whether such an already-persisted value should also be
repaired).

0.17 → 0.18 (WP-1102): ``Instrument.background_peaks`` became
``extra_components``, a list of the discriminated union
:data:`~rietx.schemas.instrument.ExtraComponent` whose one member today is
``HumpComponent`` (v1.2's ``BackgroundPeak``, plus a ``kind`` field);
``RefinementResult.n_background_peaks`` became ``n_extra_components``.  A
**rename**, which every earlier entry here avoided, so it is stated in the
direction it breaks: **old documents open and old code does not.** A v1.2
project, history tree or ``.rxt`` is read by
:mod:`rietx.schemas.migrate` — the field *and* the dot-paths, because those
fail differently and only one of them fails loudly — while assigning
``instrument.background_peaks`` in code raises under ``extra="forbid"``.
The path half is the reason the migration exists at all: a stored plan glob
under the old spelling loads clean and then matches nothing, which stops
refining a declared hump in silence.

0.19 → 0.20 (issue #283): ``StageResult.n_degenerate_cell_probes`` — the
count of degenerate-cell trial points a stage's search reached (zero or
negative direct-metric-tensor determinant, refused by name from
``crystallography.lattice.d_spacings`` as ``DegenerateCellError``) and the
solver-side guard (``optimize.least_squares._DegenerateCellGuard``) pushed
back out before the reported values were ever computed from one.
Additive and defaulted to 0, the honest empty state for a fit whose search
never left the physical cell, but it is a new field on every stage result
a consumer enumerates — bump per observable change (the precedent is
0.8 → 0.9, where ``Structure.phases`` being allowed empty grew the set of
legal documents with no field added at all; a new field is squarely that,
and more so).  Surfaced beside it, not instead of it, as the ``info``-level
``CELL_DEGENERATE_PROBE`` diagnostic: the guard already contained the
excursion before it reached the caller, so however often an underdetermined
cell stage reaches this, nothing about the reported values is in question.

0.20 → 0.21 (WP-1309): ``BackgroundFixedPlusChebyshev`` grew ``scale`` (the
multiplier TOPAS's ``bkg_file("f.xy", @, s)`` has), ``fixed_sigma`` (the
curve's own counting statistics) and ``fixed_source`` (where the curve came
from).  Three new fields on a union member a consumer enumerates, so the same
rule as 0.19 → 0.20.  **No document changes meaning**: all three default to
the state the member was in — a scale of 1.0 held, no esds, no provenance —
so a stored instrument opens and refines exactly as it did.  What does change
without a stored field is that every plan preset frees
``instrument.background.*``, which now reaches the scale; the v1.4 record's
break list has that half.

0.21 → 0.22 (WP-1438): ``RefinementResult.tick_hkl`` and
``HistogramResult.tick_hkl`` — which reflection each entry of ``ticks`` is,
as the orbit representative ``h k l``, paired with the positions by index.
Additive and defaulted to ``{}``, and the same rule as 0.19 → 0.20: a new
field on a result a consumer enumerates bumps the version whether or not any
stored document changes meaning.  **None does** — a result written before
this opens with the mapping empty, which is the honest empty state rather
than a claim, and the three pages that draw ticks fall back to hovering the
2θ they always did.
The field is a *companion*, not a change of shape: ``ticks`` keeps its
``dict[str, list[float]]``, because its four readers want positions and none
of them wants this.  A phase is **absent** from ``tick_hkl`` rather than
empty where there is nothing to say, which is the case for the reserved
declared-peaks key: a peak given by centre has no Miller index, and ``[]``
there would claim it had none of its own.

0.22 → 0.23 (issue #375): ``SeriesResult.failures``
(``list[SeriesFailure]``) and ``.n_failed`` — a pattern
``SequentialRefinement.fit``'s new ``on_error`` policy caught rather than
letting crash the whole chain.  Additive and defaulted to ``[]``/``0``, the
same rule as 0.19 → 0.20: a stored series from before this opens with no
failures recorded, which is the honest statement that this field did not
exist yet, never a claim that every pattern fit — the default policy is
still ``on_error="raise"``, unchanged behaviour, so no existing chain's
reported entries move.

0.23 → 0.24 (issue #211): ``StageResult.blocked_by_hold`` — the paths a
stage's ``turn_on`` matched and a caller's ``Refinement.hold`` kept fixed,
and ``RefinementState.holds``/``NodeAction.held``/``.unheld``, the register
a checkout restores it from.  Additive and defaulted to ``[]``, the same
rule as 0.19 → 0.20: a stored result from before this opens with nothing
blocked, which is true of it — no hold could be declared, so no plan's glob
was ever refused.

0.24 → 0.25 (WP-1333, issue #224): ``SeriesEntry.rungs_raised`` — the rungs
of a pattern's escalation ladder whose fit raised rather than returned, now
that a raised rung escalates like a diverged one instead of abandoning the
pattern.  Additive and defaulted to ``{}``, the same rule as 0.19 → 0.20: a
stored series from before this opens with no rung raised, which is true of
it — a raise then ended the pattern, so no entry could carry one.

0.25 → 0.26 (WP-1414, issue #265): ``StageResult.unknown_paths`` — the
literal ``turn_on`` paths naming no parameter of the model — and
``StageResult.unreached_histograms``, per histogram of a joint fit the globs
that reached another histogram and none of its rows.  Additive, the rule of
0.19 → 0.20, and defaulted to ``None`` rather than empty, unlike 0.24's
``blocked_by_hold`` or 0.25's ``rungs_raised``: no hold could exist before
its field, and no rung could raise and survive, so an empty default was
true of every older document there, while a typo'd literal freed nothing in
silence long before this one.  A stored result from before this opens with
``None``, "nobody looked", and every runner now writes a value (WP-1076's
rule).

0.26 → 0.27 (issue #270): ``CandidateGroup.delta_bic_raw_n`` and
``SuggestionResult.n_effective`` — ``CandidateGroup.delta_bic`` is now
charged at N/f² (the probe residual's rows over its squared Bérar-Lelann
factor) and the raw-N figure rides beside it.  Additive and defaulted to
``None``, the same rule as 0.19 → 0.20.

0.27 → 0.28 (WP-1327): two additive fields, both defaulted to ``None``,
which is the honest empty state and the bit-identical one — a phase that
declares neither serializes apart from the new nulls, and refines, exactly
as before.  ``Atom.moment`` (crystal-axis components in μ_B, the magCIF
``_atom_site_moment.crystalaxis_*`` convention, with the ion and the Landé
g the dipole form factor needs) and ``Phase.magnetic_symmetry`` (the magCIF
operator and centring loops with their time-reversal signs, the BNS/OG
symbol as metadata).

0.28 → 0.29 (WP-1454): ``BackgroundPSpline.air_scatter`` is
``Parameter | None`` and defaults to ``None``, which is no 1/(2θ) term at
all rather than one at zero.  Not additive: a stored ``null`` does not load
before this.  A document from before it carries the old default, a
``Parameter`` at 0, and opens with that term declared, so it refines as it
did; setting the field to ``None`` is what drops it.  In the same step
``BackgroundPSpline.lambda_units`` (``"dimensionless"`` default,
``"intensity"`` the old rows): a document from before it has no such key,
so its stored λ opens as the new pure number and its penalty changes.  That
is deliberate rather than defaulted, because the old λ's meaning moved with
the intensity unit and no stored value says which unit it was chosen in;
``lambda_units="intensity"`` refits it as before.

0.29 → 0.30 (WP-1327, the operation-list phase split out of PR #433):
``Phase.symmetry_operations``, the phase's own ``x,y,z`` operation list,
defaulted to ``None`` — the honest empty state and the bit-identical one:
a phase that declares none serializes apart from the new null, and refines,
exactly as before.  Written for the distortion-mode track's M-1 rung and for
a k ≠ 0 magnetic supercell, where a parent glide's ½ along a doubled axis
is a ¼ in the child and no symbol carries it.  What a consumer notices
beyond the null is that ``space_group`` may then be a bracketed *label*,
and that a bracketed label with no list, or a plain symbol that does not
generate the list, is refused.  0.30 → 0.31 (WP-1327, the k ≠ 0 route):
``MagneticSymmetry.propagation_vector_parent``, the parent's k recorded on
a magnetic supercell ``magnetic.supercell.magnetic_supercell`` builds,
defaulted to ``None``.

0.31 → 0.32 (WP-1326): ``Phase.propagation_vector`` — a commensurate k on
the nuclear cell, which adds satellites at Q = H ± k to the phase's frozen
reflection list — and ``ReflectionState.satellite_order``, the m that makes
(H, m) the key a Le Bail/Pawley intensity is restored on.  Both additive and
both defaulted to ``None``, which is the honest empty state *and* the
bit-identical one: a phase that declares no k serializes exactly as before
apart from the new null, and its reflection list, its intensities and every
number the fit produces are unchanged.  One shape widens without a new
field: a satellite's ``tick_hkl`` row is ``[h, k, l, m]`` (H and its order),
since H alone does not identify it; a nuclear row keeps its three.  0.31 is
the magnetic supercell's (#477), which landed first; this is the rung after
it.

0.32 → 0.33 (WP-1320): ``FractionProfile`` and ``FractionProfilePoint``
(``schemas/fraction.py``), the answer ``Refinement.profile_fraction``
returns — every weight fraction of one phase the pattern admits along its
width, beside the QPA rather than inside it.  Additive: no existing model
gains or loses a field and every stored document loads unchanged, but a
new answer type is a new shape a consumer parses, which since WP-1117 is
the whole test.

0.33 → 0.34 (WP-1468): ``Atom.disorder_assembly`` and
``Atom.disorder_group``, the CIF core dictionary's two disorder items as
strings.  Additive and defaulted to ``None``, an ordered site, which is the
honest empty state and the bit-identical one: a structure that declares
none serializes apart from the new nulls, and refines, exactly as before.
No forward model reads them; the structure viewer does.

0.34 → 0.35 (WP-1321, issues #204 and #209): every class whose
``Parameter`` fields declare a range in their ``default_factory`` now does
what ``Atom`` has done since 0.17 — ``Phase``, ``PreferredOrientation``,
``AnisoU``, ``Moment``, ``StephensStrain`` and eleven instrument classes
(:class:`_InheritsDeclaredDefaults`).  A caller's own ``Parameter``
inherits the ``min``/``max``/``unit`` it left out, and the ``transform``
together with the bounds that transform enforces.  No field changed shape;
the 0.16 → 0.17 shape again, stated in the direction it bites.  **Legal
constructions shrank**: ``ProfileTCHZ(u=Parameter(value=1.576))``, storable
before, raises naming ``ProfileTCHZ.coarse``.  **One grew**: a
``PeakComponent`` width leaving ``max`` unset takes the declared box rather
than being refused.  **What moves without a refusal is the
parameterisation**: ``Phase(scale=Parameter(value=5e-3, vary=True))`` is
softplus from zero, where it was an unbounded identity, so a fit built that
way walks a different path to its answer.  **Documents already written are
repaired at read** where they carry the defect
(``RefinementTree.load``, ``DECLARED_RANGE_RESTORED``), gated on the
version each node was written under, which is why this bump is
load-bearing.  That needs ``HistoryNode.schema_version``, additive and
defaulted to ``None`` (a node written before it, read at its header's
version): the header stamps a log's creation, and a node appended to an
old log by this release would otherwise be read as old.  A log whose
header says 0.35 or later is never walked.

0.35 → 0.36 (WP-1469, issue #481): ``SeriesEntry.rwp_fence`` — the Rwp
limit the chain's fence set at the pattern, so the verdict on a kept
attempt still above it (``SEQUENTIAL_RWP_OUTLIER``, gone in 0.60) is read off the entry —
and ``SeriesResult.discontinuities`` (``list[SeriesStep]``), the pair each
``SEQUENTIAL_DISCONTINUITY`` names in prose.  Both additive and defaulted to
``None``, the rule of 0.25 → 0.26: a series from before this may have had
an outlier or a flagged step, so an empty default would claim what nobody
checked.  Opened, it reports neither code's new half, which is true — no
fence recorded one.

0.36 → 0.37 (WP-1343): ``Phase.magnetic_lor_size`` and
``Phase.magnetic_lor_strain``, the magnetic component's own extra
Lorentzian size (1/cosθ) and strain (tanθ) broadening in deg 2θ
(``min = 0.0``, softplus, default 0.0, refused non-zero or free on a phase
with no ``magnetic_symmetry``).  Both are exactly off at that default, so
every document written before loads unchanged and no fit's number moves;
what a consumer notices is two new keys in every serialized phase, two new
parameter paths on a phase that declares a magnetic structure, and the
reflection table's new ``component`` column.  WP-1469 took 0.36 first, and
its sibling WP-1329 took 0.38 on top of this.

0.37 → 0.38 (WP-1329): ``SeriesEntry.magnetic``, the moment along a
series — WP-1327's ``MomentEvidence`` rows per pattern of a sequential
refinement.  Before it, a magnetic series handed back a signed
``phases.i.atoms.j.moment.dof0`` row in ``parameters`` and *none* of the
evidence that stops it being misread: ``supported``, the esd the ratio is
against, the direction the powder could not determine, the dipole
approximation in force.  Written by ``sequential._chain`` from the same
``report.magnetic.analyse_moments`` a single-pattern report uses, keyed on
``MomentEvidence.path`` (already stored since WP-1327).  Additive and
defaulted to an empty list, which is the honest empty state and the
bit-identical one: a series whose phases declare no moment serializes
exactly as before apart from that list, and no number any fit produces
moves.  ``MagneticTrajectory``/``MagneticOnset`` are *derived* views over it
and are stored nowhere.  WP-1343 took 0.37 first.

0.38 → 0.39 (issue #599): ``StageResult.moment_flat_axes`` and
``StageResult.moment_turned`` — the flat rotation axis of every three-DOF
moment site whose azimuth a stage held as a flat combination of its two
angles, and which of those sites the stage turned onto the axis's meridian
first.  The record the report's moment note is a projection of (review of
#624, item 2): the turn changes the direction a fit reports, so it ships
with a field stating it.  Additive and defaulted to empty, which is every
fit without such a site; a document written before loads unchanged.

0.39 → 0.40 (WP-1534): ``StageResult.scale_b_held`` — per phase whose
displacement parameters a stage held because the fitted range cannot
separate them from the phase's scale, the column separation measured.
Additive, and defaulted to ``None`` rather than empty, the 0.25 → 0.26 rule:
a stored result from before this may have walked that ridge (issue #204's
did), so an empty default would say "looked, nothing held" of a fit nobody
looked at.  Both single-histogram runners now write a mapping on every
stage; the joint runner does not ask, and leaves ``None``.

0.40 → 0.41 (WP-1323): ``PlanSpec.lebail_passes``, the cap on Le Bail passes.
Additive and defaulted to 1, the single run every earlier plan made; an older
build refuses a document carrying it (``extra="forbid"``), which is the point
of the bump.

0.41 → 0.42 (#788): ``RefinementState.free_declared``, whether a node's
``free_paths`` is a declaration or "nothing declared yet" (the models' own
``vary`` flags then are the free set).  Additive and defaulted to ``False``,
the reading every earlier document had, so an old tree loads unchanged; an
older build refuses a document carrying it (``extra="forbid"``).

0.42 → 0.43 (WP-1805): ``Phase.rigid_bodies``, a list of ``RigidBody``
(template, origin, orientation quaternion) over the phase's own atoms.
Additive and defaulted to empty, which builds exactly the table every
earlier document built; an older build refuses a document carrying a body.

0.43 → 0.44 (WP-1930): ``StageResult.seeded``, each row a stage lifted
before solving and the value it started at, and ``.floor_unseeded``, the
freed rows left on their softplus floor for want of a seed size.  Additive,
and defaulted to ``None``, the 0.25 → 0.26 rule: a stored result from
before this may have freed a row on its floor (issue #832's did), so an
empty default would say "looked, nothing seeded" of a fit nobody looked at.
All three runners write both on every stage.

0.44 → 0.45 (WP-1808): ``RigidBody.torsions``, named-bond torsions inside
a body (axis, declared moved set, the angle record).  Additive and defaulted to
empty, a body without one building exactly the 0.44 table.

0.45 → 0.46 (WP-1938): two fields leave.  ``Parameter.transform`` goes
because every parameter is now refined in its own units, with its bounds
passed to the driver as a box.  A stored or passed ``transform`` is folded
into the bounds it enforced by a ``mode="before"`` validator on
``Parameter`` (:func:`legacy_transform_bounds`): softplus and exp become
``min ≥ 0``, logit also ``max ≤ 1``.  ``StageResult.floor_unseeded`` (0.44)
goes with WP-1930's floor seed, and a before-validator on ``StageResult``
drops a stored one.  Every document written before opens unchanged in
meaning, since the table already built each declared transform as that box.
A document written here carries neither key, and an older build reads it as
all-identity with the same bounds.

0.46 → 0.47 (WP-1931): ``BackgroundSelection.diagnostics``, the findings a
selector carries beside its scan (``BACKGROUND_ORDER_AT_CAP``).  Additive and
defaulted to empty, the reading every earlier selection had.

0.47 → 0.48 (WP-1929): ``ParameterInterval`` and ``ParameterIntervalPoint``
(``schemas/interval.py``), the answer ``Refinement.profile_interval``
returns — the profile-likelihood interval for one refined parameter,
one-sided for a row on its bound.  Additive, the 0.32 → 0.33 shape: no
existing model gains or loses a field, but a new answer type is a new shape
a consumer parses.

0.48 → 0.49 (WP-1929): ``StageResult.moment_angle_tests``, a list of
``MomentAngleTest``, each round of the stationary-angle test the stage's
covariance ran.  Additive and defaulted to ``None``, the 0.25 → 0.26 rule:
a stored result from before ran no test, so an empty list would claim one.
``ParameterInterval.stderr`` becomes ``float | None``: an angle the test
left out of the covariance has a profile interval and no esd.  Every
earlier document opens unchanged; an older build refuses one carrying the
new field, or an interval whose ``stderr`` is ``None``.

0.49 → 0.50 (WP-1809): ``TetherRestraint`` and ``AntiBumpRestraint`` join
the ``Restraint`` union, and ``RestraintRow.kind`` gains ``"tether"`` and
``"anti_bump"``.  Additive: no existing document carries either.

0.50 → 0.51 (WP-1317): ``SeriesResult.relative_paths`` and
``.angle_paths``, the paths a run's models make steps and angles, so a
judgement across patterns made outside the run (``moved_paths``) skips and
wraps what the fences do.  Additive and defaulted to ``None``, "not
recorded", the 0.25 → 0.26 rule; ``SequentialRefinement.fit`` writes both
on every result, the backward chain's included.

0.51 → 0.52 (WP-1912): ``Phase.floating_origin``, ``"hold"`` making the
parameter table hold one coordinate DOF along each direction a polar
group's origin floats in, and ``ParameterRow.origin_axis``, the direction a
row so held fixes.  Additive and defaulted to ``None``: exactly off, the
table every earlier document built.  An older build refuses a document
carrying either key.

0.52 → 0.53 (yue-here/rietx issue #193, the time-of-flight readers and
axis): ``PatternData.two_theta`` becomes ``list[float] | None`` beside a new
``PatternData.tof`` (µs), exactly one of the two set; ``Instrument.source``
gains a third arm, ``TOFSource`` (``kind="neutron_tof"``: DIFC/DIFA/TZERO/
DIFB, the bank angle, ``ProfileTOF`` and ``IncidentSpectrum``).  Not purely additive: a
consumer that read ``two_theta`` as always present must now ask
``PatternData.axis``.  Every stored document loads unchanged — each has a
``two_theta`` — and a 2θ pattern serializes apart from the new nulls, and
refines, exactly as before.  A ``neutron_tof`` source is read and never
refined in this build.

0.53 → 0.54 (WP-1912): ``Phase.floating_origin`` gains ``"centroid"``, the
restraint of Flack & Schwarzenbach (1988) on a weighted centroid of the
phase's sites in place of a hold on one.  Additive: no existing document
carries the value, and an older build refuses one that does.

0.54 → 0.55 (WP-1325): ``RefinementResult.parametric``, a list of
``ParametricCoefficient`` — the coefficients of a joint fit's parametric
declarations, in user units at each declaration's reference — beside the
two declaration models ``CoordinateTable`` and ``ParametricTie``
(``schemas/parametric.py``) the joint path now takes.  Additive and
defaulted to ``None``, "nothing declared", which every earlier result is;
an older build refuses a result carrying the field.

0.55 → 0.56 (WP-1325): ``RefinementResult.parametric_form``, one
``ParametricFormTest`` per parametric declaration — whether the data
rejects the declared form, by a score test at the answer.  Additive and
defaulted to ``None``, as ``parametric`` is; an older build refuses a
result carrying the field.

0.56 → 0.57 (WP-1960): ``Phase.texture``, a ``SphericalHarmonicTexture``
(an even ``order`` and a name → ``Parameter`` map of coefficients), and
``RefinementResult.texture``, one ``PhaseTexture`` per textured phase.
Additive and defaulted to ``None`` and empty, so every stored document
loads and refines as before; an older build refuses either.

0.57 → 0.58 (WP-1810): ``RigidBody.riding``, the body atoms that are riding
hydrogens, and the CIF ``_atom_site_refinement_flags_posn`` /
``_atom_site_calc_flag`` columns a phase with a body now writes.  Additive.

0.58 → 0.59 (WP-1325): ``RefinedParameter.equations``, the parametric
equations whose coefficients set a row; ``ParametricFormTest.n_subset``,
the subset's size beside the patterns tested; ``ParametricFormTest``'s
``dof``/``statistic``/``cut`` moved into two ``ParametricFormReading``s,
``tied`` and ``others_freed``, each with a ``p_value``;
``RefinementResult.parametric_equations``, each equation as resolved with its
coefficients' covariance; ``RefinementResult.parametric_form_joint``, the
form test of every tested equation at once, ``None`` below two.
``ParametricFormTest.rejected`` is the ``others_freed`` reading's verdict
where there is one, and ``ParametricFormTest.provisional_on`` names the
other rejected equations; every reading divides by χ²_red alone.
``equations`` and ``parametric_equations`` default to
``None``, "not recorded", so an older result opens and claims nothing; the
form-test fields are required and the old ones gone, ``parametric_form``
being unreleased.  The declaration model is ``ParametricEquation``, which
1.9.0 called ``ParametricTie`` (no alias), and the field naming it is
``equation`` on ``ParametricCoefficient``, ``ParametricFormTest`` and
``RefinedParametricEquation``; ``ParametricCoefficient`` still reads the
0.55 key ``tie``, so a 1.9.0 result opens and is written back as ``equation``.
``ParametricValue``, built on demand and never stored, carries
``provisional_on`` and ``joint_rejected`` beside ``form_rejected``.

Also in 0.59, one number a release cycle (indexing C4): ``CellCandidate.n_search_unindexed`` and
``.unindexed_two_theta``, the search's acceptance as an output (the inlier
rule replaces the absolute ``n_unindexed`` cap, which a ``SearchSpecSpec``
still accepts as a declared int, its default now ``None``).  Additive and
defaulted to ``None``, "not computed", the 0.25 → 0.26 rule.

Also in 0.59 (WP-2002, B8): ``StageResult.cell_reset``, the free cell
parameters a stage put back at its starting values after their phase's cell
left the safety window.  Additive and defaulted to ``None``, the 0.25 → 0.26
rule; all three runners write a list on every stage.

Also in 0.59 (WP-2002, B14): ``StageResult.collapsed``, the free parameters
a stage restored to its starting values and held after its first solve found
them flat (WP-1301's collapse restore).  Additive and defaulted to ``None``,
the 0.25 → 0.26 rule; all three runners write a list on every stage.  And
``StageResult.seeded`` gains a second writer, ``Stage.strain_seed``'s
Stephens rows, with no change of type.

Also in 0.59 (WP-2002, B2): ``RefinedParameter.interval``, the profile
interval of a moment angle the stationary-angle test left out of the
covariance.  Additive and defaulted to ``None``, "not computed", the
0.25 → 0.26 rule; a single fit writes it on exactly those rows.

Also in 0.59 (WP-2002, B1): ``PlanSpec.phase_support_sigma``, the
absent-phase hold's threshold, defaulting to the 3σ every fit used, so a
stored plan loads and runs as before; ``None`` switches the hold off.  An
older build refuses a plan carrying it.

Also in 0.59 (WP-2002, B4): ``RefinedParameter.stderr_uncorrected``, the
esd without the Bérar-Lelann factor, as GSAS-II and FullProf print it.
Additive and defaulted to ``None``, the 0.25 → 0.26 rule; both fit
builders write it on every row that has an esd.

Also in 0.59 (WP-2002, B1): ``NodeAction.phase_support_sigma`` and
``.correlation_guard``, the two plan settings a stage ran at, so a
cherry-pick replays them.  Additive and defaulted to the 3σ and 0.98 the
package defaulted to before them (a plan's own guard went unrecorded), the
0.4 → 0.5 rule for ``NodeAction.ftol``; both stage runners write them on
every stage node.

Also in 0.59 (WP-2002, the sixth round's Q1 and Q2):
``PlanSpec.closing_window_tol``, the closing stage's window area fraction,
defaulting to 1e-3, so a stored plan gains a closing stage on its next run;
``None`` runs as before.  And ``NodeAction.window_area_tol``, the fraction a
stage ran at, defaulting to ``None`` (the compiler default every earlier
node ran at), the same rule.  And ``StageResult.n_lapack_fallbacks``, the
decompositions a stage repeated with LAPACK's second driver, defaulting to
0, which every earlier stage took.

Also in 0.59 (WP-1958, #954): ``QuantitativePhaseAnalysis.unmeasured_phases``,
the phases with no reflection in the fitted range, and
``PhaseQuantity.weight_fraction`` widened to ``None`` for them, the others
normalised over the phases seen.  Additive and defaulted to the empty list,
the 0.25 → 0.26 rule; an older build refuses a row whose fraction is ``None``.
And ``QuantitativePhaseAnalysis.unmeasured_held`` (which of those a stage held
rather than found lineless) and ``NodeMetrics.held_scale_phases`` (the held
scales a node's replay reads), both defaulting to the empty list.

0.59 → 0.60 (WP-2042): ``RefinementResult.radiation`` and
``HistogramResult.radiation``, the source's kind and line wavelengths a
fit used, which ``result.plot()`` names on its 2θ axis.  Additive and
defaulted to ``None``, "not recorded", the 0.25 → 0.26 rule; both fit
builders write it on every result and every histogram.
0.60, C3 (issue #916), same cycle as the 0.60 above: ``LeBailValidation.predicted_but_absent_uncancellable``,
``.predicted_but_absent_uncancellable_in_window``, ``.absent_source`` and
``.n_lines_screened``,
the line screen's counts beside the one it replaces; ``SupercellCheck.relation``,
whether the parent is a sublattice or only indexes a subset of the lines.
Additive, every new field defaulted to the reading an earlier document had
(``None`` = not counted, ``"fitted_background"``, ``"sublattice"``).

Also in 0.60 (#939): ``ExtinctionScreen.prefit_rwp`` and
``ExtinctionScreen.reference_rwp_net``, the cell-free Le Bail's Rwp and the
reference fit's background-subtracted Rwp, and ``"unreliable"`` as a
``status`` value.  Additive and defaulted to ``None``, the 0.25 → 0.26 rule.

Also in 0.60 (WP-2033): ``ExtinctionPrior.z``, ``.density``, ``.formula`` and
``.ordered``, ``ExtinctionCandidate.exclusion_reasons``, ``.special_positions``
and ``.count_notes``, and ``ExtinctionScreen.z``, ``.z_from_density`` and
``.z_candidates``: the content per cell a caller declares and what the screen
says of it.  Additive, every one defaulted to ``None`` or empty, the 0.25 → 0.26
rule.

Also in 0.60 (WP-2047): ``StageResult.window_loss`` and
``NodeMetrics.window_loss``, the share of the Bragg intensity a stage's
frozen windows dropped at its answer.  Additive and defaulted to ``None``,
"nobody looked", the 0.25 → 0.26 rule; all three runners write it on every
stage, and ``Refinement._record`` on every stage node.

Also in 0.60, one number a release cycle (WP-1809): ``PlanarityRestraint`` joins the ``Restraint``
union, and ``RestraintRow.kind`` gains ``"planarity"``.  Additive: no
existing document carries either, and an older build refuses one that does.

Also in 0.60 (WP-2003): ``SeriesEntry.seeded_from`` and ``SeriesEntry.floored``,
where each warm start came from and which moments reached it at their floor,
additive and defaulted to ``None`` and the empty list; and
``SeriesResult.discontinuities`` replaced by ``SeriesResult.steps``, with
``SeriesStep.size_esd`` and ``.cold_ratio``.  Not additive: the flagged pairs
cannot be rebuilt as every step, so a document's ``discontinuities`` key is
dropped at read (``SeriesResult``'s ``mode="before"`` validator) and its
``steps`` reads ``None``, "not recorded".

Also in 0.60 (WP-2003, C1): ``SeriesEntry.rwp_fence`` replaced by
``SeriesEntry.rwp_over_median``, the kept attempt's Rwp over the accepted
median with no threshold.  Not additive: the factor that scaled the old
limit is not on the entry, so an entry's ``rwp_fence`` key is dropped at
read (``SeriesEntry``'s ``mode="before"`` validator) and its
``rwp_over_median`` reads ``None``, "not recorded".

Also in 0.60 (WP-2003, C6): ``SeriesResult.code_counts``, a
``SeriesCodeCount`` per per-pattern code and path with its count, the
series length and the worst level.  Additive and defaulted to ``None``,
"not recorded", the 0.25 → 0.26 rule; ``SequentialRefinement.fit`` writes
it on every series.  ``SEQUENTIAL_PERSISTENT_FINDING``, the threshold it
replaces, is gone, so a document carrying one still reads.

Also in 0.60 (WP-2003, C5): ``SeriesResult.direction_gaps``, a
``DirectionGap`` per path and pattern under ``direction="both"``.  Additive
and defaulted to ``None``, "not compared"; ``SequentialRefinement.fit``
writes it whenever the two chains were compared.
``SEQUENTIAL_PATH_DEPENDENT`` is gone, and ``SEQUENTIAL_PATH_CHECK_NOT_RUN``
takes the ``warning`` half of ``SEQUENTIAL_PATH_CHECK_INCOMPLETE``; a stored
INCOMPLETE at ``warning`` still reads as not run.

Also in 0.60 (WP-2030): ``IndexingResult.formula`` and ``.temperature``, the
formula and temperature read, and ``PeakList.instrument_undeclared``,
the instrument blocks the picker found at default on a lab source.  Additive
and defaulted to ``None``, "not recorded", the 0.25 → 0.26 rule;
``index_pattern`` writes the first two on every result, ``pick_peaks`` and
``fit_peaks`` the third on every list.  Part 2 added
``CellCandidate.formula_units``, the units a cell holds by Hofmann's
volumes, written by ``index_pattern`` when a formula is given and ``None``
otherwise (additive, the same rule); ``INDEX_Z_NOT_INTEGER``, which judged
that number, is gone, so a document carrying one still reads.

Also in 0.60 (WP-1419 C3a): ``Phase.distortion_modes``, a child stated as
its parent plus absolute mode amplitudes (``DistortionModes``: the parent
group, the transform, the reference metric, one base position per atom and
a ``DistortionMode`` per mode with ``amplitude: Parameter``).  Additive and
defaulted to ``None``, exactly off, the 0.25 → 0.26 rule; written by
``displacive_statement``.  An older build refuses a phase carrying it.

Also in 0.60 (WP-2011): ``LeBailValidation.mode``, additive, its default
``"lebail"`` being what every record written before it ran.

Also in 0.60 (#939's follow-ups): ``ExtinctionScreen.perfect_fit_rwp_net``,
what that Rwp would read for a fit leaving only the noise, √(N/(N+S)).
Additive and defaulted to ``None``, the same rule.

Also in 0.60 (WP-1815): ``GeometryTable.torsions``, a ``GeometryTorsion``
per torsion over bonded chains (four labels, indices and symmetry codes, the
angle in (−180°, 180°] and its two esds), defaulted to ``None``, which an
older table reads as "not listed" (``[]`` is "listed, none found"); and ``TorsionRestraint`` joins the
``Restraint`` union, ``RestraintRow.kind`` gaining ``"torsion"``.  Additive:
no existing document carries either, and an older build refuses one that
does.  ``GeometryRequest`` is an argument and is never stored.

Also in 0.60 (WP-1419 C4a): ``RefinementResult.distortion_totals``, one
``DistortionTotal`` per irrep block of a phase on mode amplitudes (A_τ, its
esd and label, T², ``driving`` (``None`` where the record's parent
operations miss its reference structure), the sign convention, the largest
displacement), additive and defaulted to ``None`` where no phase carries
``distortion_modes``.

Also in 0.60 (#941's follow-ups): ``LeBailValidation.n_lines_screened_in_window``,
``.predicted_but_absent_density_in_window`` and
``.predicted_but_absent_excess_in_window``, the windowed count's density and
its excess over the run's cleanest candidate.  Additive and defaulted to
``None``, the 0.25 → 0.26 rule.

Also in 0.60 (#1263): ``SupercellCheck.p0_power``, the floored chance rate
the power check read, beside a ``p0`` that is now the seen test's own.
Additive and defaulted to ``None``.

Also in 0.60 (WP-1334): ``StageResult.rwp``, the stage's Rwp at its answer on
its own frozen compile, the number ``stage_end`` already emitted.  Additive
and defaulted to ``None``, "a result stored before the field", the 0.25 →
0.26 rule; all three runners write it on every stage.

Also in 0.60 (WP-1334): ``StageResult.termination``, which test ended the
solve, the token ``stage_end`` already emitted; ``slow_descent`` is the LM
driver's new one (``optimize.lm.SLOW_DESCENT_ESD``).  Additive and
defaulted to ``None``, the same rule.

Also in 0.60 (WP-1991, Yue's ruling of 2026-11-01): a ``SeriesResult``'s
paths read one series numbering, matched by phase name and atom label
(``SeriesResult.phase_names``/``.atom_labels``), and
``SeriesEntry.pattern_paths`` names each pattern's own path where it
differs.  Additive and defaulted to ``None``: a document written before the
fields stores each pattern's own paths, and nothing stored the names to
translate them, so it opens as written.

Also in 0.60 (WP-2013): ``HumpComponent.position`` is required of a caller,
where it defaulted to 0.0.  A stored document that omits it still opens, at
that 0.0, through the readers ``migrate.STORED_DOCUMENT_READ_POINTS`` names.

0.60 → 0.61 (WP-1944): ``Phase.extinction`` is ``Parameter | None`` and
defaults to ``None``, "not declared", where it defaulted to a ``Parameter``
at 0.  ``None`` has no table entry, so no plan can free it.  A file written
before 0.61 opens unchanged: its stored block reads as a declaration, and
the structural plan's extinction stage still frees it.  A phase that
declares none now stores ``null``, which 1.11.0 refuses:
``Phase`` raises a ``ValidationError``, and ``Project.open`` stops at
"malformed history record".  So a structure or a ``.rex`` project written
here does not open there.

Also in 0.61 (WP-2030 part 3): ``IndexingControls.formula`` and
``.temperature``, the specimen's formula a project stores for its indexing
run.  Additive and defaulted to ``None``; an older build refuses a document
carrying either key.

Also in 0.61 (WP-1542): ``StageSpec.lebail_tol``, ``NodeAction.lebail_tol``,
``StageResult.lebail_cycles_run`` and ``StageResult.lebail_settled``, all
additive.  ``NodeAction``'s two Le Bail defaults stay at three cycles and no
test, so a stored node reads as what it ran, while ``StageSpec`` moved to
25 000 and 1e-7.  A stored plan naming ``lebail_cycles: 3`` reads that as a
cap: it runs the same three cycles and reports ``LEBAIL_CYCLES_AT_CAP``.

Also in 0.61 (WP-1964, the maintainer's rulings of 2026-11-05):
``ParametricEquation.basis`` gains ``"expression"``, with
``ParametricEquation.expression``, the formula's text, and
``ParametricEquation.target`` may be ``None``, an intermediate a later
formula names.  Additive and defaulted, the 0.25 → 0.26 rule.  And
``Parameter.expr``, which only ever held ``None``, leaves the schema: a
stored ``"expr": null`` is dropped at read (``Parameter``'s ``mode="before"``
validator), so every file written before opens unchanged.  A parameter
written here carries no ``expr`` key, which 1.11 reads as ``None``; a
result or project declaring a formula does not open in 1.11 or earlier.
``PROJECT_FORMAT_VERSION`` does not move: the ``.rex`` layout is unchanged.

Also in 0.61 (WP-2076): ``ExtinctionCandidate.tested_hkl`` and
``.tested_two_theta``, the testable forbidden positions a class was scored
on.  Additive and defaulted to empty, the 0.25 → 0.26 rule; an older build
refuses a screen carrying either key.

Also in 0.61 (WP-2118): ``TieSpec.expression``, a user tie declared as a
formula over named variables (``Refinement.tie(path, expression=...)``).
Additive and defaulted to ``None``, a linear tie, the 0.25 → 0.26 rule; so
every stored tie opens as the linear tie it was.  An older build refuses a
document carrying the key.

Also in 0.61 (WP-1419, C2): ``Phase.parent_cell``, a ``ParentCell`` (the
parent's ``space_group``, the parent → child ``transform``, the parent's
``cell`` and one ``strain`` amplitude per Γ strain the child's group
allows), which makes the child's six cell parameters derived and locked.
Additive and defaulted to ``None``, the 0.25 → 0.26 rule, so every stored
document loads and refines as before; an older build refuses a phase
carrying it.

Also in 0.61 (WP-1952, WP-2002 B5 and B14): ``PatternData.nonpositive_sigma``
(``"exclude"`` or ``"poisson"``, default ``"exclude"``), what a σ ≤ 0
becomes, and ``RefinementResult.sigma_rule`` / ``HistogramResult.sigma_rule``,
a ``SigmaRule`` of three counts.  Additive and defaulted, the 0.25 → 0.26
rule; an older build refuses a document carrying either key.  The default
moves no stored value but moves a fit: a σ ≤ 0 used to weigh about 10⁶ times
its neighbours and now leaves the fit.

0.61 → 0.62 (WP-2107, the maintainer's ruling of 2026-11-19):
``Phase.peak_equations`` and ``Instrument.peak_equations``, lists of
``PeakEquation`` (``target``, ``expression``, ``coefficients``).  Additive and
defaulted to empty, the 0.25 → 0.26 rule, so every stored document loads and
refines as before.  A bump rather than "also in 0.61" because 1.12.0 shipped
0.61: a 1.12 build refuses a phase or instrument carrying the key, and the
version now says why.
