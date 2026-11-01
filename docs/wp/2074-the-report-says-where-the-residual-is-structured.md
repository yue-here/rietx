# WP-2074 — The report says where the residual is structured: a coherent-residual scan, the background's bulge, a replica scan on isolated lines

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: — (2004 soft: the report's tiers and thresholds land there first; 1931 soft: the auto P-spline's low-edge error is what every row meets first)
Priority: P3 2026-10-31 — a view over what the fit already knows: report-only rows over stored curves, no action, no code; waits on the maintainer's ruling on whether the report grows them

## Goal

A FitReport states, as numbers in data units, where its residual is coherent and how large
that is, how far the fitted background bulges above its own lower hull, and which isolated
lines carry a shifted copy of their own profile. Nothing in the fit changes and no code fires.

## Context

**Source.** Three proposals from one study of slight misfits (mustachefeeling, 2026-10-29),
filed separately and combined here because they share one seam (`report/`, reading the stored
`y_obs`, `y_calc`, σ and ticks), one fixture set and one maintainer decision:
- #1215: a multi-scale coherent-residual scan with edge windows, a whole-pattern Σz/√N, the
  analytic null printed beside χ²_red and DW, and a background-bulge row;
- #1216: a replica scan on isolated lines, plus an on-demand `split_lines`;
- #1218 row S1: a residual stack over a series, `rx.stack_residuals`. Gated (last task).
The other parts of those issues went elsewhere: #1215's `AIR_SCATTER_UNDECLARED` retext to
WP-2005; #1218's replicate lack-of-fit (S2) to WP-1325.

**Checked against the tree at d87c8cc91.** `BackgroundEvidence` (`report/schemas.py:716`)
carries `rwp`, `rwp_background_subtracted`, `background_share`, `off_region_durbin_watson`,
`absorption` and `worst_absorption`; no coherent-residual or bulge field. No `line_shape`,
`replicas` or `split_lines` exists in `report/`. `report/background._pooled_durbin_watson`
already pools DW within contiguous runs, the per-run rule the scan proposes.

**What the issues measured** (their tables; not re-run in triage).
- Scan, synthetic (family A cubic perovskite capillary; family B rutile Bragg–Brentano Kα1+2;
  one source): a half-absorbed hump reads +36σ at 10° against a white-noise 99 % point of 4.0,
  +3.5 % of the background; exact-model nulls 0/20 and 0/20. With `auto_background`'s P-spline
  clean patterns fire 17/20 and 20/20, caused by a real low-edge error (#833's comment).
- Scan, four public patterns in the tree (SRM 660c, FAP, SRM 1976a, 11-BM LaB6 660a): far above
  the null on every one (+25σ at 10°). **So on real data the significance column says nothing
  χ²_red does not; the content is the span, the effect in data units and the on-peak share.**
- Bulge: 2.3 / 9.8 / 41 / 82 % above the hull for a hump at 0.1-1.2 × mean background; clean
  ≤ 0.33 %. The 11-BM capillary reads 45.6 % at 29.4°, 18.5 % of background counts, no code
  firing. The width skip (`HUMP_MIN_WIDTH_MULT` × FWHM) is unmeasured; without it a measured
  blank's sharp line reads as a 185 % bulge.
- Replica scan: synthetic 5 % second line flags 3-4 of 11 lines; Kα-doublet null 1 of 60. On
  the four public single-phase standards it flags 8/14 to 18/18 lines at 1-4 % of the line,
  mostly low-angle: line-shape tails the model lacks. **The pattern-level count cannot tell a
  5 % component from the instrument's own line shape**; only the same table on a calibrant from
  the same instrument can (`split_lines(calibrant=)`).

**Rules.** Each row reports and decides nothing: Rule 1's third kind. Rule 4's new-output test
holds only if each row carries its effect size in data units, so a reader can write the next
call. Not WP-1130 (🛑): the bulge is a shape fact about the fitted curve, not a model-free
background level. Tiers per the issues: statistics 2 (Naus 1982; Siegmund & Worsley 1995;
Davies 1977/1987; Benjamini & Hochberg 1995), nulls 1, the scale set, edge widths, on-peak cut,
isolation radius, 20σ floor and δ range tier 3 until ruled.

**Decision for the maintainer** (value judgement; the brief's trigger). Whether the report
grows always-printed residual-structure rows at all, given that on every real pattern measured
the scan is never quiet and the replica count is never zero. Options: always on (as proposed),
on demand only (a function a caller or agent runs), or the bulge alone always on. WP-2037's
"attention is a cost" ruling bears on it. Then the tier-3 choices, dated.

### Inherited

(none)

## Non-goals

- Any `Diagnostic` code, threshold or action.
- `too_stiff` and the other report gates: WP-2004.
- `AIR_SCATTER_UNDECLARED`'s text: WP-2005.
- An asymmetry column with FCJ off: WP-2054. The SRM 1976a small-δ hits (up to 47 % at
  0.3 FWHM) are likely width or asymmetry; whether the replica scan's nuisance set holds
  2054's width and odd terms is a question for both.
- The auto P-spline's low-edge error: WP-1931.

## Tasks

- [ ] The maintainer's ruling on surface (always on, on demand, bulge only) and the tier-3
      choices; rows into `_audit` with tiers.
- [ ] Null texts beside χ²_red (sd √(2/(N−P))), DW (≈ 2/√N) and the off-region pair: text only.
- [ ] Coherent-residual scan + edge windows + Σz/√N with the counts-σ offset, per contiguous
      fitted run; cached Monte Carlo null (or the Siegmund–Worsley tail, as ruled).
- [ ] Bulge row, with the width skip measured on a measured-blank case before it lands.
- [ ] Replica scan on isolated lines, and `split_lines(result, lines=, calibrant=)`; blind spots
      (asymmetry 0.01, split 3e-4) in the docstring.
- [ ] Gated: `stack_residuals` over a series (#1218 S1), only after a planted broad-overshoot
      case and one real series are measured.
- [ ] Cost: within WP-1335's budget (the issues quote 0.15 s first call, then < 1 ms; 7 ms for
      9 lines).
- [ ] Tests on both synthetic families and the four public patterns + PNGs to `tests/output/`.
- [ ] Skill: none unless a row gains a name an agent reads; then its reference row.

## Acceptance

Exact-model nulls stay under their 99 % point on ≥ 19/20 per family; the planted hump, edge rise
and 5 % replica arms read as the issues report; the bulge on a measured blank's sharp line is
skipped. Every row prints its effect in data units.

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

Naus 1982, JASA 77, 177; Siegmund & Worsley 1995, Ann. Stat. 23, 608; Dümbgen & Spokoiny 2001,
Ann. Stat. 29, 124; Page 1954, Biometrika 41, 100; Durbin & Watson 1950/1951; Hill & Flack 1987,
J. Appl. Cryst. 20, 356; Davies 1977, Biometrika 64, 247; Davies 1987, Biometrika 74, 33; Turin
1960; Benjamini & Hochberg 1995; Westfall & Young 1993; Nichols & Holmes 2002. Issues #1215,
#1216, #1218, #1219 (the series of proposals), #833 (comment), #1106 (comment).

## Handover log

- **2026-10-31** — created from the issue triage (#1215, #1216, #1218 S1). No open WP owns a
  residual-structure row: WP-2004 tiers existing gates and adds none; WP-2054 owns the
  asymmetry direction only; WP-1931 owns the auto background's order; WP-1977 owns Layer 0's
  unmatched-peak rule.
