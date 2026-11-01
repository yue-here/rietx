# Validation against other codes

This page lists each comparison of rietx with another program, the protocol it used and how far the two agreed.
A section at the end gives the comparisons with a certificate or a weighed composition.

Every row is a test in the repository.
The [validation matrix](https://github.com/yue-here/rietx/blob/main/docs/VALIDATION.md) lists the rows on measured data, with every comparison against a certificate or against rietx's own results.
The texture and calculated-pattern rows compare calculated data, and their tests sit outside the matrix.

| Comparison | Other code | Data | Agreement |
| --- | --- | --- | --- |
| [Fluorapatite](#fluorapatite-against-gsas) | GSAS | Cu Kα, laboratory | cell +84 and +84 ppm; Rwp 9.28 % against 10.05 % |
| [LaB<sub>6</sub> and cBN](#lab6-and-cbn-against-topas) | TOPAS | synchrotron, APS 11-BM | cBN cell +17 ppm; LaB<sub>6</sub> fraction 0.38 esd outside TOPAS's interval |
| [Two cathode phases](#two-phases-against-topas-and-gsas-ii) | TOPAS and GSAS-II | synchrotron, NSLS-II 28-ID-1 | within 96 ppm of TOPAS, where the two codes differ by 2668 ppm |
| [Silicon](#silicon-against-xnd) | XND | synchrotron, APS 11-BM | wavelength −11 ppm from XND |
| [One specimen, two radiations](#one-specimen-two-radiations) | published refinement | synchrotron X-ray and neutron | cell +57 ppm |
| [Spherical-harmonic texture](#spherical-harmonic-texture-against-gsas-ii) | GSAS-II 5.8.4 | calculated | 16 settings, within 2×10<sup>−6</sup> |
| [Calculated patterns](#calculated-patterns-against-topas-6) | TOPAS 6 | calculated | seven inputs, within 1 % of the largest intensity |

## How a comparison is made

A comparison with another code holds only when rietx runs under that code's protocol.
That means the same refined parameters, the same held parameters, the same excluded regions and the same weights.
The fluorapatite, LaB<sub>6</sub> and cBN, and silicon tests check that rietx fitted the same channels as the other code before they compare any other number.

A protocol guessed from the other code's output does not work.
In version 0.2, fluorapatite under a guessed protocol gave Rwp 16 % and a cell 390 ppm from GSAS's.
The same version under the mirrored protocol gave 9.73 % and 116 ppm.
Later versions moved the mirrored result to the figures in the table above.

Where two codes disagree with each other, the bar is the span between them.
A second code reproduces the first only as far as the two codes' own models allow.

The tables report Rwp beside the other code's figure.
No test fails on a gap in Rwp.
Rwp depends on the peak shape and the weights as much as on the structure, so it cannot say which code's cell is the better one.

## Fluorapatite against GSAS

The reference is GSAS's converged refinement of fluorapatite, `FAP.EXP`, from the GSAS-II `LabData` tutorial.
rietx reads the file's refine flags and the 5750 channels left after its excluded region.
The Gaussian terms GU, GV and GW are held, and read as the variances GSAS states them as.

| Quantity | rietx | GSAS |
| --- | --- | --- |
| Rwp | 0.0928 | 0.1005 |
| Rp | 0.0714 | 0.0766 |
| Cell *a* | +84 ppm from GSAS | 9.371724(36) Å |
| Cell *c* | +84 ppm from GSAS | 6.885867(37) Å |
| Lorentzian size term | 0.0323° | LX 0.0335° |

The offsets on the two axes differ by 6.3×10<sup>−7</sup> in relative terms, against a bar of 10<sup>−4</sup>.
An offset equal on both axes is a difference in the d-scale convention, and a structural difference would not be equal.
The test allows 300 ppm on the cell and 10 % on the R-factors.

rietx's `stderr` carries the Bérar–Lelann factor, 2.16 on this fit, and GSAS's esds do not.
`stderr_uncorrected` leaves the factor out.
It is 4.1×10<sup>−5</sup> Å on *a* and 3.8×10<sup>−5</sup> Å on *c*, against GSAS's 3.6×10<sup>−5</sup> and 3.7×10<sup>−5</sup> Å, measured on the 1.10.0 tree.
No test compares the esds.

GSAS's file frees 28 parameters, and the plan used here frees 20.
The plan leaves out the 12 coordinate parameters.
It frees the axial divergence, which GSAS held, and a six-term Chebyshev background where GSAS refined a three-term reciprocal expansion.
That accounts for the four extra.
Freeing the coordinates as well moved Rwp from 0.092498 to 0.092314 and the cell by less than 1 ppm, measured on 2026-10-08.
The page [Names in other programs](../reference/foreign-names.md) maps the parameters one to one.

## LaB6 and cBN against TOPAS

The specimen is NIST SRM 660b LaB<sub>6</sub> mixed with cubic BN, measured at APS 11-BM.
The reference is TOPAS's two shipped models of the same histogram.
LaB<sub>6</sub>'s certified cell is held, so that the cBN cell is measured against it.

The protocol check comes first.
Rexp is 0.0529335 in rietx and 0.0529264 in TOPAS, a relative difference of 1.3×10<sup>−4</sup>.
Both codes fitted 44 895 of the file's 49 496 channels, with the weights from the file's own esd column.

| Quantity | rietx | TOPAS |
| --- | --- | --- |
| cBN cell *a* | 3.616521(17) Å | 3.616463 and 3.616466 Å |
| LaB<sub>6</sub> boron *x* | 0.19836 | 0.19890 |
| LaB<sub>6</sub> weight fraction | 17.787 ± 0.319 wt % | 17.907 and 17.950 wt % |
| Rwp | 0.1686 | 0.0810 |

The cBN cell is 17 ppm from TOPAS.
The two TOPAS models are 0.8 ppm apart, and the test allows 50 ppm.
The boron coordinate is 5.4×10<sup>−4</sup> from TOPAS, inside the fit's own esd of 2.3×10<sup>−3</sup>.
The LaB<sub>6</sub> fraction is 0.120 wt % outside the interval TOPAS's two models span, which is 0.38 of its own esd.

The Rwp gap is a profile-shape difference.
TOPAS fits a Pearson VII peak with six free shape parameters, and rietx has no Pearson VII.
88 % of χ² sits in the 11 % of channels where the calculated Bragg part is more than half the total, so the gap is at the peak tops.
A lower Rwp is not a better answer on this specimen.
Freeing each phase's Lorentzian terms beside the instrument's reaches Rwp 0.1377 and moves the LaB<sub>6</sub> fraction to 16.779 wt %, 5.8 esd outside TOPAS's interval.
The instrument and the phases then split one broadening three ways, and the data cannot tell the split apart.
In 1.9.0 the correlation between a phase's Lorentzian strain and the instrument's Y read −1.000.
rietx now holds the instrument's X and Y while a phase's matching Lorentzian term is free, so what stays free is each phase's width relative to the other's.
That freedom alone still lowers Rwp and moves the fraction.

## Two phases against TOPAS and GSAS-II

The specimen is a disordered rock-salt cathode with Li<sub>4</sub>MgWO<sub>6</sub>, measured at NSLS-II 28-ID-1 and set up as a PowderLine recipe.
Two codes' refinements of it are committed with the recipe, and they disagree.
They differ by 2668 ppm on the cubic cell and by 386 to 1770 ppm on the four free parameters of the monoclinic phase.
GSAS-II reports its own fit singular and returns a negative crystallite size for the first phase.

The bar is the span the two codes leave, widened by 300 ppm at each end.
rietx lands inside the span for every free cell parameter.
Its worst deviation from TOPAS is 96 ppm, against 2668 ppm between the two codes.

| | rietx | TOPAS | GSAS-II |
| --- | --- | --- | --- |
| Rwp | 7.322 % | 7.326 % | 10.83 % |

The phase-scale ratio agrees with TOPAS's within 20 %.
That bar is the ratio's own dependence on the size and strain valley both codes reported singular.
The absolute scales are not compared, because each code normalises its own.

A second recipe holds the cell of SRM 660c LaB<sub>6</sub> at its certificate value and fits only the instrument profile.
The held cell comes back exactly as stated, as it does in both codes.
rietx's peak widths match the width of GSAS-II's own calculated profile within 5 %, with a median of 0.5 % and a worst case of 1.0 % on the first ten reflections.
The test compares widths.
The coefficients cannot agree, because GSAS-II's model carries a constant Lorentzian term that rietx has not, and a negative Y that GSAS-II clamps on 26 of its 49 reflections.

| | rietx | TOPAS | GSAS-II |
| --- | --- | --- | --- |
| Rwp | 8.410 % | 8.519 % | 6.53 % |

rietx names three differences from the recipe when it reads it: `RECIPE_FLAG_DROPPED`, `RECIPE_ENGINE_DEFAULT_DECLINED` and `RECIPE_BACKGROUND_PEAK_DEGENERATE`.
The recipe also declares a background peak wider than its fitted range.
GSAS-II lets it run to 8.77×10<sup>10</sup>° with an esd of 0, and TOPAS holds it at 1.63° with an esd 188 times its value.
rietx reports it correlated with the background at |ρ| = 1.

## Silicon against XND

The specimen is NIST SRM 640c silicon at APS 11-BM, with the cell held at its certificate value and the wavelength refined.
The reference is XND 1.42.

| Quantity | rietx | XND |
| --- | --- | --- |
| Wavelength, 2–50° | 0.412371546 Å | 0.412376076(379) Å |
| Wavelength, symmetric peaks only | −0.4 ppm from XND | |
| B<sub>iso</sub>(Si) | 0.42188(1897) Å<sup>2</sup> | 0.438984(1711) Å<sup>2</sup> |

Over the full range the wavelengths differ by 11 ppm.
The two codes model the low-angle asymmetry differently, and rietx uses the Finger–Cox–Jephcoat model.
Dropping every channel below the (111) peak, at 7.54°, removes that difference.
The wavelengths then agree to 0.4 ppm.
The silicon displacement parameters are 0.90 combined esd apart, and both codes inflate their esds the same way.

## One specimen, two radiations

The specimen is Nd<sub>2</sub>Ru<sub>2</sub>O<sub>7</sub>, measured with synchrotron X-rays and with neutrons from a Cu(311) monochromator.
The reference is the published combined refinement (Gaultois *et al.*, *Journal of Physics: Condensed Matter* 25, 186004 (2013)), which held the X-ray wavelength and refined the neutron one.
rietx runs the same protocol as a joint fit of the two histograms.

| Quantity | rietx | Published |
| --- | --- | --- |
| Cell *a* | 10.342904(48) Å | 10.342312(8) Å |
| O 48*f* *x* | 0.33001(41) | 0.33012(7) |
| Neutron wavelength | 1.5407972(795) Å | |

The cell is 57 ppm above the published value, and the oxygen coordinate is inside its own esd.
The published refinement also carries 0.5(1) % by mole of RuO<sub>2</sub> and a λ/2 contribution, which rietx does not model.
The neutron wavelength moves 257.9 ppm from its nominal value, which is the same cell disagreement the two histograms show when each is fitted on its own.

## Spherical-harmonic texture against GSAS-II

rietx's spherical-harmonic functions were compared with GSAS-II 5.8.4's for 16 Laue classes and settings, from −1 to m-3m.
Each invariant function equals GSAS-II's up to a normalisation factor, within 2×10<sup>−6</sup>.
GSAS-II computes these functions in single precision.
The texture multiplier agrees through the stated conversion of the coefficients.
GSAS-II's `Bragg` geometry is rietx's `bragg_brentano`.
GSAS-II's `Debye` geometry has no counterpart in rietx.

## Calculated patterns against TOPAS 6

TOPAS 6 was run at zero cycles on seven inputs written by rietx, and its calculated pattern was kept.
The inputs cover NaCl with X-rays, with Sabine extinction and with a P-spline background, NaCl with neutrons, a magnetic child phase, and two neutron rutile cases, one with anisotropic strain and one with every width term.
rietx's `predict` reproduces each calculated pattern within 1 % of the largest intensity.
On the four NaCl cases the largest difference measured was between 0.22 % and 0.26 %.

TOPAS integrates the whole of each Lorentzian tail.
rietx's windows hold 98 % of a peak's area, and that accounts for the difference.
Each test also changes one term of the input and checks that the comparison then fails, so the comparison can see the term it is about.

## Against a certificate or a weighed composition

These tests compare rietx with a known answer and with no other code.

| Comparison | Reference | Agreement |
| --- | --- | --- |
| LaB<sub>6</sub>, NIST SRM 660c, laboratory Cu Kα | the certified cell, recomputed for the measurement's temperature | +24 ppm, inside the test's ±2×10<sup>−4</sup> Å |
| Corundum, NIST SRM 676a, laboratory Cu Kα | the certified a and c | c/a +29 ppm; a and c −314 and −284 ppm |
| Quantitative phase analysis, IUCr CPD round robin, sample 1 | the weighed composition of eight mixtures | worst 5.10 wt %, RMS 2.30 wt %, against the participants' spread of 6.0 wt % on a major phase |

The certificate's own uncertainty on SRM 660c is ±8×10<sup>−6</sup> Å, and rietx does not reach it.
The remaining offset varies as cot θ and sin 2θ, which is the shape of instrument aberrations a fundamental-parameters peak would model.
On corundum the two axes are off by the same fraction, within 3×10<sup>−5</sup> of each other.
An offset equal on both axes is a lab d-scale error, so the ratio c/a is the figure the certificate checks.
The round-robin tolerance is the spread of the published participants' results (Madsen *et al.*, 2001), because the esds of the fractions are several times smaller than the measured errors.

## What has no comparison

These parts of rietx have no comparison with another code.
Nothing here compares rietx's refined numbers with FullProf's, and the [FullProf page](fullprof.md) says what its file readers were checked against.
Le Bail and Pawley fits are checked against rietx's own results.
A magnetic phase's calculated pattern is compared with TOPAS 6 above, but a refined moment is checked only on two tutorial data sets, for the shape of the moment, with no reference value.
Neutron time of flight and a fundamental-parameters peak shape are fenced for a 2.0 series, and the [roadmap](roadmap.md) lists them.
