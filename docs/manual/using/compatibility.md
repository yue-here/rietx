# Compatibility

This chapter is the 1.x stability position: what a version string tells you,
which parts move most, and how to build something that outlives one interactive
session (a stored result, a parser for the agent envelope, a pipeline pinned to
a version) on a package that is still being reshaped.

## The preview position

1.x is a preview, and anything may change in any release: a name, a shape, a
threshold, an answer, a patch release included. The package is young and its
users are few and close to its development, so it trades stability for speed on
purpose. Holding every surface still would protect almost nothing and slow
everything. Three rules make the preview buildable:

- Pin an exact version. `rietx==1.1.0` in a lockfile is the stability promise.
  An upgrade is a decision, taken after reading what moved. What the preview
  does not offer is an upgrade that is safe unread.
- Any observable change moves a version string. Each data contract below carries
  one, and the rule, stated beside each constant in the source, is one sentence:
  any change a consumer could observe bumps the last component by one, and the
  comment beside the constant says what changed. No safe/minor/breaking
  classification survives, and the only question left is whether you could have
  noticed.
- A change to what an existing value means is always a documented event, even
  when no shape changes. A field that keeps its name and type but answers a
  different question is the least visible break there is, so it is never silent.

The position expires by its own terms. It tightens when the first persistent
archive of `.rex` projects exists, which is a condition rather than a date.
From that point a format change destroys accumulated work instead of a test
fixture. The version strings, their bump records and the documented-surface
partition below are kept current, so tightening is a decision and not a
rebuild.

## The six version strings

A moved version string means something you could observe changed, and the
comment beside the constant says what. Those comments are the changelog. Each
constant carries its own bump history (what moved, in which change, and why) and
no separate file restates it. Promoting that record to a hosted page
is part of tightening the promise, when there are users to face it. The strings
are the six contracts `capabilities()` reports, tabulated in [](agents.md);
`Capabilities.report_thresholds_version` and
`Capabilities.indexing_thresholds_version` share a bullet below because they
answer the same kind of question:

- The schemas (`Capabilities.schema_version`), the pydantic models everything
  else rides on: structure, pattern, instrument, plan, result, history node,
  project document. Version 0.12 is the first entry on that ladder to remove
  something rather than add. The JSON envelope and its request union went with
  the `agent` module in 1.3, and the answer types it wrapped are unchanged.
- The `.rex` project directory (`Capabilities.project_format_version`).
- The `.rxt` text document (`Capabilities.textdoc_format_version`), which is
  provisional for a different reason; see below.
- The streaming event ladder (`Capabilities.event_schema_version`). An event's
  `data` dict is declared open on both sides, so a new key in it is the contract
  working rather than a change to it. A new event kind bumps.
- The report gates and thresholds (`Capabilities.report_thresholds_version`) and
  the indexing gates (`Capabilities.indexing_thresholds_version`).

Two vocabularies carry no version string because they are open by design: the
diagnostic and guard codes. A new code may appear in any release, and an
existing code keeps its meaning. Branch on the codes you know, and pass through
the ones you do not.

## The Python surface

Every public name is documented, and none is frozen. The public call surface
(every function, class, method and field a caller can reach) is derived from the
live package rather than hand-listed, so a new public name cannot slip past it.
It fails the build until its chapter documents it, it is deferred with the
chapter still to come, or it is excluded with a written reason. That partition
gates coverage and says nothing about stability. "Documented" means the manual
describes the name as it works in this release, and a documented name may still
change in the next one, with the release notes saying so.

Everything else is internal. Anything importable outside the derived surface is
internal and may change without notice. A chapter that spells an internal helper
fully qualified (`rietx.viz.compare.run` and `rietx.viz.html.write_html` are the
standing examples) is pointing you at something that works, and promoting
nothing.

(provisional-by-declaration)=

## Provisional by declaration

Even in a preview, some parts move more than others, and the ones expected
to move are declared rather than left to be inferred:

- The GUI's HTTP routes. The application itself is documented in
  [](gui-quickstart.md), [](gui-guide.md) and [](gui-power.md), and stopped
  being a beta feature when those landed; its wire surface did not. A route may
  be added, renamed or split in any release, and the route table in
  [](gui-power.md) describes the one this release serves. Two things about the
  wire are nevertheless stated normatively below: the JSON dialect, and that
  the upload routes carry raw bytes. The `.rxt` document is the part of that
  surface that does carry a version, and it is the next entry.
- The `.rxt` text document. It is rendered in-session and never persisted, so
  nothing accumulates in it. If it ever becomes a saveable
  file, its `Capabilities.textdoc_format_version` starts moving.
- A series is session-scoped. `refine_sequential` returns its result and
  writes one history tree per pattern, but the series itself is not a saved
  document.
- Indexing is provisional as a subsystem. `pick_peaks`, `index_pattern`
  and `determine_extinction_symbol`, the answer types they return
  (`rietx.schemas.indexing`), and the helpers under `rietx.indexing` that the
  agent protocol's worked loop calls are documented in [](indexing.md) and
  are the names in the package most likely to change: the engines, the gates
  and the figures of merit are still being measured against real data. 1.0.2 is
  what that looks like: `determine_extinction_symbol` stopped refuting an
  extinction class on a neighbouring peak's tail, so its answer moved in a patch
  release. Every such change is announced in the release notes, and the
  data contracts keep their own version strings
  (`Capabilities.indexing_thresholds_version`, and the engine and search-preset
  capability types), so a consumer that parses an answer sees a bump when the
  answer's shape or meaning moves.
- `rietx.viz.render_structure` ([](exports.md)). It draws what the GUI's
  structure viewer draws, so its look and its keywords move when the viewer's
  do.
