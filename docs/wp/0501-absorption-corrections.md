# WP-0501 — Capillary (cylindrical) absorption

Milestone: v0.5 · Status: ✅ shipped 2026-07-27
Depends on: —

## Goal

A Debye-Scherrer capillary specimen carries its cylindrical absorption factor
A(µR, θ) in the Rietveld intensity chain, with µR **computed** from composition,
packing fraction and capillary radius — never refined. The deliverable is
**unbiased ADPs**: omitting the correction biases Biso low by 0.49 Å² at µR = 1
(Cu Kα) — a systematic comparable to Biso itself, which no fit statistic reveals.

## Context

### The physics, and its one load-bearing consequence

Rouse, Cooper, York & Chakera (1970), *Acta Cryst.* **A26**, 682 give the
transmission factor for equatorial reflections from a cylinder as

```
A(µR, θ) = exp{ −(a₁ + b₁·sin²θ)·µR − (a₂ + b₂·sin²θ)·µR² }

cylinder:  a₁ = 1.7133   b₁ = −0.0368   a₂ = −0.0927   b₂ = −0.3750
           max error 0.0035 over 0 ≤ µR ≤ 1     (sphere, for reference and NOT
           implemented: 1.5108, −0.0315, −0.0951, −0.2898, max error 0.0024)
```

**b₂ = −0.3750 and this cost a debugging pass — read before touching it.** The
available scan of the paper prints b₂ as "−0·0375", a digit transposition. The
error is invisible against the sin²θ = 0 column of Table 1 (which constrains only
a₁ and a₂, and passes at 0.0015 either way) and nearly invisible at low µR, but it
is 0.0821 against exact physics at µR = 1. What settles it is that with
b₂ = −0.3750 the max error against a quadrature of ITC eq. (6.3.3.4) is **exactly
0.0035 — the bound the paper itself claims** — and the table's own µR = 1,
sin²θ = 1 entry (0.2951) matches the quadrature (0.29509) rather than the
mis-transcribed formula (0.21303). Never validate this expression against a
constant-θ slice alone; the tests must span sin²θ.

**The consequence that shapes everything.** That expression factors *exactly*:

```
A = K(µR) · exp( +c(µR)·sin²θ ),    c(µR) = −(b₁·µR + b₂·µR²) > 0
```

a constant times a Debye-Waller-shaped term — and this is exact *by construction
of the fit*, not approximate. So applying A to a model whose phase scale and Biso
are free is an **exact reparameterisation**: the residual, and therefore Rwp, is
unchanged to machine precision, and the entire physical content of the correction
is a known shift in the reported values.

The *true* physics is not exactly separable — eq. (2) only fits it to 0.0035.
Measured against the ITC quadrature, the part of A that a free {scale, Biso} pair
cannot absorb is

```
µR      0.1     0.2     0.3     0.5     0.7     1.0
resid   0.03%   0.12%   0.22%   0.34%   0.20%   1.56%    of intensity
```

so even at the top of Rouse's range the non-degenerate signal is ~1.5 %, and
below µR ≈ 0.5 it is under a third of a percent. Eq. (2) models none of it.

Therefore:

- **µR is computed and fixed, never a refinable `Parameter`.** Within this model
  a free µR is *exactly* a linear combination of the scale and Biso columns — a
  singular Jacobian direction, not merely a correlated one. This is the WP-0310
  transparency trap in a sharper form.
- **The deliverable is unbiased ADPs, not a better fit.** Omitting A forces the
  fit to reproduce a calc that rises with sin²θ, which it can only do by reducing
  the Debye-Waller damping. Neglecting capillary absorption therefore biases Biso
  **low** by

  ```
  ΔB = c(µR)·λ²/2   →   0.133 Å² at µR = 0.5,   0.489 Å² at µR = 1.0   (λ = 1.5406 Å)
  ```

  Against typical Biso of 0.3–1 Å² that is a 15–100 % systematic. **Do not assert
  that Rwp improves** — it provably cannot, and it is the wrong yardstick here.

