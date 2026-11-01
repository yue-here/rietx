# %% [markdown]
# # A Rietveld refinement on your own data
#
# A template: change the cells marked ✏️ and run the notebook top to bottom.
# As shipped it runs on the fluorapatite example from notebooks 01 and 02, so you can see every output before you change anything.
# Those two notebooks explain each step on the same data.
#
# *Written by Claude Code, Anthropic's coding agent, for the rietx project.*
#
# **In Colab**, upload your files with the folder icon in the left sidebar.
# Right-click a file and choose *Copy path* to get its path, which starts `/content/`.
# Files there are deleted when the runtime stops, so download what the last cell writes.

# %%
# %pip install rietx

# %% [markdown]
# ## Your files and instrument ✏️
#
# For a capillary or a synchrotron pattern, replace the instrument with [`rx.Instrument.debye_scherrer(wavelength=...)`](https://rietx.org/docs/stable/reference/instrument.html#constructors), the wavelength in Å.
# [How to limit the fit range or leave out a region](https://rietx.org/docs/stable/guides/range.html) covers the range and excluded regions.

# %%
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.examples import examples_dir

# ✏️ your pattern
PATTERN = examples_dir() / "FAP.XRA"
# ✏️ one CIF per crystalline phase
CIFS = [examples_dir() / "fluorapatite.cif"]
# ✏️ the anode: "CuKa", "CoKa", "MoKa", ...
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
# ✏️ the range to fit, in degrees 2θ; None fits all of it
TWO_THETA_LIMITS = (15, 130)
# where the last cell writes
OUTPUT = Path("rietx_output")

# %% [markdown]
# [`rx.read_pattern`](https://rietx.org/docs/stable/reference/pattern-files.html#reading-a-pattern) recognises the format from the file.
# [`rx.capabilities().reader_formats`](https://rietx.org/docs/stable/reference/pattern-files.html#formats) lists every format it opens.
# The pattern prints its range and step, and its [`sigma`](https://rietx.org/docs/stable/reference/pattern-files.html#intensities-and-esds) row reads `None` when the file gives no esd column.
# The fit then weights each point by √y.

# %%
data = rx.read_pattern(PATTERN)
data

# %%
data.plot()

# %% [markdown]
# [`rx.diagnose`](https://rietx.org/docs/stable/reference/pattern-diagnostics.html) measures the pattern with no model.
# The instrument's source gives it the wavelength and the lines the beam can carry, so it can screen for Kβ and tungsten Lα lines.

# %%
diag = rx.diagnose(
    data,
    wavelength=instrument.source.primary_wavelength,
    source=instrument.source,
)
diag

# %% [markdown]
# Read `signal_cutoffs` and `dead_channels` first.
# They say where to set `TWO_THETA_LIMITS` and which channels to exclude.
# `dead_channels` needs a σ column, and reads `not checked (no measured σ)` when the file gives none.
# A `steps_per_fwhm` below five limits what the peak shape can tell you, and the fit reports it again.
# A line in `contamination` needs its range excluded.
# [How to check a pattern before fitting](https://rietx.org/docs/stable/guides/check.html#read-the-pattern-diagnostics) explains every row.
#
# ## The model, checked before fitting
#
# Each CIF adds its phases to one [structure](https://rietx.org/docs/stable/reference/data.html#structure).
# The background is a six-term [Chebyshev polynomial](https://rietx.org/docs/stable/reference/instrument.html#chebyshev-polynomial), its constant term started at the floor of the data.

# %%
phases = [phase for cif in CIFS for phase in rx.Structure.from_cif(cif).phases]
structure = rx.Structure(phases=phases)

instrument.background = rx.BackgroundChebyshev.with_terms(6)
c0 = float(np.percentile(data.intensity, 5))
instrument.background.coefficients[0].value = c0

ref = rx.Refinement(structure, instrument)
ref

# %% [markdown]
# Draw the model's reflection positions under the data before fitting.

# %%
# ✏️ any 10° with strong peaks
data.plot(model=ref, two_theta_range=(25, 35))

# %% [markdown]
# Every observed peak in the window should have a tick under it.
# From an anode the ticks include each reflection's Kα2 line, so most peaks have a pair.
# An offset that is the same at every angle points to the zero shift.
# An offset that grows with angle points to the cell or the wavelength.
# Least squares moves a tick only while it still overlaps its peak, so correct a larger offset in the CIF or the instrument first.
# A peak with no tick points to a phase you have not given a CIF for.
# [Check the starting cell against the peaks](https://rietx.org/docs/stable/guides/check.html#check-the-starting-cell-against-the-peaks) shows what a wrong cell looks like.
#
# ## Le Bail: does the cell index the pattern?
#
# [Le Bail](https://rietx.org/docs/stable/reference/refinement.html#modes) fits the cell and the peak shapes with free intensities.
# If it cannot fit the pattern, a Rietveld fit will not either.
# It runs on its own [`Refinement`](https://rietx.org/docs/stable/reference/refinement.html#entry-points), so the Rietveld fit below starts from the CIF.

