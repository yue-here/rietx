# WP-1344 — a joint fit owes each histogram the diagnostics its own radiation earns

Milestone: unscheduled · Status: ⬜
Depends on: — (WP-1341 owns the neighbouring "a joint fit has no report" gap)

## Goal

`multi.py`'s per-histogram diagnostics loop decides, by a stated rule rather
than by which diagnostics happened to be wired in, which checks each histogram
is entitled to — so a radiation-keyed diagnostic added to `Refinement` reaches
a joint fit's histograms too, or is recorded as deliberately not reaching them.

## Context

**Found by PR #281** (2026-09-10), an audit of the per-histogram physics of a
mixed X-ray + neutron fit, and verified in review rather than taken from the
PR: `_dispersion_diagnostics` has one definition (`src/rietx/refine.py:3416`) and
exactly one call site (`src/rietx/refine.py:1878`), both inside `Refinement`;
its other appearances are docstring cross-references, not uses. `multi.py`
names it nowhere. So a mixed joint fit raises `DISPERSION_NEGLECTED` **zero**
times, on either histogram.

The zero is not the neutron histogram correctly abstaining. Measured control in
that PR: a single-histogram `Refinement` on the same structure and instrument,
with `dispersion=None` on the X-ray side and corundum's Al at that wavelength
carrying ~3.3 % of the scattering power (above `DISPERSION_NEGLECT_FRAC`),
*does* raise it once. The joint path raises it at no count. `tests/
test_joint_xray_neutron.py::test_the_dispersion_diagnostic_is_not_wired_into_a_joint_fit_yet`
now asserts that 0 with a docstring saying it is a gap, so the defect is at
least no longer invisible — but the test is a record, not a fix.

**The same shape has already arrived again.** PR #282 (merged 2026-09-11,
`8c39a02c`) adds `NEUTRON_RESONANT_ABSORBER` through
`_resonant_absorber_diagnostics` — defined at `src/rietx/refine.py:3491` and
called once, beside the dispersion call, on `self.instrument`. One instrument
is right for `Refinement` and inherits exactly this gap for a joint fit:
`multi.py` names this helper no more than it names the other. Two codes asking one question from opposite sides is the reason this
is a WP rather than two wiring commits: whatever the rule turns out to be, it
has to give both the same answer, and any future radiation-keyed diagnostic the
same answer again.

**Source files and the seam.** `src/rietx/multi.py` (the per-histogram
diagnostics loop — today it calls `_absorption_diagnostics`,
`_capillary_offset_diagnostics`, `_wavelength_calibration_diagnostics`,
`_strain_flag_diagnostics`, `_size_flag_diagnostics` and others, and the
omissions are undocumented); `src/rietx/refine.py` (where every
`_*_diagnostics` helper lives, and where `Refinement` calls the full set);
`src/rietx/params/multi.py` for what is shared across histograms and what is
per-histogram, which is the physics constraint on the answer.

**The invariant that makes this more than tidying.** Root `CLAUDE.md`,
WP-1076: *a declared name is a claim, and an absent writer fails no test*. A
diagnostic that exists, is documented in the skill's `diagnostics.md`, and is
reachable from one entry point but not another is that failure one rank up —
the vocabulary claims a check the joint path does not perform, nothing goes
red, and a reader of `result.diagnostics` on a joint fit reasonably concludes
the check passed.

**The physics constraint.** Root `CLAUDE.md`, WP-1131: exactly two of the six
sample-broadening quantities are not one number across wavelengths, and
`params.multi.SIZE_LAMBDA_POWER` is that list as data. The equivalent list does
not exist for diagnostics, and writing it is most of this WP: which checks are
a fact about the *specimen* (one answer for the fit), which about a
*histogram's radiation* (one answer each), and which about the *fit as a whole*.

## Non-goals

- **Not the report.** A joint fit having no `FitReport` is WP-1341; this WP is
  about the raw `Diagnostic` list only.
- **Not new diagnostics.** No code in the vocabulary changes meaning; this is
  about which entry points compute the existing ones.
- **Not `SeriesResult`.** A series is N separate refinements each with its own
  diagnostics, so it does not have this gap.

## Tasks

- [ ] Enumerate every `_*_diagnostics` helper in `refine.py` and classify each
      as specimen-wide, per-histogram, or whole-fit — as **data**, in the
      `SIZE_LAMBDA_POWER` idiom, not as a comment, so a new helper has to
      declare which it is.
- [ ] A meta-test that fails when a helper exists with no classification, and
      when the joint path's loop disagrees with the classification. This is the
      part that stops the gap reopening; without it the fix is one commit old.
- [ ] Wire `_dispersion_diagnostics` and `_resonant_absorber_diagnostics` per
      histogram, and re-point
      `test_the_dispersion_diagnostic_is_not_wired_into_a_joint_fit_yet` at the
      intended count — 1, on the X-ray histogram only. Its docstring already
      says this is the test to rewrite and what to rewrite it to.
- [ ] Check the omissions that are *deliberate*: some of what `multi.py` leaves
      out may be correct, and each one that survives needs its reason recorded
      where the classification lives, not lost in the diff.
- [ ] Skill rows: `docs/skill/rietx/references/` — whichever rows say a code
      fires need to stop implying it fires everywhere, if any do.

## Acceptance

`.venv/bin/python -m pytest tests/test_joint_xray_neutron.py tests/test_multi.py -n auto --dist loadgroup`

and the fast suite green, with the count moving by exactly the number of tests
added (root `CLAUDE.md` § Numbers).

## References

- PR #281 (merged 2026-09-10) — the audit that found it, and the control
  measurement establishing that the 0 is a gap rather than a result.
- PR #282 (merged 2026-09-11) — the second diagnostic of the same shape,
  in the tree now and carrying the gap as predicted.
- Root `CLAUDE.md` § Invariants, WP-1076 (a declared name is a claim) and
  WP-1131 (what is shared across histograms and what is not).
- [1341](1341-a-joint-fit-has-no-report.md) — the neighbouring gap, deliberately
  out of scope here.

## Handover log

- **2026-09-11** — a freshness pass before this WP's filing PR (#297) merges;
  no work on the WP itself started. PR #282 had merged (`8c39a02c`) between the
  filing and now, so the Context section's "open at the time of writing" was
  about to land already false, and the two `refine.py` line numbers matched
  neither the merged tree nor this branch's own base. Re-verified both claims
  against the merged tree and corrected them: `_dispersion_diagnostics` is one
  definition (3416) and one call (1878), the extra grep hits being docstring
  cross-references rather than uses, and `_resonant_absorber_diagnostics`
  (3491) is called once beside it. `multi.py` names neither, so the gap this WP
  exists for is confirmed present with both diagnostics now in the tree, not
  predicted. The WP's substance is unchanged; only its citations moved. Next is
  still the classification table, unchanged.

- **2026-09-10** — created from a `/pr-review all` pass, on the maintainer's
  decision to make this a WP rather than wire the two diagnostics in ad hoc.
  Nothing started. First action: the classification table, since both the
  meta-test and the wiring depend on it.
