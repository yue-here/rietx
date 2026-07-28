# pxrd-refine — Roadmap

Canonical milestone **index**. The content that used to live here is split so
a work session loads only what it needs:

- **[AGENT_PROTOCOL.md](AGENT_PROTOCOL.md)** — how to *use* the package as an
  automated operator: turn-on order, degeneracies, abstention handling,
  diagnostic-code semantics, and the measured findings that change agent
  behaviour. Written for consumers, not maintainers; a WP that adds a
  diagnostic code or a correction should add its row there.
- **[DESIGN.md](DESIGN.md)** — the design record (rationale, locked decisions,
  invariants). Stable; read the specific section a work package links.
- **[milestones/](milestones/)** — shipped-milestone records with the measured
  acceptance blocks (`v0.1.md`, `v0.2.md`, …).
- **[wp/](wp/)** — one self-contained **work package (WP)** per task. Each has
  its own context, commit-sized checklist, acceptance command, and handover
  log. `wp/TEMPLATE.md` defines the format.

## Session protocol

1. **Start** from "Current focus" below (or the WP the user names). Read that
   one WP file — it is self-contained on top of CLAUDE.md. Open DESIGN.md only
   at sections the WP links; do not read other WP files.
2. **During**: land tasks as small commits prefixed with the WP id
   (`WP-0301: …`); check items off in the WP file as they land.
3. **End** — or whenever interruption is a risk: append a dated entry to the
   WP's handover log (done / in flight / next / gotchas), update its Status
   line, and mirror the glyph in the WP index row below.
3b. **Push forward-references downstream.** If this session learned anything
   that changes work in a *not-yet-started* WP — a constant now exported for
   reuse, a design bullet there that has gone stale, a deferral into it, a
   gotcha that would mislead it — edit **that WP's `### Inherited` section**
   (see `wp/TEMPLATE.md`) and name this WP as the source. Step 1 forbids
   reading other WP files, so **a handover log is not a channel to anyone but
   your own successor on the same WP**: a "next WP should…" note left only in
   your own log, or only in "Current focus" below, will never be read. Current
   focus is a rolling narrative and gets rewritten when the next WP lands.
4. **Milestone ships**: record the measured acceptance block in
   `milestones/vX.Y.md`, flip the milestone row here, and check the roadmap
   claims in README.md.

*Step 3b was added 2026-07-24 and applied retroactively the same day: the
handover logs of all 14 then-landed WPs were swept for forward-references and
the results written into 16 downstream WPs' `### Inherited` sections. That
backlog is cleared — new sessions only need to keep up with their own.*

## Current focus

**v0.5 shipped 2026-07-28** — all eight WPs (0501–0508) landed; measured
acceptance in [milestones/v0.5.md](milestones/v0.5.md). The headline is the
milestone's own method result rather than any single correction: **not one of
the eight is well judged by Δ Rwp.** Two provably cannot move it (capillary
absorption moves Rwp by 3e-8 on real data while shifting every Biso by exactly
the predicted 0.0166542 Å²), one moves it the *wrong way* when it is right (a
flat-plate thickness declared on a thick specimen — which is how you learn the
specimen was not thin), three move it while changing nothing quotable, and the
two largest accuracy wins — dispersion taking round-robin QPA from RMS 2.26 to
0.69 wt %, and absorption unbiasing ADPs by up to 1.5 Å² — are invisible in it.
That is why each correction ships with a record field or a diagnostic that says
what it did, and why AGENT_PROTOCOL leads with it.