- The run directory and the watcher's routes. Every fit writes a run directory
  ([](refining.md)) and `rietx watch` serves it over seven HTTP routes
  ([](cli.md)). Neither carries a version string, and the omission is a decision
  rather than an oversight. A run directory is a contract between two processes,
  which is the argument for versioning it. Against it: nothing negotiates over
  the layout yet, and a contract nothing has exercised is an untested guess, so
  a version string on it would promise more than has been checked. It gets one
  when the layout has survived a release. Until then a file may be added,
  renamed or dropped from a run, and a route may be added, renamed or split, in
  any release. What is stable in the meantime is the reader's side: a directory
  holding an `events.jsonl` is a run, a run that predates a field is read rather
  than refused, and an unknown key in one of the JSON sidecars is ignored.
- Magnetic structure *determination* is provisional as a subsystem.
  `solve_magnetic` and the answer it returns (`rietx.strategy.magnetic`:
  `MagneticSolution`, `MagneticTrial`, `MomentRow`) are documented in
  [](refining.md). The *chain* is settled (a propagation vector, candidate
  models per k, one trial refinement per powder-equivalence class, a ranked
  list with an abstention) and the criterion is not: it is a ΔBIC
  ordering with a magnetic-only R and parsimony behind it, and the rungs still
  to come change what a trial refines (mode amplitudes) and add a branch this
  release abstains on (an incommensurate k). Expect the fields to grow and the
  ranking to be restated; the operator list, the moments and the magCIF a
  solution writes are the stable part and carry the promises their own
  chapters make.
- The satellite test and the moment along a series are provisional too, and
  are named here because their modules also hold stable types.
  `SatelliteEvidence` and the `SatelliteCandidate` rows it ranks
  (`FitReport.satellites`) answer from a fixed set of zone-boundary vectors.
  The generator still to come changes what is ranked and what a candidate
  carries. `MagneticTrajectory` and the `MagneticOnset` it carries were
  measured on a synthetic ramp and one two-pattern pair, and the rule that
  folds two chains' brackets has already changed once. The builder for a
  k ≠ 0 supercell, `magnetic_supercell`, and the P1 restatement of a magnetic
  phase or structure, `restate_phase_in_p1` and `restate_in_p1`, are not
  exported at the top level and may change in any release.
- Rigid bodies are provisional, and are named here because their types live in
  `rietx.schemas.structure` beside stable ones. `RigidBody`, `BodyOrigin`,
  the phase field that holds them, the parameter row's field that names a
  row's body, and the builders in
  `rietx.crystallography.bodies` shipped in 1.7.0 as the first piece of a
  milestone that is still open. Torsions inside a body, riding hydrogens and a
  fragment library are still to come, and each may add fields or change what
  a body refines. A document that carries a body needs schema 0.43, and a build
  older than 1.7.0 refuses it.
- The foreign-refinement readers are provisional as a subsystem.
  `read_project_model`, `identify_project_format`, `read_topas_inp`,
  `read_fullprof_pcr`, `read_gsas_exp` and the per-format models they answer
  with (`rietx.io.projects`) are documented in [](files.md) and are expected to
  move: the registry over them has three formats and two more queued, each of
  which is evidence about the shape it should have, and the write direction is
  not written at all. The third format is already why `ProjectFormat.reports_at`
  has a `"both"` value it did not have when it shipped. A format's own model mirrors that format, so
  its fields move when the reader's coverage does. What a reader refuses is the
  stable part: a construct this package cannot represent raises naming the file,
  in this release and in the next.

## The JSON the package writes

Two facts about the wire are normative even where the routes above are not:

- Non-finite floats serialise as the strings `"Infinity"`, `"-Infinity"` and
  `"NaN"`, everywhere the package writes JSON. A parameter bound of ±inf
  survives a round-trip, and a consumer's JSON parser must expect the string
  form.
- The upload routes carry raw bytes rather than JSON. A pattern file's bytes are
  the contract: the file is stored byte for byte, and the reader that claimed it
  is recorded beside it, so no upload is wrapped, encoded or re-serialised.

## The name and the formats are separate promises

The brand tokens (the distribution name, the state directory, the server's own
short name) track the distribution, and would move together if the package were
ever renamed. The format tokens (the `.rex` suffix, the `rxt` header word, the
instrument-profile tag) name versioned contracts, and do not move because a
brand did. A future rename is therefore no format break. A project written
today opens under whatever the package is called when you open it.

## The kernel wheel has its own version

The compiled kernels ship as a second package, `rietx-kernels`, with its own
version ({ref}`the-compiled-kernels`). Its major version is the kernel
interface rietx calls, and rietx pins that major: `rietx-kernels>=1,<2`. A new
major is an interface break, and it arrives with a rietx release that moves the
pin. A new kernel is a minor release, and the rietx release that first calls it
raises the floor.

The move from `numba` to the wheel changed no number a fit returns. The Rust
kernels match the `numba` ones bit for bit on all five platforms the wheel
ships for. Two things you could observe did change. `numba` is no longer
installed with rietx. An install without the kernels now warns once per
process, where an install without `numba` ran the numpy path in silence.

## What a default promises

One principle decides defaults, and it explains why the same content can
default differently on two surfaces. A library primitive is cheap, and a
delivery surface is complete. `Refinement.fit` is called in loops (suites,
series, parameter sweeps), so anything that costs a multiple of the fit is
opt-in there (`stage_reports=True`). A surface read once per fit by a consumer
that was not watching carries the complete story by default instead: the GUI's
report route builds Layers 1-2 without being asked, and the JSON envelope did
the same until 1.3 retired it. A future addition lands under the same rule, on
whichever side its cost puts it.
