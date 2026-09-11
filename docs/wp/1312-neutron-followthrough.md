# WP-1312 — CW neutron follow-through: the seed, the resonant flag, the joint fit

Milestone: unscheduled · Status: ⬜
Depends on: — (WP-1132 is the maintainer's and does not gate any task here)

## Goal

The three loose ends the CW-neutron landing left are closed: the
`constant_wavelength_neutron` seed matches its own docstring, a resonant
absorber in a structure is named instead of silently mis-tabulated, and a
combined X-ray + neutron joint refinement is exercised, verified and
documented rather than merely admissible.

## Context

From issues #124 (maintainer-filed, fix stated), #113 item (a) (the cheap
slice; the rest is fenced), and #194 (verify, don't build).

**1. The seed (issue #124).** `Instrument.constant_wavelength_neutron(...,
fwhm_deg=...)` seeds `w = (0.5·fwhm)²` *and* `x = fwhm`. `w` gives a constant
Γ_G = fwhm/2, which is right; `x` is the Lorentzian Scherrer term
Γ_L = X/cosθ, so the full-FWHM seed both double-counts the width and makes it
strongly angle-dependent. Measured at fwhm_deg = 0.3, the seeded TCHZ FWHM
is 0.369° at 2θ = 20 (1.23×), 0.405 at 60, 0.474 at 90, 0.637 at 120,
**1.179 at 150 (3.93×)** — over exactly the high-angle peaks a CW neutron
cell refinement leans on hardest. Not a correctness bug (the terms refine
afterwards; every #108 fit converged) but three things make it worth fixing:
the docstring promises the observed width; the frozen per-stage windows are
sized from the seed, so the over-width is paid at every stage compile; and
the shape is wrong as well as the size — a real CW neutron resolution
function is narrowest near the focusing angle (Caglioti, Paoletti & Ricci
1958), and a monotonically widening seed is not a coarse version of that.
**Fix: seed `w` alone**; test asserts the seeded FWHM stays near `fwhm_deg`
across 20–150°, not only at low angle; a line in WP-1134's record.

**2. The resonant flag (issue #113 item a).** `crystallography/neutron.py`'s
Sears table ships `RESONANT_ABSORBERS` (Cd, Sm, Eu, Gd). Natural Yb belongs
in it: σ_abs 34.80 barn (14× Ru's 2.56) with an isotopic spread of nearly
three orders (¹⁶⁸Yb 2230.40 vs ¹⁷⁶Yb 2.85 barn) — absorption that large and
that isotope-dependent *is* a nuclear resonance, and a resonance is
energy-dependent, which the thermal table cannot express (the module's own
fence says so). The cheap, honest slice: add Yb, and emit a diagnostic when a
resonant absorber sits in a refined structure — the neutron analogue of
"this wavelength straddles an absorption edge", needing only the species
list plus a cited resonance energy per nuclide. The energy-dependent
correction itself (σ_abs(λ), the S(Q)-level utility) **stays fenced** with
TOF; issue #113 holds that design.

**3. The joint fit is admissible and unexercised (issue #194).**
Multi-histogram refinement ships (`multi.py`, WP-0308) and is stacked per
Von Dreele (1997), *J. Appl. Cryst.* **30**, 517 — the combined
X-ray/neutron paper itself. Nothing in `params/multi.py` restricts radiation
kind, and CW neutron landed in WP-1134 — so a mixed fit is structurally
admissible **today**, and no test or example runs one. Three tasks the issue
lists: an acceptance/example of a genuine X-ray + neutron joint fit on one
shared structure (source a public dual dataset — search the maintainer-local
paper corpus before asking); an audit that per-histogram physics keys on the
histogram's **own** radiation across a mixed fit (anomalous dispersion — on
by default, X-ray-only — must no-op cleanly on the neutron histogram; b vs
f(Q); polarization vs none; the WP-1134 paths); and a check that the
shared-vs-per-histogram parameter split holds when the two histograms weight
structure factors differently. WP-1134's own log notes three defects found
only by *combining* parts on a single path — the same argument for
exercising this combination.

### Inherited

- **2026-09-02, from the magnetic scattering track
  ([1327](1327-magnetic-structure.md)): the joint-fit audit gains a third row
  when the moment lands.** Task 3 here audits that per-histogram physics keys
  on the histogram's own radiation (dispersion no-ops on the neutron arm, b
  against f(Q), polarisation against none). 1327 adds a magnetic term that
  enters a `neutron_cw` histogram only and is identically zero on an X-ray
  one, so shape the audit as a table keyed on the source kind that a new
  term joins with one row, rather than three hand-written checks. Nothing to
  build here for it now.
- **2026-09-03, from the issue triage (issue #252): the joint fit has now
  been exercised from outside.** An outside campaign ran a converged
  two-histogram X-ray + neutron fit on one shared structure (41 free
  parameters, Rwp 0.088, GoF 1.47) — evidence for task 3's "admissible and
  unexercised", though not the audit it asks for. What that run found missing
  is reporting and telemetry (`summary`/`report`, `events=`,
  `max_shift_over_esd`), which is
  [1341](1341-a-joint-fit-has-no-report.md), not this WP.

## Non-goals

- **Not the neutron µR estimator** —
  [1132](1132-neutron-specimen-absorption.md), the maintainer's, checklist
  already written. Its absence does not gate any task here (declare no µR on
  the neutron histogram in the example, as every fit does today).
- **Not σ_abs(λ), S(Q) reduction, or anything TOF** — fenced; issue #113
  holds the design.
- **Not new physics.** Every task verifies, seeds, or names; none adds a
  correction.

## Tasks

- [ ] Seed fix: `w` alone; the 20–150° FWHM assertion; the WP-1134 record
      line. In flight as PR #280, held on the `ProfileTCHZ.w` bound —
      decided 2026-09-11, see the entry.
- [ ] ~~Yb into `RESONANT_ABSORBERS`; the resonant-absorber diagnostic;
      skill row~~ — landed from outside, PR #282 (`8c39a02c`). **Left: a
      cited resonance energy per member**, which that PR deliberately
      declined for want of a citation (2026-09-11 entry).
- [ ] The mixed-fit acceptance/example (public dual dataset, provenance row)
      + the radiation-kind audit, any fix it forces landing as its own
      commit; obs/calc/diff PNGs for both histograms to `tests/output/`.
- [ ] Manual: the joint-refinement section states what is shared, what is
      per-histogram, and which corrections key on radiation kind.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_neutron_cw.py tests/test_multi_histogram.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the seeded FWHM tracks `fwhm_deg` across the range; the diagnostic
fires for an Yb-bearing structure and is silent for Ru/O; the mixed fit
refines one structure against both histograms with dispersion active on the
X-ray one only, and the audit's findings (if any) each carry a test.

The shipping PR carries `Closes #124`, `Closes #194`, and a comment on
issue #113 saying its (a) slice landed — #113 stays open for the fenced
(b)/(c) halves.

