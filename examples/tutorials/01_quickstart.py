# %% [markdown]
# # Quickstart: look at a pattern, then fit it with Le Bail
#
# We read a laboratory powder pattern, look at it, and fit its cell and peak shapes.
# The fit uses no atomic positions.
# By the end you can read a fit's summary in the order rietx prints it, and keep the best of several Le Bail passes.
#
# *Written by Claude Code, Anthropic's coding agent, for the rietx project.*
#
# **You need** Python 3.11 or later and rietx 1.10 or later, which the next cell installs.
# Run the cells in order from the top.
# Shift+Enter runs the selected cell, and so does the ▶ button in the toolbar.
# You do not need to have refined anything in rietx before.
#
# **The data** is fluorapatite, Ca₅(PO₄)₃F, measured on a Bragg-Brentano diffractometer with a copper tube.
# It is the `LabData` example from the GSAS-II tutorials and ships with rietx.
# Its provenance and licence are in the repository's `tests/data/README.md`.
#
# **Runtime** is under a minute on a laptop.

# %%
# %pip install rietx

# %%
import numpy as np

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
data

# %% [markdown]
# A pattern prints as its size and range.
# `sigma: None` means the file has no esd column, so the fit weights each point by √y.
#
# ## Look before fitting
#
# Plot the pattern before any model touches it.

# %%
data.plot()

# %% [markdown]
# The peaks are sharp and the background is low and smooth.
# Nothing in the scan looks like a second phase or an amorphous hump, so one phase is a fair start.
#
# `rx.diagnose` measures the pattern with no model.
# Pass the Cu Kα1 wavelength so it can screen for Kβ and tungsten Lα lines.

# %%
diag = rx.diagnose(data, wavelength=1.5406)
diag

# %% [markdown]
# The rows print in the order to read them.
# Four of them decide how this pattern can be fitted.
#
# - `dead_channels` is empty, but `coverage_plateau` is `None`. The file gives no σ, so dead channels could not be looked for.
# - `steps_per_fwhm` is below the five steps the IUCr guidelines ask for. No refinement recovers that, and the fit will report it again.
# - `contamination` is empty, so no Kβ or tungsten Lα line was found.
# - `signal_to_background` compares the tallest peaks with the median background.
#
# The last three rows are rough peak counts. Nothing in the fit reads them.
# [How to check a pattern before fitting](https://rietx.org/docs/stable/guides/check.html#read-the-pattern-diagnostics) explains every row.
#
# ## Build a model
#
# A Le Bail fit needs a cell, a space group and an instrument.
# The cell and space group come from a CIF of fluorapatite shipped beside the pattern.
# The CIF has atoms too. A Le Bail fit ignores them.
#
# The background is a six-term Chebyshev polynomial.
# Its constant term starts at the 5th percentile of the counts, which sits near the background level between the peaks.
# At zero, the first Le Bail extraction would count the background under each peak as peak intensity.
# `rx.auto_background(data).background` would size a penalised spline instead.
# On this pattern the spline reports hundreds of correlated coefficient pairs.
# They would crowd the diagnostics below.

# %%
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(6)
instrument.background.coefficients[0].value = float(np.percentile(data.intensity, 5))

ref = rx.Refinement(structure, instrument)
ref

# %% [markdown]
# A `Refinement` holds the structure and the instrument.
# Its `mode` is the default until a fit names another.
# Only the background varies so far.
# The fit's plan sets the refine flags afresh at each stage, as [About a fit](https://rietx.org/docs/stable/concepts/fit.html#the-plan) describes.
#
# Before fitting, draw the model's reflection positions under the data.
# Expect a tick under every peak.

# %%
data.plot(model=ref, two_theta_range=(25, 35))

