# WP-1122 — compiled peaks buffer: the declared-tolerance tier

Milestone: v1.1 · Status: 🛑 2026-08-22 — NO-GO on v1.1's terms; deferred to be built **with FPA**, which is what moves the break-even
Track: Speed
Depends on: 1115 (the substrate and its rules), 1121 (the gate: its closing
remainder prices this WP)

## Goal

rietx gains a second, **declared** forward mode: every (line, reflection)
profile reconstructed from a few dozen exactly-computed anchor shapes per
width family, under one stated interpolation tolerance that provenance
records and the harness prices in esd currency — or a recorded NO-GO
measuring why the compiled economics still do not pay. This is the only
measured route to v1.1's stretch target (cold trigger fit < 1 s), and it is
the package's first approximation whose equivalence bar cannot be
bit-identity. That trade is the point of the WP, not a side effect: it is
taken openly, priced, and put to the user, or not taken at all.

## Context

**The gate is passed, and the stretch is still wanted.** Both blockers
closed 2026-08-22: [1121](1121-per-reflection-cost.md) took the
exact-arithmetic remainder and [1123](1123-fast-tolerance-default.md) took
1113's priced ftol flip. The cold trigger fit stands at **5.67-5.70 s**
against v1.1's stretch of < 1 s, so the gap is ~5.7× and the WP is live.

**Where the cost stands** (`examples/bench_refinement.py`, best of three,
worktree `[dev]` venv, darwin/arm64, python 3.12.12, machine idle; measured
by 1123 on the merged tree it left behind — *re-measure before quoting any
absolute*): trigger cold 5.67-5.70 s; cpd-1a 270 nfev at 1.52 s; cpd-2 329
at 2.27-2.28 s; nac 39 at 0.34-0.35 s.

1121's decomposition of the cold trigger fit is still the right one — the
flip removed *evaluations*, not work per evaluation, so each share below is
roughly unchanged while the seconds behind it are ~1.5× fewer. Read the
percentages against 5.7 s, never against the 8.7 s they were taken on:

| seam | share | what it is |
|---|---|---|
| jacobian: bases | 32.8 % | plane work, ~2× off its numpy floor |
| residual (forward) | 22.2 % | plane work, same |
| perturbed `phase_peaks` | 20.2 % | **per-reflection, dispatch-bound** |
| solver + runner | 10.5 % | scipy TRF |
| plane accumulation / decode / FD arithmetic | 3.6 / 3.2 / 3.7 % | |
| `compile_model` | 2.0 % | |

**The mechanism finding that shapes this WP's cost model** (1121
§ Findings 4). The per-reflection blocks are **dispatch-bound**, the
opposite of what 1115 measured for the planes: the trigger's phases hold
98-282 reflections each (594 total), and a `phase_peaks` call in which
*every* memo slot hits still costs **562 ns per reflection**, against 2-4 ns
per element on the ~10⁵-element planes. That is why 1115's tier bought 11.0×
on the scatter, ~2× on the two profile kernels and **1.03×** on
`phase_peaks`. So a buffer that removes *element volume* is priced against
the plane seam — 55 % of wall, already near its floor — and buys nothing on
the per-reflection 20 %, whose lever is fewer, larger calls or compiled code
that does not dispatch. The ceiling this WP can reach is bounded by that
split, and task 1 states it in numbers before any code is written.

**What 1121 left on the table, priced, neither of it blocking.** The
per-line intensity assembly inside `phase_peaks` (0.29 s, 3.3 %) runs on
every column including those that cannot move an intensity — claiming
otherwise is the *inverse* of `_INTENSITY_ONLY`, and root CLAUDE.md warns
that a wrong inverse list costs a silently short column. `table.decode`
(0.28 s, 3.2 %) rebuilds the whole parameter dict per column for a one-entry
change.

**Two method rules 1121 paid for, and this WP's probe re-hits both.**
*Price a removal by removing it*: a per-family timing census over a cache
charges each column for whatever its predecessor evicted, and it over-read
the scale family by 5×. And an unbounded-cache "would-hit" figure is not
headroom — depth 8 built exactly the same blocks as depth 2, to the call.
(*Corrected 2026-11-16, WP-1945:* that measurement could not have differed,
because the lookup compared only the two newest keys whatever the depth. The
first rule stands; this example of the second does not.)

