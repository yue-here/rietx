(guide-hold)=
# How to keep a parameter fixed whatever the plan frees

Call `Refinement.hold` on the parameter before the fit, and no stage of any plan will refine it until you call `Refinement.unhold`.

Use it for a value you know from elsewhere, such as a standard's certified lattice parameters during an instrument calibration.

## Why a cleared refine flag is not enough

Each stage of a plan sets the refine flags afresh from its own list of parameters.
A parameter you set to `vary=False` by hand is freed again by the first stage whose list includes it.
The fit refines it, and nothing reports that your setting was replaced.

## Hold the parameter

Pass `hold` a parameter's name, such as `phases.0.cell.a`, or a list of names.
A `*` in a name matches any run of characters, dots included, so `phases.0.cell.*` is every lattice parameter of the first phase.
[Parameter map](../reference/parameters.md) lists every name.
It returns the paths it held.

```python
import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))
held = ref.hold("phases.0.cell.*")
assert held == ["phases.0.cell.a", "phases.0.cell.alpha", "phases.0.cell.b",
                "phases.0.cell.beta", "phases.0.cell.c", "phases.0.cell.gamma"]
```

All six lattice parameters are marked as held.
In this hexagonal cell only `a` and `c` could have refined anyway, because the space group ties `b` to `a` and fixes the three angles.
A hold never overrides the space group.

## Run the fit and read what the hold blocked

This fit uses the GSAS-II tutorial fluorapatite pattern that ships with rietx.
The `lab_bragg_brentano` plan has a `cell` stage that frees the lattice parameters.

```{literalinclude} ../../../examples/guides/hold.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/hold.py -->
```text
9.3717
cell ['phases.0.cell.a', 'phases.0.cell.c']
closing ['phases.0.cell.a', 'phases.0.cell.c']
2 held parameters were matched by the turn_on glob of stages 'cell', 'closing' and stayed fixed: phases.0.cell.a, phases.0.cell.c.
```

The lattice parameter `a` ends at the value the CIF gave it.
`StageResult.blocked_by_hold` names what each stage tried to free and could not.
The closing stage that ends every plan names every parameter the plan's stages named, so the hold blocks it too.
The fit also reports [`HOLD_BLOCKED_PLAN`](../reference/diagnostics-refinement.md#hold_blocked_plan) at level `info`.
Nothing is wrong when it appears.
It records that your hold overrode the plan.

Without the hold, the same plan moves `a` by about 300 ppm.
The figure differs between platforms by tens of ppm, so the script prints the floor they all clear:

<!-- output of examples/guides/hold.py -->
```text
without the hold: a moves by more than 250 ppm
```

The full script is `examples/guides/hold.py`.

## Release the parameter

`unhold` takes the same names.
The parameter comes back fixed at its current value, and the next plan that names it frees it.

```python
import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))
ref.hold("phases.0.cell.*")
released = ref.unhold(["phases.0.cell.a", "phases.0.cell.c"])
assert released == ["phases.0.cell.a", "phases.0.cell.c"]
```

`unhold` raises `ValueError` for a literal path that is not held, so a typing mistake is reported.
A name with `*` that matches no held parameter returns an empty list.

## Check which parameters are held

`Refinement.parameters` lists every parameter.
A held one has `refinable` false, and `held_because` says why it cannot move:

```python
import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))
ref.hold("phases.0.cell.*")
rows = {row.path: row for row in ref.parameters()}
assert rows["phases.0.cell.a"].held_because.startswith("held by this refinement")
assert rows["phases.0.cell.b"].held_because == "tied: = 1·phases.0.cell.a"
```

When several reasons apply, `held_because` gives the one that wins.
The space group outranks a hold, and a hold outranks a plan.
So `b` still reads as tied to `a`, which `unhold` cannot change.

## Hold a parameter across a series

A hold belongs to one `Refinement`, and a sequential refinement builds a new one for each pattern.
To hold a parameter in every pattern, call `hold` inside the function you pass as `SequentialRefinement.fit`'s `constrain` argument.
rietx calls it with each pattern's index and its `Refinement` before that pattern's fit.

<!-- api-doc: no-exec — it needs a list of patterns to fit -->
```python
def constrain(index, ref):
    ref.hold("phases.0.cell.*")

series = rx.SequentialRefinement(structure, instrument)
result = series.fit(patterns, constrain=constrain)
```

## See also

- [About a fit](../concepts/fit.md) describes the plan, its stages and the other reasons a parameter stays fixed.
- [About correlations and esds](../concepts/correlations.md) explains when holding a parameter is the right answer to a correlation.
