# Guides

Each guide does one task from start to finish. Its title names the task as "How to …", and the menu names the task alone, since the tab already says it is a guide.

Each guide's fits are a script in `examples/guides/`, run by the test suite, and the output a guide shows is what its script printed.

## Before the fit

- [How to check a pattern before fitting](check.md) reads `rietx.diagnose` and draws the reflection ticks.
- [How to limit the fit range or leave out a region](range.md) sets `two_theta_limits` and `PatternData.excluded_regions`.

## Instrument

- [How to calibrate an instrument on a standard and reuse it](calibrate.md) saves the widths a standard measured and loads them for each sample.

## Background and extra peaks

- [How to use a measured blank as the background](blank.md) holds an empty-container scan under the pattern with `BackgroundFixedPlusChebyshev`.
- [How to add a hump to the background](hump.md) declares a broad Gaussian for amorphous or container scattering.
- [How to fit a peak from the sample holder](holder.md) declares a sharp line no phase explains with a `PeakComponent`.

## Constraints and plans

- [How to keep a parameter fixed whatever the plan frees](hold.md) uses `Refinement.hold`.
- [How to tie parameters together](tie.md) makes parameters equal, or one a linear function of others.
- [How to restrain a bond length or an angle](restrain.md) adds chemistry as weighted observations.
- [How to add a stage to a refinement plan](plan.md) edits a preset or builds a plan.

## Running a fit

- [How to run a plan one stage at a time](stage.md) uses `Refinement.run_stage` and a report at each stage.
- [How to choose the next parameter to free](next.md) reads `Refinement.suggest` and measures the move with `compare_freed`.
- [How to branch a refinement, compare the branches and roll back](branch.md) uses `Refinement.branch`, `RefinementTree.compare` and `Refinement.checkout`.
- [How to watch or stop a running fit](watch.md) uses `rietx watch`, a cancel token, and the switches that turn recording off.

## Results

- [How to find the weight fraction of each phase in a mixture](qpa.md) reads `result.qpa`, checks a minor phase, and corrects for microabsorption.
- [How to quote lattice parameters with their esds](cell.md) reads the cell, its volume and `rx.format_su`, and shows what the esd leaves out.
- [How to quote a parameter that ended on its bound](interval.md) uses `Refinement.profile_interval`.
- [How to export the refined structure as a CIF and the reflection list as a table](export.md) uses `Refinement.write_cif` and `Refinement.write_reflection_table`.

## Other programs

- [How to open a GSAS, TOPAS or FullProf refinement and write one back](foreign.md) uses `rx.read_project_model` and the four writers.

## Series

- [How to fit a temperature series](series.md) chains one refinement per pattern with `refine_sequential` and reads a trajectory.
- [How to check a series for path dependence](path.md) runs the chain both ways and refits a flagged step from cold.
- [How to refine a cell edge as a function of temperature](equation.md) refines an equation's coefficients against every pattern at once.

## Magnetic structures

- [How to refit the nuclear model with the moment present](moment.md) takes the nuclear model from a pattern above the ordering temperature, or refits it with the moment in, and reads the moment after.

## Several radiations

- [How to fit an X-ray and a neutron pattern together](joint.md) refines one structure against both with `MultiHistogramRefinement`, and refines the neutron wavelength.

```{toctree}
:hidden:

Check a pattern before fitting <check>
Limit the fit range or leave out a region <range>
Calibrate an instrument on a standard and reuse it <calibrate>
Use a measured blank as the background <blank>
Add a hump to the background <hump>
Fit a peak from the sample holder <holder>
Keep a parameter fixed whatever the plan frees <hold>
Tie parameters together <tie>
Restrain a bond length or an angle <restrain>
Add a stage to a refinement plan <plan>
Run a plan one stage at a time <stage>
Choose the next parameter to free <next>
Branch a refinement, compare the branches and roll back <branch>
Watch or stop a running fit <watch>
Find the weight fraction of each phase in a mixture <qpa>
Quote lattice parameters with their esds <cell>
Quote a parameter that ended on its bound <interval>
Export the refined structure as a CIF and the reflection list as a table <export>
Open a GSAS, TOPAS or FullProf refinement and write one back <foreign>
Fit a temperature series <series>
Check a series for path dependence <path>
Refine a cell edge as a function of temperature <equation>
Fit an X-ray and a neutron pattern together <joint>
Refit the nuclear model with the moment present <moment>
```
