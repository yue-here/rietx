# WP-1132 — a neutron µR, from the table this package already ships

Milestone: unscheduled · Status: ✅ 2026-11-08 — items 1–6 (PR #541) and #543's Brindley µ (PR #576) landed; a validation against a measured µR, the capabilities field and a resonance-aware refusal are issue #1467
Track: The specimen is not an angle, and the neutron follow-through
Depends on: the CW neutron source (PR #108, open) — `NeutronSource` and
`crystallography/neutron.py` are both prerequisites and both land there

## Goal

`Geometry.mu_r` and `Geometry.mu_t` can be **estimated from composition on a
neutron instrument**, from the Sears table this package already ships, with
the same "estimate, or say why not" contract the X-ray path has. Today the
estimator is fenced off from neutrons entirely (PR #108,
`refine._NON_XRAY_ABSORPTION_ESTIMATE`), which is correct but leaves a
neutron capillary fit with no absorption correction unless the user measured
µR themselves.

## Context — why the X-ray estimator is not merely coarse here

`crystallography/attenuation.py` is an **X-ray** compilation: photoabsorption
plus scattering, cross-checked against the Cromer-Liberman f'' table. Running
it on a neutron instrument does not give a rough answer, it gives an unrelated
number, and the two disagree in **kind**, not in precision:

| | X-ray µ/ρ | neutron µ |
|---|---|---|
| λ dependence | ≈ λ³ between edges | σ_abs ∝ **λ** (1/v), σ_scatt flat |
| discontinuities | absorption edges | nuclear **resonances** (isotope-specific) |
| Z dependence | rises steeply and smoothly with Z | no trend in Z at all |
| hydrogen | nearly transparent | one of the strongest attenuators (σ_inc = 80.27 barn) |
| isotopes | identical | up to 3 orders apart (¹⁶⁸Yb 2230 barn vs ¹⁷⁶Yb 2.85) |

The hydrogen row is the one that matters in practice: an organic or hydrous
specimen that an X-ray estimator calls transparent is the specimen a neutron
beam struggles to get through. Writing the X-ray number into `Geometry.mu_r`
would apply a confidently wrong correction with nothing said — the failure
this repo's own rules rank worst.

## What makes it tractable

**The table is already here.** PR #108 ships
`crystallography/neutron.py` over Sears (1992) / *International Tables* C
Table 4.4.4.1, whose `properties()` already returns `sigma_coh`, `sigma_inc`
and `sigma_abs` per species. Nothing new needs licensing or digitising.

The physics is one line, and unlike the X-ray case it has no edges to
interpolate across:

```
mu(lambda) = ( sum_i n_i * [ sigma_abs_i * (lambda / 1.798) + sigma_coh_i + sigma_inc_i ] ) / V
```

with `n_i` the occupancy-weighted atom count per cell, `V` the cell volume in
Å³, σ in barn, and **1.798 Å** the 2200 m/s wavelength at which σ_abs is
tabulated. µR and µt then reuse `attenuation.packed_mu_r` and the flat-plate
twin unchanged — the packing-fraction and geometry half is radiation-blind
and must not be duplicated.

## Checklist (commit-sized)

1. `crystallography/neutron.py`: `linear_attenuation_neutron(element_counts,
   volume, wavelength)` beside the existing `b_coh`/`properties`, citing Sears
   1992 in the docstring per the house rule. Its own test: σ_abs must scale
   **linearly** in λ (the 1/v law is the whole difference from the X-ray case),
   and a hydrogen-bearing composition must come out far *more* attenuating than
   the X-ray estimator says for the same cell — a test that would fail if the
   X-ray table were wired in by mistake.
2. `optimize/qpa.py`: dispatch `estimate_capillary_mu_r` /
   `estimate_flat_plate_mu_t` on `instrument.source.kind` rather than assuming
   X-ray. One seam, not two code paths — the volume-fraction weighting,
   packing fraction and geometry are shared, only µ per phase differs.
3. `refine.py`: `_resolve_specimen_absorption` stops returning
   `_NON_XRAY_ABSORPTION_ESTIMATE` for `neutron_cw` and estimates instead;
   `estimate_mu_r` likewise. **Keep the fence for every source that still has
   no table** — it is the mechanism that made this WP visible, and deleting it
   wholesale would re-open the hole for TOF.
4. **Refuse rather than guess where the table cannot answer**: a resonant
   absorber (`is_resonant_absorber`) at a λ near its resonance, where the
   thermal σ_abs is wrong in principle rather than merely imprecise. This is
   the neutron analogue of the X-ray "wavelength straddles an edge" reason and
   should read the same way. See also issue #113 (TOF resonant absorption).
5. Validate against a real measurement — the Cr₂WO₆ BT-1 60 K histogram
   (λ = 2.078 Å) is the obvious candidate, since a heavy W-bearing oxide in a
   vanadium can is where µR is least negligible.
6. Manual: a row in the specimen-absorption section of Part 2 with a
   `*Source:*` line, and Part 1 prose saying an estimate now happens on
   neutron instruments.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_neutron_cw.py tests/test_qpa.py \
    tests/test_acceptance_capillary.py -q
```

plus the estimated µR for the Cr₂WO₆ case quoted against a hand-computed value
from the Sears table, and the X-ray control in
`tests/test_neutron_cw.py::test_the_xray_control_still_estimates` still green —
that test exists precisely so a future change here cannot quietly turn X-ray
estimation off.

## Deliberately not in scope

- **Energy-dependent σ_abs near a resonance.** Item 4 *refuses* there; making
  it answer is issue #113's subject and needs a tabulation this package does
  not have.
- **TOF.** A bank spans a range of λ, so µ varies within one histogram; the
  v2 fence covers it.
- **Making µR refinable.** It is exactly singular against scale ⊗ Biso
  (`model/absorption.py`), and that is unchanged by the radiation.

## Handover log

- **2026-11-08** — closed (ghostshift runner, PR #1469; no code changed). What this WP set
  out to give is shipped: a neutron capillary or flat plate with a declared size now gets an
  absorption correction estimated from the Sears table, a source with no table is refused
  rather than given the X-ray number, and the Brindley correction reads the neutron µ. What
  it never had was a measurement to check the estimate against, and none can come from a
  fit, so that, the capabilities field and a narrower resonance refusal move to issue
  #1467 rather than holding the WP open.

  *Checked before closing.* The six checklist items are PR #541 (`fd8026a3`) and the
  `### Inherited` #543 entry is PR #576 (`03870fec`), both ancestors of `main` at
  `63d7c120a`; #117 closed with #541. The 2026-10-01 entry's *Next*, the nuclide-mass rule
  beside ZM = Σ occ·m·A in Part 2, landed in `aa3c611c5` and now reads at
  `docs/docs/theory/corrections.md:439`. The contributor's fork-local `pr/tof-*` branches
  (`pr/tof-t2t3-20261102`, `pr/tof-t2t3-20261106`, `pr/tof-t5-20261106`,
  `pr/tof-t6-20261106`, and one worktree detached at `f4be484d6`) carry 12 to 32 unlanded
  commits each, all the TOF track's T-2 to T-6. One of them (`c0fc9c9d4`)
  adds a TOF µ(λ) over the same Sears table, but TOF is this WP's *Deliberately not in
  scope*, and none carries a `WP-1132:` commit.

  *Left, in issue #1467.* (1) Item 5 stays a hand check at an assumed R = 3.0 mm
  (µR = 0.135045 on HB-2A), since the tree holds no measured neutron µR. (2)
  `capabilities().radiations` does not read `qpa.LINEAR_ATTENUATION_BY_SOURCE`, so a
  client cannot tell before a fit whether µR will be estimated. (3) Item 4 refuses every
  `RESONANT_ABSORBERS` species at every λ until resonance energies are cited, which
  overlaps #113. The `### Inherited` section was consumed (#543, #117) and is deleted
  with the Priority line.

  *Not run:* the code review (a prose-only branch), the fast suite (no code or test
  changed), the generality judge (no heuristic added).

  *Next:* none here. Issue #1467 is the maintainer's to schedule.

- **2026-10-01** — A neutron fit that sets `particle_radius_um` now takes its
  Brindley correction from the neutron attenuation, so #543's silent wrong
  weight fractions are gone. A structure written with a nuclide (`D`, `2H`,
  `7Li`) now runs QPA and weighs the nuclide as itself. *Done:* PR #576
  (`839321a4`), merged as `03870fec`, closing #543 and #556 follow-up 1.
  `LINEAR_ATTENUATION_BY_SOURCE` now maps a source kind to a per-phase µ that
  takes a `ZMV`. X-ray reads `element_counts`, neutron reads the new
  `species_counts`, and `CompiledModel.source_kind` is frozen at compile.
  *Checked by the review:* the test is #543's NaCl + W reproduction on HB-2A's
  λ, against Sears µ computed by hand, with an arm that fails on the old code.
  Every species a neutron fit can compile resolves: `D` and `2H` both give
  0.306 cm⁻¹ against H's 3.29 (4 atoms in 100 Å³, 1.54 Å). X-ray numbers do
  not move. *Gotchas:* `qpa.element_symbol` now maps `D` to `H`, while
  `gui/structure3d.py` keeps its own parser that passes `D` through. The
  nuclide-mass rule (²H at 2.0141, otherwise the mass number A, within 0.26 %
  above A = 4) is in Part 1 and the docstring, but not beside
  ZM = Σ occ·m·A in `docs/manual/corrections.md:352`. *Next:* that Part 2
  sentence, then the `### Inherited` items.

- **2026-09-29** — Items 1–6 landed on PR #541, one commit each. Four places
  where the tree differs from this file's text. (a) Step 5 and the Acceptance
  line name a Cr₂WO₆ **BT-1** 60 K histogram at 2.078 Å. The tree has no BT-1
  file, so the check runs on the vendored **HB-2A** instrument instead
  (`gsas2_hb2a_cr2wo6.prm`, λ = 2.4067 Å), as Yue confirmed on the PR. No
  vendored file states a sample radius, so R = 3.0 mm is an *assumption*,
  named as one in the test. Estimate and hand value agree: µR = 0.135045 at
  packing 0.6. That is arithmetic, not a validation against a measurement.
  None is in the tree, and a capillary fit cannot supply one, since µR is
  exactly scale ⊗ Biso. (b) "Far more attenuating than the X-ray estimator
  says" is false in absolute terms at a common λ: brucite at 2.4067 Å gives
  ≈ 206 cm⁻¹ X-ray against ≈ 4.35 neutron. The test therefore asserts the
  *share* hydrogen carries: ≈ 93 % of the neutron µ against < 1 % of the
  X-ray one. (c) The tree carries no resonance energies, so item 4 refuses
  for every `RESONANT_ABSORBERS` species at every λ. A narrower "near the
  resonance" rule needs cited energies. (d) The fence constant is renamed
  `_NO_ATTENUATION_TABLE_ESTIMATE`, because `neutron_cw` now has a table.
  No TOF source kind exists in the tree yet, so the fence is tested by
  removing the neutron entry from `qpa.LINEAR_ATTENUATION_BY_SOURCE`. Not
  done here: the Brindley microabsorption path (`qpa._apply_microabsorption`)
  still reads the X-ray table whatever the source, and a mass-numbered
  species (`157Gd`, `2H`) cannot enter the QPA composition
  (`qpa.element_symbol`).

- **2026-08-24** — Specified while fixing two defects found in PR #108's own
  code. First, `Instrument.constant_wavelength_neutron` wrapped `mu_r` in a
  `Parameter` where `Geometry.mu_r` is a plain float, so *every* call passing
  a µR raised `ValidationError`; no test passed one, which is why it survived.
  Second, and worse, `_resolve_specimen_absorption` runs **automatically** at
  fit time, so a neutron capillary with a declared radius was silently having
  an X-ray µR computed and written onto it. Both fixed in PR #108; the fence
  and this WP are what the second one turned into.

- **2026-09-30** — PR #541 merged (`fd8026a3`, closing issue #117) after three
  review rounds, on a stacked gate with #532, #546 and #522 (fast 7156 passed /
  101 skipped, slow 234 passed / 12 skipped; macOS arm64, `[dev,jax]`).
  - **What the rounds changed.** Round 1 found #530's radiation-keyed pin
    failing on merged main (the neutron histogram now gets a µR), so the row
    is keyed on the table each histogram reads. It also found the X-ray µ/ρ
    described as falling as λ⁻³ at five sites (it rises as λ³, measured
    exponent 3.04 for O between 1 and 2 Å) and the Sears cross-sections
    described as free-atom (they are the bound values, H 82.0 b against 20.5 b
    free). Round 3 is a docstring: the bound-value test checks a *mixed*
    table, not a self-consistent free-atom one.
  - **What it does not do.** Step 5 remains a hand check at an assumed 3.0 mm
    radius, not a validation against a measurement, so the WP stays open.
    The Brindley path on neutron is #543. `Capabilities.radiations` reading
    `LINEAR_ATTENUATION_BY_SOURCE` is unbuilt.
