# WP-0602 — Agent JSON surface hardened

Milestone: v0.6 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Agent JSON surface hardened: `agent.refine_json(dict) → dict`, JSON-Schema
  export for tool-calling

## Context pointers

- Every schema already exports JSON Schema (pydantic v2, `extra="forbid"`,
  ±inf-safe serialization) — this WP is the single-call composition and its
  hardening (errors as structured, actionable JSON), not new schema work.
- The MCP server wrapping `refine_json` stays fenced in v2.

## Inherited

From **WP-0508** (flat-plate absorption, landed 2026-07-28) — new surface to
cover, and one enum that is no longer binary.

- **`Geometry.kind` has three values**, not two: `debye_scherrer`,
  `bragg_brentano` and `flat_plate_transmission`. Anything that branches on
  "capillary or flat plate" (JSON schema enums, request validation, the
  worked examples) needs the third, and the two flat kinds behave differently —
  only `bragg_brentano` accepts `surface_roughness`, and the absorption
  expression differs between them.
- **`AbsorptionCorrection` grew four fields** (`method`, `unabsorbed_fraction`,
  `identifiable_fraction`, `intensity_fraction_of_optimal`), and `method` is
  the discriminator a consumer must read before interpreting `mu_r` — it is
  µ·R for a cylinder and µ·t for a plate, deliberately one field because it is
  one dimensionless product, but they are not the same quantity.
- **Two new diagnostic codes**, both flat-plate: `ABSORPTION_THICKNESS_MATTERS`
  (`info`, but it is the one that says a wrong thickness lands partly in the
  ADPs) and `ABSORPTION_PLATE_THICKNESS` (`info`, specimen-preparation advice
  with no bearing on the fit). Their agent-facing semantics are in
  AGENT_PROTOCOL §7's table and §8.12; the JSON surface should not restate
  them, only stay consistent with them.

Four result-surface shapes landed in v0.3 that a single-call JSON API will trip
over. All are real, none are bugs.

From **WP-0303** (anisotropic ADPs): **not all six U^ij components appear in
`result.parameters`.** Symmetry-locked components (U13/U23 on rutile's 4f, say)
never enter θ at all, so a consumer that assumes six entries per anisotropic
atom will `KeyError` on exactly the high-symmetry sites. Report what is there;
do not synthesise zeros.

From **WP-0308** (multi-histogram): `refine_multi` runs **without** the
`RefinementTree` DAG — no history, no per-stage nodes — because a multi-pattern
fingerprint was left as a future seam. So a uniform `refine_json(dict) → dict`
either excludes multi-histogram or returns a fit with no history where the
single-pattern call has one. That asymmetry needs a deliberate answer in the
schema, not an accident. The `RefinementResult` itself still fully serializes.

From **WP-0505** (sequential series, landed 2026-07-28): **there is now a
second top-level result type.** `SeriesResult` (`schemas/sequential.py`) is
what `SequentialRefinement` / `refine_sequential` return, and it is *not* a
`RefinementResult` — it carries per-pattern `SeriesEntry` summaries (statistics,
refined values + esds, QPA, diagnostics, node/tree ids) and deliberately no
curves, so a `refine_json` that only knows how to emit `RefinementResult` cannot
express a series at all. It also brings three diagnostic codes the agent
vocabulary must carry: `SEQUENTIAL_RESEED`, `SEQUENTIAL_DISCONTINUITY`,
`SEQUENTIAL_PATH_DEPENDENT` (semantics in `docs/AGENT_PROTOCOL.md` §9b). One
asymmetry to decide deliberately rather than by accident, the same shape as the
0308 one above: a series produces **one history tree per pattern**, so its
`node_id`/`tree_id` are per entry and there is no single tree id for the run.

From **WP-0307** (March-Dollase): `FitReport.texture` reports a diagnosed
preferred-orientation axis, but **no Layer-2 `ActionKind` was ever added for
it** — the vocabulary is versioned, so 0307 deferred it and no WP has claimed
it since. An agent surface consuming Layer-2 actions is the closest natural
owner; either claim it here or it stays orphaned.

From **WP-0408** (torch backend, landed 2026-07-27) — two surface facts a
single-call JSON API has to get right:

- **`backend` is a name from a registry, not a boolean.** There are four:
  `numpy`, `jax`, `torch`, `torch-mps`. `backend.api._BACKEND_NAMES` is the live
  list and `resolve_backend` is the validator both `Refinement` and
  `MultiHistogramRefinement` now call, raising with the available set. A JSON
  surface should validate through the same call rather than restate a literal
  union that will go stale — the fourth name arrived after the third by two
  days.
- **`Provenance.backend` / `.dtype` are now populated** (they had said
  `"numpy"` / `"float64"` since v0.1 no matter what ran). `dtype` is
  `"float64"` except on Apple GPU, where it is
  `"float64/jacobian:float32"` — the residual and solve are fp64 there too, so
  it is one honest string rather than a dtype per stage. An agent reporting
  reproducibility metadata should surface both; do not parse the string for the
  fp32 substring to decide anything, ask
  `backend.api.backend_dtype_note(name)`.

From **WP-0506** (secondary extinction): **never expose the raw `ext`
coefficient with a fixed bound or plausibility check.** Its scale is
wavelength/cell-dependent (x ∝ (λ/V)²): ~0 for CuKα/LaB6 but ~300 for
0.414 Å/NAC. Judge extinction by its *effect* (x, or the minimum E across
reflections), never by the coefficient — a hard-coded range would be wrong for
half the instruments.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
