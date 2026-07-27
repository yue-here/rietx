"""Surface roughness (WP-0502): Suortti (1972) and Pitschke et al. (1993).

A rough or loosely-packed flat specimen depresses diffracted intensity at low
2theta.  Left uncorrected the depression is absorbed by Biso/ADPs (driving them
toward — and past — zero), by the phase scales and by a flexible background, so
every test here is written twice over: once for the physics, once for the
degeneracy that physics creates.
"""

import math

import pytest
from pydantic import ValidationError

from pxrdref import Instrument
from pxrdref.schemas import Geometry, RoughnessPitschke, RoughnessSuortti

# -- schema ------------------------------------------------------------------


def test_roughness_blocks_default_to_the_identity():
    """Attaching a block must change nothing until it is deliberately refined."""
    s = RoughnessSuortti()
    assert s.kind == "suortti"
    assert s.b.value == 0.0 and s.b.vary is False
    assert s.b.min == 0.0 and s.b.transform == "softplus"
    # a is strictly interior on purpose: at b = 0 the gradient
    # dR/db = (1-a)(1 - 1/sin(theta)) vanishes identically when a = 1, so a
    # default of 1.0 would make the parameter unable to lift off.
    assert 0.0 < s.a.value < 1.0
    assert s.a.transform == "identity"

    p = RoughnessPitschke()
    assert p.kind == "pitschke"
    assert p.c.value == 0.0 and p.c.vary is False
    assert p.c.min == 0.0 and p.c.transform == "softplus"
    assert 0.0 < p.tau.value < p.tau.max  # interior, same lift-off reason
    assert p.tau.transform == "identity"


def test_roughness_bounds_encode_the_published_regimes():
    # tau < 0.3 is Pitschke's own estimate of the physical upper limit for real
    # powders (its fitted values span 0.005-0.12); c < 4 keeps R > 0 inside the
    # valid range, since max u(1-u) = 1/4.
    p = RoughnessPitschke()
    assert p.tau.max == pytest.approx(0.3)
    assert p.c.max == pytest.approx(4.0)
    # a is a fraction; b is a positive optical depth
    s = RoughnessSuortti()
    assert (s.a.min, s.a.max) == (0.0, 1.0)
    assert s.b.min == 0.0


def test_roughness_requires_a_flat_specimen():
    """A spinning capillary has no illuminated flat surface to roughen."""
    with pytest.raises(ValidationError) as err:
        Geometry(kind="debye_scherrer", surface_roughness=RoughnessSuortti())
    assert "bragg_brentano" in str(err.value)

    # ... and the Bragg-Brentano case is accepted
    g = Geometry(kind="bragg_brentano", goniometer_radius_mm=217.5,
                 surface_roughness=RoughnessSuortti())
    assert g.surface_roughness is not None


def test_roughness_json_round_trip_selects_the_right_kind():
    """The union must survive JSON without collapsing to the wrong model."""
    for block in (RoughnessSuortti(), RoughnessPitschke()):
        ins = Instrument.bragg_brentano()
        ins.geometry.surface_roughness = block
        back = Instrument.model_validate_json(ins.model_dump_json())
        assert back == ins
        assert type(back.geometry.surface_roughness) is type(block)


def test_instrument_presets_carry_no_roughness_block():
    """Off by default: existing refinements must be bit-identical to before."""
    assert Instrument.bragg_brentano().geometry.surface_roughness is None
    assert Instrument.debye_scherrer(wavelength=1.5406).geometry.surface_roughness is None


def test_the_two_models_are_exactly_the_identity_when_off():
    """Not 'approximately 1' — bit-exactly 1.0, so the off state needs no branch.

    Suortti: at b = 0 numerator and denominator reduce to the *identical*
    expression a + (1-a)*1.0, whatever a is.
    Pitschke: at c = 0 the whole correction term is multiplied by zero.
    """
    for a in (0.0, 0.1, 0.5, 0.9, 1.0):
        for two_theta in (5.0, 37.0, 91.0, 150.0):
            s = math.sin(math.radians(two_theta / 2.0))
            r = (a + (1.0 - a) * math.exp(-0.0 / s)) / (a + (1.0 - a) * math.exp(-0.0))
            assert r == 1.0
    for tau in (0.0, 0.05, 0.3):
        for two_theta in (5.0, 37.0, 91.0, 150.0):
            s = math.sin(math.radians(two_theta / 2.0))
            u = tau / s
            assert 1.0 - 0.0 * u * (1.0 - u) == 1.0
