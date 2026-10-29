# WP-1992 — N-W2 (group half): magnetic superspace groups generated from the operators

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (N-W1 landed as PR #682; 1419 soft, the `representation/` package it extends)
Priority: P3 2026-10-16 — library code with a contributor ready to build it, but no user-visible result until N-W5 (the magnetic Fourier forward model) lands on it

## Goal

`crystallography/superspace/` generates the (3+1)D magnetic superspace group
(MSSG) for each irrep at a real propagation vector, and pins its counts and
sign patterns against published tables. This is the group half of chunk N-W2
in #678's cut; the allowed-subspace function and the forward model are later
chunks.

## Context

Issue #678 (mustachefeeling, 2026-10-02) cuts modulated structures (#258)
into ten chunks, N-W1 to N-W10. Background for a reader new to it: a
modulated structure has atoms displaced by a wave that does not repeat with
the cell, and its symmetry needs a superspace group with one extra
dimension for the wave's phase. A magnetic one adds time reversal (1′).

Decided on #678, 2026-10-08: N-W2's group half and N-W3 (WP-1993) open after
TOF T-1 merges; one WP per chunk, numbered when cut; N-W4 onward wait for
the magnetic forward seam. T-1 merged on 2026-10-13 (PRs #911 and #961,
WP-1927). Cut 2026-10-16 from the issue triage. Modulated structures are
still behind ROADMAP § v2+; this WP and WP-1993 are the library half that
the decision lets in.

The reporter's scope for the group half (their comment of 2026-10-06): θ on
the operator, {1′|000½}, generating the MSSG per irrep, with the P222/I222,
SrFeO₃ and Stokes & Campbell (2022) Fig. 4 pins. It changes neither
`schemas/structure.py` nor the forward model.

Checked at `138d55dc`:

- N-W1 is on `main`: `crystallography/superspace/` (`operators.py`,
  `generation.py`, `symbols.py`), unexported.
- The irreps code #678 calls `magnetic/irreps.py` now lives in
  `crystallography/representation/irreps.py` (moved by #842 and #889 under
  WP-1419). The "real-k door" is opened there.
- spgrep is a dependency (`spgrep>=0.7`).

First act, before the design is fixed (decided 2026-10-08): check that
spgrep's little group and small irreps hold at an irrational k. A rational k
must be reproduced at its float value, and a near-rational k must not snap.

#682's three follow-ups fold into this WP's PR: the `number` field,
function-level references, and the hand-typed 775/24 counts.

Licensing: papers only (#678 § Prior art). The ISO(3+d)D tables forbid
redistribution, so rietx ships a generator and pins published counts.

### Inherited

## Non-goals

- The allowed-subspace function (N-W2's second half), the schema (N-W4)
  and the forward model (N-W5).
- #678's amendments A3–A6, which belong to N-W4, N-W5, N-W8 and N-W10, and
  A1, which lands in WP-1418 (#795's k-search).

## Tasks

- [x] The spgrep check at an irrational k, recorded here before any design.
- [x] θ on `SuperspaceOperator` and {1′|000½}; MSSG generation per irrep through the real-k door.
- [x] #682's three follow-ups.
- [x] Tests: the P222/I222, SrFeO₃ and Stokes & Campbell (2022) Fig. 4 pins; the 9 303 d = 1 MSSG count as an opt-in slow test
- [x] Skill: none expected while the package stays unexported; say why at handover

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k superspace -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Stokes, Campbell & van Smaalen (2011), *Acta Cryst.* A67, 45.
- Perez-Mato, Ribeiro, Petříček & Aroyo (2012), *J. Phys.: Condens. Matter* 24, 163201.
- Stokes & Campbell (2022), as cited in #678 (journal details to confirm at the WP's start).
- Issues #678, #258, #682.

## Handover log

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #678).
  The maintainer decided to cut N-W2's group half and N-W3 now that T-1 has
  merged. Checked against the tree at `138d55dc`: N-W1 is on `main`, and the
  irreps code sits in `representation/irreps.py`. No open WP owns it: WP-1418
  and WP-1419 own the commensurate magnetic track. Next: the spgrep check.
- **2026-10-20** — built on `nw2/group-half` (three commits: #682's three
  follow-ups, then θ / {1′|000½} / the MSSGs over an SSG, then the real-k door
  and the group of an irrep). The spgrep check, recorded here as the first
  task asked (spike `checks/spikes/nw2-step0-20261006/spgrep_real_k.md`,
  2026-10-06, spgrep 0.7.0): on the nine lines Pnma (0,0,γ), (½,0,γ),
  (0,γ,0), (0,½,γ), P6₃/mmc (0,0,γ), (⅓,⅓,γ), I4/mmm (α,α,0), (0,0,γ) and
  P4/ncc (½,½,γ) spgrep's G_k at an irrational γ equals the hand rule by index
  with orders 4, 4, 4, 4, 12, 6, 4, 8, 8; a rational k as a float reproduces
  the exact group 18/18; spgrep snaps a near-rational k below |Rᵀk − k| ≈ 1e-8;
  `real=True` declines on 6 of the 9 lines. So the door computes the group from
  a declared line (`little_group_on_line`) and spgrep stays a dev-only oracle,
  its arms now unit tests (`tests/test_incommensurate_irreps.py`). Pins: Stokes
  & Campbell 2022 Tables 1–3, p. 365, p. 369 (12 and 40) and Fig. 4's group;
  Perez-Mato 2012 Table 1 and p. 17; SrFeO₃'s six MSSGs with Gallego 2016
  Fig. 6's (n, m) and symbols; the polar-axial shift sign on P4 and P6₃.
  Table 6: types 1–3 = 775/775/3100 as printed, type 4 = 4651 against 4653
  (strict xfail, open; ~1 min single-core). Fast suite (`.venv-test` [dev],
  macOS arm64, alone): 11000 passed, 121 skipped, 2 xfailed, 7 min 14 s.
  Skill: none, the package stays unexported. spgrep stays in the `dev` extra:
  l. 43's "a dependency" reads "a test oracle" (noted on the PR).

