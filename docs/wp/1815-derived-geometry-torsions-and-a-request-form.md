# WP-1815 — derived geometry: torsions, a request form, one table every writer reads

Milestone: rigid-bodies · Status: ✅ 2026-11-02 — torsion rows, the request form and `TorsionRestraint` (PR #1261); the CIF `_geom_torsion` loop and the skill row (PR #1319)
Depends on: 1804 (the derived block's local Jacobian, for body atoms)

## Goal

`GeometryTable` carries torsion angles with esds beside bonds, contacts and
angles. A caller can ask for particular distances, angles and torsions. The
CIF writer, the FitReport and the foreign exporters read that one table and
never compute an esd themselves.

## Context

Issue #759 (mustachefeeling, 2026-10-06), section 2, chunk "1815" in its
own provisional numbering, kept here. Decided 2026-10-16 (the issue triage,
maintainer): file this first and the Z-matrix internals (WP-1814) behind
it; fence TLS and the TOPAS rigid import.

Checked at `138d55dc`: `model/geometry.py` has no torsion rows. It lists
bonds, contacts and angles with esds through the full covariance, built once
at fit close because the covariance is never serialised. The CIF writer
writes `_geom_bond`, `_geom_contact` and `_geom_angle` only.

The proposal (#759 § 2):

- `GeometryTable.torsions` (`GeometryTorsion`: four labels, four symmetry
  codes, value, esd, diagonal-only esd), listed over bonded chains with a
  cap recorded in `notes`; Klyne–Prelog sign, range (−180, 180]
  (cif_core `_geom_torsion.angle`).
- `GeometryRequest(distances, angles, torsions)` and
  `Refinement.geometry(request=None)`, answered while the last stage's
  covariance is live; a replay answers values with `None` esds, as today.
- `TorsionRestraint` sharing the torsion row's partials (the WP-1072 reuse
  rule: a geometry row is a restraint row); its residual is the circular
  difference, so 180° is a smooth target.

Three rules the reporter measured, to keep:

- A quantity fixed by symmetry or by a body reports no esd (the existing
  `VARIANCE_CANCELLATION_FLOOR`).
- Esds carry the Bérar–Lelann factor once. The covariance is already built
  from the inflated diagonal, so nothing downstream multiplies again.
- Torsion partials are analytic through atan2. A central difference at
  exactly 180° gave an esd of 6·10⁶°.

## Non-goals

- Refinable Z-matrix internals (WP-1814).
- TLS and the TOPAS rigid import (#759 § 4, fenced 2026-10-16).
- Riding hydrogens on a free atom (#759's "1816"), not filed in this round.

## Tasks

- [x] `GeometryTorsion` rows over bonded chains, with the cap in `notes`. (PR #1261, `9c6ccf7d`)
- [x] `GeometryRequest` and `Refinement.geometry(request=)`. (PR #1261)
- [x] `TorsionRestraint` on the shared partials. (PR #1261)
- [x] The CIF torsion loop (with WP-1933, which waits on it).
- [x] Tests: J·Cov·Jᵀ against Monte Carlo (circular difference) within 5 %; a template-fixed bond reports `None`; a torsion at exactly 180° has a finite esd (these three PR #1261); the CIF torsion loop round-trips
- [x] Skill: the reference row for `Refinement.geometry` (PR #1261 wrote it in `references/numbers.md`; this WP added the pre-0.60 `None` reading)

## Acceptance

```sh
.venv/bin/python -m pytest tests/ -k geometry -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Klyne & Prelog (1960), *Experientia* 16, 521 (torsion sign convention).
- Issues #759, #756.

## Handover log

- **2026-11-02** (ghostshift runner) — closed. A refinement CIF now carries the torsion angles the geometry table lists, so a journal submission gets the torsion table without a second program. Each row reads back from the file as the table's row: labels, symmetry codes, value and su. The loop is flagged `no` for publication, the CIF dictionary's default, because the table lists every bonded chain up to 36 per atom, ionic coordination contacts included; LaB6 alone writes 72. The su sentence in `_geom_special_details` now names only the kinds whose written rows carry an su. That changes every refinement CIF: on LaB6 it read "distances and angles" while every angle was written without an su, and it now reads "distances". Next: none in this WP. Two CIF gaps the review found went to WP-1933's Inherited.
  - *Done.* Ticked the three items PR #1261 built, verified in the tree at `a8f67985` (`8120bce7`). `_geom_torsion` loop in `io/exporters._write_geometry_loops` with nine `io/cif/registry.py` rows, checked against the vendored `cif_core.dic` by `test_cif_registry.py` (`5a4e8e38`). One builder for the angle and torsion loops, the su-sentence fix and publ_flag `no` came from `/code-review high --fix` (`f5068c4d`). The skill's torsion row in `references/numbers.md` now says a pre-0.60 result reopens with `torsions` `None`, meaning "not listed", and `[]` means none found (`46cb37af`). Manual `reference/exports.md` and skill `references/judging.md` name the new loop.
  - *Review.* `/code-review high --fix` returned eight findings. Fixed: the su sentence claimed a method for rows with no su; the round-trip test never reached its su branch; the manual said one row per table row, though a row needing an unwritable symmetry code is left out; the two loop builders were copies. Settled here: publ_flag, the reviewer's open question, set to `no`. Declined: a no-su torsion is written at its full repr (`45.000000000000014`), the documented convention for angles too. Passed to WP-1933: the table's cap notes never reach the CIF, and the no-su sentence omits two reasons an esd is absent.
  - *Measured.* Fast selection on `origin/main` merged into the branch (`eb1c9363`), `[dev]` venv, Mac arm64, Python 3.12, run under the machine's suite lock with no other suite running: 13 285 passed, 310 skipped, 32 xfailed, 2 failed. One failure was this branch's: the export guide counted ten CIF loops and fluorapatite now writes eleven, fixed in the next commit and re-run alone, 1 passed. The other is `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`: this Mac's Jupyter kernel spec points at a deleted venv, a machine fault this branch does not touch. One test added, 0.10 s locally. The full suite did not run: the change writes a CIF and moves no fitted number.
  - *Reader output.* `python -m tests.reader_output`: unchanged against `db94d90a`. It covers printed text, not the CIF. The CIF changes are the new loop and the su sentence above.
  - *Generality.* Not dispatched: the branch touches no `_audit.py` row, and the one literal added is the torsion loop's publ_flag, an output label like the bond, contact and angle flags, which the table does not carry either.
  - *Gotchas.* Every LaB6 torsion is symmetry-fixed and has no su, so a test of the su path has to give rows an esd itself, as the round-trip test does.

- **2026-11-01** (`/pr-review`) — merged from outside as PR #1261 (`9c6ccf7d`). `GeometryTable.torsions` holds a `GeometryTorsion` per torsion over bonded chains. Each has its angle in (-180°, 180°] and two esds. `GeometryRequest` is the request form. It is an argument and is never stored. `TorsionRestraint` joins the `Restraint` union, and `RestraintRow.kind` gains `"torsion"`. `torsions` defaults to `None`, so an older table reads "not listed", while `[]` means "listed, none found". Schema 0.60 carries a note. Three audit rows came with it, all tier 1 and held by the generality judge: `MAX_TORSIONS_PER_ATOM`, `_KEY_OFFSET` and `_TORSION_SIN2_FLOOR`. The branch was synced with main once before merge (the schema-history note, `9a7df4a5`). The PR does not build the CIF torsion loop, so that task stays open with WP-1933 waiting on it. It ticked nothing, and the first three task boxes are built and left for the maintainer. Follow-up, not blocking: `docs/skill/rietx/references/numbers.md:143` could say that `torsions` is `None` on a reopened pre-0.60 result. What ran: the PR was replayed in a stack with the other round's merges onto `main` `276fe91d` and run at `635d25e3` (Mac arm64, Python 3.12, `[dev,jax]`). Full suite 14 161 passed, 235 skipped, 50 xfailed, 0 failed. The manual `-W` build was green. `main` now equals that tree.

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #759).
  The maintainer took the triage's recommendation: this WP first, WP-1814
  behind it, TLS and TOPAS rigid import fenced. Checked against the tree at
  `138d55dc`: no torsion rows in `model/geometry.py`. No open WP owns it:
  WP-1808 and WP-1922 name it as a non-goal and are closed. Next: the rows.
