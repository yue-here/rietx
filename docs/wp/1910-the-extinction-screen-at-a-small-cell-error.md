# WP-1910 — the extinction screen at a small cell error, and the other centring

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-05 — a silent wrong answer on a path few fits run: at +0.06 % the screen refutes certified corundum's class and returns one whose members exclude it, nothing names the cell, and the skill's own recipe screens the unrefined index cell

## Goal

`determine_extinction_symbol` states what it requires of the cell it is
handed. A cell a few hundred ppm off then either gets the certified class or a
finding that names the cell as the cause. A P candidate whose R twin is in the
candidate list is told that the screen cannot reach the twin's groups.

## Context

**Source.** Issue #726 (2026-10-05), a design proposal on the IUCr CPD
round-robin SRM 676a corundum pattern (`tests/data/qarr/corundum.prn`;
Madsen et al. 2001). It asks which of two behaviours is intended and for the
documentation to say so.

**1. The screen holds the cell.** Its first step is one shared profile fit of
the absence-free lattice group under `workflow.validation_plan`
(`src/rietx/indexing/workflow.py:256`): background, one shift parameter, `w`,
then `u/v/x/y`. The cell is held on purpose. The docstring argues for
*validation*: "the candidate *is* the hypothesis under test … a candidate whose
metric is slightly wrong is supposed to validate badly". Every class is then
fitted with that cell and instrument frozen (`indexing/extinction.py:654`,
pipeline steps 1-3). A uniform cell error leaves a tan θ position error that
the one shift cannot take, and the absence test reads the misfit at forbidden
positions as intensity.

Measured on `32ef5a6` (`[dev]`, Linux) with the suite's own fixture from
`tests/test_extinction_symbol.py` (`corundum_inputs`: `qarr_instrument()` +
`seed_widths`, 20-90°, certified cell a = 4.759355, c = 12.99231 Å), every
axis multiplied by the factor:

| factor | best class | `R - c -` | shared-fit Rwp |
|---|---|---|---|
| 0.9992 | `R - c -` (ΔBIC −2925.9) | survives | 0.2618 |
| 1.0000 | `R - c -` (ΔBIC −3434.4) | survives, 0 of 6 testable occupied | 0.2587 |
| 1.0004 | `R - c -` (ΔBIC −1811.8) | survives | — |
| 1.0006 | `R - - -` | refuted at (2,0,−1) 44.406°, 1 of 7 | 0.3035 |
| 1.0008 | `R - - -` | refuted at (2,0,5) 56.904°, 1 of 8 | 0.3375 |
| 1.0012-1.0030 | `R - - -` | refuted, 2 of 8 | — |

`R - - -` lists `R 3`, `R -3`, `R 3 2`, `R 3 m`, `R -3 m`, and none is the
certified `R -3 c`. (2,0,5) is one of the two positions WP-1077 removed as
neighbour-tail evidence; here it comes back through the cell. The reporter
measured the flip at ×1.0008 on their own instrument and said ×1.0012 still
passed with `qarr_instrument()`. That second reading did not reproduce with
the seeded fixture. Their certified-cell ΔBIC (−1284) is from another
instrument.

**Where a caller meets it.** The skill's indexing recipe
(`docs/skill/rietx/references/diagnostics-indexing.md:193-197`) runs
`rietx.refine(..., mode="lebail", plan="profile_only")`, discards the result,
and screens `cell`, the unrefined index candidate. The manual
(`docs/manual/using/indexing.md` § The extinction symbol) says to give the
screen "a range and a width law its profile fit can actually match", and says
nothing about the cell. Under the acceptance protocol, `index_pattern`'s
corundum cell sits within 150 ppm of the certificate (asserted in
`tests/test_acceptance_indexing.py`, `test_a_certified_lab_pattern_…`), inside
the measured +0.04 %. The reporter's index cell (a ≈ 4.765, +0.12 %) came from
their own protocol and was not re-run here.

**2. The other centring.** `compatible_groups` (`extinction.py:206`) keeps
the groups whose centring is the candidate's, and its docstring excludes the
`:R` settings because an R lattice arrives in hexagonal axes. Measured: a
trigonal R candidate reaches 7 groups including `R -3 c`; a trigonal P or a
hexagonal P one reaches 45, with no R among them. So a caller who keeps the
hexagonal P twin, which a Le Bail Rwp ladder favours because it has three
times the reflections, can never reach `R -3 c`. The candidate carries no
signal for this. `bravais_ambiguous` means only "the lattice symmetry appears
only at a loose tolerance, or the two methods disagree"
(`schemas/indexing.py:439`, set at `consensus.py:631`). The supercell check
(`supercell_refuted`, WP-1449) relates a superlattice to its parent in the
ranking, never in the screen. Whether `index_pattern` lists the P twin for
corundum, and with which caveats, was not checked here.

