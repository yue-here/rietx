"""A synthetic X-ray and neutron pair of one corundum specimen, for `docs/docs/guides/joint.md`.

No pattern rietx ships pairs two radiations on one specimen, so this makes
them, as `tests/test_joint_xray_neutron.py` does: a Cu Kα1 capillary pattern
(15-120°, 2·10⁴ counts at the strongest peak, zero shift +0.01°) and a
constant-wavelength neutron pattern (10-150°, 5·10³ counts, zero shift
−0.03°), each with Poisson noise from a fixed seed. Corundum ranks its two
sites oppositely under the two radiations: f(0) is 13 electrons for Al and 8
for O, while b is 3.449 fm for Al and 5.803 fm for O.

The neutron pattern is computed at `NEUTRON_TRUE`, 300 ppm longer than the
`LAM_N` its instrument declares, as a monochromator calibration error.

The guide script skips this file by its leading underscore.
"""

import numpy as np

import rietx as rx

LAM_X, LAM_N = 1.5406, 2.0780     # Å, as declared
NEUTRON_TRUE = LAM_N * (1 + 300e-6)  # Å, as measured
CELL = (4.758877, 12.992880)       # Å, a and c
#: the structure both patterns are computed from
TRUTH = {"phases.0.atoms.0.z": 0.35216, "phases.0.atoms.1.x": 0.30642,
         "phases.0.atoms.0.biso": 0.30, "phases.0.atoms.1.biso": 0.35}


def corundum(z_al=0.3530, x_o=0.3050, biso_al=0.6, biso_o=0.7):
    """Corundum, by default started off the truth in every coordinate and Biso."""
    a, c = CELL
    return rx.Structure(phases=[rx.Phase(
        name="Al2O3", space_group="R -3 c :H",
        cell=rx.Cell(a=rx.Parameter(value=a), b=rx.Parameter(value=a), c=rx.Parameter(value=c),
                     alpha=rx.Parameter(value=90.0), beta=rx.Parameter(value=90.0),
                     gamma=rx.Parameter(value=120.0)),
        scale=rx.Parameter(value=1.0, min=0.0),
        atoms=[rx.Atom(label="Al", species="Al", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=z_al),
                       biso=rx.Parameter(value=biso_al, min=0.0, max=5.0)),
               rx.Atom(label="O", species="O", x=rx.Parameter(value=x_o),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.25),
                       biso=rx.Parameter(value=biso_o, min=0.0, max=5.0))])])


def _measure(instrument, two_theta, peak, seed, zero):
    instrument.zero_shift.value = zero
    truth = corundum(*TRUTH.values())
    truth.phases[0].scale.value = peak / rx.Refinement(truth, instrument).predict(two_theta).max()
    counts = rx.Refinement(truth, instrument).predict(two_theta) + 50.0
    noisy = np.random.default_rng(seed).poisson(counts).astype(float)
    return rx.PatternData(two_theta=two_theta, intensity=noisy)


def xray_pattern():
    return _measure(rx.Instrument.debye_scherrer(wavelength=LAM_X),
                    np.arange(15, 120, 0.02), 2e4, seed=1, zero=0.01)


def neutron_pattern():
    return _measure(rx.Instrument.constant_wavelength_neutron(NEUTRON_TRUE, fwhm_deg=0.3),
                    np.arange(10, 150, 0.05), 5e3, seed=11, zero=-0.03)