### Convention, stated by physics not letters

ITC Vol. C (6.3.3.1)/(6.3.3.2): the **transmission coefficient A = (1/V)∫exp(−µT)dV
is ≤ 1** and is what the forward model *multiplies* into calc; the **absorption
correction A\* = 1/A ≥ 1** is what most tables print. Rouse Table 1 tabulates
A (transmission) directly — its µR = 0 row is 1.0000 — so no inversion is needed
against that fixture. Any comparison against an A\* table must invert one side,
and A(µR=0) = A\*(µR=0) = 1 makes an identity test blind to a swap; the direction
tests (A decreasing in µR, *increasing* with 2θ) are what catch it.

### Sources and their standing

| Rung | Source | Status |
|---|---|---|
| Implementation | Rouse et al. (1970) A26 682 eq. (2), cylinder | **Verified** against an ITC (6.3.3.4) quadrature to 0.0035 — the paper's own claimed bound — *after* correcting the printed b₂ (above) |
| Ground truth | Rouse Table 1(a)/(b): A vs µR (0.00–1.00 step 0.01) × sin²θ, 4 dp | **Usable with care** — see the transcription trap below. The blocks carried into `tests/data/` were each validated against the quadrature to ≤1.7e-4 |
| Independent physics | ITC Vol. C eq. (6.3.3.4), the exact cylinder integral | Clean, and **the load-bearing check** — it is what caught the b₂ transposition, which the published table alone did not. Its µR→0 slope reproduces the exact mean chord 16/(3π) = 1.69765 to 5 dp |
| Fence rationale | ITC Table 6.3.3.1(1a): thick flat plate A = 1/2µ | Clean |
| Cross-code only | Lobanov & Alte da Veiga, as used by GSAS-II `Absorb`/TOPAS `abs_lobanov` | Coefficients trace to a **conference abstract** (6th EPDIC, P12-16) that cannot be obtained; usable only as a *tolerance* comparison, never as a golden |
| Do not use | ITC Table 6.3.3.2 (cylinder A\*), Table 6.3.3.5 (Tibballs K_m) | The available scan of 6.3.3.2 is scrambled beyond recovery (the block that follows it is a mean-path-length table, not A\* — its µR = 0 row reads 1.5000); 6.3.3.5 is only referenced, not reproduced. Rouse supersedes both for µR ≤ 1 — do not spend a session re-extracting them |

**Transcription trap, and it is not obvious.** In the available scan of Rouse
Table 1 each cell holds **five consecutive µR rows**, and the printed µR labels
are offset by exactly 3 from the values they sit beside (label "0.20" sits at
index 17). Read the sin²θ = 0 column as one continuous run and it recovers exactly
51 entries = µR 0.00…0.50 — that count is the check that the reading is aligned.
A naive read attributes each label to the first value in its cell and shifts every
µR by up to 4 steps.

### Existing machinery to reuse, not rebuild

