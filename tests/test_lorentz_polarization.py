"""The Lorentz-polarisation factor against its published closed forms.

Klug & Alexander (1974), *X-ray Diffraction Procedures*, 2nd ed., Wiley, and
International Tables for Crystallography Vol. C § 6.2: the powder Lorentz
factor is 1/(sin²θ cosθ) and an unpolarised beam's polarisation factor is
(1 + cos²2θ)/2.  ``polarization`` K in :func:`lorentz_polarization` is the
σ-polarised fraction, so K = 0.5 is the unpolarised classic form and K = 1
leaves the Lorentz part alone.  The expressions below are written out here from
those references, not imported from the package.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.model.corrections import lorentz_polarization

TWO_THETA = np.array([10.0, 26.6, 40.0, 60.0, 90.0, 140.0])


def _theta(two_theta):
    return np.radians(two_theta) / 2.0


def test_the_factor_matches_the_published_form_at_both_polarisations() -> None:
    """K = 0.5 is Klug and Alexander's unpolarised form; K = 1 is the Lorentz part.

    The positive arm: a factor with the wrong cos² weight (cos2θ in place of
    cos²2θ) fails the same bar, so it can see a wrong polarisation term.
    """
    th = _theta(TWO_THETA)
    lorentz = 1.0 / (np.sin(th) ** 2 * np.cos(th))
    unpolarised = (1.0 + np.cos(2 * th) ** 2) / 2.0 * lorentz
    np.testing.assert_allclose(lorentz_polarization(TWO_THETA, 0.5),
                               unpolarised, rtol=1e-14)
    np.testing.assert_allclose(lorentz_polarization(TWO_THETA, 1.0),
                               lorentz, rtol=1e-14)
    wrong = (1.0 + np.cos(2 * th)) / 2.0 * lorentz
    assert not np.allclose(wrong, unpolarised, rtol=1e-3)
    with pytest.raises(AssertionError):
        np.testing.assert_allclose(lorentz_polarization(TWO_THETA, 0.5),
                                   wrong, rtol=1e-14)
