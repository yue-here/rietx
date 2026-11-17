(guide-tie)=
# How to tie parameters together

Call `Refinement.tie_equal` to make several parameters refine as one, or `Refinement.tie` to make one follow another as value = scale × source + offset.

A tied parameter leaves the refinement's free parameters and follows its source exactly, so the fit has one parameter fewer for each tie.
This is a constraint in the sense of the IUCr guidelines {cite}`mccusker1999`.
A restraint adds an observation and keeps every parameter; [How to restrain a bond length or an angle](restrain.md) covers those.

## Make parameters equal

Pass `tie_equal` the parameters' names, such as `phases.0.atoms.4.biso`.
A `*` in a name matches any run of characters, dots included, and [Parameter map](../reference/parameters.md) and [Instrument parameter map](../reference/parameters-instrument.md) list every name.
The first match in table order becomes the source, and the call returns the others, which now follow it.

```python
import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))
followers = ref.tie_equal(["phases.0.atoms.4.biso",
                           "phases.0.atoms.5.biso",
                           "phases.0.atoms.6.biso"])
assert followers == ["phases.0.atoms.5.biso", "phases.0.atoms.6.biso"]
```

Atoms 4, 5 and 6 are the three oxygens of fluorapatite's phosphate group.
Pass `source=` to choose which path carries the freedom.

## Check that the data allow the tie

Before you tie, refine the parameters free and compare them.
This fit refines the GSAS-II tutorial fluorapatite pattern twice under one plan, the second time with the three Biso tied:

```{literalinclude} ../../../examples/guides/tie.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/tie.py -->
```text
34 0.0898
  phases.0.atoms.4.biso  0.242 ± 0.150
  phases.0.atoms.5.biso  0.467 ± 0.159
  phases.0.atoms.6.biso  0.363 ± 0.110
32 0.0898
  phases.0.atoms.4.biso  0.360 ± 0.077
  phases.0.atoms.5.biso  0.360 ± 0.077
  phases.0.atoms.6.biso  0.360 ± 0.077
```

For each pair of free values, divide their difference by their combined esd, the square root of the sum of the two squared esds.
The script prints the three ratios:

<!-- output of examples/guides/tie.py -->
```text
pair gaps: 1.03, 0.65, 0.53
```

All three are under 2, so the free fit does not contradict the claim that the three oxygens share one displacement parameter.
Where a ratio is larger, the atoms are probably not in the same environment, and a tie would replace a measurement with an assumption.

The tie gives one Biso with an esd of 0.077 Å², smaller than any of the three free esds.
Rwp is the same to four figures, which says only that the tie does not make the fit worse.
The full script is `examples/guides/tie.py`.

## Tie with a scale and an offset

`tie` takes one dependent path and its source.
The dependent then equals `scale` × source + `offset`.
Two species sharing one site, with occupancies that sum to 1, are the common case:

<!-- api-doc: no-exec — it needs a structure with two species on one site -->
```python
ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0, offset=1.0)
```

The dependent takes its new value at once, and every later fit keeps the relation.

The dependent's own limits carry over to its source, and you don't have to work them out.
Each occupancy has a lower limit of 0, so `occ₁ = 1 − occ₀` keeps `occ₀` between 0 and 1, and the fit uses that range for `occ₀`.
When a fit stops at such a limit, it reports [`BOUND_HIT`](../reference/diagnostics-refinement.md#bound_hit) on the source.
Widen the dependent's limit if the source needs more room.

## What tie refuses

`tie` and `tie_equal` raise `ValueError`, naming the parameter and the reason, for:

- a parameter the space group already ties or fixes, such as `b` in a hexagonal cell;
- a source that itself follows another parameter, which would make a chain;
- a parameter the current intensity mode fixes, such as an atom's Biso when the fit is in Le Bail or Pawley mode;
- a tie whose value would fall outside the dependent's own limits.

With `expression=`, `tie` also refuses:

- a name in the formula that is not a declared variable;
- a formula that reads no variable, which `set_values` does instead;
- a formula whose value is not finite at the variables' present values, such as the logarithm of a negative number;
- a site's coordinate degree of freedom or a rigid body's origin or rotation, which hold a step from where the fit began rather than a value.

A formula that cannot be parsed raises `ExpressionError`, a `ValueError` that points at the column it stopped at.

## Release a tie

`Refinement.untie` takes the names of the tied parameters and returns the ones it released.
Each released parameter keeps its current value.

```python
import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))
ref.tie_equal("phases.0.atoms.*.biso")
released = ref.untie("phases.0.atoms.*.biso")
assert released == [f"phases.0.atoms.{j}.biso" for j in range(1, 7)]
```

## Tie to a quantity of your own

Sometimes the shared quantity is no single atom's.
The three oxygens have one displacement parameter between them, and making atom 4 the source misrepresents that.
`Refinement.add_variable` declares the quantity in its own right:

```python
import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))

path = ref.add_variable("B_phosphate", 0.5, min=0.0, max=25.0)
for j in (4, 5, 6):
    ref.tie(f"phases.0.atoms.{j}.biso", path)