- `crystallography/attenuation.py` (WP-0305): `linear_attenuation(element_counts,
  volume, wavelength) -> cm⁻¹` per phase, backed by bundled
  `data/mu_McMaster.dat`. It interpolates log-log and **refuses** a wavelength
  whose grid interval contains an absorption edge, refuses outside 2–120 keV, and
  raises `KeyError` for elements absent from the compilation. Measured vs NIST
  Hubbell-Seltzer at 8 keV: ≤2.5 % for Z ≥ 9, but B −7 % and O −3.6 %
  (McMaster's low-Z weakness) — relevant if µR is ever asserted against a
  light-element standard.
- `optimize/qpa.py`: `phase_zmv(...) -> ZMV` supplies `element_counts`,
  `cell_volume` and `ZMV.density`; `_apply_microabsorption` (`qpa.py:374-414`) is
  the **catch-and-degrade-to-a-reason-string** pattern to copy verbatim for the
  estimator — it catches `(KeyError, ValueError)` from the attenuation module
  rather than letting an edge refusal abort a refinement.
- `model/extinction.py` and `model/preferred_orientation.py` are the module shape
  to follow (physics + `_and_d…` derivative twin + module docstring citing the
  reference); `tests/test_extinction.py` is the test-layering template.

### Invariants this WP must respect

- **`model/*` is xp-routed** (WP-0401): bind `xp = get_backend()` once as the
  first statement of each public function, all math via `xp.*`, `np` only as a
  dtype token. Bare `np.*` breaks the jax and torch backends silently.
- **Frozen-per-stage discreteness**: µR is resolved once at compile onto
  `CompiledModel` and never derived from θ. A itself is *not* frozen — it depends
  on `tt_bragg`, which moves with the cell — so it is evaluated per residual call.
- **µR = 0 must be bit-identical to today.** `exp(−0.0) == 1.0` and `a * 1.0 == a`
  bit-for-bit, which is what protects every existing
  `tests/data/backend_goldens/*.npz`. Never reach this by a `1 - something` form.

### Inherited

From **WP-0305** (Brindley, landed 2026-07-23): the per-phase µ machinery already
exists — reuse `crystallography/attenuation.py` rather than rebuilding, including
its edge-refusal guard and its low-Z accuracy caveat (both restated above).
Brindley acts on QPA *weight fractions*; this WP acts on the profile intensity vs
θ. They are distinct and both may be active.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24): specimen transparency was
measured on SRM 676a and deliberately **kept at 0** — freeing it is a wash
(Rwp 14.37 → 14.33 %) that merely re-apportions the correlated
{zero, displacement, t} triple. Judge new absorption terms by whether they buy
band-resolved residual structure or an unbiased physical quantity, **not by Rwp**,
and do not silently change the acceptance protocol that holds transparency at 0.
This WP's answer to that warning is to make µR non-refinable outright.

From **WP-0401** (op shim, landed 2026-07-24): `model/` is xp-routed (restated
above). A *new op* would have to land on every backend and in `_OP_NAMES`; this
WP needs only `exp`, `sin`, `radians`, `asarray`, so it adds none.

## Non-goals

- **Flat-plate absorption in any form** — fenced into WP-0508 with its formulas.
  Reflection off a thick specimen is *exactly* angle-independent (ITC Table
  6.3.3.1(1a): A = 1/2µ, no θ) and therefore identical to the phase scale, which
  is why GSAS-II returns `1.0` for its `'Bragg'` case. The finite-thickness case
  6.3.3.1(2), A = {1 − exp(−2µt·cosec θ)}/2µ, and the transmission plate
  6.3.3.1(3), A = t·sec θ·exp(−µt·sec θ) at φ = 0, do have θ-signatures but need a
  sample thickness and tilt that no schema carries.
- **A refinable µR.** See above; this is a design decision, not a deferral.
- **µR > 1.** Outside Rouse's validity; diagnosed, not extrapolated.
- **A real-data capillary acceptance.** There is no capillary dataset in
  `tests/data/` — every real pattern is flat-plate Bragg-Brentano, and 11-BM is
  fitted with the geometry-agnostic `debye_scherrer` preset, which carries no
  capillary metadata. Deferred to WP-0508; the milestone row must say
  *algorithm-level* consistency.
- Microabsorption (WP-0305, already landed) and surface roughness (WP-0502).

From **WP-0502** (surface roughness, landed 2026-07-27) — landed in parallel
with this WP and in the geometry it fenced out, so its forward-references were
written into **[WP-0508](0508-flat-plate-absorption.md)** rather than here: this
WP had already shipped by the time 0502 signed off, and `### Inherited` on a
shipped WP reaches nobody. The short version, for anyone auditing 0501 itself:
`optimize/statistics.block_projection_r2` gained a **nuisance** argument (any
multiplicative correction is trivially ~0.96 "scale-like", so only the partial
R² carries signal); a correction must be judged at reflection positions, not on
the fitted grid; and a pre-existing `|ρ| > 1` in the reported correlation matrix
shows up wherever conditioning is poor.

