# WP-2042 — a result names its radiation

Milestone: unscheduled · Status: ✅ 2026-10-24 — a result records its radiation, and `result.plot()` and each joint histogram's view name it on the 2θ axis
Track: Render what the fit already knows
Depends on: —

## Goal

`RefinementResult.plot()` labels its 2θ axis with the radiation, as `PatternData.plot()` does,
without the caller passing it.

## Context

- WP-2039 made `plot_pattern` name the radiation on its 2θ label (`viz/plots.py`,
  `_stated_radiation`): the model's source where its lines match the radiation table, else the
  file's own `anode` and wavelength from `data.metadata`.
- `plot_result` cannot do the same. A `RefinementResult` carries no field naming its source, so
  the function can only take `wavelength=`. In the tutorials, `data.plot()` says "Cu Kα" and
  `best.plot()` a few cells later says nothing.
- Closing it needs a recorded field on the result, so it is a schema change
  (`schemas/results.py`). A new field's default and its writer are named at review (root
  CLAUDE.md, WP-1076): an old result reopened from JSON has no value, and `None` must read as
  "not recorded", never as "no radiation".
- `_stated_radiation`'s rule (name an anode only where the lines match the table to the last
  digit) is the one to reuse, never a second copy.

## Non-goals

- Any other figure's labels.

## Tasks

- [x] The field on `RefinementResult`, written where `refine` builds the result, and read by
      `plot_result` through `_stated_radiation`'s rule. Also on `HistogramResult`, written by
      the joint fit's builder and swapped in by `for_histogram`, which copies the top-level
      fields and would otherwise label histogram 1 with histogram 0's λ. Schema 0.59 → 0.60.
- [x] Tests: a fit on a preset source labels the axis; a result from an older JSON file loads
      and draws an unnamed axis. Plus a refined λ and a synchrotron λ stated unnamed, and each
      joint histogram's view naming its own λ (`tests/test_multi_histogram.py`).
- [x] Skill: none. A figure label changes no judgement. The generated `api.md` field line
      moves with the schema.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_viz.py -q
