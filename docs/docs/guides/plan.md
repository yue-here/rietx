(guide-plan)=
# How to add a stage to a refinement plan

Take a preset from `RefinementPlan`, add a `Stage` to its `stages` list, and pass the plan to `Refinement.fit`.

A plan is an ordinary Python object, and `RefinementPlan.stages` is a plain list.
Each stage frees the parameters it names and keeps every parameter earlier stages freed, so the last stage refines everything together.

## Add a stage at the end

`mccusker_default` frees the scale, background, zero shift, lattice parameters and peak widths, and never the atoms.
This fit appends a stage that frees every atom's Biso, on the GSAS-II tutorial fluorapatite pattern that ships with rietx:

```{literalinclude} ../../../examples/guides/plan.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/plan.py -->
```text
scale_bkg     7 freed  converged
zero          1 freed  converged
cell          2 freed  converged
profile_w     1 freed  converged
profile       4 freed  converged
biso          7 freed  converged
closing      22 freed  converged
```

`StageResult.freed` lists the parameters each stage's names matched.
The `cell` stage freed two, because the hexagonal space group leaves only `a` and `c` free.
The fit ends with the closing stage, which every plan adds after its own stages ([The closing stage](../reference/refinement.md#the-closing-stage)).
It names every parameter the other stages named, so it lists all 22.
The full script is `examples/guides/plan.py`.

## Insert or remove a stage

Use the list's own methods.
This inserts a Biso stage after the `cell` stage of `mccusker_structural` and drops its `roughness` stage:

```python
import rietx as rx

plan = rx.RefinementPlan.mccusker_structural()
names = [stage.name for stage in plan.stages]
plan.stages.insert(names.index("cell") + 1, rx.Stage("biso_early", ["phases.*.atoms.*.biso"]))
plan.stages = [stage for stage in plan.stages if stage.name != "roughness"]

assert [stage.name for stage in plan.stages][:4] == ["scale_bkg", "zero", "cell", "biso_early"]
assert "roughness" not in [stage.name for stage in plan.stages]
```

## Build a plan from nothing

Pass `RefinementPlan` the list of stages:

```python
import rietx as rx

plan = rx.RefinementPlan(stages=[
    rx.Stage("background", ["instrument.background.*", "phases.*.scale"]),
    rx.Stage("cell", ["instrument.zero_shift", "phases.*.cell.*"]),
    rx.Stage("profile", ["instrument.profile.*"]),
    rx.Stage("atoms", ["phases.*.atoms.*.dof.*", "phases.*.atoms.*.biso"]),
])
assert len(plan.stages) == 4
```

## Name the parameters a stage frees

The second argument of `Stage`, `turn_on`, is a list of parameter names such as `phases.0.cell.a`.
A `*` in a name matches any run of characters, dots included, so `phases.*.atoms.*.biso` matches every atom's Biso in every phase.
Names take no square brackets, because the matching reads `[0]` as a set of characters and not as an index.
[Parameter map](../reference/parameters.md) lists every name.

A stage never frees a parameter the space group fixes or ties, or one you hold with `Refinement.hold`, whatever its names match.
The other `Stage` arguments have defaults.
The ones most often set are:

- `max_iter`, the iteration limit for the stage (100);
- `restraint_weight_scale`, a factor on every restraint's weight for the stage (1.0), which [How to restrain a bond length or an angle](restrain.md) uses;
- `seed`, a starting value for each freed parameter that sits exactly on a lower limit of 0 or above, so the fit can move it off the limit (0.0, which seeds nothing).

`help(rx.Stage)` lists the rest.

## Where to put the new stage

The presets follow the order of the IUCr guidelines {cite}`mccusker1999`, and a new stage fits into it:

1. scale and background;
2. peak positions: the lattice parameters and the zero shift, with specimen displacement where the geometry has one;
3. peak widths, then asymmetry;
4. atom positions, then displacement parameters;
5. intensity corrections such as preferred orientation, extinction and surface roughness.

Free the constant width term `w` before `u`, `v`, `x` and `y`, or the angle-dependent terms absorb a constant offset and then fight `w` for it.
Free an intensity correction late, or it takes intensity that belongs to the structure.

## Use a preset by name

`fit` also takes a preset's name, as `plan="lab_calibrate"`.
`PLAN_INFO` maps each name to its title, description, fit modes and when to use it, so a program can offer the choice without its own list:

```python
import rietx as rx

info = rx.PLAN_INFO["lab_calibrate"]
assert info.title == "Lab: calibrate on a standard"
assert set(rx.PLAN_INFO) >= {"mccusker_default", "mccusker_structural", "profile_only"}
```

[Plan presets](../reference/plans.md) draws every stage of every preset.

## See also

- [About a fit](../concepts/fit.md) follows one stage from freeing its parameters to committing its history node.
- [How to keep a parameter fixed whatever the plan frees](hold.md) stops a stage freeing one parameter.
