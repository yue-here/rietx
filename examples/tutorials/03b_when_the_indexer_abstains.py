# %% [markdown]
# # When the indexer abstains
#
# Notebook 03 indexes a synthetic aragonite pattern, and rietx names its cell.
# Here we give the same search less of the same pattern, and rietx names no cell.
# By the end you can read why an indexing result abstains, and what would let it name a cell.
#
# *Written by Claude Code, Anthropic's coding agent, for the rietx project.*
#
# **You need** rietx 1.10 or later, which the next cell installs.
# Notebook 03 introduces picking peaks, the indexing search and how to read its result.
#
# **The data** is notebook 03's synthetic aragonite, CaCO₃, made from its published structure: Dal Negro and Ungaretti (1971), *American Mineralogist* 56, 768, as entry 9000229 of the Crystallography Open Database (public domain).
#
# **Runtime** is under a minute on a laptop, most of it the indexing search.

# %%
# %pip install rietx

# %% [markdown]
# ## The pattern and the search
#
# This cell repeats notebook 03's synthetic pattern, its default copper instrument and its narrowed search.
# Notebook 03 explains each step.

# %%
import tempfile
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.indexing import SearchSpec

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
    encoding="utf-8",
)
truth = rx.Structure.from_cif(cif)

true_instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
true_instrument.profile.w.value = 0.004
true_instrument.profile.x.value = 0.05
true_instrument.background = rx.BackgroundChebyshev.with_terms(1)
true_instrument.background.coefficients[0].value = 200.0

two_theta = np.arange(10, 80, 0.02)
y = rx.Refinement(truth, true_instrument).predict(two_theta) - 200.0
truth.phases[0].scale.value *= 20000 / y.max()
y = rx.Refinement(truth, true_instrument).predict(two_theta)
data = rx.PatternData(
    two_theta=two_theta,
    intensity=np.random.default_rng(0).poisson(y).astype(float),
)

lab = rx.Instrument.bragg_brentano(radiation="CuKa")
spec = SearchSpec(
    systems=("orthorhombic",),
    min_volume=200,
    max_volume=250,
    max_d_axis=8.5,
    budget_seconds=120,
)

# %% [markdown]
# ## A shorter scan
#
# Cut the pattern at 45° 2θ, pick its peaks, and search with the same `spec`.

# %%
short = data.crop(10, 45)
short_peaks = rx.pick_peaks(short, lab)
short_indexing = rx.index_pattern(
    short_peaks, data=short, instrument=lab, spec=spec
)
short_indexing

# %% [markdown]
# The header counts 15 lines, against 54 over notebook 03's whole range.
# The top candidate is still the true cell, and all three engines still found it.
# Its row indexes 14 of the 15 lines, and the Pawley fit reaches Rwp 0.047.
# Its grade is `medium`.
# The row's `not higher because` names the two caveats that hold it there:
#
# - `fom_panel_reduced`: 15 lines are fewer than the 20 that the `m20` and `f_n` figures of merit are scored on, so the ranking panel leaves those two figures out. [`INDEX_PANEL_REDUCED`](https://rietx.org/docs/stable/reference/diagnostics-indexing.html#index-panel-reduced) says so.
# - `shift_allowance_assumed`: over the whole range, notebook 03's search measured a systematic 2θ shift from 8 pairs of harmonic reflections (lines whose sin θ are integer multiples of one another). These 15 lines give no such measurement, so [`INDEX_SHIFT_ALLOWANCE`](https://rietx.org/docs/stable/reference/diagnostics-indexing.html#index-shift-allowance) adds an assumed 0.050° in quadrature to every line's σ.
#
# Neither caveat says the cell is wrong.
# Each says the evidence is too thin to call it right, and a longer scan closes both.
# So the verdict line says NO CELL, and [`INDEX_ABSTAINED`](https://rietx.org/docs/stable/reference/diagnostics-indexing.html#index-abstained) names the best candidate and its two caveats.
# Its help line says to act first on any caveat that refutes a cell.
# This candidate has none.
#
# The row also raises [`INDEX_IMPURITY_LINES`](https://rietx.org/docs/stable/reference/diagnostics-indexing.html#index-impurity-lines) for one region near 25.54°.
# That region is the low-angle tail of the strongest line, at 26.22°.
# The pattern holds one phase.
# The Pawley fit draws that line's profile only from about 25.6° upward, so the tail below 25.6° stays in the residual.
#
# [`best_or_none()`](https://rietx.org/docs/stable/reference/indexing.html#the-result-object) returns `None`.

# %%
print(short_indexing.best_or_none())

# %% [markdown]
# With a real unknown, read the caveats before you test any candidate.
# Here both caveats ask for more lines.
# With all 54 lines, notebook 03's search named the cell at `high`.