# %%
lebail = rx.Refinement(structure, instrument).fit(
    data,
    mode="lebail",
    plan="profile_only",
    two_theta_limits=TWO_THETA_LIMITS,
)
lebail.plot()

# %% [markdown]
# A flat difference curve here means the cell and the peak shapes are right.
# The [plot's title](https://rietx.org/docs/stable/reference/figures.html#the-fit-figure) carries the Le Bail Rwp, so note it.
# A Rietveld Rwp well above it points at the structure model rather than the cell or the peaks.
# It is not a floor.
# The [`profile_only`](https://rietx.org/docs/stable/reference/plans.html#profile-only) plan frees fewer instrument terms than the Rietveld one, so a Rietveld Rwp a little below it is normal.
#
# ## Rietveld
#
# `mccusker_structural` frees the scale and background first, then the zero shift, the cell and the peak widths, then the atoms.
# [Plan presets](https://rietx.org/docs/stable/reference/plans.html) draws its stages and those of every other plan.

# %%
result = ref.fit(
    data,
    plan="mccusker_structural",
    two_theta_limits=TWO_THETA_LIMITS,
)
result.plot()

# %% [markdown]
# Set the Rwp in the title beside the Le Bail one.
#
# ## What the fit says about itself
#
# Read every diagnostic before quoting a number.
# [`deliverable`](https://rietx.org/docs/stable/reference/result.html#printing-a-result) picks the rows that decide whether the fit is done for one purpose: `"structure"`, `"qpa"`, `"phase_id"`, `"cell"`, `"microstructure"`, `"calibration"`, `"magnetic"` or `"series"`.

# %%
print(ref.summary(deliverable="structure"))

# %% [markdown]
# The diagnostics come before the statistics.
# Each ends with a `help` line saying what to do about it.
# [Diagnostic codes](https://rietx.org/docs/stable/reference/diagnostics.html) lists every code, and [About the report](https://rietx.org/docs/stable/concepts/report.html) explains the report's misfit regions.
#
# ## The refined structure
#
# [`result.parameters`](https://rietx.org/docs/stable/reference/parameter-table.html#refined-rows) lists every refined value with its esd.

# %%
result.parameters

# %% [markdown]
# [`rx.viz.render_structure`](https://rietx.org/docs/stable/reference/figures.html#structure-pictures) draws the refined structure.
# The default view is oblique.
# [`view`](https://rietx.org/docs/stable/reference/figures.html#views) takes `"a"`, `"b"`, `"c"`, a direction `[u, v, w]`, a plane normal `{"hkl": (h, k, l)}`, or `"auto"`, which picks the low-index direction that hides the fewest atoms.
# A view down a symmetry axis is often the one a reader recognises.
# `turn="-15x"` tips the view, and `atom_labels=True` names the sites.

# %%
# ✏️ view=, turn=, phase=1 for a second phase
rx.viz.render_structure(ref.structure)

# %% [markdown]
# ## Save the results
#
# [The CIF](https://rietx.org/docs/stable/reference/exports.html#the-refinement-cif) carries the refined structure with its esds, the R factors, the pattern and the reflection list.
# The project directory starts from the refined model with these settings, and [`rietx gui`](https://rietx.org/docs/stable/reference/cli.html#rietx-gui) opens it.
# It does not hold this fit's stages.
# A fit run through [`rx.Project`](https://rietx.org/docs/stable/reference/project.html#creating-a-project) would record them.
# A `refinement.rex` that exists already is kept as it is, so rename or delete it before saving another fit there.
# [About the project](https://rietx.org/docs/stable/concepts/project.html) describes what the directory holds.

# %%
OUTPUT.mkdir(exist_ok=True)
ref.write_cif(OUTPUT / "refined.cif")
result.plot(path=OUTPUT / "fit.png")
rex = OUTPUT / "refinement.rex"
if not rex.exists():
    rx.Project.create(
        rex,
        pattern=PATTERN,
        structure=ref.structure,
        instrument=ref.instrument,
        plan="mccusker_structural",
        two_theta_limits=TWO_THETA_LIMITS,
    ).save()
sorted(item.name for item in OUTPUT.iterdir())
