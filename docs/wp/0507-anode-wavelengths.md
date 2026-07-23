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

## Tasks

- [ ] Expand this stub into a full WP before writing code
- [ ] Transcribe Co/Cr/Fe Kα1,Kα2 (Hölzer 1997) and Mo/Ag Kα1,Kα2
      (Deslattes 2003), each with a source line in the `_RADIATIONS` comment
- [ ] Round-trip / lookup test per anode; confirm the doublet weight and
      polarization defaults still make sense off Cu

## Acceptance

`Instrument.bragg_brentano(radiation="MoKa")` (and Co/Cr/Fe/Ag) returns a
two-line source with the transcribed wavelengths; a lookup test pins each
value to its cited source.

## Handover log

- **2026-07-23** — created as a stub during the cross-code review that landed
  WP-0506; the wavelengths are documentation-checked but not yet transcribed.