**Why volume, and not another cost-per-element win.** The exact plane seam
is finished: WP-1115 fused the three plane kernels and threads them
(trigger cold 17.6 → 8.86-8.99 s, cpd-1a 2.17-2.21 s, nac 0.40-0.41 s;
darwin/arm64, worktree `[dev]` venv, best of 3), and that seam now runs ~2×
off its own memory floor with no third factor in it. What no exact path can
remove is the arithmetic *volume*: on the trigger case one forward
evaluation computes **269-367 profile elements per pattern point** — 34.6
window points per point (structural overlap, already at the honest
`WINDOW_AREA_TOL` windows) times a 7.8-9× FCJ image multiplier — about
1.1 M exact profile elements per residual call. If ~30 shapes suffice where
the exact path computes ~500 profiles per evaluation, no vectorisation of
the 500 reaches the 30. Removing volume is the buffer's whole content, and
it is TOPAS's single biggest forward-model asymmetry against this package
(Coelho 2018 §5.1: "a small number of peaks being calculated across the
whole 2θ range").

**What the 1114 spike settled** (restated — the protocol forbids reading
closed WPs; every number from `examples/bench_peaks_buffer.py`, darwin/arm64
`[dev]`, 2026-08-21):

- **Shapes reuse, everywhere measured.** A C² cubic spline through
  greedily-placed anchors meets 1e-3 at **K ≤ 16** and 1e-4 at **K ≤ 32**
  on worst-case relative area, first moment (FWHM units) and central second
  moment — every harness case, cold state *and* converged (nac 8,
  cpd-1a/cpd-2 16→32, trigger 24/32 at 1e-4). Anchors are per distinct
  width family and shared across emission lines (Γ, η, FCJ geometry are
  functions of position alone). Greedy probe-and-bisect placement survives
  the genuine C¹ kinks where the fitted Caglioti quadratic goes negative
  and `_MIN_GAMMA_G2` clamps Γ_G (cpd converged states, 2θ ≈ 92-134°);
  every fixed grid plateaus at ~3-5e-4 there.
- **The fit-level price at 1e-4 is below anything a report quotes.** Full
  protocols through the prototype: median value deviation 0.0020 esd
  (trigger) / 0.018 esd (cpd-2), worst 0.107 / 0.215 esd — and every esd
  row that moved > 5 % is a width-decomposition direction with
  esd/|value| between 7e2 and 3e9, a covariance artefact in the exact fit
  too. Trigger Rwp identical to five digits. Where buffered and shipped
  rows disagree most, the buffer is the *more* accurate: its rows sit
  ≤ 8e-5 (m1, FWHM units) from a 128-image reference where the shipped
  path's sub-threshold FCJ skip sits 3.3e-3 away.
- **The NO-GO was the substrate, never the physics.** Batched exact numpy
  runs at ~8-11 ns/element — within ~2× of the memory floor — while the
  buffer's numpy gathers run ~0.8 ns/element but carry their own
  multipliers (7 planes against 4, 4 taps, ~2× `w_max` padding, the
  θ-spline over the stored grid): parity on the trigger bases, a 7-10×
  *loss* on the symmetric lab cases, whose 3-12 elements per point never
  had volume to remove. Interpolation traded away arithmetic nobody was
  paying for.
- **What changed since:** WP-1115's tier is that substrate replaced. In a
  fused `njit` kernel the resample genuinely is a few fma per point while
  the exact path pays an `exp` (and FCJ quadrature) per element. A
  compiled exact kernel and a compiled buffer *compose*; the projected win
  is (image multiplier × exact-per-element cost / fma-per-element cost) on
  FCJ cases and only the cost ratio on symmetric ones. So the buffer is an
  FCJ-and-dense-overlap lever — exactly the stretch target's shape — and
  the lab cases must be shown **unharmed**, not merely unimproved:
  buffering is chosen per width family at compile, from the measured
  element volume, never globally.

**The mode owns the tolerance; the substrate never does.** The compiled
tier's contract (root CLAUDE.md § Conventions) is that nothing above
`compile_model` branches on whether the kernels ran, and `RIETX_COMPILED=0`
changes speed, not answers. A buffer that existed only inside the compiled
tier would break that: the two substrates would disagree by the tolerance,
not by rounding. So the buffer is a **mode of the forward model with two
substrates** — a numpy reference implementation (the oracle, and the
mandatory fallback; 1114's prototype already proved it correct and merely
slow) and the njit kernels — held to the same per-kernel rounding bars the
exact tier uses today. Exact vs buffered is the declared choice; numpy vs
compiled stays invisible.

**The design seed** (1114's design note, restated so this file suffices):

- *Layout.* One buffer per (stage, distinct width family): phases sharing
  (U, V, W, X, Y, `gauss_*`, `lor_*`, S/L, H/L) share one, emission lines
  always share it. Frozen at stage compile — the same class as windows and
  node counts (invariant 1): anchor positions (greedy probe-and-bisect to
  the stage tolerance, domain split at the Γ_G-clamp roots, which the
  compile knows analytically), per-anchor FCJ node counts (floored, never
  the sub-threshold skip), the stored offset grid (step
  min(pattern step, Γ_min/16); half-width from the frozen windows plus a
  drift margin). Anchor *values* are recomputed from the current θ on
  every evaluation — shapes follow the parameters smoothly between
  recompiles; only indices and counts are discrete.
- *Reconstruction.* Each anchor stores four planes: S = Ω and its exact
  partials S_x, S_Γ, S_η (FCJ-mixed at the anchor's own geometry). A C²
  cubic spline in θ interpolates each plane; a reflection at position p
  with widths (Γ_k, η_k) reconstructs
  `Ω = S(p) + (Γ_k − Γ_law(p))·S_Γ(p) + (η_k − η_law(p))·S_η(p)`,
  resampled onto its window by 4 cubic B-spline taps over Unser-prefiltered
  samples (the exact C² interpolating spline in Δ at 4-tap cost). The
  Taylor term keeps Ω first-order exact wherever a reflection's width
  leaves the law — position corrections move p off 2θ_Bragg today, and a
  Stephens Λ(hkl) block is *exactly* this term later.
- *Jacobian, off the same anchors* (or the win halves): ∂Ω/∂Γ = S_Γ,
  ∂Ω/∂η = S_η, and
  `∂Ω/∂pos = S_θ(p) − S_x(p) − Γ_law′(p)·S_Γ(p) − η_law′(p)·S_η(p)` with
  S_θ the spline's own θ-derivative — the FCJ geometry motion the shipped
  path node-FDs comes out of the spline for free, and the two law-drift
  subtractions stop the width motion being counted twice against the
  scalar chain's ∂Γ/∂p. ∂Ω/∂(S/L), ∂Ω/∂(H/L) are anchor-level FDs (two
  extra anchor sets, K each). Everything is C¹ in θ and in every
  parameter, so the analytic-Jacobian invariant survives; linear blends
  are C⁰ at anchors and lose twice (accuracy, and kinks a moving cell
  drags through the residual).
- *Cost model.* Per evaluation: K × images × n_stored exact elements
  (~0.1 M on the trigger, against the shipped 1.12 M) plus ~8 fma per
  (row, window point) for the spline combine and resample.

**The traps, each already paid for once** (1114 § Findings 3-4; any
implementation re-hits them first):

1. A 4-tap resample of *raw* samples is O(h³) and measurably not enough —
   prefilter (Unser) so the same taps evaluate the C² interpolating spline.
2. The stored step keys to **Γ/16**: the O(h⁴) constant lives in
   σ = Γ/2.355 units and the flank carries f⁗ ~ 10²/σ⁴; /4 was 1e-3-wrong.
3. An anchor must **never** take the sub-threshold FCJ skip (node count 0):
   the spline smears the family discontinuity into every neighbour
   (measured 1.0e-3 FWHM of m1 against 1.2e-5 with the count floored).
4. A per-compile cache keys on an **owned reference**, never `id()` of an
   unreferenced model — a dead model's id is recycled and a stale buffer
   served a different stage's frozen state, allocator-dependently.
5. The compiled-tier rules bind (root CLAUDE.md § Conventions): serial
   `njit(cache=True, nogil=True)` kernels over row ranges on the shared
   pool, never `prange`; one path per process; the per-kernel equivalence
   bar stated and asserted; the numpy side stays exercised.

**The deal, made clauses.** This is the package's first approximate forward
mode, and the honesty contract is the acceptance, not decoration:

- (a) **One tolerance constant, with its formula**, stated in the same
  discarded-area currency as `forward.WINDOW_AREA_TOL` so the two compose
  rather than stack; the default chosen from the measured anchor curve,
  after checking the shape of TOPAS's own accuracy knob in the paper
  (prior art shapes the seam — never port, concepts only).
- (b) **Measured against the exact path on the full harness and the
  acceptance suites**, per-parameter and per-esd, in esd currency.
- (c) **Reported**: provenance and/or a diagnostic naming the mode and its
  tolerance — a new correction ships with a record field, and never an Rwp
  comparison as evidence. `capabilities().features` carries the mode as a
  derived predicate, not a literal.
- (d) **Default-on vs opt-in is the user's decision, made from the
  measured table** — never assumed by this WP.
- (e) **The exact path stays**, and every test that pins a number declares
  which mode it pins (the dispersion-default rule meeting its third
  default).

The precedent that makes this a third stated truncation rather than a first
sin: the exact path already carries `WINDOW_AREA_TOL = 2e-2` and the
sub-threshold FCJ skip, both declared, both measured. The difference — the
buffer touches every row — is why it is a *mode*, not a constant.

**There is now a shape to copy, so do not invent one.** The buffer would be
the first approximate *forward* mode but the package's **second**
declared-tolerance concession: 1123 shipped
`RefinementPlan.intermediate_ftol` with exactly the parts (a)-(e) ask for —
a measured bound in esd currency (≤ 0.03 esd on a single fit), an off switch
reproducing the old answer bit for bit, a record of what each stage actually
*ran* at rather than what it declared (`StageResult.ftol`,
`NodeAction.ftol`), and a line in every acceptance suite naming the setting.
Its session reports that the switch was cheap and the **recording** was what
cost time; budget accordingly.

**Judge the mode on single fits, and say so.** 1123's chained-series
comparison changed sign between two trees one commit apart — 1.04× worse,
then 1.12× better, with nothing about the schedule changed — because a warm
chain turns a bounded per-fit difference into a rung escalation or a rung
avoided, an effect unbounded in magnitude and not fixed in sign. A tolerance
mode judged on a series number is judged on an amplifier.

## Non-goals

FPA and FFT convolution (v2-fenced — this WP reuses the existing TCHZ/FCJ
shapes, no new physics); re-opening 1114's NO-GO on its original numpy
terms (the numpy buffer exists here only as oracle and fallback, never as
the performance claim); Le Bail/Pawley partitioning; any tolerance looser
than 1e-3 without the user in the loop; a second approximate mode; touching
window semantics beyond composing the two tolerance currencies.

## Findings

### 1 — the gate's numbers, re-measured on this tree (2026-08-22)

Everything below is `[dev]` venv (numpy 2.5.2, scipy 1.18.1, numba 0.67.0),
darwin/arm64, python 3.12.12, machine idle. The harness first, because a
projection multiplies it (`bench_refinement.py`, best of three):

| case | wall (s) | nfev | njev | Rwp |
|---|---|---|---|---|
| nac | 0.34-0.35 | 39 | 36 | 0.09317 |
| cpd-1a | 1.49-1.52 | 270 | 215 | 0.17127 |
| cpd-2 | 2.27-2.29 | 329 | 254 | 0.13267 |
| trigger | 5.68-5.81 | 232 | 190 | 0.01998 |

1123's figures reproduce. Then the seams of the trigger cold fit, from
`bench_compiled_kernel.py --seams` on a 5.75 s run — 1121's share table,
re-measured rather than quoted:

| seam | s | share |
|---|---|---|
| residual (forward) | 1.270 | 22.1 % |
| jacobian: bases | 1.886 | 32.8 % |
| jacobian: columns | 1.743 | 30.3 % |
| — of which `phase_peaks` | 1.118 | 19.4 % |
| — of which `accumulate` | 0.198 | 3.4 % |
| `compile_model` | 0.175 | 3.0 % |
| solver + runner | 0.679 | 11.8 % |

### 2 — the ceiling is 2.22×, and it is a fact about the fit, not about the buffer

The plane seam this WP attacks is forward + bases = **54.9 %** of the cold
trigger fit. A plane seam of **zero** cost therefore leaves 2.56 s, and
**v1.1's stretch target (< 1 s cold) is unreachable by this WP whatever the
buffer's own ratio turns out to be**. That is arithmetic on measured shares,
it needed none of the work below, and it falsifies this WP's opening claim
that the buffer is "the only measured route to v1.1's stretch target": there
is no route to < 1 s through the planes alone. Reaching it would need the
per-reflection 19.4 %, the solver's 11.8 % and the column seam's remainder
as well — three more fronts, two of which 1121 measured and left.

### 3 — the two per-element costs, measured (`examples/bench_compiled_buffer.py`)

The probe times the shipped compiled plane seam on each case's own frozen
rows against a fused `njit` reconstruction kernel over the anchors, stored
grid and step that 1114's prototype produces — so the shapes priced are the
shapes that met 1e-4. Both sides run **serially** (`RIETX_COMPILED_THREADS=1`):
each is row-parallel over disjoint outputs, so the pool multiplies them
together, and left alone `_spread`'s 512-row threshold compared a threaded
buffer against a serial exact path on the one phase big enough to cross it.
The kernel is checked against the prototype's numpy reconstruction and agrees
to 2.2e-16 - 4.3e-16, so what is timed is arithmetic that produces the right
answer.

| quantity | measured |
|---|---|
| exact forward, per profile element | 2.03-3.88 ns |
| exact bases (Ω + 3 partials), per element | 4.96-6.84 ns |
| reconstruction, per (row, window point) | 5.60-8.77 ns |
| anchor build, per element (charged at the bases rate) | as above |

Three volume figures cross-check the WP's own Context against an independent
measurement: the trigger's four phases carry **1 125 778** profile elements
per forward evaluation (Context says ~1.1 M), **34.6** window points per
pattern point, and an image multiplier of **7.79-7.87**.

### 4 — the number that decides it: break-even is ~3-4 images per window point

The buffer replaces `Σwin × images` exact elements with an anchor build plus
one reconstruction per window point. What decides whether that pays is
therefore neither the tolerance nor the anchor count but **how many FCJ
images a window point carries**, and the probe reports the break-even per
phase (`img*`):

| case | images | break-even | ideal ratio |
|---|---|---|---|
| nac (2 phases) | 1.00 | 3.35, 6.30 | 0.30, 0.16 |
| cpd-1a (3) | 1.00 | 4.11-6.72 | 0.24, 0.20, 0.15 |
| cpd-2 (4) | 1.00 | 3.97-6.48 | 0.15-0.25 |
| trigger (4) | 7.79-7.87 | 2.78-4.16 | 1.89-2.81 |

So a **symmetric family can never pay** — not at a looser tolerance, not with
a better kernel, not with more anchors — because at one image per point the
exact path computes fewer elements than the anchor build alone (the probe's
`vol×` column: 0.26-0.59 on the lab cases, i.e. building the anchors costs
*more* exact elements than the whole exact evaluation). That is structural,
and it is the same wall 1114 hit, standing in a different place: 1114's numpy
buffer lost on all cases, this one loses on every symmetric family and wins
only where FCJ multiplies the volume.

The ratios above are the buffer's **best case**, not a forecast. They price
the anchor planes at the exact path's own compiled per-element cost and the
spline build at zero (as built, in numpy, the trigger phases run 0.53-1.11×,
i.e. mostly a loss), and they charge the mode for none of the masking,
per-row scalar state, NaN handling, compile-time placement or fallback
substrate a shipped one owes.

### 5 — what it would buy, per case

Applying the measured seam shares, and buffering only the families whose own
volume pays (the per-family decision this WP already requires):

| case | wall (s) | plane seam | projected (s) | whole fit |
|---|---|---|---|---|
| nac | 0.34 | declines | 0.34 | 1.00× |
| cpd-1a | 1.49 | declines | 1.49 | 1.00× |
| cpd-2 | 2.27 | declines | 2.27 | 1.00× |
| trigger | 5.68 | 2.45× | 3.83 | **1.48×** |

One case of four, at 1.48× of an upper bound, against a stretch target that
needs 5.7×. Sharing the anchor build between the forward and the bases call
wherever θ coincides — the most generous accounting available, and not
generally available (232 residual against 190 Jacobian evaluations) — moves
that to about 1.58×.

**A caveat that bounds the beneficiary set, and the harness cannot settle
it.** The three cases that decline are symmetric *because the harness has no
lab case with FCJ actually on*: `qarr_instrument` leaves both axial ratios at
0.0, so cpd-1a and cpd-2 compile no real quadrature, and nac is a synchrotron
Debye-Scherrer pattern. A real Bragg-Brentano fit with axial divergence
declared would carry some image multiplier between 1 and the trigger's 7.8,
and where it falls decides whether the buffer serves one simulated case or a
class of real ones. Measuring that needs a lab dataset with declared axial
ratios, which the harness does not have.

### 6 — go/no-go: **the economics do not pay for the stated goal**

Recorded as the WP's last task asks, with the ratios. Three measured
statements, in the order they bind:

1. The stretch (< 1 s cold trigger) is **unreachable** through the plane
   seam, by 2.5× at a free plane seam. Finding 2, and it holds whatever is
   built.
2. The buffer's best case is **1.48× on one harness case of four**, and a
   3-7× **loss** on the other three unless each declines it per family.
3. The price is the package's first approximate forward mode: a declared
   tolerance, two substrates held to per-kernel bars, per-family selection,
   and the honesty surface (a)-(e). 1123 reports that the *recording*, not
   the switch, is what such a mode costs.

The recommendation is therefore **NO-GO on v1.1's terms**, and the stretch
target declared unreachable on those terms — a second substrate verdict on
the shelf beside 1114's, taken on the substrate that verdict said to re-take
it on. What is *not* being said: that shape reuse does not work (1114 proved
it does), that a compiled buffer is slower than a compiled exact path (on
FCJ-dense families it is 1.9-2.8× faster), or that this closes off a v2 that
wants FPA — where the image multiplier is far larger and the same break-even
arithmetic would come out the other way.

The remaining decision is the maintainer's, because it is a milestone-scope
call rather than a measurement: close 1122 🛑 on these numbers, or build the
mode anyway for the 1.48× on FCJ-dense fits with the stretch target dropped.

## Tasks

- [x] **Gate reading + economics probe.** Re-measure the harness on this
      tree (§ Context's figures are 1123's), then measure the two per-element
      costs
      the cost model needs on the current tree: the compiled exact pV/FCJ
      element against a compiled prefilter + 4-tap resample + spline-combine
      microkernel on trigger-shaped planes (`examples/bench_compiled_buffer.py`).
      Project the fit-level ceiling per harness case from measured ratios,
      and record **go/no-go for the build** with the numbers.
- [ ] **Buffer compile.** Width-family detection, greedy anchor placement
      with the clamp-root domain split, floored node sets, stored grid +
      prefilter — frozen at stage compile; owned-reference caching; the
      per-family buffering decision from measured element volume.
- [ ] **Forward reconstruction, numpy first.** The reference implementation
      is the oracle; per-row equivalence bar vs the exact path asserted
      (≤ tol on area, m1, m2), whole-pattern bar stated. Then the njit
      kernels, held to the exact tier's per-kernel rounding bars against
      the numpy buffer.
- [ ] **Derivative bases off the same anchors.** The `_column_extras` /
      `moving_paths` gates re-checked under the mode; the cross-backend
      configs grow with the new derivative path (CLAUDE.md rule).
- [ ] **The honesty surface**: the tolerance constant + formula, the
      provenance/diagnostic field, the `capabilities()` flag, the
      `rietx compare` row (`tests/test_compare_ui.py`), and every pinned
      test declaring its mode.
- [ ] **Fit-level measurement**: full harness both modes, per-parameter/esd
      deviation table, acceptance suites green, obs/calc/diff PNGs to
      `tests/output/`.
- [ ] **The user decision**: default-on vs opt-in and the tolerance
      default, put with the tables — and with 1113's flip status beside
      them, since the factors multiply.
- [x] If the economics still do not pay, record **NO-GO** with the measured
      ratios — a second substrate verdict on the shelf beside 1114's, and
      the stretch target declared unreachable on v1.1's terms.
      (§ Findings 6; the close itself is the maintainer's call.)

## Acceptance

```sh
.venv/bin/python examples/bench_compiled_buffer.py   # the probe: per-element ratios, anchor counts
.venv/bin/python examples/bench_refinement.py        # exact mode: ranges unchanged
.venv/bin/python examples/bench_refinement.py --buffered            # the mode's spelling is task 2's
RIETX_COMPILED=0 .venv/bin/python examples/bench_refinement.py --buffered  # same answers, numpy substrate
.venv/bin/python -m pytest -n auto --dist loadgroup  # full: this moves numbers
.venv/bin/python -m ruff check src tests examples
```

Before/after as harness ranges with venv and platform; every deviation
quoted in esd currency per parameter; the per-kernel bars stated; the
stretch (< 1 s cold) reported either way; never an Rwp comparison.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210-218, §5.1 — the peaks
  buffer's existence and role. TOPAS is closed source: **papers only,
  concepts only** (CLAUDE.md licensing fence).
- Cheary, R. W. & Coelho, A. (1992). *J. Appl. Cryst.* **25**, 109-121 —
  the FPA context the buffer was built for (background only; FPA is
  v2-fenced).
- Unser, M. (1999). *IEEE Signal Process. Mag.* **16**(6), 22-38 — the
  B-spline prefilter behind trap 1.
- WP-1114 § Findings 2-4 and § Design note — the seed this file restates;
  its anchor-curve figure is `tests/output/wp1114_anchor_curve.png`.
- WP-1115 — the substrate and its rules (now root CLAUDE.md § Conventions).
- WP-1121 — the gate; WP-1113 § Findings — the multiplying flip.

## Handover log

### 2026-08-22 (2nd session) — closed 🛑, and handed to FPA rather than shelved

The maintainer's decision on § Findings 6: **do not build the mode, and build
it at the same time as FPA.** That is a different answer from 1114's shelf,
and a better one. What this WP measured is not that shape reuse fails but
that it needs a point to be computing the same shape several times over
before it can pay, and the thing that will make that true across the board is
fundamental-parameters peak shapes, which are v2-fenced. So the buffer stops
being a speed WP looking for a case and becomes a component of the FPA work,
where the arithmetic it removes is the arithmetic FPA adds.

Nothing was built, and nothing here needs unbuilding: the only code this WP
added is a benchmark (`examples/bench_compiled_buffer.py`), production code
is untouched, and the exact path is the only forward mode the package has.

*What closing this settles.*

- **v1.1's stretch target is unreachable and is now recorded as such**, not
  quietly dropped. Under 1 s cold needed the plane seam gone, and the plane
  seam is 54.9 % of the fit, so zero cost there still leaves 2.56 s. The
  milestone's two *gating* targets are unaffected by this close; the stretch
  row in `milestones/v1.1.md` now says what was measured and what it waits on.
- **The break-even is the durable result**, and it is what a future session
  needs: 2.8-4.2 FCJ images per window point, below which no tolerance, kernel
  or anchor count can make the buffer pay, because the anchor build alone then
  costs more exact elements than the whole exact evaluation. It is stated in
  root CLAUDE.md § Backends beside the fence so that re-opening this needs a
  reason rather than an oversight.
- **The physics half stays proven and stays 1114's.** K ≤ 32 anchors at 1e-4
  on every case and both states, and this WP's reconstruction kernel agreeing
  with that prototype to 4.3e-16, are the two halves of "the design works".
  An FPA session inherits both and re-derives neither.

*Gotchas for the FPA session that picks this up.* All of § Findings still
applies, and three parts of it are what that session should read first:
Findings 4 for the break-even and why the tolerance is not the deciding
variable; Findings 3 for the two ways to measure this wrong, both of which
flatter the buffer (the thread-pool threshold, and pricing a numpy anchor
build against a compiled exact path); and Findings 5's caveat, which is the
one open measurement — the harness holds no lab case with FCJ actually on, so
where a real Bragg-Brentano fit sits against the break-even is still unknown,
and under FPA that question changes shape anyway.

*Next.* Nothing on this WP; it is closed. The buffer is now a component of
the v2 FPA work (root CLAUDE.md § Backends, ROADMAP's v2+ row), and the
design it would start from is [1114](1114-peaks-buffer-spike.md)'s note plus
this file's § Findings.

### 2026-08-22 — the buffer is priced, and it misses what it was created for

Reusing peak shapes — computing a few dozen exact profiles across the range
and interpolating the rest — was measured on the compiled substrate that
1114's NO-GO said to re-take it on. It would pay on patterns whose peaks are
smeared by axial divergence: about 2.4× on the part of a fit that computes
peak shapes, and 1.5× on the whole fit, for the one harness case shaped that
way. It would not pay on the other three, which have to decline it rather
than merely fail to benefit. And the target the WP was created for — a cold
four-phase fit under a second — is out of reach whatever is built here,
because peak-shape work is 55 % of that fit and removing **all** of it still
leaves 2.6 s. So the recommendation is not to build the mode on this
milestone's terms. The physics was never the problem, was not re-tested, and
is not what failed; what failed is that the seam it attacks is too small a
share of the remaining time.

*Done.* The mailbox is consumed — all eight entries were still true (both
blockers closed the same day) and none was stale, so they were folded into
Context rather than dropped: the gate paragraph became a statement of where
the cost stands, 1121's share table came with it, and 1123's shape for a
declared-tolerance mode plus its caution against judging one on a chained
series joined the honesty clauses. Then task 1: `examples/bench_compiled_buffer.py`,
and § Findings 1-6.

*Measured* (worktree `[dev]` venv — numpy 2.5.2, scipy 1.18.1, numba 0.67.0,
no jax/torch — darwin/arm64, python 3.12.12, machine idle):

- Harness, best of three: nac 0.34-0.35 s, cpd-1a 1.49-1.52 s, cpd-2
  2.27-2.29 s, trigger cold **5.68-5.81 s**. 1123's figures reproduce.
- Seams of the cold trigger fit (`bench_compiled_kernel.py --seams`, 5.75 s):
  forward 22.1 %, bases 32.8 %, columns 30.3 % (`phase_peaks` 19.4 %,
  `accumulate` 3.4 %), `compile_model` 3.0 %, solver 11.8 %. 1121's table,
  re-measured rather than quoted.
- Exact plane seam 2.03-3.88 ns per profile element (forward) and 4.96-6.84 ns
  (bases); the buffered reconstruction 5.60-8.77 ns per (row, window point).
- **Break-even is 2.78-4.16 FCJ images per window point.** The trigger's four
  phases carry 7.79-7.87 and reach 1.89-2.81× each; every other family in the
  harness carries exactly 1.00 and loses 3-7×.
- Whole-fit projection with per-family selection: trigger 5.68 → 3.83 s
  (**1.48×**), the other three unchanged. Amdahl ceiling **2.22×** (2.56 s).
- Fast selection **2619 passed, 117 skipped in 1:55**, exit 0 — unmoved from
  1123's closing count, which is right: this session added an example script
  and documentation, and no test. No full-suite run, because nothing here can
  move a measured number.
- `ruff check src tests examples` clean; `tests/test_docs_consistency.py` 20
  passed.

*Gotchas for whoever comes next.*

- **Two confounds have to be removed or the probe answers a different
  question, and both flatter the buffer.** `compiled._spread` only engages
  the thread pool above 512 rows and the exact path splits by FCJ *bucket*
  while a reconstruction splits by row, so on the trigger's one 564-row phase
  the first cut compared a threaded buffer against a serial exact path and
  read 1.29× where the serial answer is 1.11×. Everything is now timed under
  `RIETX_COMPILED_THREADS=1`; both sides are row-parallel over disjoint
  outputs, so the pool multiplies them together and cancels. The other is the
  anchor build: 1114's prototype builds it in numpy, and charging the buffer
  for that against a compiled exact path reads 0.53-1.11× where the compiled
  rate gives 1.89-2.81×. The probe reports both columns for this reason.
- **The deciding quantity is not the tolerance.** It is images per window
  point, which is why `img*` is a column: a family below break-even cannot pay
  at any tolerance, with any kernel, at any anchor count, because building the
  anchors then costs more exact elements than the whole exact evaluation does
  (`vol×` 0.26-0.59 on the lab cases). A looser tolerance moves K, and K is
  not what the cost is in.
- **The harness cannot settle the beneficiary set, and this bounds the
  finding.** cpd-1a and cpd-2 are lab geometries whose instrument leaves both
  axial ratios at 0.0, so they compile no real quadrature, and nac is
  synchrotron Debye-Scherrer. The harness therefore contains **no lab case
  with FCJ actually on**, and a real Bragg-Brentano fit with declared axial
  divergence would sit somewhere between 1 and the trigger's 7.8. Where it
  falls decides whether the buffer would serve one simulated case or a class
  of real ones, and answering it needs a dataset the harness does not have.
- Three of the probe's volume figures reproduce numbers this WP's Context had
  from an independent measurement — 1 125 778 elements per forward
  evaluation, 34.6 window points per pattern point, 7.8× images — and the
  reconstruction kernel agrees with 1114's numpy prototype to 4.3e-16. Both
  were deliberate: a cost model that cannot reproduce a known volume is not
  measuring the thing it names.

*Next.* One decision, and it is the maintainer's, because it is milestone
scope rather than measurement: **close 1122 🛑 on these numbers, or build the
mode anyway** for 1.48× on FCJ-dense fits with the stretch target dropped.
Nothing else in the WP can start before it — tasks 2-7 all presuppose the
build. On a 🛑 close, three things follow in order: delete the (already
consumed) `### Inherited` heading, rewrite ROADMAP's Current focus, and
correct `milestones/v1.1.md`, whose stretch row still ties < 1 s to 1114's
go/no-go — that row is now measured unreachable through this route and should
say so rather than being quietly dropped. If instead the mode is built,
§ Findings 4's break-even is the compile-time rule the per-family decision
should use, and § Findings 3's caveats are the two ways to measure it wrong.

- **2026-08-22** — created, at the maintainer's direction, to give the
  compiled-substrate option in 1114's design note an owner and the v1.1
  stretch target its one measured route. The exact-arithmetic road ends
  around 4-5 s on the cold trigger fit (1121 + the flip, projected): its
  remaining volume is structural, and only shape reuse removes volume. The
  physics half is proven (K ≤ 32 anchors at 1e-4, every case, both
  states); the substrate half failed once, on numpy, for economics 1115
  has since replaced. What this WP decides is therefore not whether shapes
  reuse but whether rietx takes its first *declared-tolerance* mode — the
  bargain TOPAS's speed has always rested on — priced in esd currency and
  put to the user. Gated on 1121's close; nothing is started. **Next**:
  task 1, and only after 1121's remainder lands in `### Inherited` here.
