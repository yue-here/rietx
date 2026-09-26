# WP-1326 — satellites at G ± k, with no moment model: is it magnetic?

Milestone: v1.6 · Status: 🔄 2026-09-26 — the satellites and their report arm landed from outside (PR #468); the public k ≠ 0 pattern and the Cr₂WO₆ PNG remain
Depends on: — (first rung of the magnetic scattering track; 1327 builds on
its reflection list)
Priority: P2 2026-09-23 — the open milestone's first rung, nothing blocks it

## Goal

A phase can declare a commensurate propagation vector k, and the compiled
model then carries reflections at G ± k beside the nuclear list: Le Bail and
Pawley extract intensity on them, a Rietveld stage contributes zero nuclear
intensity there, and the unexplained-intensity report gains an arm that says
whether the residual peaks index as satellites of a small candidate set of k.
A user with unindexed low-angle intensity in a neutron pattern can test the
magnetic hypothesis without stating a single moment.

## Context

This is the first of four WPs that take magnetic scattering out of the v2
fence (ROADMAP § Unscheduled, the magnetic scattering track; the grounds are
recorded in DESIGN.md under *Scope discipline*). It is deliberately the rung
that needs no form factor, no magnetic symmetry and no neutron-only physics:
a satellite is a position, and positions are what the package already
freezes per stage.

**The asymmetry this rung closes.** `refine.py`'s unexplained-intensity
report names *a magnetic contribution* among the causes of intensity the
model puts nowhere (`refine.py` ≈ line 3067 and 3156, the same sentence the
manual repeats in `using/refining.md`). The package can therefore tell a
user their residual might be magnetic and offers no way to test it. The
readers refuse the same construct in three places (`io/projects/coverage.py`
`Stance.REFUSED` over `mag_space_group`, `mlx`, `mly`, `mlz`, …; the TOPAS
reader's raise at ≈ line 1915; WP-1314's refusal list). Those refusals stay
until WP-1328.

**What a propagation vector does to the reflection list.** For a commensurate
k, magnetic intensity sits at Q = H ± k for every reciprocal-lattice vector H
of the nuclear cell. Two rules from the FullProf manual (Rodríguez-Carvajal,
*FullProf Manual*, § Propagation vectors; in the maintainer's corpus) that a
naive generator gets wrong:

- k and −k are one vector when 2k is a reciprocal-lattice vector, and that
  test respects centring: on a C lattice (½, 0, 0) and (−½, 0, 0) are
  distinct, because (1, 0, 0) violates h + k = 2n; (0, 0, ½) is single
  because (0, 0, 1) is a lattice point.
- H runs over the reciprocal *lattice*. Centring conditions define which H
  exist and are kept; glide and screw absences are conditions on the nuclear
  structure factor, not on the lattice, and are not applied to a satellite.

The satellite multiplicity is the number of distinct Q in the union over the
Laue orbit of H and the star of k, found by enumeration and checked by orbit
counting, never by a formula (root CLAUDE.md's rule for a neighbour search
applies to a reflection orbit for the same reason). `generate_reflections`
merges ±h under the nuclear Laue group; satellites join that machinery as a
second `ReflectionSet` on the compiled phase, frozen at stage compile with
the nuclear one.

**What this rung cannot say, stated in the output.** With k = 0 the satellites
coincide with the nuclear lines, so a Le Bail extraction absorbs the magnetic
intensity into the nuclear intensities and the hypothesis is untestable by
this route. The report arm says so: "the excess sits on nuclear lines; a k = 0
structure and a nuclear misfit look alike here, and a pattern of the same
specimen above its ordering temperature separates them". WP-1329 makes that
comparison a series measurement. On an X-ray histogram a satellite is a
superstructure reflection, not magnetism, and the arm says that too.

**The candidate set is enumerated, not searched.** The arm scores the
zone-boundary vectors {0, ½}³ minus the origin (seven on a primitive
lattice, fewer distinct ones under centring) plus the third-order points
(⅓, ⅓, 0) and (⅓, ⅓, ½) on hexagonal and trigonal lattices, by how many
unexplained peaks fall inside the report's own 0.4·FWHM validity radius of a
satellite. It returns a ranked list and never a singleton (the indexing
rule); an incommensurate k is outside the set by construction and the arm's
sentence names that as the reason a good pattern can score nothing.

**Seams.** `crystallography/symmetry.py` (`generate_reflections`,
`reflection_orbits`, the transposed-rotation action on hkl), `model/forward.py`
(the per-phase reflection list frozen at compile; `lebail_update` and the
Pawley block take the satellites as more rows), `optimize/statistics.py`
(`count_unique_reflections` and `effective_observations` count satellites:
the observation count is reflections, and a satellite is one),
`schemas/structure.py` (`Phase.propagation_vector`), the report's
unexplained-intensity section, and `help.py` (a new parameter family fails
`tests/test_help.py` until it has an entry).

**Prior art, concepts only.** FullProf generates satellites from a list of up
to 24 k vectors and refines k in reciprocal-lattice units (an incommensurate
capability this WP fences). GSAS-II describes a commensurate structure in
its magnetic supercell instead, which is the shape WP-1327 adopts for the
moment model; the k-vector form here is the hypothesis tool and the two must
not both be declared on one phase.

### Inherited

- **2026-09-15, from the issue triage (issue #257 A1–A3, and PR #290):
  three amendments to this WP, and a layer that landed under it.**
  PR #290 (2026-09-10) added `crystallography.magnetic.operators`: operators
  with ε, groups from spglib's database, `identify()`,
  `allowed_moment_basis`. Nothing there generates satellites, so this WP's
  generator is still unwritten, but the operations a star of k needs can
  come from the spglib calls PR #290 already wraps. A1: make the candidate
  set a **pluggable generator** returning labelled k's rather than the
  literal {0, ½}³ plus the two trigonal/hexagonal points, so 1418's M-8
  (every special point and line of the zone, then a general-k grid) drops
  in without touching the arm. A2: label k where it has a CDML label (Aroyo
  et al. 2014), since MAGNDATA, ISODISTORT and k-SUBGROUPSMAG speak those
  labels and a user cross-checks against them. A3: the ±k multiplicity test
  in § Tasks covers a C-centred cell only; add P, I, F and R against
  |Laue orbit of H| × |star of k| minus coincidences, because the
  coincidence rule is where the enumeration and a formula disagree.

- **2026-09-17, from [1436](1436-k-is-the-wavevector-everywhere-else.md):
  `k` is free for the propagation vector.** The earlier note here warned that
  `scattering.py`, `structure_factor.py` and `dispersion.py` all spent `k` on
  sinθ/λ, in the same subpackage `crystallography/magnetic/` lives in, and
  asked this WP to spell the propagation vector out rather than add a second
  bare `k`. 1436 has landed: that quantity is `stol` in python and `s` in
  equations throughout, following Waasmaier & Kirfel and the IUCr core
  dictionary, and a tree-wide sweep found no line left pairing a bare `k` with
  sinθ/λ in `src/`, `tests/`, `examples/` or the manual. **So name the
  propagation vector `k` and add no qualifier.** Root CLAUDE.md § Conventions
  carries the rule that keeps it free. The same note is in 1327, 1328, 1329 and 1418.

## Non-goals

- Any moment, form factor, or magnetic symmetry: WP-1327.
- An incommensurate or refinable k. Rational components only; a k that is
  not a fraction with a small denominator is refused by name.
- More than one k on a phase.
- Multi-phase indexing of the residual (fenced by 1018–1027). The arm tests a
  fixed candidate set against a cell the user has; it does not index.

## Tasks

- [x] `Phase.propagation_vector`: rational components over the conventional
      reciprocal basis, validated commensurate, with the ±k equivalence test
      and the centring rule above; refused together with a magnetic operator
      list once 1327 adds one.
- [x] Satellite generation as a second `ReflectionSet` per phase: enumeration
      over the lattice, multiplicity by orbit counting, an equivalence test on
      a C-centred cell against the manual's two examples.
- [x] The compiled model carries satellites through every mode: Le Bail and
      Pawley rows, zero nuclear contribution under Rietveld, ticks for every
      emission line, the observation count.
- [x] The report arm: the enumerated candidate set, the ranked list, the k = 0
      sentence, the X-ray sentence.
- [x] `help.py` entry, skill row, manual Part 1 (`using/refining.md`, the
      unexplained-intensity section) and Part 2 (the satellite condition as
      an equation with its *Source* line). (`help.py`: no arm covers a
      `Phase` schema field, so there is no entry — handover 2026-09-26.)
- [x] Vendor the Cr₂WO₆ 4 K and 150 K HB-2A patterns from the GSAS-II
      tutorial repository (`Magnetic-II/data`, ORNL data distributed by
      Argonne; licence checked per file, a `tests/data/README.md` row each);
      they serve 1327's acceptance as well. (Vendored by WP-1327's PR #433.)
- [ ] Source a public constant-wavelength neutron pattern with a published
      k ≠ 0 structure (search the maintainer's corpus first, then ask; the
      GSAS-II `Magnetic-III` … `-V` folders are the first place to look).
- [ ] Tests, including the acceptance below, with obs/calc/diff PNGs to
      `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_satellites.py -q
.venv/bin/python -m ruff check src tests examples
```

- A synthetic pattern with peaks at G ± (0, 0, ½) on a known cell: the Le
  Bail extraction puts intensity on the satellites and the report arm ranks
  (0, 0, ½) first, by generated positions rather than by eye.
- The satellite count on a C-centred cell matches the manual's equivalence
  rule for both worked examples.
- The Cr₂WO₆ 4 K pattern against its 150 K nuclear model: the arm reports the
  excess on nuclear lines and names the k = 0 ambiguity; no candidate scores.
- Every number a shipped fixture pins is bit-identical with
  `propagation_vector=None`.

## References

- Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
  manual's § Propagation vectors and eqs 3.47–3.54 are in the maintainer's
  corpus.
- GSAS-II tutorials, `Magnetic-II` (Cr₂WO₆, HB-2A at HFIR, 4 K and 150 K,
  λ = 2.4067 Å) — github.com/AdvancedPhotonSource/GSAS-II-tutorials.
- [1327](1327-magnetic-structure.md) the moment model; [1328](1328-magnetic-interchange.md)
  the readers; [1329](1329-moment-in-a-series.md) the series;
  [1134](1134-constant-wavelength-neutron.md) the CW-neutron instrument and
  the fence this track opens.

## Handover log

### 2026-09-26 — the satellites landed from outside

A phase can now declare a commensurate propagation vector, and its satellites
at Q = H ± k join the frozen reflection list. The unexplained-intensity report
now asks whether leftover peaks index as satellites of some k. Neither needs a
moment, a form factor or a magnetic group. It arrived as the contributor's
PR #468, first in the order on #286. It was reviewed over three rounds (one
finding list, one stray-file and rebase round, one rebase onto #477) and
merged after #477, so its rung is `SCHEMA_VERSION` 0.32. Six of the eight
task lines tick. Four tick outright. The manual-and-skill line ticks with
`help.py` recorded as moot. The vendoring line ticks because WP-1327's PR #433
had already done it (`0e3119d`). The public k ≠ 0 pattern and the tests line,
which asks for the Cr₂WO₆ PNG, remain.

- *Done*: PR #468, merged as `a15959be`.
  - **`Phase.propagation_vector`** stores three exact rational strings, whatever
    the spelling it was given. An incommensurate component is refused by name,
    and so is a k ≡ 0 modulo the reciprocal lattice, a test that respects
    centring. It is refused beside a moment model through WP-1327's
    `refuse_moment_model_with_k`, which now runs for real.
  - **`crystallography/satellites.py`** enumerates H over the reciprocal
    *lattice*, so centring conditions apply and glides and screws do not. The
    multiplicity comes from orbit counting under Rᵀ with Friedel mates, and a
    product-formula test checks it against an independent orbit count on
    P/I/F/R cells. The file also holds the ±k rule and the zone-boundary
    candidate generator. The arm takes any `CandidateGenerator` (#257 A1), and
    `cdml_label` returns `None` until the CDML tables are sourced (#257 A2).
  - **The compiled model** merges the satellites into the phase's list at stage
    compile. Le Bail and Pawley put intensity on those rows. Under Rietveld
    they contribute exactly zero through WP-1327's `nuclear_mask`. Le Bail
    carries intensities on (H, m), because H + k and H − k can share one H.
    `ReflectionState.satellite_order` stores the m. The no-k path is
    arithmetic-identical: it has no mask multiply and no merge.
  - **Every reader that identifies a reflection takes (H, m) or H + m·k.**
    That is `tick_hkl` (a satellite row is `[h, k, l, m]`) in `refine.py`,
    `multi.py` and `viz/snapshot.py`; `report/strain.py`'s d and Stephens
    monomials; and the `PAWLEY_OVERLAP_UNRESOLVED`, `PAWLEY_OFF_DATA_RIDGED`
    and `STEPHENS_STRAIN_NOT_POSITIVE` names. `ReflectionSet.hklm` and
    `reflection_label` hold the one spelling. The structure factor and the Le
    Bail key's H half read the parent on purpose.
  - **`FitReport.satellites`** (`THRESHOLDS_VERSION` 1.7, no new threshold)
    sorts positive residual peaks three ways: on a calculated line, on a
    forbidden reciprocal-lattice point, or neither.
    - It ranks the candidates against the third group within
      `VALIDITY_RADIUS_FWHM`. It names the best with its `n_satellites`, the
      runner-up's `matched` and `n_satellites`, and a tie flag.
    - A peak on a forbidden point gets a sentence naming what the arm cannot
      separate: a true group lacking that glide or screw, λ/2, an impurity
      line, and a k = 0 magnetic structure on neutrons only. It cites
      Gallego et al. (2012) for the complementary absence rule.
    - The parent grid is built once per phase and offset per candidate.
  - Part 2 § Satellites of a propagation vector (`peak-positions.md`, two
    equations); Part 1 across `refining.md`, `report.md`, `data.md`,
    `history.md` and `exports.md`; the skill's satellite-arm section in
    `references/magnetic.md` and the widened §7j routing row.
  - A `satellites` config in `test_cross_backend.py` covers the masked `df2`
    branch a satellite phase now reaches. The contributor made it fail on
    purpose by removing the mask multiply.
- *Not done*:
  - **The public k ≠ 0 pattern** (task line 7). The tree has Ba₂FeSbSe₅'s
    nuclear model and not its pattern. `Magnetic-III`/`-IV` (#257 A7) are
    still the first place to look.
  - **The Cr₂WO₆ acceptance writes no PNG.** Only the synthetic positive arm
    writes `tests/output/satellites_k_00half.png`.
  - **`help.py`** has no arm for a `Phase` schema field, so
    `propagation_vector` has no entry. Adding one is an arm, not a row.
  - **An operation-list phase with a k** is still refused by
    `check_propagation_vector`. Three places need the list when it lands:
    `_k_is_usable`, `compile_model`'s `satellite_reflections(...)` call and
    `merge_satellites`. `_resolve`'s docstring names them.
  - **Canonical k.** `as_kvector(("3/2", "0", "0"))` keeps 3/2. Positions and
    counts agree with ½ (probed in P m m m, P 1 and P -1), but every parent H
    shifts, so a Le Bail node written under one spelling cannot restore under
    the other. This needs its own rung with a migration.
  - **The three browser pages** show a four-index `tick_hkl` row unlabelled
    rather than as its parent. They need a dist rebuild.
  - **The GSAS-style peak list** (`io/recipe.py`) writes a satellite as its
    parent H. That is a format decision.
- *Deviation from the acceptance text*: "no candidate scores" on Cr₂WO₆ does
  not hold. At 4 K the two best zone-boundary candidates each index 2 of the
  6 leftover peaks. At 150 K, with no magnetic order, the best indexes 2 of 5.
  The arm has no chance baseline, so the test asserts the k = 0 signature (4
  peaks on forbidden points at 4 K, 0 at 150 K) and not that clause. The note
  now prints the comparison a reader needs to see that for themselves.
- *Gotchas found in review* (round one; each fixed with a test):
  - The k = 0 sentence first called any peak on a forbidden point "a result
    rather than an ambiguity", on X-rays too.
  - The best candidate was named without the runner-up, which read as a
    confident singleton on a pattern with no magnetic order.
  - Of 15 readers of `reflections.hkl`, 9 took the parent H where they meant
    the satellite. A satellite of (0 0 0) got d = ∞ in the strain report.
  - The arm re-enumerated the whole grid per candidate: 27.7 s on a
    moderate P2₁/c cell to 150°. The contributor measured 7.1-8.6 s → 1.43-1.46
    s on their machine after the fix.
  - A no-k Le Bail node gained `"satellite_order": null`. The comment is now
    true, and a test pins the dump.
- *Measured on the merged tree* (Linux x86_64, python 3.12.3, `[dev,jax]`, 4
  cores, run as root, nothing else running):
  - ruff clean.
  - Fast suite on `dfd09df` + #468: 6307 passed, 109 skipped, 1 failed,
    20:39. The failure is `test_telemetry`'s unwritable-directory case, which
    fails identically on `main` as root. `ee2a027` adds docs only, and
    `test_docs_consistency.py` passes on it.
  - Full `-m slow` on `ee2a027` + #468: 227 passed, 14 skipped, 2 failed,
    1:22:04. Neither failure is the PR's, and both are the pair #477's merge
    met.
    - The ramp runaway guard in `test_held_phase` took 152 s against 60 s
      under `-n auto`. It passes alone in 14 s on the same tree.
    - Brucite's strict xfail passed. It is in indexing, which the PR does not
      touch.
  - `main` moved to `2443090` (#483, the polyhedra) during the slow run. #483
    shares no file with #468, and `gui/structure3d.py` reads nothing #468
    changes. The maintainer merged on the evidence above rather than wait for
    a re-run, so **no suite ran on the final merged tree**.
  - CI's fast jobs and lint were green on `14d4705a`.
- *Next*: #478 (WP-1328, magnetic interchange) conflicts with this merge in
  eight files. Its §7j routing row cannot simply be unioned with this one
  under `SKILL_MAX_BYTES`. After that come the public k ≠ 0 pattern and the
  Cr₂WO₆ PNG.

- **2026-09-02** — created, from the assessment of PR #221 (an outside
  proposal for a single magnetic WP, which conflicted with main and left the
  design open). Split off as the rung that needs no moment: a satellite is a
  position. No code touched. First task is the schema field and the
  equivalence test.
