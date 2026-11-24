# Parametric conditions and globs

This page gives the two shorter ways to write a `ParametricEquation`: a subset as a condition on the coordinates (`where`), and a target as a glob that expands into one declaration per path.
Both resolve to the data form that [Parametric refinement](parametric.md) describes.

## A subset by condition

`where` states the subset as a condition on the coordinate columns, in the condition syntax of [Expressions](expressions.md): a comparison such as `"T < 800"`, or comparisons joined by `and`, `or` and `not`, such as `"x >= 0.1 and x <= 0.3"`.
A comparison chain such as `0.1 <= x <= 0.3` is refused, as it is in an expression.

The condition is what is stored, and it is evaluated again each time the declaration is resolved.
An index list names positions in the patterns as passed, so dropping one bad pattern from a library moves every later index, and the list then names other specimens.
A condition names the specimens by where they sit, so the equation covers the same ones afterwards, and a pattern that joins inside the field joins the equation.
The reference and scale are still fixed at the first resolution ([Reference and scale](parametric.md#reference-and-scale)), so a coefficient keeps its meaning while the subset follows the campaign.

A pattern with no value for a column the condition reads is refused, since its membership is undecided.
So is a pattern where a comparison, inside an `if(...)` too, meets a value that is not finite, unless `and` or `or` is settled by its other operand there.
So is a condition that holds at no pattern.
A design basis takes no condition, because its rows follow the subset's order, one per pattern.

Two phase fields of a ramp, each with its own line:

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))],
)])
temperatures = [300.0, 450.0, 600.0, 900.0, 1050.0, 1200.0]
instruments = [rx.Instrument.debye_scherrer(wavelength=0.4139) for _ in temperatures]
coordinates = rx.CoordinateTable(columns={"T": temperatures}, units={"T": "K"})

low = rx.ParametricEquation(name="a_low", target="phases.0.cell.a", basis="polynomial",
                            terms=[[], ["T"]], where="T < 800")
high = rx.ParametricEquation(name="a_high", target="phases.0.cell.a", basis="polynomial",
                             terms=[[], ["T"]], where="T >= 800")
joint = rx.MultiHistogramRefinement(lab6, instruments, coordinates=coordinates,
                                    parametric=[low, high])

resolved_low, resolved_high = joint.parametric
assert resolved_low.where == "T < 800" and resolved_low.patterns is None
assert resolved_low.reference == {"T": 450.0}
```

## A target glob

On a constant, polynomial or design basis the target may be a glob, such as `phases.0.cell.*` or `phases.0.atoms.*.biso`.
It is expanded when the declaration is resolved, into one declaration per matched path, each with its own coefficients.
An orthorhombic cell linear in T is then one declaration rather than three.

Each member is named `<name>_<tail>`, where the tail is the matched path after the glob's leading literal segments, with its dots written `_`.
A declaration `cell` on `phases.0.cell.*` has the member `cell_a` on `phases.0.cell.a`, whose coefficients are `vars.cell_a_0` and `vars.cell_a_1` for a line in T.
A member named like another declaration is refused, as two declarations of one name are.

A glob may match paths that no equation can drive: on a cubic phase, `phases.0.cell.*` matches `b` and `c`, which are tied to `a`, and three locked angles.
Those paths are skipped, silently: the space group fixes them, and the declarations the result carries show which paths moved.
A skip you could not foresee, a path held for the floating origin, is named in [`PARAMETRIC_GLOB_SKIPPED`](diagnostics-series.md#parametric_glob_skipped), an info.
A path is skipped only where every pattern of the subset refuses it. One that the capillary locks and the flat plate frees can be driven on the plate, so the glob is refused, naming the pattern, whatever order the patterns come in.
A glob that matches nothing, or matches only such paths, is refused.
So is a glob that matches a path refused for another reason, such as a rigid body's increment or a moment component, since that is a path you may have meant to drive.
The glob is matched against the model of every pattern of the subset, so a path that only some of them have, such as a background term, is a member, and the patterns without it are refused by name.

The declarations as resolved carry the bare targets, so `MultiHistogramRefinement.parametric` lists one per member, and a refit passing them back wires the same equations.
An expression equation takes no glob: its variables are shared, so every matched path would take one value.

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
           rx.Atom(label="B", species="B", x=rx.Parameter(value=0.1975),
                   y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))],
)])
temperatures = [300.0, 450.0, 600.0, 750.0, 900.0]
instruments = [rx.Instrument.debye_scherrer(wavelength=0.4139) for _ in temperatures]
coordinates = rx.CoordinateTable(columns={"T": temperatures}, units={"T": "K"})

cell = rx.ParametricEquation(name="cell", target="phases.0.cell.*", basis="polynomial",
                             terms=[[], ["T"]])
biso = rx.ParametricEquation(name="B", target="phases.0.atoms.*.biso", basis="polynomial",
                             terms=[[], ["T"]])
joint = rx.MultiHistogramRefinement(lab6, instruments, coordinates=coordinates,
                                    parametric=[cell, biso])

assert [(e.name, e.target) for e in joint.parametric] == [
    ("cell_a", "phases.0.cell.a"),
    ("B_0_biso", "phases.0.atoms.0.biso"),
    ("B_1_biso", "phases.0.atoms.1.biso"),
]
```
