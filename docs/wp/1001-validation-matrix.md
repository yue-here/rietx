# WP-1001 — Validation matrix + tolerance policy

Milestone: v1.0 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Validation matrix green: NIST certificates as **absolute anchors** (with
  stated uncertainties); GSAS-II as a *consistency* check with tolerances
  that respect legitimate inter-code convention differences (not 1e-4 Å
  ground truth)
- Three-tier tolerance policy documented per test (exact / tight-scientific /
  statistical)

## Context pointers

- [../DESIGN.md](../DESIGN.md#testing--validation-policy) — the policy this
  formalises, including both v0.2 lessons (protocol adoption; disagreement
  shape as evidence).
- Existing anchors: SRM 660c (absolute), FAP (cross-code), NAC (synchrotron)
  — see `tests/data/README.md` and `docs/milestones/`.

## Inherited

From **WP-0508** (flat-plate absorption, landed 2026-07-28) — a new suite, a
new *kind* of tolerance, and a dataset with a documented circularity.

- **An eighth acceptance suite exists**: `tests/test_acceptance_capillary.py`
  (slow, ~17 s), on `11BM_LaB6_660a.fxye` — NIST SRM 660a LaB₆ at APS 11-BM in
  the beamline's documented 0.81 mm Kapton bore.
- **Its tolerances are a tier the matrix does not yet have: *identity*
  tolerances.** The capillary correction is an exact reparameterisation of
  {scale, Biso}, so the assertions are |ΔRwp| < 1e-6, |Δa| < 1e-9 Å and
  |ΔB − predicted| < 1e-5 Å² *between two fits*, not agreement with an external
  value. Measured margins are 3e-8, 8e-12 and ~1e-7, i.e. two to four orders
  inside the bars. This tier is not referenced to a certificate, to a
  participant spread, or to σ — it is referenced to floating-point arithmetic,
  and the policy should name it rather than force it into an accuracy band.
- **The cell from that dataset must never enter the matrix as an anchor.** λ was
  calibrated at the beamline against LaB₆ itself (`# Calibration from:
  .../11bmb_3843.calib`), so a refined LaB₆ cell reproduces the standard by
  construction. It lands 16 ppm from the SRM 660a certificate, which is worth
  recording as consistency and nothing more. The absolute anchors stay SRM 660c
  and SRM 676a.
- **The v0.5 milestone record ends with a table this WP should adopt**
  ([../milestones/v0.5.md](../milestones/v0.5.md)): for each of the eight
  corrections, Δ Rwp versus what it actually changes. Not one of the eight is
  well judged by Δ Rwp — two cannot move it, one moves it the wrong way when it
  is right, and the two largest accuracy wins are invisible in it. A validation
  matrix whose columns are agreement indices would score this milestone as
  having delivered nothing.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — two measured ceilings
that a tolerance policy written from certificates alone would violate.

- **SRM 676a is a `c/a` anchor, not an absolute-axis anchor.** Measured c/a is
  +30 ppm vs certificate, but the absolute axes are −313/−283 ppm — a uniform
  lab d-scale systematic, asserted as such rather than absorbed into a widened
  band. A tolerance written against the certificate's own ±8e-6 would be
  unmeetable by construction on lab data. The tier this belongs in is
  "certificate-grade on the *ratio*, systematics-limited on the scale".
- **The achievable GoF for analytical-PSF lab fits is floor-limited at
  1.5–1.9** (Cline et al. 2015, J. Res. NIST 120, 173, for this instrument
  class; FPA reaches 1.08 and is fenced to v2). Measured 1.61 on corundum with
  Rexp ≈ 8.9 %, so Rwp = 14.4 % is mostly counting statistics, not misfit. A
  policy demanding GoF → 1 would be demanding FPA.

From **WP-0507** (anode wavelengths, landed 2026-07-28) — **every acceptance
number in the repo is a Cu measurement, and that is now a stated gap rather
than an unstated assumption.** Six anodes ship (Cr/Fe/Co/Cu/Mo/Ag, plus Kα1-only
variants); none but Cu has a dataset behind it, so what is validated is the
*table and its checks*, not a refinement at those wavelengths. Two things for
the matrix:

- **A non-Cu dataset is the single cheapest new tier** — Co Kα on an Fe-bearing
  specimen is the routine real case (Cu Kα fluoresces Fe: µ/ρ = 297.7 vs 56.2)
  and would exercise the parts of the chain that are wavelength-dependent all
  at once: dispersion (f′ = −3.3 e for Fe at Co Kα, 180 eV under its K edge),
  absorption, and the per-anode Kβ contamination check.
- **Wavelength scale is a validation axis of its own.** All six anodes come from
  one column of one evaluation (NIST XRTE SRD 128) and the shipped Cu pair is
  bit-identical to it; a test asserts that, because if the table were ever
  re-sourced, every cell in `tests/data` would move with it and *no other
  assertion in the suite would notice*. Any tolerance policy on cell parameters
  is downstream of that assertion — the SRM 676a ±30 ppm result above is
  measured on this scale.

From **WP-0505** (sequential series, landed 2026-07-28) — a new acceptance
suite, and a *tier* the policy does not yet name.
`tests/test_acceptance_sequential.py` refits the eight round-robin sample-1
mixtures as a warm-started chain under the v0.3 QPA protocol imported wholesale
from `test_acceptance_qpa_roundrobin`, so what it measures is the chaining and
nothing else. Its assertions are the *same* participant-spread tolerances, plus
a "chained agrees with independent" band of 1 wt %. Two consequences:

- **The comparison target is this package's own other result**, not a
  certificate and not another code — a third kind of anchor beside the
  absolute (SRM) and cross-code (GSAS) ones the scope names, and the tier it
  belongs in is closer to "exact" than either: two runs of the same protocol
  differing only in starting values should agree far inside any physical
  tolerance, and 1 wt % is generous rather than tight.
- **Its numbers move when the round-robin protocol moves.** The chained pass
  reproduces the v0.3 independent-fit record exactly (RMS |ΔW| 2.26 wt %, worst
  5.13, mean Rwp 0.1278) because it *is* that protocol; the WP-0504 note above
  about re-measuring if dispersion is switched on by default therefore applies
  to this suite too, in lockstep.

From **WP-0401** (op shim, landed 2026-07-24): current baselines to write the
matrix against are SRM 660c Rwp 8.66 % and NAC Rwp 9.31 % (unchanged across the
shim refactor, verified bit-identical). SRM 660c's cell sits +28 ppm from the
CIF block value under an explicitly *interim* ±2e-4 Å band — the residual bias
there is unmodelled equatorial divergence, tube tails and monochromator
passband, i.e. the same FPA territory.

From **WP-0503** (Stephens anisotropic strain, landed 2026-07-27) — **do not
name Hamilton's R-ratio test as the arbiter of "are these parameters
justified".** Measured on the 7251-channel round-robin patterns: at α = 0.05 it
blesses a *0.13 %* χ² improvement from three inert parameters on corundum
exactly as it blesses a real 6.9 % one on brucite. Hamilton's threshold does
not grow with the channel count, so on modern step-scanned patterns almost any
added parameter clears it. ΔBIC separated the same pair by +488 vs −17 (its
ln(N) penalty does grow with N), and is the statistic the policy should quote.
Both are already implemented in `report/layer2.py`.

Also from WP-0503, a third acceptance *shape* the policy should recognise
alongside "absolute anchor" and "cross-code consistency": **a test that asserts
a model is inadmissible.** `tests/test_acceptance_stephens.py` asserts that an
Rwp improvement both statistical tests bless is nonetheless rejected by a
physics guard (the strain-variance cone), on real data. That tier is neither
exact nor statistical — it is "characterisation", the same tier round-robin
sample 4 occupies for microabsorption, and the matrix needs a name for it.

From **WP-0504** (anomalous f′/f″, landed 2026-07-27) — **every acceptance
number recorded in `docs/milestones/` was measured with dispersion OFF, and
turning it on is the right default for v1.0.** `Source.dispersion` shipped
opt-in precisely so that landing it did not invalidate the record; flipping the
default is a re-measurement of the whole matrix, and that is this WP's job.

What the flip is worth, measured, not projected: on the eight IUCr round-robin
sample-1 mixtures under the *identical* v0.3 protocol, the QPA error goes from
RMS 2.26 → **0.69 wt %** and worst |ΔW| 5.13 → **1.39 wt %**. It also
**re-derives a v0.3 conclusion**: the signed bias shape v0.3 attributed to
untreated microabsorption is mostly neglected dispersion (the giveaway was
fluorite coming back *high*, which microabsorption could not explain).
`test_sample1_bias_has_the_dispersion_shape` carries the corrected reasoning
while still asserting the dispersion-off shape, because that suite deliberately
stays comparable to v0.3.

Three consequences for the policy:

* Numbers to re-measure when the default flips: every QPA figure in
  `milestones/v0.3.md`, and the lab Rwp/Biso baselines (SRM 660c moves Rwp
  8.661 → 8.640 % and B(La)/B(B) by 12 %/22 % — the cell does **not** move,
  4.156895 Å either way, so the absolute anchor is safe).
* The **`DISPERSION_NEGLECTED` diagnostic** (`refine.py`) already names which
  species and by how much. A validation matrix entry that runs dispersion-off
  should assert the diagnostic is present, not merely tolerate it.
* This is a fourth acceptance shape, alongside 0503's "assert a model is
  inadmissible": **a pre-registered prediction about numbers already
  recorded.** The prediction here was parameter-free (each phase's Bragg power
  ratio), written into the WP before the refits, and beat itself (predicted RMS
  0.83, measured 0.69). The matrix should have a name for that tier — it is
  much stronger evidence than a tolerance being met.

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