# %% [markdown]
# The ticks include the Kα2 line of each reflection, so most peaks have a pair.
# Each pair sits slightly to the right of its peak, by about the same angle across this range.
# A gap that is the same at every angle is a zero shift, and the fit's `zero` stage corrects it.
# A gap that grows with 2θ means the starting cell or the wavelength is wrong.
# Least squares moves a tick only while it still overlaps its peak.
# So correct the CIF or the instrument first when a tick sits a peak width or more from its peak.
#
# ## Fit
#
# `mode="lebail"` extracts each reflection's intensity from the data.
# The `profile_only` plan runs five stages, named `bkg`, `zero`, `cell`, `profile_w` and `profile`.
# Each frees one more group and keeps the earlier groups free: the background, the zero shift, the cell, the Gaussian width term W, then the other width terms U, V, X and Y.
# A sixth stage, `closing`, then refines all of them together.
# [Plan presets](https://rietx.org/docs/stable/reference/plans.html) draws its stages.
# `two_theta_limits` sets the channels the fit uses.
# We stop at 130° to match the GSAS-II tutorial.
#
# Expect the summary to report the under-sampling again.

# %%
LIMITS = (15, 130)
result = ref.fit(data, mode="lebail", plan="profile_only", two_theta_limits=LIMITS)
result

# %% [markdown]
# Read the summary from the top.
#
# 1. Each stage line gives its status, the residual evaluations it took and its `ftol`.
#    `ftol` is the relative fall in χ² below which the stage stops.
#    The first five stages stop at `ftol=1e-06`, a looser tolerance than the solver's own, because a later stage refines their parameters again.
#    The `closing` stage runs at the solver's default, and its values are the ones to quote.
#    `max|Δθ|/esd` is the largest final step of any parameter in units of its own esd.
# 2. The diagnostics outrank every statistic.
#    Under each one, `at:` names the parameters, `help:` says what to do, and `means:` says what the code means.
#    `FLOOR_HIT` says the Lorentzian width term `y` ended on its lower limit of zero.
#    `PATTERN_UNDERSAMPLED` is the step count from `diagnose`.
# 3. The agreement indices come last. Rwp compares two fits of the same data over the same channels, and says little on its own.
#
# The table under the summary is every refined parameter with its esd.
# A Le Bail fit lists the atoms too, held at the CIF's values.
# The `at_bound` column is `true` for a parameter that ended on one of its limits, and empty for a row the fit did not vary, such as a tied or held one.
#
# ## Fit again, and keep the best pass
#
# A Le Bail fit holds its extracted intensities fixed inside each least-squares run.
# The intensities and the profile converge only by alternating, so run the plan twice more.

# %%
second = ref.fit(data, mode="lebail", plan="profile_only", two_theta_limits=LIMITS)
third = ref.fit(data, mode="lebail", plan="profile_only", two_theta_limits=LIMITS)
ref.history

# %% [markdown]
# Each stage committed a node to the refinement's history, so each pass adds six nodes and ends on a `stage:closing` node.
# A later pass is not guaranteed to end lower, so the next cell keeps the lowest.
# `*` marks the head, the node the working state stands at.
# A node's Rwp is measured on the model compiled at the start of its stage, so it can differ slightly from the result's.
#
# Keep the pass with the lowest Rwp, and return the working state to its node.

# %%
best = min([result, second, third], key=lambda r: r.statistics.rwp)
ref.checkout(best.node_id)
best

# %% [markdown]
# The kept pass carries its own diagnostics, and they differ from the first pass's.
# `FLOOR_HIT` is gone, because `y` ended above zero this time.
# `RESOLUTION_UNCONSTRAINED` says the peak widths are not quotable until the instrument's own widths are calibrated on a standard.
# Notebook 04 does that calibration.
#
# The cell's esds are counting statistics.
# They include no error in the wavelength or the zero shift.
# [About a fit](https://rietx.org/docs/stable/concepts/fit.html#the-history) describes the history and `checkout`.
#
# ## Look at the fit

# %%
best.plot()

# %% [markdown]
# The grey trace under the pattern is the difference between the data and the model.
# A good fit leaves it as noise of even width across the scan.
# A wiggle at every peak means the peak shape is wrong.
# A peak with no tick under it means a phase the model lacks.
# Here the largest misfit sits on the strongest peaks, near 32°.
#
# Notebook 02 refines the same pattern with atoms.