WP-0508 closed the milestone by answering the two questions it was blocked on
with measurements rather than assumptions: the capillary dataset exists (11-BM's
SRM 660a LaB₆, in the beamline's documented 0.81 mm Kapton bore, µR ≈ 0.5–0.7),
and flat-plate µt is *not* the exactly-singular direction µR is — it keeps
3–47 % of its signature — so it is held fixed on stated grounds rather than on
an identity, with the number reported so a caller can disagree.

**Next: v0.6 — solver, performance & agents.** Nothing blocks it. The obvious
first row is **[0605](wp/0605-batched-peak-loop.md)**, which behaves like a v0.5
row: its ≈2.4× lands on the **default numpy path** and needs no optional
dependency; it was found in 0408 rather than belonging where it sits. Then
[0601](wp/0601-bounded-lm-solver.md) (a bounded LM, which 0503 wants for the
Stephens positivity cone and 0508 would let revisit whether µt is refinable),
[0602](wp/0602-agent-json-surface.md) (the agent JSON surface, now with a
consumer-facing protocol document to be faithful to) and
[0604](wp/0604-theory-manual.md).

<details>
<summary>How v0.5 got here — the per-WP narrative (superseded by the record)</summary>

**v0.4 shipped 2026-07-27** — all eight WPs (0401–0408) landed; measured
acceptance in [milestones/v0.4.md](milestones/v0.4.md). The headline is
deliberately two-sided: every backend computes the same Jacobian (and an
all-fp32 Apple-GPU refinement lands 3.5e-8 Å from numpy fp64, confirming the
fp64-host-boundary invariant on real hardware), while device *acceleration* was
measured not to exist at this problem size.

Signed off with the duplication closed rather than documented: the residual row
layout now lives once in `model/rows.py`, the traced residual once in
`backend/traced.py`, and `tests/test_backend_conformance.py` is driven by the
backend **registry**, so a new backend inherits every rule and cannot ship
without its agreement rows. `[torch]` is marked **experimental** — an
independent opinion in the matrix and a route to differentiable-layer use, not
a faster path. What being differentiable could buy later (posterior sampling,
Poisson likelihoods, exact Hessians, the model as a torch layer) is recorded in
[DESIGN.md](DESIGN.md#what-the-differentiable-core-unlocks-deferred-not-planned)
— deferred, not planned.

**Now: v0.5 — corrections & microstructure.** Four rows landed 2026-07-27 in
parallel and were merged: [0501](wp/0501-absorption-corrections.md) (capillary
absorption), [0502](wp/0502-surface-roughness.md) (surface roughness),
[0503](wp/0503-stephens-anisotropic-strain.md) (Stephens anisotropic strain) and
[0504](wp/0504-anomalous-scattering-xraydb.md) (anomalous f′/f″) — the last two
taken out of order; each has its own note below. They are orthogonal in the peak
chain — 0501 and 0502 act on intensity in geometries that exclude each other
(capillary vs flat-plate), 0504 on |F|², 0503 on widths — which is why the
merges were clean. [0505](wp/0505-sequential-refinement.md) (sequential warm
start) landed 2026-07-28 — see its note below.
[0507](wp/0507-anode-wavelengths.md) (anode wavelengths) landed 2026-07-28 —
see its note below. [0508](wp/0508-flat-plate-absorption.md) closed the
milestone the same day: it was a stub needing a capillary dataset the repo did
not have, and the dataset turned out to exist (11-BM's SRM 660a LaB₆, in the
beamline's documented 0.81 mm bore).

**[0507](wp/0507-anode-wavelengths.md) (anode wavelengths) landed 2026-07-28.**
Five anodes joined `CuKa` — Cr, Fe, Co, Mo, Ag, each also as a Kα1-only variant
for an incident-side-monochromated beam. Nominally a data-table extension, and
the table itself is four lines; the work was in the two questions around it.

*Which scale.* All six come from one column of one evaluation — the NIST X-ray
Transition Energies Database (SRD 128), direct-experimental KL3/KL2 — and the
argument for trusting it is internal rather than bibliographic: **that column's
Cu pair is bit-identical to the `CuKa` values shipped since v0.2**, so the
existing entry is unchanged and doubles as the proof the new rows share its
scale. A test asserts it, including the negative half (≠ Bearden's 1.540562).
The textbook alternative, Bearden 1967, differs by 24–26 ppm at Mo/Ag; taking
one anode from it while Cu stays Hölzer is exactly the ~100 ppm cell error the
WP existed to avoid, so "correcting" a row toward the familiar numbers is a
regression, not a fix.

*What silently assumed Cu.* Two things, both found by scoping rather than by a
test failing:

- `background.diagnostics._contamination_flags` returned `[]` for any wavelength
  more than 0.01 Å from Cu Kα1 — so every anode this WP enables would have
  reported `contamination == []`, which reads as *clean* rather than *not
  checked*. It is now per anode (`identify_anode`, exported), with Kβ from the
  same database column. The two ghosts are looked up differently because they
  are different physics: Kβ comes off the target, W Lα1 off the **filament**,
  so W is checked for every anode and Kβ only for a recognised one.
- The `26.6°` graphite monochromator angle in the `bragg_brentano` docstring is
  a *Cu* number, not a property of the crystal — the same graphite sits at 12.1°
  at Mo Kα, where the polarization constant K is 0.511 rather than 0.500.

One finding worth carrying forward: **the one-|F|²-per-source assumption is
weaker off Cu, and measurably so.** The Kα1/Kα2 gap grows from 20 eV at Cu to
173 eV at Ag, and a census over Z = 3–98 × six anodes finds `dispersion.resolve`
refusing 7 of 576 combinations — nothing at all at Cr and Fe Kα (9 and 13 eV
apart, no edge fits between the lines), and at Ag one specimen someone will
actually mount: **Ru, K edge 22.14 keV, right between the lines**. The census is
pinned as a test so a table or tolerance change has to restate it. Relatedly,
`DISPERSION_NEGLECTED`'s severity is anode-dependent — hematite is a `warning`
at Co Kα (180 eV below the Fe K edge, f′ = −3.3 e) and an `info` at Mo Kα
(f′ = +0.3 e). Both are now in AGENT_PROTOCOL §8.11.

**[0505](wp/0505-sequential-refinement.md) (sequential series) landed
2026-07-28** (890 tests green). `SequentialRefinement` / `refine_sequential`
chains N refinements over an ordered series, each warm-started from its
predecessor, and returns a `SeriesResult` of per-pattern summaries plus
parameter *trajectories* — state, not curves, the same rule the history nodes
follow. Distinct from `multi.py` throughout: nothing is shared, only the
starting point crosses a pattern boundary. One history tree per pattern (a tree
is pinned to its pattern by `TreeHeader.data_fingerprint`, and that check is
what stops a node being replayed against the wrong data), chained by annotation
notes rather than parent edges.

The measured results changed two defaults and refuted one design assumption.
On the eight round-robin sample-1 mixtures, under the v0.3 QPA protocol
imported wholesale so only the *chaining* differs: **2863 iterations unchained,
1623 re-walking the staged plan warm, 904 with the plan collapsed into one
stage** — at identical mean Rwp (0.1278) and QPA accuracy identical to the v0.3
independent-fit record (RMS |ΔW| 2.26 wt %, worst 5.13). So `refit="single"` is
the default: the staged turn-on order exists to keep early stages conditioned
from a *poor* starting model, and a converged neighbour is not one. And the
`carry`-glob hypothesis — that chaining a phase scale across a 1 → 94 wt % swing
would be worse than starting cold — **is false**: carrying everything costs 838
iterations against 904 for a carry that excludes the scales and re-seeds them
per pattern. `carry` stays as a control for parameters that must provably not
be chained, not as tuning; the docstring says so rather than the reverse.

Three findings worth carrying forward:

- **A sequential trajectory is path-dependent by construction, and a smooth
  curve is exactly what a poisoned chain produces.** `direction="both"` runs
  the series each way and reports `SEQUENTIAL_PATH_DEPENDENT` per parameter —
  the only check that separates a measured trajectory from an ordering
  artefact, and the one to run on anything publishable.
- **Ratio-based fences need a noise floor, and the σ leg cannot supply it.** A
  softplus coefficient dying on its floor has dp/du → 0, so its esd collapses
  *alongside* its value and the significance test inverts instead of
  protecting: an unrefinable `instrument.profile.y` came back with a median
  step of 4e-16, one step of 1.3e-11 (29 000× the median) and σ ≈ 4e-55, and
  the two chains "disagreed" at 1e16 σ over 1e-60 vs 1e-74. Both fences now
  also require the step to be 1e-9 of the parameter's own magnitude. Any future
  trajectory- or ratio-shaped statistic wants the same guard.
- **The reseed fence never fired on the hostile series.** The collapsed refit
  recovers a bad warm start *within* the fit, so the cold restart is insurance
  rather than a routine mechanism — which is why its mechanics are pinned by
  unit tests rather than by the acceptance suite.

**0502 (surface roughness)** is the flat-plate counterpart to 0501, and lands
the same shape: an opt-in `Geometry.surface_roughness` block with two published
models behind a `kind` seam (Suortti 1972, Pitschke 1993), exactly the identity
when off, folded into all three intensity assemblies so the analytic
dof/adp/March columns cannot drift from FD. Both models were verified against
primary sources *before* coding, which killed two of the WP's own draft claims:
Pitschke's P₀ is dropped (angle-independent ⇒ exactly degenerate with the phase
scale, and the paper never resolved it either), and Suortti's `b` turned out to
be **bimodal** — both b → 0 and b → ∞ are the identity — so its bound, stage
seed and fence come from measured sensitivity rather than convention.

Three findings worth carrying forward:

- **A multiplicative correction is trivially ~0.96 "scale-like".** The first
  roughness↔ADP guard scored that regardless of the data — a guard that always
  fires. `optimize.statistics.block_projection_r2` therefore takes a
  **nuisance** argument: project the scale and background out of the whole
  Jacobian first and read the *partial* R². Measured, that tracks
  identifiability properly (R²(b) = 0.06 → 0.95 as the low-angle reflections
  leave the fitted range), and `ROUGHNESS_ABSORPTION_GUARD = 0.9` sits in the
  gap. Any future intensity correction wants the same treatment.
- **Judge a correction at the reflections, not on the fitted grid.** Real data
  forced this: the IUCr round-robin patterns start at 5° 2θ but their first
  reflections are at 25–32°, and a grid-based fence cheerfully reported a 27 %
  depression no modelled peak ever saw.
- **No dataset in the repo can constrain a low-angle intensity correction** —
  qarr phases first reflect at 25.6/28.3/31.8°, SRM 660c at 21.4°. So 0502's
  real-data result is a *negative* one and it is the fences that are accepted:
  two of three qarr phases collapse to the identity and raise
  `ROUGHNESS_UNCONSTRAINED`, the third slides along the roughness↔Biso
  degenerate direction for 0.0001 in Rwp with ρ(a,b) = +1.000. Roughness is
  therefore **not** a competing explanation for the sample-1 QPA bias, and 0502
  left that shape test alone. WP-0504 later found what *is* the explanation
  (neglected anomalous scattering) and renamed it
  `test_sample1_bias_has_the_dispersion_shape` — 0502's negative result is what
  makes that attribution clean instead of one of two candidates.

0501 narrowed its own scope on evidence. Cylindrical only: flat-plate reflection
off a thick specimen is *exactly* angle-independent (ITC Table 6.3.3.1(1a),
A = 1/2µ) and hence not degenerate with the phase scale but **identical** to it,
so the transmission cases and a real-data capillary acceptance both went to a new
[0508](wp/0508-flat-plate-absorption.md). It implements Rouse et al. (1970) A26
682 eq. (2) rather than the Lobanov fit GSAS-II and TOPAS use, because Lobanov's
coefficients trace only to a conference abstract nobody can obtain.

Two findings worth carrying forward:

- **The correction cannot improve the fit, and that is the point.** Rouse's
  expression factors *exactly* into a constant × exp(c·sin²θ) — a Debye-Waller
  shape — so applying it is an exact reparameterisation of the phase scale and
  the displacement parameters. Rwp is provably unchanged (measured: identical to
  1e-5 percentage points). Its entire content is that a Biso refined without it
  comes back low by **0.489 Å² at µR = 1** (Cu Kα), recovered to four decimals at
  18.8σ. So µR is computed and held fixed, never refined — it is an *exactly
  singular* direction, not a correlated one — and `RefinementResult.absorption`
  reports the bias, because no fit statistic can. That is the WP-0310
  transparency lesson applied before the fact rather than after.
- **Validate a two-argument fit across both arguments.** The available scan of
  Rouse prints b₂ as "−0·0375" when it is −0·3750. That error passes a check
  against the paper's *own* four-decimal table at 0.0015, because the slice used
  (sin²θ = 0) constrains only a₁ and a₂ — and it is 0.0821 wrong at µR = 1. What
  caught it was a quadrature of the exact ITC eq. (6.3.3.4) integral, which
  shares no constant with any published fit. The general form of the lesson is
  in [DESIGN.md](DESIGN.md#absorption-a-correction-that-cannot-improve-the-fit):
  the strongest anchor is the integral a fit approximates, not another code's
  transcription of the same fit.

### Repo-wide audit, 2026-07-28

Not a WP — a sweep for doc/code drift and physics errors across the whole tree,
run at the user's request alongside two new deliverables. What it changed:

- **A real bug, root-caused and fixed.** `np.linalg.pinv` was taking its general
  SVD path on JᵀJ, losing symmetry on the cond ≈ 10²⁰ normal matrices this
  package routinely forms and emitting |ρ| up to 1.6 × 10³ (WP-0502 had logged
  the symptom on the fluorite fit as "worth its own fix"). `hermitian=True` on a
  symmetrised matrix caps it at 1 + 4 ulp. Correlation reporting — and therefore
  the 0.98 guard both 0501 and 0502 lean on — is trustworthy again.
- **WP-0501's b₂ question is settled**, without needing a clean copy of the
  paper: an independently written quadrature of ITC (6.3.3.4) reproduces
  Rouse's own 0.0035 bound with −0.3750 (0.0820 with −0.0375), and the sphere
  coefficients from the same table make the transposition visible without any
  computation (see that WP's "Open for review"). One of the three open items is
  therefore closed; the other two remain judgement calls.
- **Two new deliverables.** [AGENT_PROTOCOL.md](AGENT_PROTOCOL.md) — the
  consumer-facing protocol for driving this package from an agent — and
  `pxrdref compare`, a browser UI comparing refinement settings on the bundled
  standards (`viz/compare.py` + `compare_app.py`, tested in
  `tests/test_compare_ui.py`, whose anti-drift test pins its protocols to the
  acceptance suites').
- **Stale docs corrected**: test counts (835 / 775, ~17 min / ~2.5 min),
  `pyproject.version` 0.2.0.dev0 → 0.5.0.dev0 (it is stamped into every result's
  provenance), README's status header and its missing roughness/extinction rows,
  `symmetry.py`'s now-wrong claim that Friedel merging depends on there being no
  anomalous scattering, and WP-0501's "µR > 1 … not extrapolated" bullet, which
  contradicted both the code and its own "Open for review" item.

The physics itself was checked module by module against its cited sources and
**no errors were found**: FCJ's cos 2φ relation and ξ_max cap, the TCH and Voigt
closed-form partials, the Friedel-average ⟨|F|²⟩ = |A|² + |B|² identity, the
Stephens Λ = (180/π)·10⁻⁶·d²√(ΣS·mono) chain, Sabine's branches, Brindley's τ
series, and the Rouse ΔB = c·λ²/2 bias all reproduce independently.

**0501 left three things open for review** (one now closed above), listed with
what would settle each in
[its "Open for review" section](wp/0501-absorption-corrections.md#open-for-review):
the b₂ coefficient contradicts the printed source (a clean copy of the paper
settles it); µR > 1 is used-but-warned rather than refused, which is a judgement
call and not an obvious one, since LaB6 at Cu Kα in a 0.5 mm capillary is µR ≈ 34;
and the milestone criterion above was weakened on purpose because no capillary
dataset exists in the repo. None blocks further work.

Two live forward notes survive v0.4:

- **[0605](wp/0605-batched-peak-loop.md) is a v0.6 row that behaves like a v0.5
  one.** Its ≈2.4× lands on the **default numpy path** and needs no optional
  dependency; it was found in 0408 rather than belonging where it sits. Pulling
  it forward the way 0408 was pulled forward is the obvious move if anyone wants
  a broad win before more physics.
- **Device acceleration is a scale story, not a backend story** (see the v2+
  note at the bottom): break-even ≈50-65 k elements per kernel, ceiling ≈2.5-3×,
  and one pattern is below break-even even after batching. Do not re-open it as
  a backend question.

<details>
<summary>How v0.4 got here — the per-WP narrative (superseded by the record)</summary>

The backend op shim [0401](wp/0401-backend-op-shim.md) **landed 2026-07-24**
(363 tests green, bit-identity goldens in `tests/test_backend_shim.py`): the
hot path speaks `xp.*` and the residual purity refactors (functional
intensity threading, unconditional off-value evaluation, `where`-masked
guards) are in.  The jax backend [0402](wp/0402-jax-backend.md) **landed
2026-07-24**: `backend="jax"` dispatches a scoped-x64, jit-compiled chunked
jacfwd Jacobian (numpy residual/solve untouched); jacfwd matches
analytic/FD on every family and SRM 660c end-to-end matches the numpy `a`
within 1e-6 Å.  The mixed-precision policy
[0403](wp/0403-cuda-mixed-precision.md) **landed 2026-07-24** (388 tests
green): `backend/linalg64.py` is now the single fp64 host boundary —
`MixedPrecisionPolicy` makes an fp32 residual or solve *unspellable*, and
`cast_columns` hooks in at `_jacobian_for`, the exit point every backend
shares.  SRM 660c under simulated fp32 columns moves `a` by 2.6e-11 Å and Rwp
by 1.1e-13; read that margin as proof of *plumbing*, not of device numerics
(the CPU round-trip captures fp32 representation loss only).  The agreement CI
[0404](wp/0404-cross-backend-jacobian-ci.md) **landed 2026-07-24** (434 tests
green):
`tests/test_cross_backend.py` runs (analytic | central FD | jax | torch |
fp32-policy) × (18 analytic families, Le Bail, Pawley, aniso/PO/extinction,
srm660c, nac) plus the stacked multi-histogram layout and three stage-boundary
plans — every fp64 method inside 8.8e-4 off the documented FCJ S/L == H/L kink,
and the frozen state proved bit-identical across each solve.  Every backend row
self-skips without its package, so the same command is green on a numpy-only
checkout.

Three backend-independent WPs landed 2026-07-24.  Restraint penalty rows
[0406](wp/0406-restraint-penalty-rows.md): bond/angle/value soft restraints as
√w·(computed−target)/σ rows below the data (in JᵀJ, out of Rwp/DW/Bérar-Lelann),
with the analytic nonlinear row-Jacobian chained through the affine constraint
block, a `RestraintReport` + `RESTRAINT_TENSION` diagnostic, and a 6th backend
golden (`toy_restraints`); Rietveld- and single-histogram-only (multi-histogram
deferred — see WP-0308 `### Inherited`).  True Voigt
[0405](wp/0405-faddeeva-voigt.md): `Instrument.profile.shape="voigt"` selects an
opt-in Gaussian⊗Lorentzian peak built on one backend-agnostic Weideman-N=32
Faddeeva `w(z)` (no per-backend `wofz`); TCHZ stays the default, the U,V,W,X,Y
widths and FCJ are shared, and numpy↔jax agree to 1e-16 on `w(z)`.  esd
reconciliation [0407](wp/0407-esd-reconciliation.md): the Bérar-Lelann placement
bug is fixed — reported physical esds now genuinely carry the inflation the
docstrings claim (SRM 660c `a`-esd 2.49e-5 = raw 7.4e-6 × BL 3.38), the returned
correlation matrix is a true Pearson matrix (unit diagonal), and the 0.98
high-correlation guard is live again (it fires on collinear zero-shift ~
sample-displacement); it un-masked two unit tests that had ridden the bug
(extinction↔scale is a genuine ρ≈0.97 degeneracy, not separable; aniso U11/U33
separate at ≈2.2σ against honest esds) — reconciled to the true physics, not
silenced.

The torch backend [0408](wp/0408-torch-mps-backend.md) **landed 2026-07-27**,
and it split into a win and a finding.  *Win:* `backend="torch"` is an
independent fp64 row of the agreement matrix on every config, and
`backend="torch-mps"` gives the **first real-hardware confirmation of WP-0403's
fp32-column policy** — an SRM 676a refinement with the whole peak chain and every
column computed in fp32 on the Apple GPU lands 3.5e-8 Å from the numpy fp64
cell, because the trust region re-measures each step against an fp64 cost.
*Finding:* **MPS is 60-125× slower than numpy** (re-measured for the milestone
record at 46-182×, depending on pattern and quantity)
(`examples/bench_torch_mps.py`), and not for a precision or backend-quality
reason — the residual walks ~130 frozen windows of 200-900 points one at a time
in python, and MPS per-op cost is flat at 110-165 µs from 64 to 65 536 elements,
i.e. pure launch latency.  The obvious remedy was then measured rather than
assumed: batching the peak loop collapses MPS from 10.6 ms to ~0.4 ms at fixed
work — *and numpy from 1.36 to ~0.55 ms*.  A size sweep pins the two numbers that
settle it: **break-even ≈ 50-65 k elements per kernel, ceiling ≈2.5-3×** (the
peak chain is memory-bound, so GPU arithmetic throughput never participates).  So
the batched loop is a **numpy-path win** (≈2.4×, every user, no optional
dependency), scoped as a measure-then-decide spike in
[0605](wp/0605-batched-peak-loop.md); Apple-GPU *acceleration* needs ≈10
synchrotron or ≈60 lab patterns batched together to reach that ≈3× — the
v2-fenced in-situ series — and a single lab pattern is below break-even even
after batching.  `torch.compile` does not help either (2.5× slower on CPU;
per-window recompile failure on MPS).
The two hot-path rules that bind *all* future work are in CLAUDE.md's Conventions
(no frozen numpy constant on the left of an operator against a traced value; a
new op must land on every backend); the torch-specific traps are in 0408's
handover log.

0405/0406/0407 and 0408 were developed in parallel and **integrated 2026-07-27**:
the torch traced residual grew the soft-restraint rows (0406's row layout is
written out in three places — numpy, jax, torch), the agreement matrix gained the
`toy_restraints` and true-Voigt configs so the new derivative paths are covered
on every backend row, and four 1-D·1-D dot products in the restraint geometry
were routed through `xp.matmul` (MPS cannot batch `aten::dot`).

</details>

**Out of order: Stephens anisotropic strain
[0503](wp/0503-stephens-anisotropic-strain.md) landed 2026-07-27** (v0.5,
pulled forward on request; 525 tests green). `Phase.microstrain` is an optional
block of the fifteen S_HKL invariants, with the Laue-allowed subspace *derived*
from the gemmi operators by exact rational algebra rather than tabulated (the
DOF counts reproduce Stephens' Table 1 for all eleven Laue classes, checked
twice — against the published table and against the character count of the
degree-4 symmetric power). It brings the first genuinely hkl-dependent peak
width, a `report/strain.py` Layer-1 diagnostic that recovers an injected 3.46×
directional contrast as 3.45×, and a `toy_stephens` backend golden that jacfwd
traces. The acceptance is a *characterisation*, not a win: on round-robin
brucite the three added patterns improve Rwp 18.55 → 17.90 % with ΔBIC +488 and
still leave the physical cone, so `STEPHENS_STRAIN_NOT_POSITIVE` fires and the
coefficients are not quotable. Two findings were pushed downstream: the cone is
a *linear* inequality a constrained solver could enforce
([0601](wp/0601-bounded-lm-solver.md) `### Inherited`), and Hamilton's R-ratio
test is useless at 7251 channels — it blesses an inert 0.13 % χ² improvement —
so ΔBIC is the statistic to quote ([1001](wp/1001-validation-matrix.md)
`### Inherited`).

**Out of order: anomalous scattering
[0504](wp/0504-anomalous-scattering-xraydb.md) landed 2026-07-27** (v0.5, same
session as 0503; and it supplies the explanation 0502 went looking for and
correctly declined to claim). `Source.dispersion` is an opt-in block applying f′ + i·f″ from
a bundled Cromer-Liberman table (`data/f1f2_CromerLiberman.dat`, DABAX/MIT,
Kissel-Pratt-corrected — **not** xraydb, which needs sqlalchemy, and **not**
Chantler, whose DABAX file carries an ESRF-only restriction over a live NIST SRD
copyright). The load-bearing piece is not that f goes complex — F was already
complex — but that a powder measures the **Friedel average**: `generate_reflections`
merges ±h into one orbit and evaluates one representative, which is exact only
while f is real. The closed form ⟨|F|²⟩ = |A|² + |B|² (A carrying f₀+f′, B
carrying f″, over the *same* orbit sums) is exact, needs no second orbit pass and
no centro/non-centro split, and reduces bit-identically when the block is absent.
The acceptance **re-derives a v0.3 conclusion**: refitting the eight IUCr
round-robin sample-1 mixtures under the identical protocol takes the QPA error
from RMS 2.26 → **0.69 wt %** and worst |ΔW| 5.13 → **1.39**, so the signed bias
v0.3 attributed to microabsorption is mostly neglected dispersion (the giveaway
was fluorite coming back *high*, which microabsorption could not explain). Its
sharpest single result is elsewhere: on pure ZnO, Rwp barely moves but B(O) goes
from 0.022 to 0.429 Å² — a displacement parameter that had been spent absorbing
Zn's missing f′. The default stays **off** so every shipped acceptance number
remains valid; flipping it is a re-measurement of the validation matrix
([1001](wp/1001-validation-matrix.md) `### Inherited`), and per-anode dispersion
checks are written into [0507](wp/0507-anode-wavelengths.md).

**Out of order, landed 2026-07-27: v0.5 surface roughness
[0502](wp/0502-surface-roughness.md)** — backend-independent, so it neither
blocks nor depends on the 0404 → 0408 chain. `Geometry.surface_roughness` is an
opt-in, Bragg-Brentano-only, Rietveld-only intensity multiplier with two
published models behind a `kind` seam (Suortti 1972, Pitschke 1993), exactly the
identity when off, folded into all three intensity assemblies so the analytic
dof/adp/March columns cannot drift from FD, and a 7th backend golden.

Both models were verified against primary sources *before* coding: Suortti via
GSAS-II `SurfaceRough` **and** Pitschke's independent quotation of it; Pitschke
by numerically rederiving its equations from the (OCR'd) paper — Eqs 7/9/10 are
exact identities and Eq 12 reproduces its Table I to ≤1.6 %. Two design
decisions fell out: P₀ is dropped (angle-independent ⇒ exactly degenerate with
the phase scale, and the paper itself never resolved it) and τ is refined
directly rather than t₀.

The measured outcome is a **negative** one, and it is the fences that are
accepted rather than the correction. Roughness is constrained by low-angle
*reflections*, not grid points, and no dataset here has any — qarr corundum /
fluorite / zincite first reflect at 25.6 / 28.3 / 31.8°, SRM 660c at 21.4°. Two
of three qarr phases drive the correction back to the identity and raise
`ROUGHNESS_UNCONSTRAINED`; the third slides along the roughness↔Biso degenerate
direction for 0.0001 in Rwp, with ρ(a,b) = +1.000 and esds 350× the values. So
roughness is **not** a competing explanation for the sample-1 QPA bias, and
0502 left that shape test alone. **0504 then found what is** — neglected
anomalous scattering — and renamed it
`test_sample1_bias_has_the_dispersion_shape`; 0502's negative result is what
makes that attribution clean rather than one of two candidates.

Three things this WP exports downstream (all written into WP-0501's
`### Inherited`): `optimize.statistics.block_projection_r2` with its
**nuisance** argument — any multiplicative correction is trivially ~0.96
"scale-like", so only the *partial* R² carries signal; the rule that a
correction is judged at reflection positions, not on the fitted grid (real data
forced that fix); and a pre-existing `|ρ| > 1` in the reported correlation
matrix under poor conditioning, which undermines the correlation guard that both
0501 and 0502 lean on. **That third one was fixed 2026-07-28** in a repo-wide
audit rather than a WP: `np.linalg.pinv`'s default general-SVD path loses
symmetry on the cond ≈ 10²⁰ normal matrices this package routinely forms
(reproduced at |ρ| ≈ 1.6 × 10³), and `covariance_estimates` now symmetrises JᵀJ
and passes `hermitian=True`. Every reported correlation is a valid Pearson
correlation again, so the 0.98 guard measures the data's degeneracies and not
the linear algebra's.

</details>

## Milestones

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v0.1 | Vertical slice: synchrotron CW, Rietveld + Le Bail | ✅ **shipped** ([record](milestones/v0.1.md)) | 11-BM NAC: a = 10.251285(12) Å, Rwp 9.2%, CaF₂ impurity auto-flagged |
| v0.2 | Lab diffractometer + FitReport attribution + viz | ✅ **shipped 2026-07-22** ([record](milestones/v0.2.md)) | SRM 660c LaB6: a = 4.156895(25) Å (+28 ppm vs NIST value for this dataset, Bérar-Lelann-inflated esd), Rwp 8.7%; GSAS-II FAP tutorial: Rwp 9.73% vs GSAS's 10.05% on identical channels, cell +116 ppm (uniform d-scale convention offset) |
| v0.3 | Multi-phase QPA, Pawley, aniso ADPs, multi-histogram | ✅ **shipped 2026-07-24** ([record](milestones/v0.3.md)) | SRM 676a corundum: c/a +30 ppm vs certificate (absolute axes −313/−283 ppm, uniform d-scale); IUCr round robin: sample-1 worst 5.1 wt% (traces ≤1.3), sample 2 worst 2.9 wt% with brucite March-Dollase r=0.67, sample 4 characterised as the designed Brindley failure (µR fence fires) |
| v0.4 | Differentiable backends: JAX jacfwd, mixed precision, torch-MPS; true Voigt; restraints | ✅ **shipped 2026-07-27** ([record](milestones/v0.4.md)) | Cross-backend Jacobian agreement (analytic/FD/jax/torch × 8 configs + multi-histogram + stage boundaries) inside the 5e-3 rel-L2 fp64 bar; an all-fp32 Apple-GPU refinement of SRM 676a lands Δa = −3.5e-8 Å from numpy fp64 (bar 3e-5); wall-clock reported, not gated — and it is a *finding*: MPS is 46-182× slower (launch-latency-bound) and jit'd jacfwd is within 2.1× of the analytic assembly at best, so the batched peak loop is a numpy-path win (WP-0605), not GPU enablement |
| v0.5 | Corrections & microstructure (absorption, Stephens, f′f″) | ✅ **shipped 2026-07-28** ([record](milestones/v0.5.md)) | capillary absorption validated at **both** levels: the Rouse (1970) cylinder factor against a quadrature of the exact ITC eq. (6.3.3.4) integral across 0 ≤ µR ≤ 1 *and* 0 ≤ sin²θ ≤ 1 (0.0035, the paper's own bound), and on real 11-BM SRM 660a LaB₆ data in a documented 0.81 mm bore — Rwp moves 3e-8, the cell 8e-12 Å, and *both* Biso move by the predicted 0.0166542 Å². Plus the two accuracy wins no fit statistic shows: dispersion takes the round-robin QPA error from RMS 2.26 → 0.69 wt %, and a mis-declared flat-plate thickness biases Biso by up to −1.5 Å² |
| v0.6 | TOPAS-style bounded LM, agent surface, batched peak loop | ⬜ | solver benchmark vs scipy TRF (a **CPU** comparison — device acceleration was measured not to exist at this problem size, see 0408) |
| v1.0 | Hardening, API freeze, PyPI | ⬜ | full validation matrix green |
| v2+ | FPA, neutron/TOF, texture, MCP server | ⬜ fenced | — |

## Work packages

### v0.3 — multi-phase workflows (detailed, ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0301](wp/0301-wyckoff-constraints.md) | Wyckoff/site-symmetry constraints (affine p = C·θ + d) | ✅ 2026-07-22 | — |
| [0302](wp/0302-atomic-coordinates.md) | Atomic-coordinate refinement | ✅ 2026-07-23 | 0301 |
| [0303](wp/0303-anisotropic-adps.md) | Anisotropic ADPs | ✅ 2026-07-23 | 0301 |
| [0304](wp/0304-qpa-hill-howard.md) | QPA: Hill-Howard ZMV mass fractions | ✅ 2026-07-23 | — |
| [0305](wp/0305-brindley-microabsorption.md) | Brindley microabsorption | ✅ 2026-07-23 | 0304 |
| [0306](wp/0306-pawley-mode.md) | Pawley mode | ✅ 2026-07-23 | — |
| [0307](wp/0307-march-dollase.md) | March-Dollase preferred orientation | ✅ 2026-07-23 | — |
| [0308](wp/0308-multi-histogram.md) | Multi-histogram stacked residuals | ✅ 2026-07-24 | — |
| [0309](wp/0309-exporters.md) | Exporters: reflection table, CIF+esds (structure side landed in 0303), QPA table | ✅ 2026-07-24 | 0304 |
| [0310](wp/0310-acceptance-srm676a-qpa.md) | Acceptance: SRM 676a + IUCr QPA round robin | ✅ 2026-07-24 | 0304, 0305 |

### v0.4 — differentiable backends (expanded 2026-07-24; ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0401](wp/0401-backend-op-shim.md) | Backend op shim (34 named ops + `window_add`/`segment_sum`; the WP was scoped at "~41" before the survey) + residual purity refactors | ✅ 2026-07-24 | — |
| [0402](wp/0402-jax-backend.md) | JAX backend: chunked jacfwd | ✅ 2026-07-24 | 0401 |
| [0403](wp/0403-cuda-mixed-precision.md) | Mixed-precision policy (CUDA-deferred, CPU-testable) | ✅ 2026-07-24 | 0402 |
| [0404](wp/0404-cross-backend-jacobian-ci.md) | Cross-backend Jacobian CI | ✅ 2026-07-24 | 0402 |
| [0405](wp/0405-faddeeva-voigt.md) | True Voigt via shared Faddeeva w(z) | ✅ 2026-07-24 | 0401 |
| [0406](wp/0406-restraint-penalty-rows.md) | Restraint penalty rows | ✅ 2026-07-24 | — |
| [0407](wp/0407-esd-reconciliation.md) | esd reconciliation (Bérar-Lelann placement) | ✅ 2026-07-24 | — |
| [0408](wp/0408-torch-mps-backend.md) | torch backend (MPS fp32 forward) — moved from v0.6 | ✅ 2026-07-27 | 0401, 0402, 0404 |

### v0.5 — corrections & microstructure (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0501](wp/0501-absorption-corrections.md) | Capillary (cylindrical) absorption | ✅ 2026-07-27 | — |
| [0502](wp/0502-surface-roughness.md) | Surface roughness (Suortti + Pitschke) | ✅ 2026-07-27 | — |
| [0503](wp/0503-stephens-anisotropic-strain.md) | Stephens anisotropic strain | ✅ 2026-07-27 | — |
| [0504](wp/0504-anomalous-scattering-xraydb.md) | Anomalous f′,f″ (bundled Cromer-Liberman, not xraydb) | ✅ 2026-07-27 | — |
| [0505](wp/0505-sequential-refinement.md) | SequentialRefinement warm start | ✅ 2026-07-28 | — |
| [0506](wp/0506-secondary-extinction.md) | Secondary extinction (Sabine) | ✅ 2026-07-23 | — |
| [0507](wp/0507-anode-wavelengths.md) | Additional anode wavelengths (Co/Cr/Fe/Mo/Ag) | ✅ 2026-07-28 | — |
| [0508](wp/0508-flat-plate-absorption.md) | Flat-plate absorption + real-data capillary acceptance | ✅ 2026-07-28 | 0501 |

### v0.6 — solver, performance & agents (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0601](wp/0601-bounded-lm-solver.md) | TOPAS-style bounded LM | ⬜ | — |
| [0602](wp/0602-agent-json-surface.md) | Agent JSON surface hardened | ⬜ | — |
| [0604](wp/0604-theory-manual.md) | Sphinx + MyST theory manual | ⬜ | — |
| [0605](wp/0605-batched-peak-loop.md) | Batched peak loop (spike, then decide) | ⬜ | — |

(0603 — the torch/MPS backend — moved to v0.4 as
[0408](wp/0408-torch-mps-backend.md) on 2026-07-24; the number is left unused so
the history stays readable.)

0605 could be pulled forward the way 0408 was: its ≈2.4× lands on the **default
numpy path** and needs no optional dependency, so nothing about it belongs to
v0.6 except that it was found there.

### v1.0 — hardening & release (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1001](wp/1001-validation-matrix.md) | Validation matrix + tolerance policy | ⬜ | — |
| [1002](wp/1002-ci-matrix.md) | CI matrix | ⬜ | — |
| [1003](wp/1003-api-freeze-pypi.md) | API freeze + PyPI | ⬜ | 1001, 1002 |

## v2+ (seams pre-built, implementations fenced out)

Fundamental Parameters Approach as a differentiable convolution stack
(Cheary-Coelho 1992); neutron CW; TOF (new Source/Profile implementations
behind the frozen seams); spherical-harmonics texture (Von Dreele 1997);
rigid bodies; MCP server wrapping `refine_json`; internal-standard/amorphous
QPA; `vmap`-batched in-situ series; GUI/notebook widgets.

No WP files for v2+ on purpose — the fence is a scope-discipline decision
([DESIGN.md](DESIGN.md#locked-decisions)), and pre-writing packages invites
scope creep.

One note against the day that fence is revisited: **`vmap`-batched in-situ series
is the only accelerator story this package's hardware supports**, and WP-0408
measured its size. A device breaks even at ≈50-65 k elements per kernel and tops
out at **≈2.5-3×** — the work is memory-bound, so that ceiling is not a tuning
problem. One batched pattern is 17-121 k elements, so the plateau needs ≈10
(synchrotron) to ≈60 (lab) patterns processed together. Worth having for a
series; worth nobody's time for a single pattern, which is below break-even even
after batching.
