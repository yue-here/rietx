"""Synthetic standards and samples for `docs/docs/guides/calibrate.md`, on two lab setups.

No pattern rietx ships pairs a line-profile standard with a sample from the
same diffractometer, so this makes them: LaB6 as the standard and CeO2 as the
sample, each computed with `Refinement.predict` on a Cu Kα Bragg-Brentano
instrument and given Poisson counts from a fixed seed. The sample has a
Lorentzian crystallite size and microstrain and no Gaussian broadening.

`SETUPS` holds the two instruments' Caglioti U, V, W and Lorentzian X, Y. The
second has twice the first's W and X. Both have the same axial divergence:
S/L = `AXIAL_SL`, and H/L = `AXIAL_HL`, a 3 mm receiving slit on a 200 mm
goniometer. Tutorial 04 builds a pair like the first, with no axial divergence,
step by step.

The guide script skips this file by its leading underscore.
"""

import numpy as np

import rietx as rx
from rietx.model.profiles.caglioti import (
    size_coefficient_for_size,
    strain_coefficient_for_microstrain,
)

SETUPS = {"first": (0.004, -0.003, 0.003, 0.015, 0.02),
          "second": (0.004, -0.003, 0.006, 0.030, 0.02)}
AXIAL_SL, AXIAL_HL = 0.025, 0.015
TRUE_SIZE = 300.0     # Å, the sample's coherent domain size
TRUE_STRAIN = 1.0e-3  # Δd/d
TWO_THETA = np.arange(15, 130, 0.015)


def _cubic(name, space_group, a, sites):
    edge, right = rx.Parameter(value=a), rx.Parameter(value=90.0)
    return rx.Structure(phases=[rx.Phase(
        name=name, space_group=space_group,
        cell=rx.Cell(a=edge, b=edge, c=edge, alpha=right, beta=right, gamma=right),
        scale=rx.Parameter(value=1.0, min=0.0),
        atoms=[rx.Atom(label=label, species=species, x=rx.Parameter(value=x),
                       y=rx.Parameter(value=y), z=rx.Parameter(value=z),
                       biso=rx.Parameter(value=biso, min=0.0))
               for label, species, x, y, z, biso in sites])])


def lab6():
    """LaB6 at a = 4.15689 Å, the cell tutorial 04 uses."""
    return _cubic("LaB6", "P m -3 m", 4.15689,
                  [("La1", "La", 0, 0, 0, 0.25), ("B1", "B", 0.1996, 0.5, 0.5, 0.35)])


def ceo2():
    return _cubic("CeO2", "F m -3 m", 5.411,
                  [("Ce1", "Ce", 0, 0, 0, 0.3), ("O1", "O", 0.25, 0.25, 0.25, 0.6)])


def _instrument(setup):
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    for name, value in zip("uvwxy", SETUPS[setup]):
        getattr(instrument.profile, name).value = value
    instrument.zero_shift.value = 0.02
    instrument.geometry.axial_sl.value = AXIAL_SL
    instrument.geometry.axial_hl.value = AXIAL_HL
    instrument.background = rx.BackgroundChebyshev.with_terms(1)
    instrument.background.coefficients[0].value = 150.0
    return instrument


def _measure(structure, instrument, seed):
    counts = rx.Refinement(structure, instrument).predict(TWO_THETA)
    noisy = np.random.default_rng(seed).poisson(counts).astype(float)
    return rx.PatternData(two_theta=TWO_THETA, intensity=noisy)


def standard(setup):
    """The LaB6 standard measured on `setup`, strongest peak near 30 000 counts."""
    truth = lab6()
    truth.phases[0].scale.value = 0.006
    return _measure(truth, _instrument(setup), seed=list(SETUPS).index(setup))


def sample(setup):
    """The CeO2 sample measured on `setup`, with `TRUE_SIZE` and `TRUE_STRAIN`."""
    instrument = _instrument(setup)
    wavelength = max(line.wavelength.value for line in instrument.source.lines)
    truth = ceo2()
    phase = truth.phases[0]
    phase.scale.value = 0.0016
    phase.lor_size.value = size_coefficient_for_size(TRUE_SIZE, wavelength)
    phase.lor_strain.value = strain_coefficient_for_microstrain(TRUE_STRAIN)
    return _measure(truth, instrument, seed=10 + list(SETUPS).index(setup))
