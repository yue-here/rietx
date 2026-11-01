# Tutorial notebooks

The tutorials are {{ N_TUTORIALS }} executed notebooks that fit a laboratory pattern and synthetic ones in Python.
Each runs in under a minute, and the data ships inside the package.
Read a notebook here with its outputs, or download it and run it yourself.
Its first code cell installs `rietx`.

The notebooks show `rietx`'s moves one step a cell, for readers who already know
the Rietveld method.
[](first-fit.md) covers the same ground as a script, on a synchrotron
pattern with an impurity phase.

| Notebook | What it teaches | Download |
|---|---|---|
| [](tutorials/01_quickstart.ipynb) | Look at a pattern, check a model against it, fit the cell and peak shapes with Le Bail, and read the summary in order | {download}`01_quickstart.ipynb <tutorials/01_quickstart.ipynb>` |
| [](tutorials/02_simple_rietveld.ipynb) | A staged Rietveld refinement, the parameter table, bond lengths, the refined structure drawn, and a project | {download}`02_simple_rietveld.ipynb <tutorials/02_simple_rietveld.ipynb>` |
| [](tutorials/02b_steering_a_refinement.ipynb) | Tying three atoms' Biso, two parameters the data cannot separate, going back in the history and holding one, and the verdict for a structure | {download}`02b_steering_a_refinement.ipynb <tutorials/02b_steering_a_refinement.ipynb>` |
| [](tutorials/03_peaks_indexing_lebail.ipynb) | Picking peaks, indexing with a narrowed search, when the indexer names a cell, and checking a candidate cell with Le Bail | {download}`03_peaks_indexing_lebail.ipynb <tutorials/03_peaks_indexing_lebail.ipynb>` |
| [](tutorials/04_peak_shape_and_microstructure.ipynb) | Calibrating an instrument on a standard, then measuring crystallite size and strain against a known truth | {download}`04_peak_shape_and_microstructure.ipynb <tutorials/04_peak_shape_and_microstructure.ipynb>` |
| [](tutorials/05_sequential_fits.ipynb) | Fitting a heating ramp pattern by pattern, a parameter's trajectory, and what the series reports when one frame fails | {download}`05_sequential_fits.ipynb <tutorials/05_sequential_fits.ipynb>` |
| [](tutorials/06_your_own_data.ipynb) | A template for your own pattern and CIFs: change the marked cells and run it top to bottom | {download}`06_your_own_data.ipynb <tutorials/06_your_own_data.ipynb>` |

Notebooks 01 and 02 fit fluorapatite from the GSAS-II `LabData` tutorial, a
laboratory Cu Kα pattern.
Notebooks 03 to 05 build their patterns in the notebook, so each fit can be
checked against the values it was built from.
Notebook 06 is a template rather than a tutorial, committed without outputs.
It runs on the fluorapatite files as shipped, and you replace them with your own.

<!-- Guard note (WP-1916, WP-1986): tests/test_manual_api.py checks the names
on this page and never in the notebooks, so a rietx name in a notebook's
markdown cell goes unchecked.  Their code is covered, because
tests/test_tutorials.py executes every notebook.  docs/docs/conf.py copies the
notebooks into start/tutorials/ from examples/tutorials/ at build, through
docs/sphinx_shared.py's copy_tutorials, and each is generated from the .py of
its name. -->

```{toctree}
:hidden:

tutorials/01_quickstart
tutorials/02_simple_rietveld
tutorials/02b_steering_a_refinement
tutorials/03_peaks_indexing_lebail
tutorials/04_peak_shape_and_microstructure
tutorials/05_sequential_fits
tutorials/06_your_own_data
```