```

## References

None.

## Handover log

### 2026-10-24 (2nd session) — closed: a result records its radiation and its figure names it

A fitted result now records the radiation it was fitted with, so its figure labels the 2θ axis
as the pattern's figure does, with nothing passed: `Cu Kα, λ = 1.54059 Å` for a tube preset,
and λ alone for a synchrotron, a neutron source or a refined wavelength. A joint fit records
each pattern's own, so each pattern's figure states its own λ. Before this, the per-pattern view
copied the top level and would have labelled the second pattern with the first one's λ. A result
saved before this change opens and draws the figure it always drew, byte for byte. No fitted
number moved: this is a new record and a label.

*Done.*
- `Radiation(kind, wavelengths)` in `schemas/results.py`, on `RefinementResult.radiation` and
  `HistogramResult.radiation`, default `None` meaning not recorded. One builder,
  `refine._radiation`, reads the compiled model's `source_kind` and `line_lambdas(values)`. Its
  two callers are `refine._build_result` (every single fit, `run_stage` and `replay`) and the
  joint fit's builder per histogram. A joint result's top level mirrors histogram 0, as its
  curves do, and `for_histogram(h)` swaps in histogram h's.
- `plot_result` reads it through `_stated_radiation(None, None, recorded)`. The rule is
  WP-2039's, unchanged: it gained an input. `wavelength=` still replaces it, and Q and d still
  need `wavelength=`.
- Schema 0.59 → 0.60, the first change after 1.10.0's tree. Also: the help entry, the GUI's
  help-key fixture, `_audit.OTHER_RECORD_FIELDS`, the skill's generated `api.md` (three copies),
  and the manual's `reference/figures.md`, `reference/joint.md` and `start/first-fit.md`.
- Inherited: none on arrival.

*Measured* (`[dev]` venv, darwin/arm64, no other suite running; main had not moved, so the
branch tree is the merged tree).
- Fast selection: 11656 passed, 272 skipped, 27 xfailed, 6:37. The branch adds 5 tests (four
  functions, one over two cases), all passes. Main's own count was not re-measured.
- The added tests' time, one local run: `test_a_result_names_the_radiation_its_fit_used` 0.46 s
  (2 cases), `test_each_histograms_view_names_its_own_radiation` 0.42 s,
  `test_a_synchrotron_or_refined_wavelength_is_stated_and_never_named` 0.13 s,
  `test_a_result_without_a_recorded_radiation_draws_an_unnamed_axis` 0.02 s. Per file:
  `test_viz.py` 0.62 s, `test_multi_histogram.py` 0.42 s. None joins the slow tail.
- vitest after the fixture changed: 590 passed in 24 files.
- Full selection: not run. Nothing a fit computes moved (`tests/CLAUDE.md` § Running, rung 3).
- Each guard made to fail once. Dropping the `for_histogram` swap fails the joint test with
  histogram 1 labelled `λ = 0.4139 Å`. Dropping the read in `plot_result` fails 3 of the 4
  `test_viz.py` additions. Recording the compiled λ instead of the refined one could not fail:
  `_final_compile` (`refine.py:5150`) recompiles at the answer, so on a single fit the two are
  equal. `line_lambdas(values)` stays, because it reads what the curves were evaluated with
  whatever the compile.

*Review.* `/code-review high --fix` found no code bug and six findings. Three were fixed (one
commit): `reference/joint.md` said a joint result does not record each pattern's radiation, its
field table and `for_histogram` list lacked the field, and the first-fit guide still passed a
`wavelength=` the result now carries. Three were declined. `plot_for_vlm`'s axis still reads
`2θ (deg)`: another figure, this WP's non-goal. The top level shares histogram 0's `Radiation`
object, as `qpa` already does. A restructure of `_stated_radiation` saves almost nothing.

*Not generalised.* `plot_for_vlm`, the GUI's plot and `rietx watch` label nothing new. Each is
"any other figure's labels", this WP's non-goal.

*Generality* (the `generality-review` judge, pasted unedited):

> ## `RefinementResult.radiation` added to `OTHER_RECORD_FIELDS`
>
> (`OTHER_RECORD_FIELDS` is `_audit.py`'s list of result fields that report no automatic action.)
>
> **Verdict: holds.** The evidence that the field only copies the source is in the code. I found none that it records a choice the package made alone.
>
> | Question | Author's answer, and where | What I found | Verdict |
> |---|---|---|---|
> | 1. What does it decide that the caller did not ask for? | Dispatch: "it reports no action the package took on its own; it copies what the caller declared (or what the fit refined, which the caller freed)." `refine._radiation` docstring: "the compiled kind and each line's λ at `values`, so a refined wavelength is recorded as refined." | `_radiation` returns two things. `kind` is `model.source_kind`, which `compile_model` sets from `instrument.source.kind`. `wavelengths` is `model.line_lambdas(values)`: the θ row where λ is free, the frozen declared value where it is not, and λ/n for a declared harmonic. There are exactly two writers, `refine.py:8116` and `multi.py:1915/2056`, the only constructors of `RefinementResult` and `HistogramResult` in `src/rietx`. Two conventions are the package's own. (a) A joint fit's top-level field copies histogram 0, as the top-level curves already do (`multi.py:2062`). (b) `None` means "not recorded", per the schema comment. Neither moves a fitted value. Separately, `HistogramResult.radiation` sits outside the guard, because `HistogramResult` is not in `RECORD_SCHEMAS` (the result types whose fields the audit table holds). Its other per-histogram fields are outside it too. | Decides nothing |
> | 2. Which kind of ambiguity, and does the row agree? | No `ambiguity` field. A list entry carries none. | No kind applies. It is a record of inputs and fitted values, like its neighbours `ticks`, `two_theta` and `sigma` in the same list. | Agrees |
> | 3. Case against (that it hides an action and needs a row) | — | none found | — |
> | 4. Case for keeping it a plain record | WP file § Context: "`None` must read as 'not recorded', never as 'no radiation'." | The default and both writers are named, as root CLAUDE.md asks of a new field (WP-1076, the rule that an empty default must not read as an answer). `test_a_result_without_a_recorded_radiation_draws_an_unnamed_axis` (`tests/test_viz.py`) loads a result with the key deleted and checks it reads `None`. `test_each_histograms_view_names_its_own_radiation` (`tests/test_multi_histogram.py`) checks that each histogram records its own λ. | Holds |
> | 5. Tier and source | Not applicable to a list entry. | Not applicable. | — |
> | 6. Dataset families behind a threshold | None given. There is no threshold. | Not applicable. | — |
> | 7. Which field or code says it fired | It is the record itself. | Nothing fires. | — |
>
> Evidence that would change the verdict: a third writer of `RefinementResult` that fills `radiation` from something other than the compiled source. Or a reader that acts on the field rather than printing it, for example something converting λ to Q or d without `wavelength=`.
>
> ## The 2θ-label naming rule (`viz/plots._stated_radiation`), now reading the recorded `Radiation`
>
> (`_stated_radiation` decides what radiation a figure's 2θ axis names. It was added in WP-2039 for pattern plots. `_RADIATIONS` is the package's table of tube Kα wavelengths.)
>
> **Verdict: holds, as a handover note and not a table row.** The rule only restates numbers the caller declared or the fit refined. The table has no kind of row that could hold it.
>
> | Question | Author's answer, and where | What I found | Verdict |
> |---|---|---|---|
> | 1. What does it decide that the caller did not ask for? | `_stated_radiation` docstring: "an X-ray source is named only where its lines are one entry of the radiation table to the last digit … A wavelength near a Kα1 names nothing … a neutron source is never named. A recorded radiation is the source's kind and lines, so it is named by the same test." | It decides one thing: whether to print an anode name, "Cu Kα", beside λ on a result figure. The test is exact tuple equality of every line's λ with one `_RADIATIONS` entry, X-ray only (`plots.py:1142-1143`). The branch for a recorded radiation uses the same comparison as the model branch, so the rule itself is unchanged. One small difference: λ is `lines[0]` rather than `source.primary_wavelength`. An explicit `wavelength=` drops the name and prints only that λ (`plots.py:865-866`). That path was asked for by the caller. | Decides a label only |
> | 2. Which kind of ambiguity, and does a row agree? | None given. There is no row, and the WP has no generality note yet; the handover log holds only its creation entry. | Kind 1 (the data settle it). Exact equality means the caller's source was built from that table entry, for example `bragg_brentano(radiation="CuKa")`. Naming it repeats the caller's declaration. Every other case prints λ, which is the caller's own number or the fitted one. | Kind 1 |
> | 3. Case against acting (naming the anode) | Docstring: "a synchrotron beam can sit within any tolerance of one" (the reason nearness is refused). | none found. A false name needs an X-ray source declared with every line exactly equal to a table entry while not being that tube. One edge case: a wavelength freed in a stage that ends exactly on its starting value would be named. The label would still be true to the number. | — |
> | 4. Case for acting (naming more often, by nearness) | Same docstring passage, rejecting nearness. | A refiner who typed a Cu wavelength by hand (1.5406), or who refined λ on a Cu tube, gets λ alone and no "Cu Kα". The cost is a caption word. No rerun and no moved number: λ is still printed. No measurement given, and none is needed at this cost. | Weak case, rightly declined |
> | 5. Tier and source | None given. | Not a table kind. The table's five kinds are a diagnostic code, a record field, a module-level number, a default at a declared seat, and a `suggestion=` site. This rule is none of them. It is a lookup and a fallback order inside `viz`, which `_audit.NOT_WALKED` declares out ("figures and the live snapshot: sizes, colours, point caps and the 3D view drawn first"). The module docstring lists "an ordering or a fallback chain" among what the guard cannot see. I did not check what the seven programs print on a plot axis, and `docs/practice.md` has no entry on axis labels. | No row can be keyed |
> | 6. Dataset families behind a threshold | None given. | There is no threshold: the test is exact equality, with no tolerance. Not applicable. | — |
> | 7. Which field or code says it fired | — | The label is the output. The facts it reads, `Radiation.kind` and `.wavelengths`, are on the result. So a reader can always see why a name was or was not printed. | Visible |
>
> Precedent: WP-2039's handover covered the same rule with a one-line "*Generality.* Not dispatched … the radiation fallback order live[s] in … `viz`, … in `NOT_WALKED`" (`docs/wp/2039-a-tutorial-reads-without-decoding.md:349-352`). WP-2042's handover should carry the same note. It should say that the reuse adds an input and leaves the rule unchanged.
>
> Evidence that would change the verdict: the rule gaining a tolerance or a nearness match. That would be a threshold, and it would need a row or a constant in a walked file. Or the label's anode name being read by anything other than a figure, such as an exported CIF or report text.

Author's note on the second item: the reuse adds an input, the recorded `Radiation`, and leaves the
rule unchanged. It lives in `viz`, which `NOT_WALKED` declares out.

*Lanes.* None dispatched.

*Gotchas.*
- The 1.10.0 tag is pending (WP-2043). If #1152 merges after it, this ships in 1.11 and owes a
  staged-notes line there. If before, it owes one in 1.10.0's notes. WP-2043's `### Inherited`
  carries the line. This WP's narrative is in `milestones/v1.10.md` because `pyproject.version`
  reads 1.10.0; it moves to v1.11's record if the merge follows the tag.
- The tutorial notebooks' committed outputs show the new label only after their next rebuild.
  `build.py --check` compares cells and the stamp, never outputs.

Next: none for this WP. Merge after the 1.10.0 tag, or add its line to 1.10.0's notes first.
WP-2041 (a tutorial shows the indexer abstain) is unclaimed and starts in a fresh session.

- **2026-10-24** — Created from WP-2039's inherited note to WP-2040, because no open WP owns
  the result schema's source fields and WP-1444, which added figure titles, is closed.
  Next: the first task.
