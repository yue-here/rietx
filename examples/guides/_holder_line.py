"""A synthetic sample-holder line, added to a real pattern for `docs/docs/guides/holder.md`.

No pattern rietx ships has a holder line, so this adds one: the 110
reflection of a ferritic steel (body-centred iron, a ≈ 2.866 Å), at the
apparent 2θ a holder sitting off the focusing circle might give it. The line is
a pseudo-Voigt with its Cu Kα2 image at half the area, and its counts carry
Poisson noise from a fixed seed. FAP.XRA has no esd column, so the fit's
weights follow the new counts by themselves.

The guide script skips this file by its leading underscore.
"""

import numpy as np

#: the line as made: apparent centre of the Kα1 image (°2θ), area (counts·°),
#: FWHM (°2θ) and Lorentzian fraction.
CENTER, AREA, FWHM, ETA = 44.65, 60.0, 0.12, 0.5
KA1, KA2 = 1.5405929, 1.5444274


def _pseudo_voigt(x, center):
    u = (x - center) / FWHM
    gauss = np.sqrt(4 * np.log(2) / np.pi) / FWHM * np.exp(-4 * np.log(2) * u**2)
    lorentz = 2 / (np.pi * FWHM) / (1 + 4 * u**2)
    return AREA * (ETA * lorentz + (1 - ETA) * gauss)


def with_holder_line(pattern, seed=1):
    """A copy of `pattern` with the steel line's counts added."""
    two_theta = np.asarray(pattern.two_theta)
    d = KA1 / (2 * np.sin(np.radians(CENTER / 2)))
    center_ka2 = 2 * np.degrees(np.arcsin(KA2 / (2 * d)))
    line = _pseudo_voigt(two_theta, CENTER) + 0.5 * _pseudo_voigt(two_theta, center_ka2)
    counts = np.asarray(pattern.intensity) + np.random.default_rng(seed).poisson(line)
    # assigned rather than passed to `model_copy(update=)`, which validates
    # nothing, so the schema's checks run on the new counts
    noisy = pattern.model_copy()
    noisy.intensity = counts.tolist()
    return noisy
