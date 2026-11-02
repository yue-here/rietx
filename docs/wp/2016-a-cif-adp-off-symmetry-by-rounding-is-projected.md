# WP-2016 — A literature CIF's U^ij that breaks site symmetry only by rounding is projected, and says so

Milestone: generality · Status: ✅ 2026-11-02 — closed: a CIF U^ij off its site symmetry by rounding is read on the allowed form and reported; #1345
Track: The audits
Depends on: —

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

- [x] In the CIF reader, project an aniso tensor onto `wyckoff.adp_basis`'s subspace when
      every component's residual is within half a unit in its last printed digit (or its
      su), and record `CIF_ADP_SYMMETRY_PROJECTED` with the site, the components moved and
      the largest move. Beyond it, leave the values as written so the table refuses them.
- [x] Tests: the ZnO case (projected, diagnostic quoted); a tensor off by ten units in the
      last digit (refused, as today); a tensor already exact (silent).
- [x] `help.py` entry for the new code; the skill's diagnostics reference row.
- [x] The audit row for the code (WP-2001's table), with the precision rule as its
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

- **2026-11-02** — PR #1345. A CIF whose anisotropic displacement tensor misses its site's symmetry only by the file's rounding now reads, where it used to be refused when the fit built its parameter table. ZnO printed with U11 = 0.0123 and U12 = 0.0062 is the case: U12 = U11/2 rounded to four decimals. The reader moves the tensor to the nearest allowed one inside half a unit of each component's last printed digit and reports it as `CIF_ADP_SYMMETRY_PROJECTED` (info). A tensor further off is left as printed, and the table's refusal now names the site, the component furthest from the allowed form and by how much. The same work found and fixed a sibling in the magnetic-CIF reader: a moment component the symmetry leaves free could be moved by up to 0.02 μ_B for no reason.

  *Done.*
  - `crystallography/cif.py`: `_aniso_statements` reads the six U^ij tokens per aniso row; `_adp_within_print` builds the box (half a unit in the last printed digit, `CIF_PRINTED_ROUNDING`); `_project_printed_adps` stores the projected tensor in place after every merge, drop and snap, then re-checks it with the table's own test; `_adp_projected_diagnostic` builds one info diagnostic per file (sites, components moved, largest move as `value`, `where` per component path). `_printed_half` is now the one copy of the half-unit arithmetic, shared with `_within_printed_rounding`.
  - `crystallography/wyckoff.py`: `adp_projection` is the one "already exact" test (the 1e-6-relative round-off floor, moved unchanged out of `ParameterTable._collect_atom_adps`); `nearest_allowed_within_print` is the two-stage linear programme (Chebyshev fit, then minimum summed moves inside that box). A Chebyshev fit alone is degenerate in a component the symmetry ties to nothing; HiGHS's vertex moved ZnO's free U33 by a third of its rounding before the second stage existed.
  - `crystallography/magcif.py`: `moment_within_print` calls the shared programme with its 0.02 μ_B cap as an absolute bound, so its acceptance is unchanged and a free component keeps its print (the old code moved m_z = 1.5 to 1.48 on a [1 2 0]+[0 0 1] site).
  - `params/vector.py`: the refusal message names the atom label, the furthest component and its residual in Å².
  - Help entry, `help_keys.json`, the skill's `diagnostics-reading.md` row (copies re-synced), the audit row (tier 1, ambiguity 1, info), and a paragraph in the manual's `reference/structure-files.md` § Repairs and reports.
  - Tests: four ZnO cases plus a box-edge pair in `tests/test_aniso_adp.py` (projected and quoted; ten units past the print refused with the new message; a printed zero `0`/`0.0`/`0.0000` held exact and refused; an exact tensor silent; 0.0061/0.0062 accepted and 0.0060/0.0063 refused against U11 = 0.0123), and the free-component moment case in `tests/test_magcif.py`. The WP's acceptance names `tests/test_cif.py`, which does not exist; the aniso tests live in `test_aniso_adp.py`.

  *Settled by Claude* (each a call a reviewer could make the other way):
  - **The bar is the printed half-digit only; the task line's "or its su" was dropped.** Ruled by the maintainer, 2026-11-02 ("A": half a unit in the last printed digit, as built; the su bar is rejected). A residual inside the su but outside the print cannot come from rounding.
  - **A token printed as zero, at any number of decimals, is held exact.** Settled by Claude under the code review's finding: read as a rounding, `0.0` is ±0.05 Å² and would repair a hexagonal writer's U12 = 0 into 0.00615. Cost: a 2:1 tie between components small enough that one prints as zero stays refused, as before. Alternative: an absolute cap like the magnetic reader's, which needs a new constant.
  - **Reported at info, one diagnostic per file.** Settled by Claude under the maintainer's delegation (2026-11-02, "whatever is more consistent with our design ethos") and root CLAUDE.md's reader-repair rule: a stranger's file is repaired at read with the substitution recorded as a Diagnostic, as `CIF_SPECIES_NORMALISED` and `CIF_CELL_ANGLE_CORRECTED` do. WP-2037's silent coordinate snap differs in kind: its target is the one special position, where this target is the package's choice inside the box. `CIF_MAGNETIC_MOMENT_ON_ALLOWED` is already info and records the move (`value` the largest shift), so it needs no change.
  - **Which allowed point inside the box**: Chebyshev, then minimum summed moves. ZnO lands at U11 = 0.012333, U12 = 0.006167; keeping U11 and deriving U12 = 0.00615 is equally inside the print. Settled by Claude under the magnetic precedent's Chebyshev choice.

  *Generality* (the `generality-review` agent, unedited headings; full text in the session): item 1 `CIF_ADP_SYMMETRY_PROJECTED` **holds** ("with one test gap": no box-edge test; *Author:* added). Item 2a, zero held exact, **holds** ("whole-number branch untested"; *Author:* `0` is that branch, as a whole number that is also zero; a nonzero whole-number U is not a value any file prints). Item 2b, the point chosen, **holds** ("say in the handover whether any golden moved"; *Author:* no magnetic or ADP test moved; the fast suite is green with every existing `test_magcif.py` case unchanged). Item 2c, `adp_projection`, **holds** ("wording ambiguous" on the floor; *Author:* docstring reworded). Item 3a, su dropped, **weak, on process** ("the departure recorded in the WP handover with its reason"; *Author:* recorded above and put to the maintainer). Item 3b, info versus silence, **cannot tell** ("a maintainer ruling"; *Author:* put to the maintainer). It also noted the audit row's evidence read like a measured case; *Author:* reworded as a constructed case.

  *Measured.* Fast suite, `[dev]`, macOS arm64, sharing the machine with other runners' suites (37:41 wall): 13513 passed, 314 skipped, 34 xfailed, 2 failed. One failure was this branch's refusal message breaking `test_gui_server.py`'s `<path>:` prefix, fixed in 68854d2ee (that file, `test_display.py` and `test_aniso_adp.py` then 243 passed, 1 failed). The other, `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`, fails on this machine's Jupyter kernel spec pointing at a deleted venv, outside this diff. Tests added: 7 before that run (ZnO four, one of them three cases, plus the magnetic one), 4 after (the box-edge cases). `tests.reader_output`: unchanged against e84a0fced. `tests.audit_delta`: 1 added, 0 at `unaudited`. Full suite not run: no measured number can move, since the projection acts only on a file the table refused before.

  *Not generalised.* The TOPAS project reader (`io/projects/topas.py`) builds `AnisoU` from the printed `u_ij` with no rounding projection, so the same rounded hexagonal tensor from a `.inp` is still refused (code review). The FullProf reader's anisotropic β lines are the same shape. Each has its own token access; neither is reported by a user. Exponential tokens: the ADP box reads `1.23E-2` as ±5e-5 (its mantissa's digits), while `magcif._last_digit_half` holds exponential notation exact.

  *Answered.* Both questions above were answered on 2026-11-02: the bar by the maintainer's ruling, the level under the maintainer's delegation. The maintainer approved the PR's reader output for merge the same day.

  Next: none; closed. The open gap is the *Not generalised* paragraph's TOPAS and FullProf readers, which no user has reported.
- **2026-10-20** — Filed from WP-2002's session on the second read of its batch (Mike Gaultois, PR #1050, item B10.10), agreed by the maintainer the same day. Nothing built.
