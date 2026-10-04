# WP-1337 — an authored refusal, not a raw traceback

Milestone: unscheduled · Status: ✅ 2026-10-03 — both refusals landed (PR #537) and shipped in 1.6.0
Track: What fires, and what stays silent
Depends on: — (1311, 1321 soft: they own the bounds this refusal inherits)

## Goal

Two paths that fail loudly fail *legibly*: a tie whose implied value leaves a
declared bound refuses in the same voice as `tie()`'s other six refusals,
and a Pawley `summary()` no longer dies in a numpy broadcast whose traceback
names neither the parameter nor the mode.

## Context

WP-1302 shipped the rule these two miss: **the error is the documentation.**
Both were found by an outside campaign driving the package hard (#244, #246),
and neither is a silent wrong answer — they fail deterministically, which is
the safe direction. They are diagnosability defects, with one genuine bug
underneath.

**#246 — `tie()`'s bound refusal stops one rank short of the coordinate.**
`Refinement.tie()` documents seven refusals, and the last of them is this
one: *"an implied value outside the target's own bounds would start the
bounded solver infeasible."* The code makes it (`_declare_ties`, checking
`entry.lo <= implied <= entry.hi`) — on the **target entry's own** bounds. A
symmetry-adapted displacement DOF has bounds of ±∞, so that check passes, and
the bound that fails is on the *coordinate* the DOF reaches through the
symmetry affine map, one rank down, where what comes back is raw pydantic
from `validate_assignment`:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Parameter
  Value error, value 3.2482 lies outside bounds [0.0, 1.0]
```

Two things make it hard to act on. **The number in the error is not the number
the caller passed**: the tie is on a symmetry-adapted displacement DOF, which
loads at `0.0`, so `1.0·0.0 + 3.0` is a displacement of 3.0 while the value
that fails the bound is the resulting *coordinate*, `0.2482 + 3.0 = 3.2482`.
The caller sees `3.2482` against `[0.0, 1.0]` with no mention of either end of
the tie, the offset, or which atom — the reporter first read it as evidence
that the affine map used the target rather than the source, and had to check
`parameters()` to rule that out. The map is correct; the message is untraceable.

**And it only bites callers who declare bounds.** Coordinates load from a CIF
with `(-inf, inf)`, so the default path never trips. The reporter hit it
because they set `min`/`max` on every `Parameter` they construct — which is
the workaround for **#204** (`Atom(biso=Parameter(...))` discarding declared
bounds, owned by 1311/1321). Following that guidance is what creates this
exposure, so the two land better together than apart.

Reproduction, on the repo's own fixture:

```python
s = rx.Structure.from_cif("tests/data/cod_1000236.cif")
for at in s.phases[0].atoms:
    for nm in ("x", "y", "z"):
        p = getattr(at, nm); p.min, p.max = 0.0, 1.0
ref = rx.Refinement(s, rx.Instrument.debye_scherrer(wavelength=0.413957))
ref.tie("phases.0.atoms.1.dof.0", "phases.0.atoms.0.dof.0", scale=1.0, offset=3.0)
```

The wanted refusal, in the existing voice: *"tying `phases.0.atoms.1.dof.0` to
`1.0·phases.0.atoms.0.dof.0 + 3.0` implies x = 3.2482 on Al1, outside its
bounds [0.0, 1.0]; loosen the bound or change the offset."* The bound check
is right for what it checks and stays; it has to reach what the target
reaches — root CLAUDE.md's rule that a claim about what a name reaches is
verified where it is used, here applied to a refusal rather than a Jacobian.

**#244 — `suggest()` broadcasts wrong when a width sits on its transform floor
in Pawley mode.** Reached through `summary()`, so any Pawley caller asking for
one hits it:

```
ValueError: could not broadcast input array from shape (8064,) into shape (8060,)
  refine.py:1988 in _next_parameter_line -> s = self.suggest(data)
  refine.py:1082 in suggest             -> jac[:, i] = jac2[:, i]
```

The trigger is the **transform floor**, not Pawley as such: same data, same
plan, same window, `lor_size`/`gauss_size` seeded at `0.0` raises and at `0.05`
returns normally (Rwp 0.9165). `mode="rietveld"` on the identical seed does
not raise, and `ref.report(plan=...)` on the same refinement is fine — only
the suggestion path.

**The row-count gap scales with the fitted range**, so it is not an
off-by-a-constant:

| `two_theta_limits` | shapes |
|---|---|
| `(4.2, 20.0)` | 8064 vs 8060 — Δ4 |
| `None` (full pattern) | 14646 vs 14610 — Δ36 |

Suspected mechanism, unproven and to be established rather than assumed:
`suggest()`'s docstring says candidates on a transform floor are probed from
their family's stage seed, and those seeds live in a **second** build whose
only contribution is the candidates' columns. The two builds appear to
disagree on the number of residual rows in Pawley mode. **The likely seam is
`model/rows.py`** — `BLOCK_ORDER` / `layout()` is the one authority for
`[data | background-penalty | Pawley-restraint | soft-restraint]`, and the
Pawley restraint block's row count depends on the overlap grouping, which a
re-seeded build can compute differently. Check that before anything else; if
so, the fix belongs at the layout rather than at the column copy.

**No synthetic reproduction exists yet.** A clean simulated Pawley fit with
`profile_only` leaves nothing on a floor and does not raise; the reporter's
case uses an archive pattern they cannot redistribute and they have offered to
build a synthetic one that floors a width. Building that fixture is the first
task, because without it the fix cannot be pinned.

Both issues want the same thing even if the broadcast is left as it is: **a
failure that names the parameter**. That is cheaper than either fix and
lands first.

## Non-goals

- `Atom(biso=Parameter(...))` discarding declared bounds (#204) and the
  persisted repair (#209) — 1311 and 1321 own those. This WP only inherits
  the interaction.
- Loosening any bound, or the coordinate bound check itself.
- The `suggest()` ranking or its candidate vocabulary.

## Tasks

- [x] A synthetic Pawley fixture that genuinely floors a width candidate —
      without it #244 cannot be pinned. Decided 2026-09-03: take the
      reporter's offer to build it.
- [x] Establish whether the two builds' row-count disagreement is the Pawley
      restraint block in `model/rows.py::layout()`; fix at the layout, not at
      the column copy, if so.
- [x] Whatever the mechanism, `suggest()` names the parameter whose seeded
      probe changed the row count rather than letting numpy speak.
- [x] `tie()`'s bound refusal checks the coordinates a DOF target reaches
      (its symmetry affine ties), not only the target entry's own bounds —
      naming the tie, the implied value, the atom and the bound, in the voice
      of the existing six.
- [x] Tests: the #246 reproduction asserts the message's content, not just the
      raise; the Pawley fixture asserts `summary()` returns.
- [x] Skill: `references/surprises.md` — the row that declaring bounds
      everywhere (the #204 workaround) is what exposes the tie refusal, since
      an agent following one row should not be surprised by the other.

## Acceptance

Both reproductions produce an authored message naming the parameter; the
Pawley fixture's `summary()` returns.

```sh
.venv/bin/python -m pytest tests/test_params_surface.py tests/test_suggest.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #244, #246 — rietx 1.3.0, `SCHEMA_VERSION` 0.16, `main` plus PRs
  #206 and #233.
- WP-1302 — the error is the documentation; the closest-match surface.

## Handover log

- **2026-10-03** — **Closed** by a cleanup session over unowned in-flight
  WPs. Nothing landed after PR #537. *Inherited, consumed:* both entries are
  answered by #537, as its entry below says. The 1119 entry asked that the
  message name the atom and the user's own tie, and it does. The 1321 entry
  noted that declared ranges reach 57 fields, and the refusal checks every
  entry the new ties move. Narrative moved to the v1.7 record.

- **2026-09-30** — Both refusals landed from outside: PR #537
  (`mustachefeeling`), merged as `e8d15d01` in a `/pr-review` run, closing
  #244 and #246. All six tasks are ticked. `tie()` now refuses a tie that
  pushes a coordinate out of its bounds in its own voice: it names the tie
  as written, the implied value, the atom and the bound, and registers
  nothing. `suggest()` and `summary()` no longer die in a numpy broadcast on
  a Pawley fit. The PR also fixed a state bug nobody had reported: a `tie()`
  that raised used to leave the tie registered, so the corrected retry was
  refused with "already follows … untie it first". That predates #261.
  - **#246.** `_declare_ties` refreshes the new ties on its throw-away
    working table before registering them, and refuses any entry they moved
    out of its bounds. If the commit fails for any other reason, the
    register is restored. The post-solve write-back refusal stays, because
    it is still the right message for the multi-source corner § 8.22
    describes.
  - **#244: the mechanism is the Pawley restraint block, but the fix sits at
    the column copy, not in `layout()`.** This departs from task 2's
    wording, and the PR argues it: the two builds really do have different
    overlap groups, because their widths differ, so `layout()` is right for
    each. `suggest()` is the only consumer that mixes them. It now copies a
    seeded column one row block at a time. A block of equal length is copied
    bit-identically. A block whose length differs keeps the current rows,
    which is exact only where the column is zero in both builds, and that
    condition is checked where it is used. If it fails, `suggest()` raises
    naming the parameter and the block (task 3).
  - **The fixture (task 1)** is synthetic: a pseudo-tetragonal P 1 21/c 1
    cell (5.310 / 5.327 / 9.20 Å) with a narrow profile and a specimen width
    the model does not carry. A background-only Pawley fit floors all four
    sample widths, and on `main` `summary()` raised `could not broadcast …
    (1533,) into (1528,)`. The test asserts that the seeds really move the
    restraint block, that `summary()` returns a `next: free …` line, and
    that the seeded column (not only the flag) reaches the result: it scores
    in `{profile.y, lor_size, lor_strain}`. Disabling the block copy moves
    it and fails the test.
  - **Skill (task 6).** `surprises.md` § 8.22 gains the paragraph that
    declaring bounds on every coordinate is what exposes the refusal
    (`Measured: WP-1337, #246.`). Its wording reads for every space group,
    not only P 1.
  - **Gotcha for whoever lands #546 second: `surprises.md`'s budget.** This
    PR takes the file to 34 558 B, leaving 42 B of its 34 600 B budget. #546
    adds 398 B, so whichever lands second cuts on rebase. The hunks do not
    overlap (§ 8.22's tail against § 8.30).
  - **Next: prune `### Inherited` and close.** Both entries read as answered
    by this PR. The 1119 entry asked for the atom label and the user's own
    tie in the message. The 1321 entry notes that declared ranges now reach
    57 fields, and the refusal checks every entry the new ties move, not
    only coordinates. Confirm the second against the tree before deleting
    it.
  - **Measured on the merged tree** (Linux x86_64, 4 cores, py3.12.3,
    `[dev,jax]`, run as root), in one stack with #556 and #544 (no shared
    file) on `44eaa09`: 7143 passed, 119 skipped, 1 failed in 1:09:15. The
    failure is `test_held_phase`'s ramp runaway guard (70.3 s against 60 s;
    19.6 s alone, WP-1420's load sensor). `main` after the three merges,
    `e8d15d0`, is content-identical to the gated tree.
- **2026-09-03** — created, from the 2026-09-03 issue triage (issues #244,
  #246). Grouped because both are loud failures in the wrong voice, and
  because #246's exposure is created by following #204's workaround.
  Re-checked the same day against the tree: the bound refusal is documented
  (seven refusals, not three) and made, on the target's own bounds; the defect
  is that a DOF target's coordinates are not reached. Test modules named as
  they exist. Decided the same day: the reporter builds the Pawley fixture.
