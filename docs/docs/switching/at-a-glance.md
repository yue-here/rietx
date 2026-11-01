# rietx at a glance

This page says which data rietx fits, what it calculates, and what each feature has been checked against.

A row without a comparison with another code says so, and gives what it was checked against instead.
The [validation page](validation.md) has the numbers behind each link.

## Data rietx fits

rietx fits powder patterns measured with X-rays or with constant-wavelength neutrons.
Each instrument preset sets the geometry and the radiation:

| Preset | Instrument |
| --- | --- |
| `Instrument.bragg_brentano` | laboratory X-ray, flat plate |
| `Instrument.debye_scherrer` | X-ray in a capillary, including synchrotron |
| `Instrument.flat_plate_transmission` | X-ray, flat plate in transmission |
| `Instrument.constant_wavelength_neutron` | neutron, one wavelength |

A joint fit refines several patterns of one specimen together, such as a synchrotron pattern and a neutron one.
The structure is shared, and each pattern keeps its own instrument, wavelength and background.
A joint fit shares the crystallite size and scales each pattern's width in degrees by its wavelength.

`refine_sequential` fits a series of patterns one after another, each starting from the last answer.
[About a fit](../concepts/fit.md) follows one fit through its stages.

Neutron time of flight is not refined.
`Instrument.tof_neutron_bank` builds a bank and the readers open one, and a time-of-flight fit is refused by name.
The [roadmap](roadmap.md) lists it among the work fenced for a 2.0 series.

## Features and what they were checked against

| Feature | What rietx has | Checked against | Read more |
| --- | --- | --- | --- |
| Rietveld, laboratory X-ray | flat-plate, capillary and transmission geometry, with the Kα doublet | GSAS on [fluorapatite](validation.md#fluorapatite-against-gsas), a flat plate; the NIST [certificates](validation.md#against-a-certificate-or-a-weighed-composition) of LaB<sub>6</sub> and corundum | [About a fit](../concepts/fit.md), [calibrating an instrument](../guides/calibrate.md) |
| Rietveld, synchrotron X-ray | multi-phase fits and a refinable wavelength | TOPAS on [LaB6 and cBN](validation.md#lab6-and-cbn-against-topas), TOPAS and GSAS-II on [two phases](validation.md#two-phases-against-topas-and-gsas-ii), XND on [silicon](validation.md#silicon-against-xnd) | [About a fit](../concepts/fit.md) |
| Rietveld, constant-wavelength neutron | the same model with neutron scattering lengths | a [published refinement](validation.md#one-specimen-two-radiations), and TOPAS 6 on [calculated patterns](validation.md#calculated-patterns-against-topas-6) | [About a fit](../concepts/fit.md) |
| Joint fit of several patterns | one structure, one instrument per pattern, a refinable wavelength | the [published combined refinement](validation.md#one-specimen-two-radiations) of one specimen | [Fitting an X-ray and a neutron pattern together](../guides/joint.md), [joint refinement](../reference/joint.md) |
| Le Bail and Pawley | intensities refined per reflection, atoms held | rietx's own Rietveld results, since no other code was compared | [About a fit](../concepts/fit.md) |
| Peak shape and axial divergence | pseudo-Voigt (TCHZ) and Voigt, with Finger–Cox–Jephcoat axial divergence | TOPAS 6, on [calculated patterns](validation.md#calculated-patterns-against-topas-6) with the pseudo-Voigt | [About parameters](../concepts/parameters.md), [calibrating an instrument](../guides/calibrate.md) |
| Anisotropic strain | Stephens's model, with the allowed terms derived from the space group | TOPAS 6, on [calculated patterns](validation.md#calculated-patterns-against-topas-6) | [About parameters](../concepts/parameters.md) |
| Background | Chebyshev, P-spline and declared humps | TOPAS 6, on [calculated patterns](validation.md#calculated-patterns-against-topas-6) with Chebyshev and P-spline backgrounds | [About parameters](../concepts/parameters.md#background), [adding a hump](../guides/hump.md) |
| Extinction | Sabine extinction | TOPAS 6, on [calculated patterns](validation.md#calculated-patterns-against-topas-6) | [Parameter map](../reference/parameters.md) |
| Texture | March–Dollase and spherical harmonics | spherical harmonics against [GSAS-II](validation.md#spherical-harmonic-texture-against-gsas-ii) | [Parameter map](../reference/parameters.md) |
| Phase fractions | weight fractions with esds | the weighed compositions of the IUCr [round robin](validation.md#against-a-certificate-or-a-weighed-composition), and TOPAS on [LaB6 and cBN](validation.md#lab6-and-cbn-against-topas) | [Finding each phase's weight fraction](../guides/qpa.md), [about correlations and esds](../concepts/correlations.md) |
| Files from other programs | TOPAS `.inp`, FullProf `.pcr` and GSAS `.EXP` read in with their refine flags, and GSAS-II `.gpx` read in | the free set GSAS states in `FAP.EXP`, [rebuilt exactly](validation.md#fluorapatite-against-gsas) | [Opening another program's refinement](../guides/foreign.md), [names in other programs](../reference/foreign-names.md) |

Magnetic structures are in development.
The pattern rietx calculates for a magnetic phase matches TOPAS 6's on one [calculated pattern](validation.md#calculated-patterns-against-topas-6).
A refined moment has no comparison with another code yet.
The [roadmap](roadmap.md) lists the work.

## What the report adds

Beside Rwp and the table of refined values, rietx returns a report of where the fit misses the data and what that misfit looks like, and a list of diagnostics.
A diagnostic names a parameter that sits on a bound, two parameters the data cannot separate, or a phase the data cannot see.
[About the report](../concepts/report.md) describes the three layers.
Each refinement stage is also kept as a node in a history, so a stage can be restored and the plan forked.
