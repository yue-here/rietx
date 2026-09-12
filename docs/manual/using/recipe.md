# The PowderLine recipe

[PowderLine](https://github.com/NSLS2/PowderLine) is a file-less JSON recipe for
a powder refinement: one document carrying the pattern, the instrument, the
phases, the background and a refine flag per parameter, dispatched to one of
several engines behind a single result shape. `read_recipe` turns such a
document into the objects this package refines with, and `write_recipe_tables`
writes a finished refinement back out as the four tables its consumers read.

Use it when a pipeline already speaks that format and you want this package to
be one of the engines it can send work to. For everything else, build the
objects directly ([](data.md)) or open a project ([](files.md)) — a recipe is an
interchange format, not a better API.

## Running one

<!-- api-doc: no-exec — it reads a recipe file the reader supplies -->

```python
import rietx as rx

recipe = rx.read_recipe("input.json")
ref = rx.Refinement(recipe.structure, recipe.instrument)
result = ref.fit(recipe.pattern, plan=recipe.plan,
                 two_theta_limits=recipe.limits)
rx.write_recipe_tables(ref, "output/",
                       phase_names=dict(zip(
                           [p.name for p in ref.fitted_structure.phases],
                           recipe.phase_names)))
```

Pass the **path**, not a parsed dict, wherever one exists. The format is
file-less by design, so a recipe carries its whole pattern inline and a
4096-channel one is 0.4 MB of JSON; that is upstream's contract, but it is a
payload that should cross a filesystem rather than a prompt or a message body.

`Recipe` carries seven fields. `Recipe.structure`, `Recipe.instrument` and
`Recipe.pattern` are the ordinary objects of [](data.md). `Recipe.plan` and
`Recipe.limits` are the recipe's own refinement intent, so pass both rather
than picking a preset — the recipe states which parameters refine, and
`Recipe.limits` is its `fit_range`. `Recipe.schema_name` and
`Recipe.schema_version` are what the document declared, and
`Recipe.phase_names` is the recipe's own key per phase, in order, which is what
the output file names use.

`Recipe.diagnostics` is the eighth thing and the one to read. Every field
dropped, every convention assumed and every value re-seeded goes down it, and a
caller that ignores it is not being told what was changed:

<!-- api-doc: no-exec — it continues the read above -->

```python
for d in recipe.diagnostics:
    print(d.level, d.code, d.message)
```

`read_recipe` also takes `diagnostics=` — the same opt-in list `read_pattern`
takes — for a caller accumulating across several reads.

## What is refused, and why each

A recipe this package cannot represent raises `RecipeError`, a `ValueError`,
naming the field. That is upstream's own rule for an engine: reject loudly, and
never silently ignore a refine flag.

| Refused | Because |
|---|---|
| `schema_name` other than `GSASII_Rietveld` | `GSASII_SPF` is single-peak fitting, which is {ref}`fit_peaks <fitting-peaks-you-name>` here and not a recipe: it refines nothing |
| `Type` other than `PXC` | every other type puts something that is not 2θ on the x axis |
| a `size_broadening` or `strain_broadening` `model` other than `isotropic` | PowderLine itself raises `NotImplementedError` for these |
| a non-zero `Zero` | see below |
| a non-zero `Z` | this package's Lorentzian width is X/cosθ + Y·tanθ, with no constant term |
| a negative `W`, `X` or `Y` | those are softplus-bounded at zero here; reading one would silently give ≈0 rather than the declared value |
| a background peak whose Lorentzian γ exceeds one 2θ step | `BackgroundPeak` is a Gaussian, deliberately |
| an `Uaniso` atom | anisotropic displacement through a recipe is not read yet |
| a top-level `single_peaks` block with any live entry | free-standing peaks are not part of a refinement here; {ref}`fit_peaks <fitting-peaks-you-name>` fits them on their own |

**`Zero` is the interesting one.** PowderLine states its unit twice and the two
statements disagree: its easydiffraction engine converts `Zero` as
centidegrees, its config loader annotates it "degrees 2theta". The readings
differ by 100×, which is a wrong cell rather than a slightly wrong one, and no
committed recipe carries a non-zero `Zero` to settle it. So a non-zero one is
refused rather than guessed at — the same rule that governs a CIF whose cell
angle contradicts its space group ([](data.md)): where two statements
contradict each other, choosing is the caller's.

A **fixed** value the model reaches its identity at is dropped instead, with a
diagnostic naming it. `Z = 0` is no constant Lorentzian; a background peak's γ
below one channel is a width the data cannot hold. That split — a fixed
identity is a report, a live value is a contradiction — is the reader-repair
rule of [](data.md) applied one format over.

## The conventions, and how each was fixed

Every unit conversion was measured against the reference output PowderLine
commits beside its own recipes, then corroborated against upstream's second
engine. The full table with the measurements is `tests/data/README.md`; the
rows that change an answer:

| Recipe field | Unit | Becomes |
|---|---|---|
| `U`, `V`, `W` | centideg² Gaussian **variance** | `instrument.profile.u/v/w` × 8 ln2 × 10⁻⁴ |
| `X`, `Y` | centideg Lorentzian **FWHM** | `instrument.profile.x/y` × 10⁻² |
| `isotropic_size` | µm | `phases.*.lor_size` and `phases.*.gauss_size`, split by `LG_eta` |
| `isotropic_strain` | 10⁻⁶ Δd/d | `phases.*.lor_strain` and `phases.*.gauss_strain`, likewise |
| `SH/L` | (S+H)/L | `axial_sl` = `axial_hl` = SH/L ÷ 2 |
| `Uiso` | Å² | `biso` = 8π²·Uiso |
| `Itth_weights` | 1/σ² | `PatternData.sigma` = 1/√w |
| `fit_range` | °2θ, inclusive both ends | `Recipe.limits` |

GSAS-II carries one magnitude per broadening effect plus a Lorentzian share
`LG_eta`; this package carries a Lorentzian and a Gaussian parameter per effect
and no share. So the translation is a split, not a rename: η of the magnitude
becomes the Lorentzian coefficient and (1 − η) the Gaussian one. At η = 1 the
Gaussian half is exactly zero, where a softplus parameter's gradient is its own
value and the optimiser cannot move it — so that half is **held rather than
declared free**, with a warning saying the fit runs one parameter short of the
reference engine's.

Two numbers are deliberately not carried across. The Chebyshev **coefficients**
are re-seeded from zero, because the two codes scale the polynomial's domain
differently and the numbers are not the same numbers; only the term count and
the refine flag survive. The phase **scale** is re-seeded to match the summed
calculated intensity to the data, because a scale factor's normalisation is
each code's own — on the committed fixtures GSAS-II and TOPAS converge four
orders of magnitude apart for the same specimen.

## The plan is a route, not a transcription

PowderLine runs one pass over everything flagged. Translating that as a single
stage is faithful and it does not work from a cold start: on the two-phase
fixture it walked a monoclinic cell to a = 4231 Å.

So `Recipe.plan` frees the recipe's parameters over several stages in the
McCusker turn-on order of [](refining.md). Staging here is **cumulative** —
every stage keeps what the earlier ones freed — so the last stage is exactly
the recipe's single pass over everything flagged, reached by a route that
survives a cold start. The set of free parameters at the end is the recipe's;
only the order is this engine's, and the order is the engine's business.

## The four tables

`write_recipe_tables` takes the `Refinement`, not its result: a result carries
the fitted curve but not the compiled model, and the peak list needs the
per-reflection widths and |F|². It writes

- `refined_parameters.csv` — one row per refined parameter, with its esd;
- `<phase>_unit_cell_report.csv` — one per phase;
- `<phase>_peak_list_report.csv` — one per phase;
- `fit_profile.txt` — the fitted channels, tab separated.

Three of those four headers are a real contract and one is not. GSAS-II and
TOPAS write byte-identical headers for the first two and the profile, and
**different** ones for the peak list — 15 columns against 11, sharing nine. So
the first three are reproduced byte for byte and the peak list carries the
columns this package can honestly fill. `F_obs_squared` is not among them: an
observed |F|² from a Rietveld fit is I(calc) times the reflection's own
obs/calc ratio, so it flatters whatever model partitioned it ([](results.md)),
and an absent column beats a flattering one.

An esd column is empty where nothing computed the number and `0` where the
parameter is held — the two are different statements and this package does not
collapse them. `cell_volume` is the one empty esd today: propagating it needs
the cell block's covariance through dV/d(a,b,c,α,β,γ), which nothing here does
yet.

:::{admonition} For agents
:class: agent
This is a **pipeline** surface, not an agent one. There is one integration
surface for an agent and it is the python API ([](agents.md)); a recipe earns
its place only because running one specimen through several engines and
comparing is a job no python API can do for a code it cannot import. If you are
choosing, choose `Refinement.fit`.

Read `Recipe.diagnostics` before the answer. Roughly a dozen codes can fire,
all prefixed `RECIPE_`, and several of them mean the fit you are about to run
differs from the reference engine's in a stated way — a dropped refine flag, a
declined engine default, a degenerate background peak. A `RecipeError` names
the field and says what to do instead.
:::

## What the fixtures are worth

Two complete cross-engine fixtures are committed under
`tests/data/powderline/`: each is one pattern refined by **two** independent
engines with both outputs in the repository. That is a cross-code consistency
check with a second opinion attached, and the second opinion disagrees.

On the two-phase cathode the two references differ by **2665 ppm** on the cubic
cell, because the recipe co-refines size and strain on a pattern where GSAS-II
itself reports two SVD singularities and a 100 % correlation; it returns a
negative crystallite size for one phase, and TOPAS returns none at all. This
package lands 11–93 ppm from TOPAS on all five free cell parameters, at Rwp
7.333 % against TOPAS's 7.326 %, while sitting the same 1004–2575 ppm from
GSAS-II that TOPAS does.

Read that as the calibration for any cross-code claim made through this format:
**the cells are the comparable quantity across engines and the broadening
coefficients are not.** `tests/data/README.md` has the numbers and
`tests/test_acceptance_powderline.py` asserts them.