**What the reporter proposes.** (1) Document the contract in `indexing.md`:
the cell must be certificate-quality, with the margin and the remedy (refine
the cell by Le Bail first). (2) Optionally a caution, `CELL_OFFSET_REFUTES_CLASS`
in their words, when the best class's verdict flips under ±0.1 % cell scale
(two more evaluations). On this fixture it would fire at the certified cell
itself, since +0.06 % already flips it. (3) When the list holds a centring
twin, say so and screen both, or refuse to name a centring. Explicitly not
proposed: loosening the absence test, whose null model is deliberately silent
where the profile is wrong (WP-1077).

**A fourth option, from this triage.** Refine the cell inside the screen's
shared absence-free fit, then freeze it for every class. Validation's reason
for holding the cell does not transfer: in the screen the *class* is the
hypothesis and the lattice is given. This needs measuring on the three
real-data rows (FAP, NAC, corundum) before it lands, since every class
inherits the shared fit.

**Seen in passing.** The manual's corundum numbers in that section (ΔBIC
−218, five testable positions, shared-fit Rwp 0.149) are not what the suite's
fixture gives on this tree (−3434.4, six, 0.2587). The manual may describe
another protocol. Re-measure before editing the section.

**Fences.** Markvardsen, David, Johnston & Shankland (2001) is the Bayesian
form of the screen. Its full posterior is a v2 fence (`extinction.py:100-104`)
and is not proposed here. No code is ported.

## Non-goals

- Loosening the absence test or `_model_is_quiet` (WP-1077).
- The Bayesian posterior (v2 fence).
- How `index_pattern` ranks centring twins (WP-1449's supercell ordering).

## Tasks

- [ ] A failing row: the corundum fixture at ×1.0008 refutes `R - c -` today.
      Add the margin both ways at finer steps, and the same scan on FAP
      (`P 63 - -`) and the synthetic monoclinic, so the contract quotes a
      margin per pattern, not one number.
- [x] Maintainer decision on point 1, recorded here: document only; refine
      the cell in the shared fit; a caution (code name settled at review);
      or a combination. *Decided 2026-10-06: document the contract, and
      refine the cell in the shared fit as an option,
      `determine_extinction_symbol(..., refine_cell=False)` by default
      (draft PR #747). The caution was not decided.*
- [ ] Land it. If the shared fit changes, the FAP, NAC and corundum rows of
      `tests/test_extinction_symbol.py` must keep their classes.
- [ ] Maintainer decision on point 2: a new caveat or screen diagnostic for a
      centring twin in the list (not a wider `bravais_ambiguous`), screening
      both, or refusing to name a centring. Then land it.
- [ ] Manual Part 1, § The extinction symbol: the contract, and the corundum
      numbers re-measured.
- [ ] Skill: `references/diagnostics-indexing.md`'s recipe screens the
      Le Bail-refined cell (or states the contract), inside
      `tests/skill_caps.py`'s budget; a diagnostic code adds its row.
- [ ] Tests, with obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction_symbol.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_skill.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The corundum fixture at ×1.0008 either returns `R - c -` or reports a finding
that names the cell. The certified-cell, FAP and NAC rows keep their classes.
A hexagonal P candidate for corundum's metric says that the R twin's groups
are out of its reach.

## References

- Madsen, I. C. et al. (2001). *J. Appl. Cryst.* 34, 409 — the IUCr CPD QPA
  round robin, `tests/data/qarr/`.
- Markvardsen, A. J., David, W. I. F., Johnston, J. C. & Shankland, K. (2001).
  *Acta Cryst.* A57, 47-54 — cited in `extinction.py`. Not read in this
  triage.
- Issue #726; WP-1025 (the screen), WP-1077 (the neighbour-tail gate),
  WP-1449 (ranking on the screen).

## Handover log

- **2026-10-06** — Maintainer decision on point 1 of #726, through draft
  PR #747: the contract is documented, and `refine_cell=True` is wanted as
  an option with the default unchanged. Point 2 (the centring twin) and the
  `CELL_OFFSET_REFUTES_CLASS` caution are not decided, and #747 leaves both
  out.

- **2026-10-05** — created, from the 2026-10-05 issue triage (issue #726).
  Checked against the tree at 32ef5a6: on the suite's corundum fixture the
  certified class survives to ×1.0004 and is refuted from ×1.0006, and a P
  candidate reaches 45 groups with no R among them. No open WP owns it:
  WP-1510 (🔄, merged, every task landed) is the chemist's priors, WP-1511
  compares supplied cells by Le Bail and never screens a class, and WP-1447
  and WP-1542 are a ghost threshold and a Le Bail background. WP-1025, 1077,
  1449 and 1451, which built, gated and ranked the screen or share its word,
  are ✅. *Next:* task 1.