freed = ref.set_vary("vars.*", True)

assert path == "vars.B_phosphate"
assert freed == ["vars.B_phosphate"]
```

The path is `vars.` followed by the name.
From there it behaves like any other parameter: `parameters()` lists it, `set_vary` and `set_values` reach it, and the fit refines it and reports its esd.
`Refinement.remove_variable` deletes one, and refuses while any parameter still follows it.

A variable may follow other variables, so you can build a quantity from parts.
Pass the sources as a mapping from path to coefficient:

```python
import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))
ref.add_variable("B_base", 0.4)
ref.add_variable("B_extra", 0.1)
ref.add_variable("B_total", 0.5)
ref.tie("vars.B_total", {"vars.B_base": 1.0, "vars.B_extra": 1.0})

rows = {row.path: row for row in ref.parameters()}
assert rows["vars.B_total"].held_because == "tied: = 1·vars.B_base + 1·vars.B_extra"
```

Each of these relations is a sum of coefficient × source plus a constant.
The next section covers a relation that is not.

## Tie to a formula

Pass `expression=` to `tie` to set a parameter by a formula, such as the Debye model of a displacement parameter.
The formula's text follows [Expressions](../reference/expressions.md).
Each name in it is a variable you declared with `add_variable`, and every other value is a number written in the text.

The Debye model gives B = 6h²T/(m k<sub>B</sub> θ<sub>D</sub>²) [D₁(θ<sub>D</sub>/T) + θ<sub>D</sub>/4T] {cite}`willis1975`.
Here D₁ is the first Debye function, `debye(x)`, and 6h²/(m k<sub>B</sub>) is 718.1 Å² K for oxygen, of molar mass 16.00 g/mol.
This ties the three phosphate oxygens of fluorapatite to one Debye temperature at 295 K:

```python
import rietx as rx
from rietx.examples import examples_dir

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
ref = rx.Refinement(structure, rx.Instrument.bragg_brentano(radiation="CuKa"))
ref.add_variable("thD", 600.0, vary=True, min=100.0, max=3000.0)
for j in (4, 5, 6):
    ref.tie(f"phases.0.atoms.{j}.biso",
            expression="718.1 * 295 / thD^2 * (debye(thD / 295) + thD / (4 * 295))")

row = {r.path: r for r in ref.parameters()}["phases.0.atoms.4.biso"]
assert round(row.value, 4) == 0.6534
assert row.held_because == (
    "tied: = 718.1 * 295 / thD^2 * (debye(thD / 295) + thD / (4 * 295))")
```

The fit refines `vars.thD` and reports its esd.
Each Biso is reported too, at the formula's value, with an esd carried from `thD`.
`untie` releases a formula tie, and a history checkout restores one, as for any tie.

A formula reads variables and numbers only, so a model parameter enters through a variable.
Tie the parameter to a variable, then name the variable in the formula:

<!-- api-doc: no-exec — it needs a structure with two species on one site -->
```python
ref.add_variable("x_Fe", 0.5, vary=True, min=0.0, max=1.0)
ref.tie("phases.0.atoms.0.occ", "vars.x_Fe")
ref.tie("phases.0.atoms.1.occ", expression="1 - x_Fe")
```

A formula always runs as a formula, even when it is linear, as `1 - x_Fe` is.
`tie` with a source path and `tie_equal` keep the linear route they always had, so the numbers of a fit using them do not change.
The two routes give the same value for a linear relation, to within 4 × 10⁻¹⁶ relative.

Trigonometric functions take radians, and rietx stores every angle in degrees.
Write a cell angle as `cos(beta * pi / 180)`.
GSAS-II's expressions read `sin`, `cos` and `tan` in degrees, so a GSAS-II formula copied unchanged gives a different value with no error.

## Tie parameters across a series

A tie belongs to one `Refinement`, and a sequential refinement builds a new one for each pattern.
Declare the tie inside the function you pass as `SequentialRefinement.fit`'s `constrain` argument, which rietx calls with each pattern's index and `Refinement` before that pattern's fit.
A variable belongs to one `Refinement` too, so call `add_variable` in the same function.
Its value is then carried from one pattern to the next like any other parameter's.

A formula tie is declared the same way.
Write a number that changes from pattern to pattern, such as the temperature, into the formula's text:

<!-- api-doc: no-exec — a fragment; tests/test_tie_expression.py runs the series -->
```python
temperatures = [300.0, 600.0]

def constrain(index, ref):
    T = temperatures[index]
    ref.add_variable("thD", 800.0, vary=True, min=100.0, max=3000.0)
    ref.tie("phases.0.atoms.1.biso",
            expression=f"1062.9 * {T} / thD^2 * (debye(thD / {T}) + thD / (4 * {T}))")
```

A variable would not do for the temperature, since its value is carried from the previous pattern.

## See also

- [How to keep a parameter fixed whatever the plan frees](hold.md) fixes one parameter instead of linking two.
- [About correlations and esds](../concepts/correlations.md) explains when a tie is the right answer to a correlation.
