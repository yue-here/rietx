# WP-2300 — A series declares each parameter, and refuses what it cannot honour

Milestone: series · Status: ⬜
Depends on: —
Priority: P3 2026-11-22 — a feature the series milestone was opened for (P2), down a rung: its first task is the maintainer's ruling on the declaration's vocabulary; back to P2 when ruled

## Goal

A caller declares, with globs, which parameters a series refines on each pattern and which it
holds at a value the caller supplies. A declaration of a common parameter or an equation in
the series call raises, and the message names the joint call. This is series rule 1 on the
series call, and rule 2's refusal.

## Context

**The rulings.** [`../milestones/series.md`](../milestones/series.md) § The rules is the
authority. Rule 1 (accepted 2026-11-16): each parameter is declared as one of four kinds, by
glob. The kinds are refined separately on each pattern, refined as one value common to all
patterns, fixed at a value the caller supplies, and computed from an equation in the pattern's
temperature or time. A parameter with no declaration is refined on each pattern. "The globs
work as `SharingMap` and `hold` already do." Rule 2 (accepted 2026-11-16, "Yes, two calls"):
the series call accepts the per-pattern and fixed kinds only. The joint call accepts all four.
A series never stands in for a common value by freezing one pattern's value.

Two acceptance rows of the milestone land here:

- **A fixed value stays fixed** (rules 1 and 6). On WP-2081's cold-restart fixture
  (`docs/wp/2081-batch/measure_cold_rung.py`, frame 2 forced to the cold rung) a zero shift
  fixed at 0.00797° reads 0.00797° on every pattern and every attempt, and the cell stays
  within 2 ppm of the truth. WP-2081 built this for a hold declared in `constrain`
  (2026-11-22, `sequential._keep_held_values`, test
  `test_a_hold_keeps_its_value_across_the_cold_rung`). This WP proves it again through the
  declaration.
- **The series call refuses what it cannot honour** (rule 2). A parameter declared common or
  by equation in the series call raises, and the message names the joint call. No series
  result holds a common value by freezing one pattern's.

**The surface today** (read 2026-11-22 on `f590981ab`).

- Per pattern is what the series does now: the plan frees a path on every pattern, and
  `carry` (globs) passes values from the last accepted pattern.
- Fixed is spelled with a hook: `constrain=lambda i, ref: ref.hold("instrument.zero_shift")`,
  with the value in the models passed in. `vary=False` on the models does not fix anything,
  because a plan replaces the vary flags (WP-1208); only a hold does (WP-1435). Since
  WP-2081 the hold keeps its value on the cold rung, and `SeriesEntry.held_values` records it.
- The joint call (`refine_multi`, `MultiHistogramRefinement`, `multi.py`) takes
  `SharingMap(per_histogram=[...], shared=[...])` from `params/multi.py`, fnmatch globs checked
  in that order before the default. Its default is per histogram for `instrument.*` and
  `.scale` and shared for everything else. An equation is a `ParametricEquation` (WP-1325,
  WP-1964).
- So the two calls name the same idea differently today, and the series call has no
  argument for it at all.

**Open for the maintainer: the declaration's vocabulary.** This names something on the
top-level API, where the field has no standard term. A session does not pick it. Candidates
seen so far, each with what it costs:

- Reuse `SharingMap` on the series call. Its two fields are `per_histogram` and `shared`. It
  has no field for a fixed value or an equation, so it would grow two, and "histogram" is the
  joint fit's word.
- Reuse the `hold` verb. A `hold=[globs]` argument on `fit` and `refine_sequential` reads as
  today's `ref.hold`, and covers the fixed kind only. The refusal then needs a second
  argument, or the joint call's `SharingMap` passed in and refused.
- A new declaration object naming the four kinds, shared by both calls, which the joint call's
  `SharingMap` would then sit beside or be replaced by (a rename the joint call's users see).

Questions that go with the vocabulary: whether the declaration is one object used by both
calls; whether "fixed" takes the value from the models passed in or from the declaration
itself; and what the refusal's message says (reader output, so it is checked blind in the PR).

**Practice** (`docs/practice.md` § Sequential refinement). GSAS-II, FullProf, TOPAS and
EasyDiffraction keep the fixed flag on the parameter and honour it on every pattern of a
series. GSAS-II spreads flags across histograms with "Copy flags". One refined number across
patterns is a joint fit in every program: TOPAS's top-level parameters across `xdd`s,
FullProf's multi-pattern PCR, GSAS-II's multi-histogram refinement (recall). No program
surveyed refuses a shared parameter in its sequential mode, since none has one there to
refuse (inferred).

**Tier.** The declaration is a caller's statement and its default (no declaration) is
today's behaviour, which the maintainer kept on 2026-11-16. So its default row is `caller`
while that holds (`_audit.py` docstring). The refusal is no heuristic.

**Related.** WP-2081 (the discussion; question 4 built); WP-2301 (the typical temperature
preset bundles this WP's declarations, rule 4); WP-2103 (a joint fit starting from a series
result, rule 2's other half); WP-1325 and WP-1964 (equations on the joint call); WP-1435 (the
hold); WP-1441 (`constrain`).

## Non-goals

- The common and equation kinds on the joint call: they exist there (`SharingMap`,
  `ParametricEquation`). Whether that call adopts the new vocabulary is part of the
  vocabulary ruling, and building it is this WP only if the ruling says so.
- A start from a series result (WP-2103).
- The preset and the documentation route (WP-2301).

## Tasks

- [ ] The maintainer's ruling on the vocabulary (§ Context, "Open for the maintainer"),
      recorded here with his words.
- [ ] The declaration on `SequentialRefinement.fit` and `refine_sequential`: per pattern
      (the default) and fixed, the fixed kind held on every pattern and every rung.
- [ ] The refusal: a common or equation declaration raises before the first fit, naming the
      joint call; the acceptance row's test.
- [ ] The acceptance row "a fixed value stays fixed" through the declaration, on WP-2081's
      cold-restart fixture.
- [ ] Audit rows for the new defaults (`DEFAULT_SEATS`), `help.py` entries, the manual's
      `reference/series.md`.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the `constrain` bullet of `references/series.md` gives way to the declaration;
      the hold stays documented for what the declaration does not cover.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py
.venv/bin/python docs/wp/2081-batch/measure_cold_rung.py
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py tests/test_manual_api.py
```

## References

- [`../milestones/series.md`](../milestones/series.md) § The rules, § Acceptance.
- `src/rietx/sequential.py` (`fit`, `_fit_one`, `_keep_held_values`),
  `src/rietx/params/multi.py` (`SharingMap`), `src/rietx/refine.py` (`Refinement.hold`).
- `docs/practice.md` § Sequential refinement.

## Handover log

- **2026-11-22** — created (a ghostshift runner, in WP-2081's session). The series rules
  ruled on 2026-11-16 say how a caller declares each parameter, and nothing on the series call
  spells it yet. No open WP owned rule 1's declaration on the series call or rule 2's refusal:
  WP-2103 owns the joint call's verbs and its start from a series result, and WP-2081 was the
  discussion. The two are one seam (the series call's signature) and one decision (the
  vocabulary), so they are one WP. Facts above checked on `f590981ab`.

  *Next:* put the vocabulary question to the maintainer.