## References

- Issues #124, #113, #194; PR #108 / WP-1134 — where the seed and the fence
  landed.
- Caglioti, G., Paoletti, A. & Ricci, F. P. (1958), *Nucl. Instrum.* **3**,
  223 — the CW neutron resolution function.
- Von Dreele, R. B. (1997), *J. Appl. Cryst.* **30**, 517 — combined X-ray +
  neutron Rietveld refinement.
- Sears, V. F. (1992), *Neutron News* **3**(3), 26 — the shipped table.

## Handover log

### 2026-09-11 — two of the three tasks landed from outside, and this WP never opened

A CW neutron refinement now tells you when the structure contains an element
whose tabulated scattering length cannot describe it. That is task 2, live in
the package since PR #282 merged (`8c39a02c`), and it arrived from an outside
contributor rather than from a session on this WP — which is why this entry
exists at all: nothing in the tooling would have asked for one, because the
merged commits carry no `WP-NNNN:` prefix and the merge touched no file under
`docs/wp/`. Task 1, the seed fix, is PR #280, reviewed and held on one
decision that is recorded below. The WP itself stays `⬜`: no session owns it,
and the two remaining halves are real work rather than paperwork.

**Done — task 2, in part.** `RESONANT_ABSORBERS` gains natural `Yb` and
`168Yb`, and `refine._resonant_absorber_diagnostics` emits
`NEUTRON_RESONANT_ABSORBER` when such a species sits in a structure being
refined against a non-X-ray source. It reports and never refuses, because one
constant wavelength away from the resonance the thermal value is the right
number. Severity splits on `RESONANT_ABSORBER_SEVERE_BARN = 1000.0`: `warning`
for the four classic black absorbers (Cd 2520, Eu 4530, Sm 5923, Gd 49700),
`info` for Yb, whose element absorbs 34.80 and whose resonance lives in the
0.13 % minority `168Yb` at 2230.40. The skill row landed in all three
committed copies.

