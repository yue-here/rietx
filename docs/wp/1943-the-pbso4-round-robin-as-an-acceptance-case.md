# WP-1943 — the PbSO₄ round robin as an acceptance case

Milestone: unscheduled · Status: 🔄 2026-11-09 — claimed by @mustachefeeling
Track: Coming from another code
Depends on: —
Priority: P3 2026-10-11 — evidence for a validation claim; no user waits on it, and the data are already in the tree

## Goal

The suite refines the IUCr CPD PbSO₄ round-robin patterns (Hill 1992) from
the published single-crystal model and asserts the answer against the
inter-laboratory spread of 11 programs. The GSAS-II project reader hands a
caller each histogram's observed arrays, which is what makes that possible
through a public reader.

## Context

**The reference (issue #875).** Hill (1992) is the only published
inter-laboratory spread of Rietveld parameters. Two patterns of one PbSO₄
specimen: a D1A neutron pattern and a Cu Kα Bragg–Brentano pattern. 18 X-ray
and 20 neutron refinements, made with 11 programs. Table 7 gives the weighted
mean, the range and σ_ext for the cell, every coordinate and every B. Table 9
gives the neutron β_ij. The paper is **not in the local corpus** (Zotero
searched by title and DOI on 2026-10-11), so ask the maintainer for it before
writing a number.

**The data are already vendored.** `tests/data/gsas2_pbso4.gpx` is the
GSAS-II CIF tutorial's project (`tests/data/README.md`, GSAS-II Open Source
License, test data only, never in the wheel). Per the issue it carries both
round-robin patterns. The neutron one runs 10.00–155.85° in 0.05° steps,
2918 points, with the per-point counter number as the weight. The X-ray one
runs 10.000–159.975° in 0.025° steps, 6000 points. The issue's filer checked
both point for point against independent copies.

**The reader, checked at `f11e22d3`.** `read_gsas2_gpx`
(`io/projects/gsas2.py`) returns a `Gsas2Model`. `_histogram` reads the
`PWDR` payload's arrays (`payload[1]`), and `Gsas2Histogram` keeps only
`n_points` from them. No public surface returns the observed 2θ, y or
weight.

**Two ways to expose the arrays; task 1 picks one.**
- A method on the histogram returning `PatternData`, as the issue proposes.
  Small, and it stays inside the project reader.
- A `.gpx` entry in `io.readers.PATTERN_FORMATS`, with `scan=` selecting the
  histogram. A project's `DataRef` records which format claimed a file and
  its options, so only this form lets a `.rex` project reference a `.gpx`
  pattern. `src/rietx/io/CLAUDE.md` owns how a format is added.

Either way, two rules bind the weight. A foreign format's unit is measured
against that format's own reference output, never adopted from its prose
(root CLAUDE.md, comparing against another code). And σ is the file's when
the file states one (the weights invariant). GSAS-II stores w = 1/σ², and
the issue reads the neutron histogram's w·y as the per-point counter number.
That scale must be shown against GSAS-II's own Rwp of 6.171 % over 8 739
channels before any fit uses it.

**What the issue measured, at `bdaa7b62`.** An agent working from the skill
and manual alone refined from the published model. These numbers are the
filer's and are not yet reproduced on this tree.

| | neutron, iso B | X-ray, iso B | joint, λ_N free |
|---|---|---|---|
| Rwp / GoF | 3.42 % / 1.74 | 7.81 % / 1.62 | 4.91 % / 1.68 |
| round robin's Rwp / GoF range | 2.4–12.3 % / 1.0–3.1 | 8.2–20.0 % / 1.3–7.4 | — |
| Table 7 values inside the range | 18 / 19 | 19 / 19 | — |
| largest \|value − mean\| / spread | 2.0 (B of O3) | 1.6 (a) | — |

"Spread" is σ_ext·√n, Hill's esd of the mean scaled to one refinement.
Anisotropic ADPs on the neutron data gave Rwp 2.35 %, all 19 values in range
and 18 of 22 β in range. Two of Hill's qualitative findings reproduced. A
physical axial-asymmetry model (FCJ) raises the neutron cell 0.08 % toward
the X-ray cell (Hill p. 605). The joint fit measures λ_N = 1.9115(1) Å
against the nominal 1.909 Å (Hill: "closer to 1.912", p. 605).

**The envelope rule applies.** Several references form an envelope, so the
gate is the span the participants bracket, and the spread itself is
reported (root CLAUDE.md, WP-1306). Every asserted number is the paper's
published value, never this package's own.

**Not claimed: esd calibration.** Hill's √ℜ comes from one dataset refined
many ways, not from replicate measurements (his footnote, p. 606).

## Non-goals

- Esd calibration from the round robin (above).
- A GSAS-II *pattern* reader for `.fxye`/`.gsa` files. That is
  `io/readers`' existing work, not this WP's.
- Fixing anything the fit turns up. A defect found while writing the test is
  filed, and the test records it as an expected failure with the WP number.

## Tasks

- [ ] Choose the surface (above), and expose each histogram's observed 2θ,
      y and σ. Show the weight's scale against GSAS-II's stored Rwp and
      channel count before any fit reads it. *Decided 2026-10-13 (the
      maintainer, through the issue triage; #875):* the surface is a `.gpx`
      entry in `PATTERN_FORMATS` with `scan=` picking the histogram; it shares
      `gsas2.ALLOWED_GLOBALS`, sits in the binary-first dispatch position and
      declares `fmt.scans` (the biconditional), and `read_gsas2_gpx` calls the
      same histogram read.
- [ ] Obtain Hill (1992) from the maintainer. Transcribe Table 7 and Table 9
      into a fixture with the page and table cited per row.
- [ ] `tests/test_acceptance_pbso4_round_robin.py`, slow-marked: neutron,
      X-ray and joint fits from the published single-crystal model. Assert
      every Table 7 value inside the participants' range, |Δ| under a bar
      stated in spreads and justified in the docstring, and λ_N inside a
      stated band. Declare every protocol setting explicitly, dispersion
      included (`tests/test_validation_matrix.py`).
- [ ] A row in `tests/test_compare_ui.py`'s standards if the case becomes a
      `rietx compare` standard; otherwise say why not.
- [ ] `docs/VALIDATION.md`: the case as the inter-laboratory reference.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: none expected. If the agent run in the issue needed a passage
      the skill lacked, that is WP-1532's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_projects_gsas2.py tests/test_acceptance_pbso4_round_robin.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Hill, R. J. (1992). *J. Appl. Cryst.* 25, 589–610,
  doi:10.1107/S0021889892003649 — the IUCr CPD Rietveld round robin on
  PbSO₄.
- GSAS-II tutorials, `CIFtutorial/data/NXPbSO4.gpx` (the vendored file).
- Issue #875; issues #876 and #877 came from the same runs.

## Handover log

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #875).
  Checked against the tree at `f11e22d3`: the `.gpx` is vendored with its
  licence recorded, `read_gsas2_gpx` loads the arrays and exposes only their
  length, and `docs/VALIDATION.md` exists. No open WP owns it: no open WP
  names `read_gsas2_gpx`, and the open WPs naming the round robins mean the
  QARR `.prn` set, a different round robin. The issue's fit numbers are not
  reproduced here. *Next:* task 1, and ask for the paper.
