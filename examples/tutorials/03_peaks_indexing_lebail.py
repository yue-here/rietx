# %% [markdown]
# # Peaks, indexing and a Le Bail check
#
# When the phase is unknown there is no CIF to start from, and the cell has to come from the peak positions alone.
# We pick the peaks of a synthetic pattern whose answer we know, index them, and read why rietx declines to name a single cell.
# Then we check the best candidate with a Le Bail fit.
# By the end you can pick and fit peaks, run an indexing search, and test a candidate cell against the whole pattern.
#
# *Written by Claude Code, Anthropic's coding agent, for the rietx project.*
#
# **You need** rietx 1.10 or later, which the next cell installs.
# Notebook 01 introduces Le Bail fitting.
#
# **The data** is synthetic aragonite, CaCO₃, made from its published structure: Dal Negro and Ungaretti (1971), *American Mineralogist* 56, 768, as entry 9000229 of the Crystallography Open Database (public domain).
# The displacement parameters are the isotropic equivalents of that entry's anisotropic ones.
#
# **Runtime** is under a minute on a laptop, most of it the indexing search.

# %%
# %pip install rietx

# %% [markdown]
# ## A synthetic pattern
#
# Write aragonite's structure to a CIF and read it back.

# %%
import tempfile
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.indexing import SearchSpec, structure_from_candidate

work = Path(tempfile.mkdtemp())
cif = work / "aragonite.cif"
cif.write_text(
    "data_aragonite\n_space_group_name_H-M_alt 'P m c n'\n"
    "_cell_length_a 4.9616\n_cell_length_b 7.9705\n_cell_length_c 5.7394\n"
    "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
    "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
    "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
    "Ca1 Ca 0.25 0.4151 0.2403 0.67\n"
    "C1  C  0.25 0.7627 0.0850 0.80\n"
    "O1  O  0.25 0.9231 0.0952 1.25\n"
    "O2  O  0.4729 0.6801 0.0870 1.19\n",
    encoding="utf-8")
truth = rx.Structure.from_cif(cif)

# %% [markdown]
# `predict` computes a pattern from a structure and an instrument without fitting anything.
# This instrument sets its own peak widths and a flat background of 200 counts.
# We scale the phase so the strongest peak reaches about 20 000 counts above the background, then draw Poisson counts.

# %%
true_instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
true_instrument.profile.w.value = 0.004
true_instrument.profile.x.value = 0.05
true_instrument.background = rx.BackgroundChebyshev.with_terms(1)
true_instrument.background.coefficients[0].value = 200.0

two_theta = np.arange(10, 80, 0.02)
y = rx.Refinement(truth, true_instrument).predict(two_theta) - 200.0
truth.phases[0].scale.value *= 20000 / y.max()
y = rx.Refinement(truth, true_instrument).predict(two_theta)
data = rx.PatternData(two_theta=two_theta,
                      intensity=np.random.default_rng(0).poisson(y).astype(float))
data.plot()

# %% [markdown]
# From here on we pretend not to know the structure.
# The indexer should find the CIF's cell, perhaps with its axes in another order.
#
# ## Find the peaks
#
# `pick_peaks` finds every resolvable peak and fits each one for its position, with an esd.
# It needs an instrument for the wavelength and a first guess at the peak width.
# Give it a default copper instrument, as you would for an unknown sample.
# Its widths do not match these peaks, so expect the picker to say so.

# %%
lab = rx.Instrument.bragg_brentano(radiation="CuKa")
peaks = rx.pick_peaks(data, lab)
peaks

# %% [markdown]
# Each row is one peak: its position, the esd of that position, its area and its width.
# `flags` records anything the fit noticed.
# Some flags, such as `duplicate_line` and `fit_failed`, take a row out of indexing.
# The header line counts the rows left usable.
#
# The diagnostics under the table explain the list.
# `PEAK_WIDTH_LAW_MISMATCH` says the default instrument predicts narrower peaks than these, so the picker scaled its windows to the data.
# `PEAK_KALPHA2_ALIAS` lists candidates dropped as the Kα2 partner of a stronger line, so each reported position is a Kα1 position.
# Open a diagnostic to read what its code means.
# [Diagnostics: peaks and indexing](https://rietx.org/docs/stable/reference/diagnostics-indexing.html) lists every code.
#
# ## Measure lines you name
#
# `fit_peaks` fits exactly the positions you give it, and nothing else.
# Use it to measure lines you have chosen: a few reflections for a size analysis, or one line as a quick check.

# %%
chosen = rx.fit_peaks(data, lab, [26.22, 27.22, 33.13])
chosen

