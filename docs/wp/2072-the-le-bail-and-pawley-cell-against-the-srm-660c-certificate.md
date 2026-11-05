# WP-2072 — The Le Bail and Pawley cell, validated against the SRM 660c certificate

Milestone: unscheduled · Status: ⬜
Track: The fit has no reference
Depends on: 2010 (the feature registry and the `reference_kind` join, PR #1266); 2015 soft (the shipped presets pass the bar only once the declared geometry picks the offset)
Priority: P3 2026-10-31 — a validation row over a measurement already made; changes no number a user gets, but lifts one feature to "validated on development data"

## Goal

The validation matrix carries a row that compares the Le Bail and Pawley cells from the
NIST SRM 660c certification pattern with the certificate, under the NIST protocol, and
reports the mismatch in Å and ppm beside the certificate's uncertainty and the fit's esd.
The tree's quotations of the certificate's uncertainty are correct.

## Context

**Source.** Issue #1259 (2026-10-31, @mustachefeeling), a follow-up WP-2010's task list
names ("references for data already in the tree: a Le Bail cell against the SRM 660c and
676a certificates"). Under #1051's Rule 2, a certificate is an independent measurement,
so a `prediction` claim against it with `reference_kind = "independent_measurement"`
validates (WP-2010's `validates()`, landing in PR #1266).

**The reference.** NIST SRM 660c certificate (issue 29 October 2015), page 1:
a = 0.415 682 6 nm ± 0.000 008 nm at 22.5 °C, expanded uncertainty k = 2, that is
4.156826 Å ± 0.00008 Å (19 ppm). Read from the certificate PDF by the triage on
2026-10-31. Corrected to the scan's 20.85 °C: 4.156780 Å, the value
`tests/test_acceptance_srm660c.py` already uses (`A_REFERENCE`). The reporter derived
the 11 ppm correction from the CIF's own cell and the certificate's (α = 6.7e-6 K⁻¹),
not from Sirota et al. (1998), which the certificate cites; check it against Sirota.

**Measured by the reporter** (main `44de0f62a`; not re-run in triage):

| mode, plan | a (Å) | Δ vs 4.156780 | esd (Å) | Rwp |
|---|---|---|---|---|
| Pawley, zero held 0, displacement and axial freed | 4.156878 | +23.6 ppm | 1.6e-5 | 7.90 % |
| Le Bail, same plan | 4.156881 | +24.2 ppm | 1.6e-5 | 7.96 % |
| Pawley, `pawley_default` (zero freed) | 4.157067 | +69 ppm | 1.5e-5 | 9.27 % |
| Le Bail, `profile_only` (zero freed) | 4.157065 | +69 ppm | 1.6e-5 | 9.50 % |

A positive arm: scaling both Cu Kα wavelengths by 1 ± 1e-4 moves the cell ±100 ppm with
Rwp unchanged to 1e-9. Why the presets miss is #1233, folded into WP-2015.

**The bar.** 50 ppm (2e-4 Å), the interim bar `tests/test_acceptance_srm660c.py` already
sets for a non-FPA pseudo-Voigt fit. It is not the certificate's 19 ppm; the remaining
+24 ppm is the non-FPA systematic that test's docstring names (FPA is fenced to v2).

**Limits the row states.** The counts are the ones NIST certified the cell from, so this
tests rietx's extraction against NIST's FPA analysis of one dataset, not an independent
specimen. λ is held on the Hölzer scale and the zero at 0 (the instrument is
angle-calibrated), so λ is not calibrated on this pattern. The pattern was used in
development.

**SRM 676a is out.** NIST publishes no raw 676a pattern, and `qarr/corundum.prn` is
already documented as a corundum specimen, not as 676a (`tests/data/README.md`,
`test_acceptance_srm676a.py`'s docstring). Nothing to change there.

**A quotation error, settled under the certificate.** The tree writes the certificate as
"4.156826(8) Å" and "±8e-6": parenthesis notation puts the 8 in the last digit, 8e-6 Å,
ten times smaller than the certificate's ±0.00008 Å. Sites at `d87c8cc91`:
`tests/data/README.md` lines 132 and 785; `tests/test_acceptance_srm660c.py` lines 16
and 27; `tests/test_acceptance_indexing.py` line 191. The correct spelling is
4.15683(8) Å, or 4.156826 ± 0.00008 Å (k = 2).

**Tier.** A comparison with an independent measurement; no heuristic, no `_audit` row.

## Non-goals

- SRM 676a (no pattern of the certified material on a calibrated instrument).
- Making the shipped presets pass the bar: WP-2015.
- A certificate-grade (19 ppm) claim: needs FPA, fenced to v2.

## Tasks

- [ ] Correct the five quotations of the certificate's uncertainty.
- [ ] Check the temperature correction against Sirota et al. (1998); record the value.
- [ ] The test: both modes under the NIST protocol within 50 ppm of 4.156780 Å; Pawley
      and Le Bail agree within the esd; the λ × (1 ± 1e-4) positive arm fails the bar
      and the null arm passes. Shares the `srm660c` xdist group. obs/calc/diff PNGs to
      `tests/output/`.
- [ ] The validation-matrix row (`tests/validation_matrix.py`): `prediction`,
      `reference_kind="independent_measurement"`, the Le Bail/Pawley feature, dataset
      state `development`, mismatch in Å and ppm with the k = 2 uncertainty and the esd
      beside it, and the limits above; `docs/VALIDATION.md` regenerated.
- [ ] Skill: none. The validation state is the matrix's own output.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_validation_matrix.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_acceptance_srm660c.py
.venv/bin/python -m ruff check src tests examples
```

## References

- NIST Certificate of Analysis, SRM 660c (29 October 2015),
  https://tsapps.nist.gov/srmext/certificates/660c.pdf, pages 1 and 3-4.
- Black, D. R. et al. (2020). Powder Diffraction 35(1), 17-22,
  doi:10.1017/S0885715620000068 (the certification).
- Cline, J. P. et al. (2015). J. Res. NIST 120, 173, doi:10.6028/jres.120.013 (the
  instrument).
- Sirota, N. N. et al. (1998), cited by the certificate for LaB6's expansion.

## Handover log

- **2026-10-31** — created by the issue triage from #1259. WP-2010 (every feature names
  what verifies and validates it) lists this as a follow-up to file, and PR #1266, which
  completes WP-2010, names #1259 as filed and does not implement it; folding into a WP
  whose closing PR is in review would widen that PR. WP-2015 owns why the presets miss
  (#1233) and is a soft dependency.
