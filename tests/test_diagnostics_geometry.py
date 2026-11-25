"""The aberrations a geometry has and could not express.

The condition is keyed on the *geometry* (a Debye-Scherrer capillary with no
goniometer radius), not on the radiation, so the fire and silence cases build
``Instrument.debye_scherrer`` — an X-ray capillary that stands on ``main`` with
no dependency on the neutron source.  One neutron case is kept, on the BT-1
instrument that motivated the diagnostic, to hold that the same geometry reached
through ``constant_wavelength_neutron`` reads the same gate.
"""

from __future__ import annotations

import numpy as np

import rietx as rx

CODE = "CAPILLARY_OFFSET_UNAVAILABLE"

#: An X-ray capillary wavelength (Ag Kα-ish), only so the preset is not neutron.
_XRAY_LAMBDA = 0.5594


def _corundum() -> rx.Structure:
    P = rx.Parameter
    return rx.Structure(phases=[rx.Phase(
        name="Al2O3", space_group="R-3c:H",
        cell=rx.Cell(a=P(value=4.7589), b=P(value=4.7589), c=P(value=12.9929),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=120.0)),
        atoms=[
            rx.Atom(label="Al", species="Al", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.35216), biso=P(value=0.3)),
            rx.Atom(label="O", species="O", x=P(value=0.30642), y=P(value=0.0),
                    z=P(value=0.25), biso=P(value=0.3)),
        ])])


def _flat_pattern() -> rx.PatternData:
    tt = np.arange(20.0, 90.0, 0.05)
    return rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.full(tt.size, 100.0).tolist())


def _codes(instrument: rx.Instrument) -> set[str]:
    result = rx.refine(_flat_pattern(), _corundum(), instrument,
                       plan="profile_only")
    return {d.code for d in result.diagnostics}


def test_a_capillary_without_a_radius_says_the_offsets_were_unavailable():
    """The offsets are correctly held — the diagnostic is that "held" and
    "measured to be zero" are different statements (WP-1073).

    On an X-ray Debye-Scherrer instrument, which is the claim in the PR body:
    the condition is the geometry, not the radiation.
    """
    assert CODE in _codes(rx.Instrument.debye_scherrer(_XRAY_LAMBDA))


def test_declaring_the_radius_silences_it():
    """The condition is the missing field, not the geometry."""
    assert CODE not in _codes(
        rx.Instrument.debye_scherrer(_XRAY_LAMBDA, goniometer_radius_mm=1711.0))


def test_a_flat_plate_is_not_told_about_a_capillary_aberration():
    """Keyed on the geometry that *has* the eq (4) offsets, not on any
    instrument missing any field."""
    assert CODE not in _codes(rx.Instrument.bragg_brentano(radiation="CuKa"))


def test_it_reads_the_gate_off_the_table_rather_than_the_geometry():
    """The claim in the code: a locked offset entry on a capillary *is* the
    radius being absent, so the diagnostic and the parameter table cannot
    disagree about whether the aberration was available.

    Asserted rather than described, because a second opinion here is exactly
    the drift the docstring says it avoids.

    This is the one neutron case kept: the geometry the diagnostic exists for is
    a BT-1 constant-wavelength scan, so the gate is pinned on the instrument that
    reached it rather than only on the X-ray preset the other cases use.
    """
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import CAPILLARY_OFFSETS

    structure = _corundum()
    for radius, expect_locked in ((None, True), (1711.0, False)):
        instrument = rx.Instrument.constant_wavelength_neutron(
            2.0780, fwhm_deg=0.4, goniometer_radius_mm=radius)
        table = ParameterTable(structure, instrument)
        locked = {e.path for e in table.entries if e.locked}
        # The gate is ``any(...)`` over both members of ``CAPILLARY_OFFSETS``;
        # assert every one, not just the along-beam entry, so the day the pair
        # diverges is caught here rather than passing on whichever still agrees.
        for name in CAPILLARY_OFFSETS:
            got = f"instrument.geometry.{name}" in locked
            assert got is expect_locked, name
        assert (CODE in _codes(instrument)) is expect_locked


def test_the_diagnostic_names_the_field_that_opens_the_door():
    """A diagnostic that cannot be acted on is noise."""
    field = "goniometer_radius_mm"
    result = rx.refine(_flat_pattern(), _corundum(),
                       rx.Instrument.debye_scherrer(_XRAY_LAMBDA),
                       plan="profile_only")
    hit = next(d for d in result.diagnostics if d.code == CODE)
    assert hit.where == [f"instrument.geometry.{field}"]
    assert field in (hit.suggestion or "")
    assert hit.level == "info"


def test_a_joint_fit_surfaces_it_per_capillary_histogram():
    """A joint refinement's whole point is one cell drawing from every
    pattern, so two radius-less capillaries fold both held offsets into that
    one shared cell — the WP-1073 misreading at its worst.  The diagnostic is
    wired into ``refine_joint`` per pattern, beside the absorption and
    wavelength ones it shares a geometry with, so each capillary that could not
    express its offsets says so on its own ``PatternResult``.
    """
    inst = rx.Instrument.debye_scherrer(_XRAY_LAMBDA)
    result = rx.refine_joint(
        [_flat_pattern(), _flat_pattern()], _corundum(), [inst, inst],
        plan="profile_only")
    assert len(result.patterns) == 2
    for hist in result.patterns:
        assert CODE in {d.code for d in hist.diagnostics}


def test_a_joint_fit_with_the_radius_declared_is_silent():
    """Same gate as the single-pattern case, one rank up: the missing field,
    not the geometry, so declaring the radius silences every pattern."""
    inst = rx.Instrument.debye_scherrer(_XRAY_LAMBDA, goniometer_radius_mm=1711.0)
    result = rx.refine_joint(
        [_flat_pattern(), _flat_pattern()], _corundum(), [inst, inst],
        plan="profile_only")
    for hist in result.patterns:
        assert CODE not in {d.code for d in hist.diagnostics}