# %% [markdown]
# Each line is marked `manual`, because its position came from you.
# A line flagged `unnamed_neighbour` shares its fitting window with a line you did not name, and that line's intensity had nowhere to go but into it.
# A whole peak list rebuilt from edited positions in code meets this at every line it leaves out.
#
# ## The same work in the GUI
#
# Editing a peak list is easier by hand, and rietx has a graphical mode for it.
# Run `rietx gui` in a terminal, open or create a project with your pattern, and choose the Peaks tab.
# The plot then becomes an editing surface:
#
# | Gesture | Does |
# |---|---|
# | click empty space | add a line, measured by `fit_peaks` |
# | drag a marker | move it |
# | shift-click | exclude a line from indexing |
# | right-click | remove it |
#
# The same tab runs the indexing search, draws a candidate's predicted lines over the pattern, and adopts a candidate as the starting point of a Le Bail fit.
# Every gesture also has a typed equivalent in the panel.
# [The GUI panel by panel](https://rietx.org/docs/stable/reference/gui-guide.html#peaks) covers the tab in full.
#
# ## Index
#
# `index_pattern` searches for cells that index the usable peaks.
# A search over every crystal system can take minutes, so we narrow it.
# `SearchSpec` limits it to orthorhombic cells, with a volume between 200 and 250 Å³ and no axis longer than 8.5 Å.
# Those limits come from knowing the answer.
# With a real unknown, start from the formula and a wide window, and let the search run longer.

# %%
spec = SearchSpec(systems=("orthorhombic",), min_volume=200, max_volume=250, max_d_axis=8.5)
indexing = rx.index_pattern(peaks, data=data, instrument=lab, spec=spec)
indexing

# %% [markdown]
# The top candidate is the true cell, with its axes in a different order.
# All three search engines found it.
#
# Yet the verdict line says NO CELL.
# rietx names a single cell only when exactly one candidate reaches high confidence, and this one is low for the reasons in its row.
#
# - `predicted_but_absent`: the indexer tests a candidate in the lattice's highest-symmetry space group, and that group has no systematic absences. Aragonite's real space group, Pmcn, has glide planes that remove some reflections. Those reflections are predicted but absent.
# - `indexed_fraction_low`: some usable lines sit at no reflection of this lattice. Most are weak false lines the picker found near strong peaks. The line near 36° is two reflections 0.05° apart, fitted as one line between them.
#
# The candidate's `INDEX_IMPURITY_LINES` warning comes from the indexer's own quick Le Bail fit, whose Rwp in the candidate's row is poor.
# A poor fit leaves many peaks unmatched, so that count is not evidence of a second phase.
# Our own Le Bail fit below settles it.
#
# `best_or_none()` returns a cell only when the gate passes.
# Here it returns `None`.

# %%
print(indexing.best_or_none())

# %% [markdown]
# [`INDEX_ABSTAINED`](https://rietx.org/docs/stable/reference/diagnostics-indexing.html#index-abstained) says what the abstention means.
# [Indexing](https://rietx.org/docs/stable/theory/indexing.html#figures-of-merit-in-both-directions) explains the figures of merit behind the ranking.
#
# ## Check the candidate with Le Bail
#
# `structure_from_candidate` turns a candidate into a structure for Le Bail fitting.
# It uses the lattice's highest-symmetry space group, so the fit tests the lattice and nothing else.
# We test the first candidate because it is the true cell.
# With a real unknown, test each candidate whose caveats you cannot rule out.

# %%
candidate = indexing.candidates[0]
structure = structure_from_candidate(candidate)
structure.phases[0].space_group

# %% [markdown]
# As in notebook 01, start the background's constant term at the 5th percentile of the counts, and run the plan twice.

# %%
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(4)
instrument.background.coefficients[0].value = float(np.percentile(data.intensity, 5))

ref = rx.Refinement(structure, instrument)
first = ref.fit(data, mode="lebail", plan="profile_only")
second = ref.fit(data, mode="lebail", plan="profile_only")
ref.history

# %% [markdown]
# The first pass starts from the default instrument's peak widths, so its Rwp falls most at the two width stages.
# The second pass starts where the first ended.
#
# Keep the pass with the lower Rwp, and return the working state to its node.

# %%
best = min([first, second], key=lambda r: r.statistics.rwp)
ref.checkout(best.node_id)
best

# %% [markdown]
# `FLOOR_HIT` says the profile's Y term, the Lorentzian width that grows as tan θ, refined to its lower limit.
# The pattern was made with no such term, so here the limit is the right answer.
#
# The table under the summary starts with the refined cell edges.
# They match the CIF's cell, in the candidate's order of axes.
# Now look at the fit.

# %%
best.plot()

# %% [markdown]
# The fit puts a reflection under every peak and leaves only small residuals, so the lattice is right.
#
# Some ticks stand over no peak, such as those near 11° and 15.5°.
# They are reflections P m m m allows and aragonite's glide planes remove.
#
# What this does not settle is the space group.
# That is a question about which reflections are absent, and it comes after the cell is refined.
