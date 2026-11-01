# rietx tutorials

Executed notebooks that build a working picture of what rietx does with a powder pattern.
They show rietx's moves one step a cell, for readers who already know the Rietveld method.
Each links the manual for the reasons behind a step.
Notebook 06 is a template for your own data.

*Written by Claude Code, Anthropic's coding agent, for the rietx project.*

Every notebook needs rietx 1.10 or later, and its first code cell installs it with `%pip install rietx`.
The data ships inside the package, so no download is needed.

| Notebook | What it teaches | Data and licence | Runtime |
|---|---|---|---|
| [`01_quickstart.ipynb`](01_quickstart.ipynb) | Look at a pattern, check a model against it before fitting, fit the cell and peak shapes with Le Bail, read the summary in order, keep the best pass | `FAP.XRA` and `fluorapatite.cif`, fluorapatite from the GSAS-II `LabData` tutorial (Argonne/APS tutorial data, U.S. Government work) | under 30 s |
| [`02_simple_rietveld.ipynb`](02_simple_rietveld.ipynb) | A staged Rietveld refinement: the plan's stages, the parameter table and its `dof` rows, bond lengths, the refined structure drawn from two views, saving a project | The same two files | under 30 s |
| [`02b_steering_a_refinement.ipynb`](02b_steering_a_refinement.ipynb) | Changing what a fit refines: tying three atoms' Biso, two parameters the data cannot separate, going back in the history and holding one, reading the history, a verdict for a declared deliverable | The same two files | under 30 s |
| [`03_peaks_indexing_lebail.ipynb`](03_peaks_indexing_lebail.ipynb) | Picking peaks and reading the peak list, measuring lines you name, indexing with a narrowed search, when the indexer names a cell, and checking a candidate cell with Le Bail | Synthetic aragonite from COD entry 9000229 (public domain), built in the notebook | under a minute |
| [`04_peak_shape_and_microstructure.ipynb`](04_peak_shape_and_microstructure.ipynb) | How instrument and specimen widths combine, calibrating an instrument on a standard, saving and loading it, measuring crystallite size and strain against a known truth, and what skipping the calibration does | Synthetic LaB₆ and CeO₂, built in the notebook | under 30 s |
| [`05_sequential_fits.ipynb`](05_sequential_fits.ipynb) | Fitting a heating ramp pattern by pattern, the warm start and `carry`, a parameter's trajectory against the truth, running the chain both ways, and what the series reports when one frame jumps or cannot be fitted | Synthetic LaB₆, built in the notebook | under 30 s |
| [`06_your_own_data.ipynb`](06_your_own_data.ipynb) | A template, not a tutorial, committed without outputs: change the marked cells to your pattern, CIFs and anode, then run it to check the data, check the model, fit Le Bail then Rietveld, read the summary, draw the structure and save a CIF and a project | The fluorapatite files until you change them | about 15 s on the example, measured in a Linux cloud container |

Runtimes were measured on an Apple M-series laptop, kernel start included, unless a row says otherwise.

## Not covered yet

- Background shapes and amorphous humps.
- Kβ lines and other contaminating wavelengths.
- A second phase: NAC's fluorite impurity and what the difference curve shows.
- Quantitative phase analysis.

## Adding a tutorial

Each notebook is generated from the script of the same name.
Edit the `.py`, never the `.ipynb`.

1. Write `NN_slug.py` in jupytext's percent format.
   A letter after the number, as in `02b_slug.py`, files a notebook straight after the one it continues.
   `# %%` opens a code cell.
   `# %% [markdown]` opens a markdown cell, and each of its lines starts `# `.
   Put every import in the first code cell.
2. Build it with `python examples/tutorials/build.py NN_slug`.
   The build executes the notebook in a fresh kernel and refuses to write one that raised, printed to stderr, or printed your home directory.
3. Add its row to the table above.
4. Run `pytest tests/test_tutorials.py`.
   The tests find tutorials by file name, so none of them needs an edit.

Keep each notebook to a minute or less.
The test suite executes every notebook on every push.

## How a tutorial reads

The reader knows powder diffraction.
They may not know rietx, Jupyter or Python.
Nothing on the page should make them decode something.

- Nothing the reader needs comes before it is explained or linked.
  That covers a programming idea, a tool such as a Jupyter cell, and a rietx idea.
  If the explanation fits in one sentence, write that sentence instead of naming the prerequisite.
- Predict, then run.
  The markdown before a cell says what to expect.
  The markdown after it says what the output showed, in the output's own words.
- A rebuild that changes an output rereads the markdown under it.
  `build.py` lists each such cell with the first line of that markdown.
  Nothing else catches prose that has fallen behind its output.
- Each piece of the model gets a cell that shows it against the data before a fit uses it.
- A thing keeps one name on a page.
- Say what changes and where, without a metaphor of price, motion or agency.
  For example, write "the zero shift moves every tick by the same angle".
- Describe a figure by what the reader can see, then the cause, then the consequence, one sentence each.
- A call that does not fit 79 columns takes one argument per line, with a trailing comma.
  `ruff format examples/tutorials` lays the sources out that way, and `ruff format --check examples/tutorials` fails on one it has not.
  Never pad the `=` signs into a column: PEP 8 forbids spaces around a keyword `=`.

The manual's prose linter reads the markdown cells too.
`python examples/tutorials/build.py --prose` writes them to `_prose/`, and `vale examples/tutorials/_prose` checks them against the manual's rules.
CI runs both, and fails on an error.

A template is listed in `build.py`'s `UNEXECUTED`: its build executes it and commits it without outputs, so nothing from the example files reads as the reader's own.

Rebuild every notebook with `python examples/tutorials/build.py` when the package version changes.
`build.py --check` reports a notebook whose cells or version stamp have fallen behind its source.
