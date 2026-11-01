# WP-2016 — A literature CIF's U^ij that breaks site symmetry only by rounding is projected, and says so

Milestone: generality · Status: ⬜
Track: The audits
Depends on: —
Priority: P3 2026-10-20 — a reading of WP-2002's batch (Mike Gaultois, PR #1050) found that a published CIF with U^ij printed to four decimals is refused on a trigonal or hexagonal special position; the refusal is right for a contradiction and wrong for rounding

## Goal

`structure_from_cif(..., aniso=True)` accepts a U^ij tensor that misses its site's symmetry
by no more than the file's own printed precision. It projects the tensor onto the allowed
subspace and records the projection as a `Diagnostic`. A tensor that misses by more is still
refused, naming the site, the component and the residual.

## Context

**The case.** ZnO on its 3m site (P6₃mc). The site symmetry requires U12 = U11/2. A CIF
printing U11 = 0.0123 and U12 = 0.0062 to four decimals misses that by 0.00005, a relative
residual of about 3e-3, where the table's tolerance is 1e-6
(`ParameterTable:aniso_symmetry_tolerance`, a hand row). So the file is refused, although
U12 is exactly U11/2 to the precision it was written at. Every hexagonal or trigonal special
position with an odd last digit in U11 does this. Reported by both of Mike Gaultois's
readers on WP-2002's batch (B10.10), measured by one and re-checked by the other.

**The house rule this follows.** Root CLAUDE.md § Invariants: a silent correction is a
reader's to make, and only where the deviation is a report rather than a contradiction.
`CIF_CELL_ANGLE_CORRECTED` (WP-1028) is the precedent one field over: a fixed angle within
`cif.CIF_ANGLE_CORRECT_MAX_DEG` of its symmetry value is snapped at read and the snap is
recorded; past it the value is left alone and the table raises. `ParameterTable` itself
stays strict, since it has no diagnostics channel.

**What sets the bar.** The file's own precision: half a unit in the last printed digit of
each component, or its su where the file gives one. No chosen number. A residual inside that
bar is rounding; one outside it is a contradiction between the tensor and the site.

## Tasks

- [ ] In the CIF reader, project an aniso tensor onto `wyckoff.adp_basis`'s subspace when
      every component's residual is within half a unit in its last printed digit (or its
      su), and record `CIF_ADP_SYMMETRY_PROJECTED` with the site, the components moved and
      the largest move. Beyond it, leave the values as written so the table refuses them.
- [ ] Tests: the ZnO case (projected, diagnostic quoted); a tensor off by ten units in the
      last digit (refused, as today); a tensor already exact (silent).
- [ ] `help.py` entry for the new code; the skill's diagnostics reference row.
- [ ] The audit row for the code (WP-2001's table), with the precision rule as its
      evidence (tier 1: arithmetic on the file's own digits).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cif.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1028 (the cell-angle repair); WP-2002 `2002-batch/batch.md` B10; PR #1050's second
  read of the batch (B10.10).

## Handover log

- **2026-10-20** — Filed from WP-2002's session on the second read of its batch (Mike Gaultois, PR #1050, item B10.10), agreed by the maintainer the same day. Nothing built.
