# How this manual was written

Claude (Opus 5 and Fable 5) wrote this manual from the source code, its docstrings and the project's design records, under the direction of Yue Wu, who wrote and maintains rietx.

## How it is kept true

Documentation written that way can go stale or describe something the code does not do, so this manual is tested like code.
Every rietx name and parameter path on its pages resolves against the installed package.
Every walkthrough is a script from `examples/` that the test suite runs.
Every threshold the Theory tab quotes is injected from the live package when the manual builds, and each displayed equation names the symbol it was transcribed from, which a test imports.

Those guards catch names and numbers.
They cannot catch a paragraph that explains the wrong thing, so if a page misleads you, please [open an issue](https://github.com/yue-here/rietx/issues) and say which page.

## How to read it

Believe a docstring over this manual.
Every physics function in rietx cites its reference (author, year, journal) in its docstring, and the long derivations live in the module docstrings.
The manual organises that material into numbered equations under Theory and into tasks under Guides; it does not replace it.

Names follow Python's convention: `CapWords` for classes, lower case for functions and modules, and `UPPER_CASE` for module-level constants.
So `Refinement` and `FitReport` are classes, `refine` and `read_pattern` are functions, and `PLAN_INFO` is a constant.

A method or a field is written under the class that defines it, not under the variable you would hold it in.
`RefinementResult.plot` is the `plot` method of a `RefinementResult`, and in your own code that line reads `result.plot(...)`.
Written this way the name resolves, so the test suite can check it against the package.

Parameter dot-paths are the other dotted thing here, and they are never capitalised.
`phases.0.cell.a` and `instrument.profile.w` are data: addresses into the parameter table, not attributes of a class.

If an agent runs your fits, the instructions it reads are the agent skill, described under [Agents](../reference/agents.md).
This manual describes the surface the skill drives and does not restate it.
