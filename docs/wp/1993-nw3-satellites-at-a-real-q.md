# WP-1993 — N-W3: satellites at a real q, to order m, with (h k l m) rows

Milestone: unscheduled · Status: 🔄 2026-11-27 — N-W3a (`satellite_positions`, positions at a real q) built as its own PR under A2, proposed and pending the maintainer's ruling; N-W3b (the (h k l m) rows) remains
Track: Data and metadata in, a structure out
Depends on: — (N-W1 landed as PR #682; 1992 soft, the same package)
Priority: P3 2026-10-16 — library code with a contributor ready to build it; the k-search (#795, WP-1418) and both future forward models read it

## Goal

`crystallography/satellites.py` generates satellite reflections at a real
(irrational) modulation vector q, to a stated harmonic order m, as
(h k l m) rows with their absences derived from the superspace operators.
Every existing rational-q fixture stays bit-identical at m = ±1.

## Context

Issue #678 (mustachefeeling, 2026-10-02), chunk N-W3. A satellite is a
reflection at H + m·q, where H is a reciprocal-lattice vector of the
average cell and m an integer harmonic.

Decided on #678, 2026-10-08: N-W3 opens after TOF T-1 merges, which it did
on 2026-10-13 (PRs #911, #961). Cut 2026-10-16 from the issue triage, with
WP-1992 (N-W2's group half). Modulated structures stay behind ROADMAP § v2+
apart from these two library chunks.

#678's acceptance for N-W3: every 1326 fixture bit-identical at m = ±1; de
Wolff's (c/s), (6₃/h) and W^{P4bm}_{qq1̄} conditions derived from the
operators; the 1326 negative control still fails.

**Decision owed at this WP's start: amendment A2** (#678, comment of
2026-10-06). It splits N-W3 in two:

- N-W3a (S): `satellite_positions(space_group, cell, λ, range, q,
  harmonics)`, the distinct positions at a real q. The k-search and both
  forward models read this one call.
- N-W3b (M): the (h k l m) rows, the dedup under the (3+1)D point group,
  the labelled absences and the commensurate coincidence merge.

The 2026-10-08 reply deferred all six amendments to the cut. A2 is the one
that changes this WP's shape. The others belong to later chunks (see
Non-goals).

Proposed 2026-11-27: A2 (split N-W3); N-W3a lands first as its own PR,
pending the maintainer's ruling (#678 issuecomment-7219873154). If A2 is
declined, N-W3b joins this branch before it leaves draft.

Checked at `138d55dc`: `crystallography/satellites.py` exists and serves the
commensurate magnetic track (WP-1326); N-W1's operators are in
`crystallography/superspace/`.

### Inherited

## Non-goals

- The structure factor at a satellite (N-W5, N-W6) and satellite widths (N-W8).
- Amendments A1 (WP-1418), A3 (N-W4), A4 (N-W5), A5 (N-W10) and A6 (N-W8).

## Tasks

- [ ] Decide A2 with the maintainer and record it here as `Decided YYYY-MM-DD`.
- [x] Satellite positions at a real q (N-W3a, or the whole chunk if A2 is declined).
- [ ] The (h k l m) rows, dedup, absences and coincidence merge.
- [ ] Tests: the 1326 fixtures bit-identical at m = ±1; the three de Wolff conditions; the negative control
- [ ] Skill: none expected while the package stays unexported; say why at handover

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k "satellite or superspace" -q
.venv/bin/python -m ruff check src tests examples
```

## References

- de Wolff, Janssen & Janner (1981), *Acta Cryst.* A37, 625.
- Stokes, Campbell & van Smaalen (2011), *Acta Cryst.* A67, 45.
- Issues #678, #258, #795.

## Handover log

- **2026-11-27** — N-W3a built: `satellites.satellite_positions(space_group,
  cell, wavelength, two_theta_range, q, lambdas=None, harmonics=(1,))` gives
  the positions Q = H + m·q of a phase at a modulation vector that may be
  incommensurate, one d per Laue orbit, so the k-search's real-q form (K3)
  and the forward models have one position call to read. *Done:* `q` is a
  `ModulationVector` or its text, refused as a vector of numbers; `lambdas`
  declared, never inferred; an all-`Fraction` q takes today's exact path,
  so at `harmonics=(1,)` it returns `satellite_d_spacings` bit for bit;
  a float λ takes the real path, an exact orbit merge on integer codes with
  the free part read as generic; `harmonics` the declared |m|, both signs;
  `_parent_grid` gained `margin` (default unchanged) for |m·q_i| ≥ 1;
  `_ORDERS` unchanged. *Measured* (`tests/test_satellite_positions.py`, 28
  tests): every WP-1326 k (133 cases over 17 group/cell/window fixtures)
  bit-identical, and the real path's merge with no free part bit-identical
  too; NbTe₄ P4/mcc(½,½,0.691), Cu Kα₁, 5-140°: 156 positions at m = ±1
  and 356 to m = ±2, equal to a brute force with the 4/mmm orbit read off
  by hand; with the c glides applied to the parents the brute force finds
  fewer. *Gotchas:* a float λ at a commensurate value (0.5) keeps the
  coinciding ±q positions apart (64 against 32 on P m m m), as the
  docstring says. *Next:* the maintainer's ruling on A2 (#678); then N-W3b.

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #678).
  The maintainer decided to cut N-W2's group half and N-W3 now that T-1 has
  merged. Checked against the tree at `138d55dc`: `satellites.py` exists for
  the commensurate track. No open WP owns it: WP-1326 owns commensurate
  satellites. Next: the A2 decision.
