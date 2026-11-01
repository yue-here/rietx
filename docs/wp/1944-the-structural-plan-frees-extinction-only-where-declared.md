# WP-1944 — the structural plan frees extinction only where it says it does

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-11 — a plan frees a parameter its description says it leaves alone, and the esd shows the data cannot see it; nothing fires

## Goal

`mccusker_structural` frees extinction on exactly the phases its description
says, and every text describing the stage says the same thing as the code.

## Context

**The report (issue #877).** `PLAN_INFO["mccusker_structural"]`
(`strategy/staged.py`) says the plan frees "preferred orientation,
extinction and surface roughness where declared". The stages, checked at
`f11e22d3`:
- `Stage("preferred_orientation", ["phases.*.preferred_orientation.r"])`
  matches only phases that declared a PO block (`Phase.preferred_orientation`
  defaults to `None`).
- `_ROUGHNESS_STAGE` frees `instrument.geometry.surface_roughness.*`, an
  opt-in block that defaults to `None`.
- `Stage("extinction", ["phases.*.extinction"], seed=1e-3)` matches every
  phase. `Phase.extinction` is a plain `Parameter` at 0 (`schemas/structure.py`),
  and a PbSO₄ table at `f11e22d3` lists `phases.0.extinction` as refinable
  with nothing holding it.

So "where declared" is true for two of the three. The filer's agent fitted
the PbSO₄ round-robin neutron pattern with this plan and got extinction
1.2(3.5) µm² with no diagnostic (filer's numbers, `bdaa7b62`).

**Three texts make the claim, and one is accurate.**
- `PLAN_INFO`'s description: "where declared", false for extinction.
- The comment above `Phase.extinction`: "it is opt-in and never perturbs a
  structure that does not free it". The plan frees it unasked.
- The skill's plan table (`docs/skill/rietx/SKILL.md`): "PO, extinction,
  roughness", which is accurate for the code as it stands.

**Who depends on the current behaviour.** 29 files in `tests/`, `examples/`,
the manual and the skill name the plan. `test_extinction.py::
test_mccusker_structural_frees_extinction_after_displacement` pins the glob
and the seed. Which golden numbers move if extinction becomes opt-in is not
measured. Task 1 measures it.

**Decided 2026-10-11** (the maintainer, at the issue triage; posted on
#877): measure first. Neither fix is chosen until task 1's count exists. A
plan where extinction is rarely significant favours the opt-in, and one
where it often is favours correcting the texts.

**The sibling class, not generalised here.** A freed parameter the data do
not determine, reported with no diagnostic. WP-1523 settled it for a phase
scale (significance under 3σ, `refine._answer_significance`). WP-1914 owns
it for a sample-broadening coefficient at its softplus floor. This WP fixes
the plan and its texts. A general "esd exceeds value" diagnostic is not in
it.

### Inherited

- **2026-10-24, from [2044](2044-the-sabine-laue-factor-is-continuous.md):
  the QPA guide's free fit moved.** With Sabine's Laue factor continuous, the
  guide's first fit (11-BM NAC + CaF₂, `mccusker_structural`) gives CaF₂
  3.58 ± 3.53 wt% and extinction 1919 ± 4066 µm², the same on macOS and Linux,
  where 1.9.0 gave 3.09 ± 2.32. `HIGH_CORRELATION` reads scale ~ extinction at
  ρ = +0.998. That fit is this WP's worked case: an extinction the data cannot
  see, freed by the plan on a weak phase. The held fit is unchanged at
  1.37 ± 0.07 wt%. Re-pin `examples/guides/qpa.py` and its page if this WP
  changes what the plan frees.
  The fit moves a quoted weight fraction by more than the fraction itself,
  which may move this WP's priority row (noted by WP-2043).

## Non-goals

- A general significance diagnostic for every freed parameter (above).
- The extinction model itself (`model/extinction.py`, WP-0506, WP-1451).

## Tasks

- [ ] Measure: every acceptance fixture and example that runs
      `mccusker_structural`, with the extinction value and esd each ends at.
      Count those where extinction is significant (over 3σ) and those where
      it is not.
- [ ] Decide on that count, and record it here as `Decided YYYY-MM-DD:`. One
      option corrects the description and the schema comment to say every
      phase. The other makes the stage free only declared phases: an opt-in
      `Phase.extinction` defaulting to `None` like PO, with old files that
      store a value opening unchanged.
- [ ] Implement the decision. Update `test_extinction.py`, and the skill
      table if its text changes. A changed golden says which number moved
      and why.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for any fit whose number
      moves.
- [ ] Skill: the plan table row in `SKILL.md` matches the code; nothing else
      expected.

## Acceptance

`PLAN_INFO`, the schema comment, the skill table and the stage agree, and a
test asserts which phases the extinction stage frees on a two-phase model
with one phase declared and one not.

```sh
.venv/bin/python -m pytest tests/test_extinction.py tests/test_capabilities.py tests/test_skill.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #877.
- Sabine, T. M. (1988). *Acta Cryst.* A44, 368, and Sabine, Von Dreele &
  Jørgensen (1988), *Acta Cryst.* A44, 374 — the extinction model
  (`model/extinction.py` carries the full list).

## Handover log

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #877).
  Checked against the tree at `f11e22d3`: the extinction stage's glob
  matches every phase, and PO and roughness are the only opt-in blocks among
  the three. No open WP owns it: WP-1914 is the sibling for sample
  broadening and touches no plan, and no open WP names `PLAN_INFO` or the
  extinction stage. *Next:* task 1.
