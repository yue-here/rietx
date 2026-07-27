# WP-0507 — Additional anode wavelengths (Co/Cr/Fe/Mo/Ag)

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope

Extend the emission-line table so lab data from anodes other than Cu is a
one-argument change, not a hand-built `Source`. Today `_RADIATIONS`
(`src/pxrdref/schemas/instrument.py:336`) carries only `CuKa`; the code
comment immediately above it (`:334`) already anticipates the others:

> Other anodes (Co, Mo, …) will be added once their values are transcribed
> and checked against Deslattes et al. (2003), Rev. Mod. Phys. 75, 35.

## Context pointers

- The Kα1/Kα2 **peak** wavelengths (not the centroid Kᾱ) are what the
  doublet model wants, on a single consistent scale — mixing scales is the
  classic ~100 ppm cell error. Sources:
  - **Co, Cr, Fe Kα** — Hölzer et al. (1997), *Phys. Rev. A* 56, 4554
    (already cited in ATTRIBUTION.md for Cu; the same paper tabulates these).
  - **Mo, Ag Kα** — Deslattes et al. (2003), *Rev. Mod. Phys.* 75, 35
    (already named in the code comment at `instrument.py:334`).
- Add each anode as a `(Kα1, Kα2)` tuple to `_RADIATIONS`; the
  `Instrument.bragg_brentano` / doublet constructor already builds the two
  `EmissionLine`s and the Kα2/Kα1 weight from whatever tuple it finds, so no
  forward-model change is needed — this is a data-table extension.
- Kβ is a separate concern (filtered out in most lab setups); leave it out of
  the default tuples. A `Wβ`-style contamination check already exists for W
  Lα1 (Bearden 1967) and is the pattern to follow if Kβ is ever wanted.

### Inherited

From **WP-0504** (anomalous f′/f″, landed 2026-07-27) — **check each new anode
against the dispersion table, not only against the wavelength references.**
Anomalous scattering is strongly anode-dependent, and an anode is routinely
*chosen* to sit on a particular side of a constituent's absorption edge:

* `crystallography/dispersion.py` bundles Cromer-Liberman over **3–70 keV**.
  Every anode in this WP's list is inside that band (Cr Kα1 = 5.415 keV lowest,
  Ag Kα1 = 22.16 keV highest), so no re-extraction is needed — but assert it,
  because the table *refuses* out-of-band rather than extrapolating.
* `dispersion.resolve` **raises** when the Kα1/Kα2 pair straddles an absorption
  edge of a constituent, because the two lines then cannot share one |F|².
  20 eV is a narrow window at Cu, but the gap grows with the anode and real
  cases exist: **Eu at Cu Kα**, and **Ru at Ag Kα** (ΔE = 173 eV, with Ru's K
  edge between the lines). A per-anode test that checks only wavelengths will
  not see this; add a smoke test that `resolve` succeeds at each new anode.
* The **`DISPERSION_NEGLECTED` diagnostic fires per wavelength**, so its
  message changes with the anode — Fe at Co Kα (6.93 keV, just below the Fe K
  edge at 7.11 keV) is a far larger correction than Fe at Mo Kα. Expect it in
  any new anode's acceptance output.

## Tasks

- [ ] Expand this stub into a full WP before writing code
- [ ] Transcribe Co/Cr/Fe Kα1,Kα2 (Hölzer 1997) and Mo/Ag Kα1,Kα2
      (Deslattes 2003), each with a source line in the `_RADIATIONS` comment
- [ ] Round-trip / lookup test per anode; confirm the doublet weight and
      polarization defaults still make sense off Cu
- [ ] Per-anode dispersion smoke test (see `### Inherited`): every anode inside
      the bundled 3–70 keV band, and `dispersion.resolve` not refusing the
      doublet for the test structures

## Acceptance

`Instrument.bragg_brentano(radiation="MoKa")` (and Co/Cr/Fe/Ag) returns a
two-line source with the transcribed wavelengths; a lookup test pins each
value to its cited source.

## Handover log

- **2026-07-23** — created as a stub during the cross-code review that landed
  WP-0506; the wavelengths are documentation-checked but not yet transcribed.
