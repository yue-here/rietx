# WP-2300 — A series declares each parameter, and refuses what it cannot honour

Milestone: series · Status: ⬜
Depends on: —
Priority: P2 2026-11-23 — a feature the series milestone was opened for; the vocabulary and names are ruled, so it is ready to build

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

**Ruled: one declaration object for both calls** (the maintainer, 2026-11-23, "(d) one
object", choosing among a `hold=[globs]` argument (b), a grown `SharingMap`, and this). One
object names the four kinds by glob: per pattern, common, fixed and equation. The series call
and the joint call both take it. The series call raises on a common or equation declaration
and names the joint call, which the milestone's approved acceptance row needs (2026-11-18):
under (b) the series call would carry arguments that exist only to raise. The joint call's
`SharingMap` is replaced by the object rather than kept beside it, since rietx's users are few
and in direct contact. Settled by Claude with the brief, and open to the maintainer's
reversal:

- A parameter left undeclared keeps each call's default today: per pattern in a series, and
  in the joint call shared except `instrument.*` and `.scale`. One default for both would
  change the joint call's default for every user.
- "Fixed" takes its value from the models passed in, as `hold` does. The object carries globs
  only.
- The stand-in mistake (a fixed declaration meant as a common value) runs in silence under
  any shape. Series rule 2 names it as the observation that reopens the two-call ruling, and
  DESIGN Rule 4 does not reach it, since the call can honour what was written.

**The names** (chosen 2026-11-23 against DESIGN Rules 4 and 5, at the maintainer's request:
"check against our rules and choose the best option"):

```python
rx.refine_multi(patterns, s, insts,
                declare=rx.Declaration(per_pattern=["phases.*.scale"],
                                       shared=["phases.0.cell.*"],
                                       held=["instrument.*"],
                                       parametric=[rx.ParametricEquation(...)]))
```

- `shared` and `parametric` keep the joint call's words for the same jobs (Rule 5, convention):
  `SharingMap.shared`, and `refine_multi(parametric=...)`. "Parametric" is also the
  literature's word (Stinton & Evans 2007). The literature's term for a shared parameter is
  "global", which Python reserves, and TOPAS's `local` is one program's keyword (Rule 5,
  conflicts).
- `per_pattern` replaces `per_histogram`. "Histogram" is GSAS's word, and both calls take
  `PatternData`. The joint call's `hist.N.` dot-path scope becomes `pattern.N.` in this WP
  (the maintainer, 2026-11-23, "Rename, with refusal"). No stored file holds these paths, since
  a joint fit keeps no history or project. A path or glob that still starts with `hist.`
  raises and names `pattern.`, because an old plan glob would otherwise match nothing in
  silence (DESIGN Rule 4). The class `MultiHistogramRefinement` and the word in prose are not
  part of this ruling.
- `held`, not `fixed`: the kind is built on the hold (WP-1435), and its record already says
  held (`Entry.held`, `SeriesEntry.held_values`, `held_because`). A field named `fixed` would
  read as `vary=False`, which a plan overrides. That is the likeliest misuse (Rule 4), and
  this WP inherits it.
- `Declaration` and `declare=`: no existing name covers four kinds, and `SharingMap` would
  call a held parameter and an equation shared. Series rule 1's accepted text says each
  parameter "is declared", and no public name uses the word.

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

### Inherited

- **2026-11-23, from the API review (WP-2302's batch, `2302-batch/plans.md`).** The trap this
  WP's vocabulary settles reaches a single fit too. On the NAC example (`f9adf0e57`),
  `Refinement.set_vary("instrument.zero_shift", False)` and then `fit()` refines zero shift
  again, with no warning and no diagnostic, because a plan starts every fit from nothing free
  (WP-1208). DESIGN Rule 4 now says a literal the call cannot honour raises before any work,
  and Rule 5 that a convention letting the likeliest mistake pass in silence is found wrong
  (both amended 2026-11-23). Three fixes were weighed and none taken outside this WP: a
  diagnostic when a plan re-frees a path the caller fixed (withdrawn: it needs state outside
  the models, and no `set_vary` node is recorded before the first fit); making
  `set_vary(..., False)` a hold (changes the verb for every user); splitting the verb into two
  named verbs (renames the top-level surface). Measure first which calls still read a vary
  flag a caller set before a fit, then decide alongside the declaration's vocabulary.

## Non-goals

- New behaviour for the common and equation kinds on the joint call: they exist there
  (`SharingMap`, `ParametricEquation`). This WP changes only how the joint call is told
  (ruled 2026-11-23).
- A start from a series result (WP-2103).
- The preset and the documentation route (WP-2301).

## Tasks

- [x] The maintainer's ruling on the vocabulary's shape (§ Context, "Ruled"), recorded with
      his words.
- [x] The names for the object, its argument and its four fields (§ Context, "The names").
- [ ] The joint call takes the object in place of `SharingMap`.
- [ ] The joint fit's `hist.N.` path scope renamed `pattern.N.` across source, manual,
      examples and tests (338 uses on `bacb7d58b`), and a `hist.` path or glob refused with a
      message naming `pattern.`; its test, and the refusal's text checked blind as reader
      output.
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

- **2026-11-23** — the maintainer ruled the declaration's shape: one object for both calls
  ("(d) one object"). Recorded in § Context with the three calls settled alongside it. Read
  first: DESIGN Rule 4's misuse test (amended 2026-11-23) does not decide the shape, since it
  reaches only literals and patterns a call cannot honour; series.md § Acceptance's refusal row
  does. Facts checked on `bacb7d58b`.

  *Next:* the maintainer's names, then the build.

- **2026-11-23** — names chosen at the maintainer's request, against DESIGN Rules 4 and 5:
  `rx.Declaration(per_pattern=, shared=, held=, parametric=)`, taken as `declare=` by both
  calls. Grounds in § Context. The alternative weighed was `rx.Sharing(..., shared=,
  parametric=)` under `sharing=`, the smaller rename for joint-fit users; it names two of the
  four kinds wrongly.

  *Next:* the build (the tasks below the names).

- **2026-11-23** — the maintainer ruled the joint fit's `hist.N.` scope renamed `pattern.N.`,
  with the old prefix refused ("Rename, with refusal"). An earlier note here said the rename
  would change a stored format; it was wrong, since a joint fit stores none. Whether
  `MultiHistogramRefinement` is renamed too is still open for the maintainer.

  *Next:* the build.
