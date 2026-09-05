## The defect

`Atom.occ`/`Atom.biso` declare their physical range in a `default_factory`
(`occ`: min=0.0, max=1.5; `biso`: min=0.0, max=25.0, unit="A^2") rather than
as a field constraint:

```python
biso: Parameter = Field(default_factory=lambda: Parameter(value=0.5, min=0.0, max=25.0, unit="A^2"))
```

So the bounds only ever applied when the field was **omitted**. A caller
supplying their own `Parameter(value=..., vary=...)` — the natural way to
set a starting value or hold one — silently got `(-inf, +inf)` and no unit
instead. Measured cost (#204): a refined Biso of **-165 A^2** and an
**81-percentage-point QPA error at unchanged Rwp**, invisible at the call
site — two staging orders landing on the same `scale·exp(-2Bk^2)` ridge from
scales 4.4e9 apart.

`x`/`y`/`z` are unaffected: they're required fields with no `default_factory`
and default to `(-inf, inf)` regardless, so there was nothing to lose.

## The fix

`Atom._inherit_declared_bounds` (`model_validator(mode="after")`) fills
`min`/`max`/`unit` from a field's declared default wherever the caller's
`Parameter` left that attribute out of `model_fields_set` — an explicit
bound (including an explicit `min=-inf`) still wins, and only a true
omission inherits.

**Why `model_fields_set` and not a value comparison against `Parameter`'s
own bare defaults**: an explicit `min=-inf` from a caller is indistinguishable
from an omission by value alone. `model_fields_set` is pydantic's own
discriminator for "was this key present at construction", so it's the clean
signal rather than something built by hand.

**Why inherit rather than refuse a bound-less `Parameter` outright**:
refusing would require every existing caller to restate the physical range
on every construction, which breaks working code. I checked this repo's own
`Atom(biso=...)`/`Atom(occ=...)` call sites (`io/recipe.py`,
`crystallography/cif.py`, the acceptance tests, the examples) before
landing this — every one either omits the field or already passes an
explicit bound, so nothing here newly refuses a working input. Where the
inherited bound *does* reject a value (e.g. a bare `Parameter(value=-165.0)`
for `biso`), `Parameter._check_bounds` raises — that's this fix doing its
job on the exact defect scenario, not a new refusal of anything the repo
already does.

**Generalised rather than hardcoded**: the validator iterates
`Atom.model_fields`, filters for `Parameter`-typed fields carrying a
`default_factory`, and calls it to get the reference default — so it finds
`occ` and `biso` today without naming them, and a field added to `Atom` the
same way later is covered without touching this validator. A test
(`test_every_bounds_carrying_atom_field_is_inherited`) discovers the same
set independently and checks each one, so it fails if the mechanism ever
regresses to naming fields explicitly and misses one.

## Scope — the hazard is wider than `Atom`

The same shape (`Parameter` field, `default_factory` declaring
`min`/`max`/`unit`) also exists on `Phase` (`scale`, `extinction`,
`lor_size`, `lor_strain`, `gauss_size`, `gauss_strain`), `PreferredOrientation.r`,
and extensively on `Instrument` (Caglioti U/V/W/X/Y, zero-shift, sample
displacement/transparency, background-peak parameters, emission-line
weight, and more — `src/rietx/schemas/instrument.py`). I did **not** fix
those here: issue #204 and its measured consequence are specifically about
`Atom`, several of the `Instrument`/`Phase` fields are softplus-transformed
(where an omitted bound is a milder hazard — `internal_bounds` already maps
some of these to an effectively unconstrained internal variable), and
widening the fix to every schema class in this PR would mix an
easy-to-review single-class change with a much larger, harder-to-review
audit. Flagging it here rather than fixing it silently, per the issue's own
request. Happy to open a follow-up if that's wanted.

## Tests — 8 new, `a4eec1db` parent-commit proof

All in `tests/test_schemas.py`. Full accounting, N = 8 = 4 + 2 + 2:

**4 — reproduce the defect; fail on the parent commit (`a4eec1db`), pass on this branch:**
- `test_atom_bare_biso_parameter_inherits_declared_bounds` — a bare `biso=Parameter(value=1.0)` gets `(0.0, 25.0, "A^2")`
- `test_atom_bare_occ_parameter_inherits_declared_bounds` — same for `occ` → `(0.0, 1.5)`
- `test_atom_biso_out_of_declared_bounds_now_raises` — the issue's own `-165.0` value now raises `ValidationError`
- `test_every_bounds_carrying_atom_field_is_inherited` — generic discovery guard over every `Parameter` field on `Atom` with a `default_factory`, not just the two named above

**2 — guard against over-firing, proven against the *rejected* design (a parent-commit check can't show this: the parent applies no inheritance at all, so it would pass trivially either way):**
- `test_atom_explicit_parameter_bound_is_not_overwritten` — an explicit `min`/`max`/`unit` on `biso` survives
- `test_the_always_overwrite_design_would_clobber_an_explicit_bound` — the same explicit `Parameter` run through the rejected "always overwrite, no `model_fields_set` check" logic *does* get clobbered, showing what the chosen discriminator prevents

**2 — pin behaviour the parent commit already had right (regression fence, not new coverage):**
- `test_atom_omitted_biso_still_gets_declared_bounds` — omitting the field entirely still works, as before
- `test_atom_xyz_have_no_declared_bounds_to_lose` — `x`/`y`/`z` stay `(-inf, inf)`, matching the issue's own claim

Parent-commit proof: built an isolated tree with `a4eec1db`'s
`src/rietx/schemas/structure.py` plus this branch's `tests/test_schemas.py`
(via `git show a4eec1db:... > `, not `git stash`, to avoid disturbing a
sibling worktree's stash). Result: the 4 defect-reproduction tests fail
there and the other 4 pass there — exactly the split above.

```
4 failed, 4 passed, 173 deselected   # a4eec1db + this branch's tests
```
```
8 passed                             # this branch
```

Full accounting for this venv (`.venv-test`, py3.12, `[dev]` extras — no
`jax`/`torch`): `pytest --collect-only -q` on the fast selection
(`-m "not slow"`) collects **3747** tests; the fast suite
(`-n auto --dist loadgroup -m "not slow"`) ran green, 0 failures, exit 0.
`ruff check src tests examples` and `tests/test_manual.py`,
`tests/test_manual_api.py`, `tests/test_docs_consistency.py` are all clean
— no manual/API partition changes were needed since `Atom`'s field list is
unchanged (this changes validation behaviour, not the schema shape).

## What remains

Not `Fixes #204` — the issue also carries a secondary finding I have not
touched here: `docs/skill/rietx/references/judging.md` (and `SKILL.md` §9)
tell a reader *not* to look at `max_shift_over_esd` on a solve that reports
`converged`, on the assumption that a converged solve satisfies the
McCusker band a fortiori. The unbounded `biso` in the issue's repro is a
counterexample — a converged solve carried `max_shift_over_esd = 70.1`,
and the guidance's own premise doesn't hold once the schema fix above lets
that happen. That's a documentation-wording fix, not a schema one, and I'm
leaving it for a separate PR rather than bundling an unrelated change here.
Referencing #204 without the closing keyword so it stays open for that.

*Authored with Claude Code on behalf of @mustachefeeling.*