## Tasks

- [x] Expand this stub into a full WP before writing code
- [x] Rouse Table 1 ground-truth fixture → `tests/data/absorption_cylinder_rouse.dat`
      + provenance row in `tests/data/README.md` (lands *before* the physics)
- [x] `Geometry.capillary_radius_mm`, `packing_fraction`, `mu_r` — all plain
      floats, never `Parameter`; validator; `Instrument.debye_scherrer` passthrough
- [x] `model/absorption.py`: `cylinder_absorption`,
      `cylinder_absorption_and_dmur`, `equivalent_delta_biso`, `CYLINDER_MU_R_MAX`
      + the evidence-ladder tests (Rouse fixture, ITC quadrature, 16/(3π) limit,
      µR = 0 identity, dA/dµR vs FD, direction/convention guard, **degeneracy
      pinned as a test**)
- [x] µR estimator: `packed_mu_r` (attenuation.py), `estimate_capillary_mu_r`
      (qpa.py, catch-and-degrade), `estimate_mu_r` (refine.py, re-exported)
- [x] Wire A into `phase_peaks` **and both** `_structural_intensity_grad` and
      `po_intensity_grad`; hidden-Jacobian guard test with its discriminating
      pre-assert
- [x] `ABSORPTION_MU_R_OUT_OF_RANGE` / `ABSORPTION_ESTIMATE_UNAVAILABLE`
      diagnostics; report the applied µR and equivalent ΔB
- [x] `toy_capillary` cross-backend state (new state, never edit `toy_rich`);
      capture the golden **last**, from a green tree
- [x] ADP-bias test: µR = 1.0 injected, Biso biased low by 0.489 Å² without the
      correction and unbiased with it; PNGs to `tests/output/`
