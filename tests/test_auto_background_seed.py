"""``auto_background(seed=True)``: the opt-in start of #725 (the default is unchanged)."""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.background.auto import AUTO_BACKGROUND_SEED_PERCENTILE

P = rx.Parameter


def _phase(scale: float) -> rx.Phase:
    cell = rx.Cell(a=P(value=5.74), b=P(value=7.69), c=P(value=5.54),
                   alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0))

    def atom(label, species, x, y, z, b):
        return rx.Atom(label=label, species=species, x=P(value=x), y=P(value=y),
                       z=P(value=z), biso=P(value=b))

    return rx.Phase(
        name="pv", space_group="P n m a", cell=cell, scale=P(value=scale),
        atoms=[atom("La", "La", 0.0505, 0.25, 0.9945, 0.5),
               atom("Mn", "Mn", 0.0, 0.0, 0.5, 0.4),
               atom("O1", "O", 0.4876, 0.25, 0.0804, 0.6),
               atom("O2", "O", 0.2837, 0.0368, 0.7155, 0.6)])


def _neutron() -> rx.Instrument:
    return rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.5)


@pytest.fixture(scope="module")
def pedestal_pattern() -> rx.PatternData:
    """Synthetic Pnma, CW neutron, 2.4 Å, 0.1° step, FWHM 0.5°, a pedestal of
    300 + 2·(2θ) counts under peaks 22 times higher (numpy + rietx only)."""
    grid = np.arange(10.0, 150.0, 0.1)
    truth = rx.Refinement(rx.Structure(phases=[_phase(0.02)]), _neutron())
    y = np.asarray(truth.predict(grid)) + 300.0 + 2.0 * grid
    y = np.maximum(y + np.random.default_rng(1).normal(
        scale=np.sqrt(np.maximum(y, 1.0))), 0)
    return rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist())


@pytest.mark.parametrize("kind", ["pspline", "chebyshev"])
def test_the_default_still_starts_every_coefficient_at_zero(pedestal_pattern, kind):
    bkg = rx.auto_background(pedestal_pattern, kind=kind).background
    assert all(c.value == 0.0 for c in bkg.coefficients)


def test_a_seeded_pspline_starts_every_coefficient_at_the_percentile(pedestal_pattern):
    bkg = rx.auto_background(pedestal_pattern, seed=True,
                             two_theta_limits=(10.0, 150.0)).background
    want = np.percentile(pedestal_pattern.intensity, AUTO_BACKGROUND_SEED_PERCENTILE)
    assert bkg.coefficients and all(c.value == pytest.approx(want)
                                    for c in bkg.coefficients)


def test_a_seeded_chebyshev_seeds_only_its_constant_term(pedestal_pattern):
    bkg = rx.auto_background(pedestal_pattern, kind="chebyshev", seed=True).background
    want = np.percentile(pedestal_pattern.intensity, AUTO_BACKGROUND_SEED_PERCENTILE)
    assert bkg.coefficients[0].value == pytest.approx(want)
    assert all(c.value == 0.0 for c in bkg.coefficients[1:])


def test_the_seed_is_taken_over_the_fitted_range_only(pedestal_pattern):
    narrow = rx.auto_background(pedestal_pattern, seed=True,
                                two_theta_limits=(100.0, 150.0)).background
    tt = np.asarray(pedestal_pattern.two_theta)
    y = np.asarray(pedestal_pattern.intensity)[(tt >= 100.0) & (tt <= 150.0)]
    assert narrow.coefficients[0].value == pytest.approx(
        np.percentile(y, AUTO_BACKGROUND_SEED_PERCENTILE))


def test_a_seeded_start_gives_the_first_le_bail_pass_a_better_answer(pedestal_pattern):
    """The case rule 5 of the skill describes, measured on this pattern: left
    at zero the first Le Bail pass hands the pedestal to the reflections and
    the profile wanders; seeded it lands lower (Rwp 0.0605 against 0.0437 on
    macOS).  Asserted as the Rwp direction only: the refined Lorentzian X is not
    portable (CI's linux/jax job had the zero start at 5e-11 and the seeded one
    at 0.019, the reverse of macOS), so no claim rests on it."""
    def first_pass(seed: bool):
        ins = _neutron()
        ins.background = rx.auto_background(
            pedestal_pattern, two_theta_limits=(10.0, 150.0), seed=seed).background
        ref = rx.Refinement(rx.Structure(phases=[_phase(0.02)]), ins)
        result = ref.fit(pedestal_pattern, mode="lebail", plan="profile_only")
        return result.statistics.rwp

    assert first_pass(True) < first_pass(False)