**Deliberately not done, and this is what keeps the task open.** The checklist
asks for "a cited resonance-energy entry per member" and the PR ships none.
The reason given is the right one: the energies need a citation this package
does not carry (Mughabghab, *Atlas of Neutron Resonances*, is the usual
source) and transcribing them from memory is a failure this campaign has
already met once. So the flag says *that* a species is resonant and cannot yet
say *where*. Whoever picks this up needs the Atlas or an equivalent, and the
maintainer-local paper corpus is the first place to look.

**Measured** (bench worktree, `[dev,jax]`, macOS arm64, `-n auto --dist
loadgroup`, nothing else in the suite), on PR #282 merged onto `origin/main`
`ff69ec34`:

| | measured |
|---|---|
| fast selection | 4534 passed, 78 skipped, ~2m14s |
| fast selection, main alone | 4529 passed, 78 skipped, ~2m31s |
| full suite including `-m slow` | 4703 passed, 83 skipped, ~23 min |

+5 passed, no new skip — exactly the five new test functions. The full run is
the one that carries: `ci.yml` runs `-m "not slow"` and `nightly.yml` has no
`pull_request` trigger, so no acceptance suite ever sees a PR.

**Decided — task 1's held item (2026-09-11).** PR #280 seeds `w = fwhm_deg²`,
which is right, and in doing so narrows the widths the constructor accepts:
`ProfileTCHZ.w` declares `max = 1.0` deg², so the old `(0.5·fwhm)²` accepted
`fwhm_deg` up to 2.0° and the correct seed accepts 1.0°. **The bound stays at
1.0 and the constructor refuses by name.** Three reasons, in the order they
decided it:

1. *The narrowing is nominal.* The old upper range never produced a correct
   profile — at `fwhm_deg = 2.0` the old seed gave Γ_G = 1.0°, half the width
   asked for, plus a Lorentzian `X = 2.0` climbing as 1/cosθ. Nothing correct
   is being taken away.
2. *Widening is not local.* `min`/`max` are serialised fields and refinement
   bounds both, so raising the schema default changes the search box of every
   newly built instrument, laboratory X-ray included, where `help.py` puts the
   typical `w` at 0.001-0.02 — 1.0 is already 50× the top of that range. It is
   also an observable change to a serialised default, which under the
   bump-per-observable-change rule owes a `SCHEMA_VERSION` bump. That is a
   broad cost for a rare case.
3. *The rare case is already expressible.* The bound is per-`Parameter`, not
   global: `inst.profile.w = Parameter(value=1.44, min=0.0, max=4.0,
   unit="deg^2", transform="softplus")` works today and round-trips through
   `model_dump`/`Instrument(**d)` with `max = 4.0` intact (verified on
   `8c39a02c`). A genuinely coarse instrument states itself explicitly, which
   is the right place for that claim to live.

What is actually defective is the message. `fwhm_deg = 1.2` currently dies in
pydantic naming `w` and the number 1.44, neither of which the caller typed.
The fix asked for on #280 is a refusal in the constructor naming `fwhm_deg`,
its seeded `w`, the declared bound read off the field rather than restated,
and the one-line escape above.

**Gotcha for task 3, found while reviewing #282 and worth more than the PR
that found it.** `_dispersion_diagnostics` is called only from `Refinement`
and never from `multi.py`, so a joint fit loses `DISPERSION_NEGLECTED`
entirely — and the new `_resonant_absorber_diagnostics` is wired in beside it
and inherits exactly that gap. This is task 3's "audit that per-histogram
physics keys on the histogram's own radiation" arriving as a concrete defect
rather than a hypothesis. It is **not** being fixed here: WP-1344, open in
PR #297, owns how `multi.py` decides which diagnostics a histogram is
entitled to. No `### Inherited` note has been pushed there because that WP's
file does not exist on `main` yet and a live session holds it.

**Gotcha — the closing protocol no longer fits.** This WP's Acceptance
section assumes one shipping PR carrying `Closes #124`, `Closes #194` and a
comment on #113. The work is arriving piecemeal from outside instead: PR #282
covers #113(a)'s species half, #280 covers #124, and #194 is untouched.
Issue #113 still needs its comment saying the (a) slice landed, and it has
not been posted.

**Next**, in order: settle #280 with the named refusal and merge it, which
closes task 1 and issue #124; comment on #113(a); then task 3, whose first
open item is still sourcing the public X-ray + neutron dual dataset, now with
the `multi.py` diagnostics gap above as a known finding waiting for WP-1344.

- **2026-09-01** — created, from issues #124/#113(a)/#194 (2026-09-01
  triage). Settled: three verbs — fix the seed, name the absorber, exercise
  the joint fit; first open item is sourcing the public X-ray + neutron
  dual dataset.