- [x] Docs: DESIGN.md subsection, ATTRIBUTION.md rows, WP-0508 stub,
      `### Inherited` notes into WP-0502/0503, handover log, ROADMAP sync

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_absorption.py -q          # evidence ladder + ADP bias
.venv/bin/python -m pytest tests/test_backend_shim.py -q        # µR=0 is bit-identical
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_backend_conformance.py -q
.venv/bin/python -m pytest -m "not slow" -q
.venv/bin/python -m pytest -m slow -q                           # acceptance numbers UNMOVED
.venv/bin/python -m ruff check src tests examples
```

Criteria:

1. `cylinder_absorption` matches an ITC (6.3.3.4) quadrature to ≤0.0035 across
   0 ≤ µR ≤ 1 **and** 0 ≤ sin²θ ≤ 1 (a constant-θ slice does not constrain b₁, b₂
   — that is how the b₂ transposition survived), and matches the published Rouse
   fixture to ≤0.0035.
2. Injecting µR = 1.0 and refining **without** the correction returns Biso low by
   ΔB = 0.489 Å²; refining **with** it returns Biso unbiased. Because eq. (2) is an
   exact reparameterisation of {scale, Biso}, Rwp must agree between the two runs
   to ~1e-9 — assert that equality rather than an improvement.
3. Every backend agrees per-column on `toy_capillary` inside the standing
   5e-3 rel-L2 / 0.99999 cosine bars.
4. The slow suite reports **identical** NAC / SRM 660c / FAP numbers — none of
   them sets a capillary radius, so µR stays 0 and the correction is exactly the
   identity. If any moves, it is firing where it should not.

## Open for review

Three things this WP decided that a second opinion should confirm. None blocks
anything; all three are cheap to check and expensive to get wrong silently.

1. **The b₂ coefficient contradicts the printed source.** The scan says
   "−0·0375"; this WP implements **−0·3750**. The evidence is circumstantial but
   strong and mutually consistent: −0.3750 hits Rouse's own claimed 0.0035 bound
   against a quadrature of ITC eq. (6.3.3.4) while −0.0375 is off by 0.0821, and
   the paper's own Table 1 entry at µR = 1, sin²θ = 1 (0.2951) matches the
   quadrature (0.29509) rather than the printed formula (0.21303). **What would
   settle it:** one look at a clean copy of Acta Cryst. A26, 682 eq. (2). If the
   paper really prints −0.0375, then the paper has an erratum and the table is
   right — but that is worth knowing rather than assuming.
   *Detectors already in place:* `test_a_wrong_b2_would_fail_the_exact_check`
   and `test_cylinder_absorption_matches_exact_physics_across_mu_r_and_theta`.

2. **µR > 1 is used-but-warned rather than refused.** Outside Rouse's stated
   range the expression is an extrapolation, not a fit. This WP chose to apply
   it anyway with `ABSORPTION_MU_R_OUT_OF_RANGE`, on the grounds that silently
   dropping real absorption from a strongly-absorbing specimen is the worse
   failure. The opposite call — refuse, and make the user supply an explicit µR
   or change the experiment — is defensible. Note the regime matters: LaB6 in a
   0.5 mm capillary at Cu Kα is µR ≈ 34, so "outside the range" is not an exotic
   corner, it is ordinary lab practice.
   *What would settle it:* a view on whether a wrong-but-flagged correction or
   no correction is more useful to the intended user.

3. **The v0.5 milestone criterion was weakened deliberately.** It read
   "capillary/absorption vs GSAS-II consistency" and now reads *algorithm-level*,
   because `tests/data` contains no capillary pattern and this WP could not
   honestly claim dataset-level evidence. The dataset-level check is
   [WP-0508](0508-flat-plate-absorption.md), which needs a capillary pattern with
   a **stated bore diameter and specimen** — the one input that could not be
   sourced from inside the repo. *What would settle it:* an 11-BM mail-in
   dataset (capillary size is usually in the deposited metadata) or any
   published capillary pattern quoting µR.

## References

- Rouse, K. D., Cooper, M. J., York, E. J. & Chakera, A. (1970). *Absorption
  corrections for neutron diffraction.* **Acta Cryst. A26**, 682-691. — eq. (2)
  and Table 1; the implementation and its ground truth.
- *International Tables for Crystallography*, Vol. C, §6.3.3 — (6.3.3.1) A,
  (6.3.3.2) A\* = 1/A, (6.3.3.4) the exact cylinder integral, Table 6.3.3.1 the
  analytic special cases (flat-plate fence).
- Dwiggins, C. W. Jr (1975a). *Acta Cryst.* **A31**, 146-148 — cylinder A\* to
  0.1 %; the source of ITC Table 6.3.3.2. Not obtained; noted for WP-0508.
- Lobanov & Alte da Veiga (1998), 6th EPDIC abstract P12-16 — GSAS-II/TOPAS's
  fit, valid to µR ≤ 3. Cross-code reference only; coefficients unverifiable.
- Hewat, A. W. (1979). *Acta Cryst.* **A35**, 248 — states the scale × Debye-Waller
  factorisation for µr < 1 that this WP measures exactly.

## Handover log

- **2026-07-27 (c)** — **shipped.** All ten checklist items landed across nine
  commits.

  *Measured acceptance.* `cylinder_absorption` matches an ITC (6.3.3.4)
  quadrature to 0.0035 across 0 ≤ µR ≤ 1 × 0 ≤ sin²θ ≤ 1 — exactly the bound
  Rouse claim — and the published Table 1 fixture to the same. The quadrature is
  itself anchored by reproducing the exact mean chord 16/(3π) = 1.69765 to 5 dp.
  End to end, a LaB6 pattern synthesized at µR = 1.0 with Biso = 0.600 Å²
  refines to **0.6031 ± 0.0260 Å² with the correction and 0.1144 ± 0.0260 Å²
  without** — a 0.4887 Å² bias against a 0.4887 Å² closed-form prediction, 18.8σ,
  with **Rwp identical to 1e-5 percentage points** in the two runs. Every backend
  agrees per-column on the new `toy_capillary` state inside the standing
  5e-3 / 0.99999 bars, and the real-data acceptance suite (NAC, SRM 660c, FAP,
  SRM 676a, QPA round robin) is unmoved — none of them sets a capillary radius,
  so µR stays 0 and the correction is the exact identity.

  *Two things a successor should not have to rediscover.* First, the b₂ digit
  transposition and why the published table could not catch it (see above) —
  this is the single most expensive thing in the WP and it is written up in three
  places on purpose. Second, `python -m tests.test_backend_shim` used to
  re-capture **every** golden; it now requires explicit state names, because
  silently rebasing a baseline meant to be a fixed point is the one failure mode
  those files cannot detect themselves.

  *Deliberately not done, with reasons in [WP-0508](0508-flat-plate-absorption.md):*
  flat-plate transmission (needs a sample thickness the schema lacks) and a
  real-data capillary acceptance (`tests/data` has no capillary pattern — every
  real pattern is flat-plate Bragg-Brentano, and 11-BM is fitted with the
  geometry-agnostic preset). The v0.5 milestone row was reworded to say
  *algorithm-level* rather than imply dataset-level evidence that does not exist.

  *One judgement call worth flagging for review:* µR > 1 is used-but-warned
  rather than refused. Refusing would silently drop real absorption from a
  strongly-absorbing specimen, which seemed the worse failure; but it does mean
  the model extrapolates a fit outside its stated range if a user ignores the
  diagnostic.
- **2026-07-27 (b)** — physics re-verified against exact quadrature; **b₂ corrected
  to −0.3750** (the scan's "−0·0375" is a digit transposition) and every derived
  number with it: ΔB is 0.133 Å² at µR = 0.5 and **0.489 Å² at µR = 1.0**, not the
  0.033/0.088 first recorded here. The lesson worth carrying: the published table
  validated the wrong coefficients because the slice used (sin²θ = 0) constrains
  only a₁ and a₂. The ITC (6.3.3.4) quadrature is what caught it, and it is
  therefore the primary gate, not the secondary one. Also measured with it: the
  part of A that a free {scale, Biso} cannot absorb is 0.03 % of intensity at
  µR = 0.1 rising to 1.56 % at µR = 1 — strong degeneracy, but not the
  "identically zero" claimed below, which was an artefact of eq. (2) being
  separable *by construction* rather than a statement about the physics.
- **2026-07-27** — expanded from a stub into a full WP and started.
  *Done:* the physics is settled, and the degeneracy is measured rather than
  assumed — within eq. (2), `ln A` is exactly {1, sin²θ}, so applying the
  correction is an exact reparameterisation of the scale and Biso and ΔB = c·λ²/2
  is the entire physical content of the correction.
  *Decisions, taken with the user and not to be re-opened:* cylindrical only
  (flat-plate → WP-0508); Rouse rather than Lobanov, because Lobanov's
  coefficients trace only to an unobtainable conference abstract and carry a
  θ-dependent ~2.7 % branch step at µR = 3; **µR computed-and-fixed, not
  refinable** — this reverses an earlier working assumption once the degeneracy
  was measured, and reversing it back would reintroduce a near-singular column.
  *Gotchas:* the Rouse-table offset-label trap (above) — a naive read misses by
  0.055 rather than 0.0015; and the hidden-Jacobian hazard, since A multiplies
  the same product that `_structural_intensity_grad` and `po_intensity_grad`
  rebuild by hand.
  *Next:* the ground-truth fixture, then the schema.
- **2026-07-22** — created as a stub from the ROADMAP split.
