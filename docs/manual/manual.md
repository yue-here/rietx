# rietx manual

Release {{ release }}. The manual is in two parts.

Part 1, Using rietx, is the task-ordered guide to the package and its public
API: install it, run a fit, understand what the fit did, read the report it
hands back, and drive it from a program. It assumes you know powder diffraction
and not this package.

Part 2, Theory, is the equations behind that machinery, numbered and
cross-referenced, with the conventions that decide whether a number transfers
between Rietveld codes.

:::{admonition} How this manual was written
:class: note
Claude (Opus 5 and Fable 5) wrote this manual from the source code, its
docstrings and the project's design records, under the direction of Yue Wu, who
wrote and maintains `rietx`.

Documentation written that way can go stale or describe something the code does
not do, so this one is tested like code. Every rietx name and parameter path in
Part 1 resolves against the installed package, every example runs in the test
suite, and every threshold quoted in Part 2 is injected from the live package
when the manual builds. Those guards catch names and numbers. They cannot catch
a paragraph that explains the wrong thing, so if a page misleads you, please
[open an issue](https://github.com/yue-here/rietx/issues) and say which page.
:::

## Who this is written for

This manual is written for a person to read, but parts of the package are built
for a program: the `FitReport` and its three layers, `capabilities()`, the JSON
every answer type dumps to, the streaming event ladder, and the diagnostic
codes. They are documented here because a person has to understand them to
trust, debug or extend what a machine does with them. `FitReport` also answers
the question anyone looking at a plot has: where is this model wrong, and how
much of that will the package stand behind?

Notes for agents are marked like this:

:::{admonition} For agents
:class: agent
Read the agent skill first, then come back here for the object model.
`rietx skill --path` prints it, and [](using/skill.md) is the same text
rendered. The skill says what to do in what order, what to check before
believing a number, and which measured findings should change what you do. This
manual describes the surface and does not restate it.
:::

## How to read this manual

Believe a docstring over this manual. Every physics function in `rietx` cites
its reference (author, year, journal) in its docstring, and the long derivations
live in the module docstrings. This manual organises that material into numbered
equations in Part 2 and into a task order in Part 1; it does not replace it. If
the two disagree, please
[report it](https://github.com/yue-here/rietx/issues).

Both parts are guarded against drifting from the code, by different mechanisms.
In Part 2 every threshold and fenced constant is injected from the live package
when the manual builds, so a renamed constant breaks the build; each displayed
equation carries a *Source* line naming the symbol it was transcribed from, and
a test imports every one of them. In Part 1 every dotted name and every
parameter dot-path resolves against the live package, every fenced example
either runs or states why it cannot, and the walkthroughs are scripts from
`examples/` included verbatim and executed by the test suite.

Names follow Python's convention: `CapWords` for classes, lower case for
functions and modules, `UPPER_CASE` for module-level constants. So
`Refinement`, `RefinementResult` and `FitReport` are classes, `refine`,
`read_pattern` and `capabilities` are functions, `rietx.viz.compare` is a
module, and `PLAN_INFO` is a constant.

A method or a field is written under the class that defines it, not under the
variable you would hold it in. `RefinementResult.plot` is the `plot` method of a
`RefinementResult`, and in your own code that line reads `result.plot(...)`.
Written this way the name resolves, so the test suite can check every name in
Part 1 against the live package.

Parameter dot-paths are the other dotted thing here, and they are never
capitalised. `phases.0.cell.a` and `instrument.profile.w` are *data*: addresses
into the parameter table, not attributes of a class.

The two parts set a fit statistic differently, on purpose. Part 2 sets it as
mathematics ($R_{wp}$, $\chi^2_{\mathrm{red}}$, $\Delta d/d$), because there it
is a symbol in an equation, defined by one. Part 1 writes the same statistics as
plain text (Rwp, χ², GoF), because that is the word on the GUI's own header and
in a console line, and Part 1 is about driving the package rather than deriving
it. In either part a name in code font is the field and not the statistic:
`Statistics.rwp` is where the number lives.

## Part 1: Using rietx

The chapters run in the order a first session with the package runs: install
it, work through the tutorial notebooks, get one fit to the end, learn what the
objects hold and how their parameters are addressed, run a staged refinement and
control it, read the numbers and the report, go back to any state the fit
passed through, then the specialised jobs (indexing, series, quantitative phase
analysis, exports, the CLI) and the API a program drives. The closing chapter
is the stability promise.

```{toctree}
:caption: Part 1: Using rietx
:maxdepth: 2

using/install
using/quickstart
using/first-refinement
using/data
using/model
using/concepts
using/constraints
using/refining
using/results
using/report
using/history
using/files
using/indexing
using/series
using/qpa
using/exports
using/recipe
using/cli
using/gui-quickstart
using/gui-guide
using/gui-power
using/agents
using/skill
using/compatibility
using/glossary
```

## Part 2: Theory

```{include} ../docs/theory/index.md
:start-after: <!-- theory-conventions-start -->
:end-before: <!-- theory-conventions-end -->
:heading-offset: 1
```

Part 2 names quantities by their physics. The unit, default and typical range
of a named parameter (what `phases.0.cell.a` or `instrument.profile.w` holds) is
in [](using/glossary.md), which is generated from the package itself.

```{toctree}
:caption: Part 2: Theory
:maxdepth: 2
:numbered:

forward-model
peak-positions
profiles
intensities
corrections
microstructure
background
estimation
parameterisation
representation-analysis
superspace
indexing
engines
method
```

## Citing rietx

If rietx contributed to published work, cite {cite}`rietx2026`. The
repository carries the same record as `CITATION.cff`, which reference
managers and GitHub's "cite this repository" button read directly.

## Bibliography

```{bibliography}
```
