"""A mixed X-ray + neutron joint fit: does each histogram get its own physics?

Issue #194 / WP-1312 task 3.  `multi.py` stacks histograms into one residual
per Von Dreele (1997), *J. Appl. Cryst.* **30**, 517 — the combined
X-ray/neutron paper itself — and nothing in `params/multi.py` restricts the
radiation kind, so a mixed fit has been *admissible* since CW neutron landed
in WP-1134.  Admissible is not exercised.

**One thing this file does not need to add.**  A genuine mixed joint fit on
real published data already runs, in
`test_acceptance_wavelength.py::_joint` — `rx.refine_multi` over
`mg090.fxye` (11-BM synchrotron) and `mg090.Cu311.gsas` (BT-1 neutron) against
one shared `Structure`, with seven tests around it.  It landed with WP-1134
for a different reason (which wavelength is free), *after* #194 was filed, so
the issue's "I could find no test or example exercising a mixed X-ray+neutron
joint fit" is out of date.  That discharges #194's task 1.

What no test covered is #194's tasks 2 and 3: whether the per-histogram
physics keys on **the histogram's own radiation** once the two kinds are in
one residual.  Every correction below is one that must apply to one histogram
and no-op on the other, and the failure mode is silent — a neutron histogram
scattering off electron counts still converges, and still reports a good Rwp.

Synthetic throughout, so the assertions are about the machinery rather than
about a specimen: corundum ranks its two sites in *opposite* order under the
two radiations (f_Al(0) = 13 > f_O(0) = 8 electrons, while b_Al = 3.449 fm <
b_O = 5.803 fm), which makes "did this histogram use the right amplitude?" a
question about which peak is tallest rather than about a tolerance.
"""
from __future__ import annotations

import numpy as np
import pytest

import rietx as rx

CORUNDUM_CELL = (4.758877, 4.758877, 12.992880)
LAM_X, LAM_N = 1.5406, 2.0780


def corundum() -> rx.Phase:
    P = rx.Parameter
    a, _, c = CORUNDUM_CELL
    return rx.Phase(
        name="Al2O3", space_group="R -3 c :H",
        cell=rx.Cell(a=P(value=a), b=P(value=a), c=P(value=c),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=120.0)),
        scale=P(value=1.0, min=0.0, transform="softplus"),
        atoms=[
            rx.Atom(label="Al", species="Al", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.35216), biso=P(value=0.3)),
            rx.Atom(label="O", species="O", x=P(value=0.30642),
                    y=P(value=0.0), z=P(value=0.25), biso=P(value=0.3)),
        ])


def _xray() -> rx.Instrument:
    return rx.Instrument.debye_scherrer(LAM_X)


def _neutron() -> rx.Instrument:
    return rx.Instrument.constant_wavelength_neutron(LAM_N, fwhm_deg=0.3)


def _flat(lo: float, hi: float, step: float = 0.05) -> rx.PatternData:
    tt = np.arange(lo, hi, step)
    return rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.ones_like(tt).tolist())


def _y_calc(structure, instrument, data) -> np.ndarray:
    """y_calc at the stored values, through the seam a fit uses."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    model = compile_model(structure, instrument, data)
    table = ParameterTable(structure, instrument)
    return model.evaluate(table.decode(table.x0()))


# --------------------------------------------------------------- the seam ---
def test_a_mixed_joint_fit_runs_at_all():
    """The structural claim, asserted rather than inferred from a grep.

    Two histograms, two radiation kinds, one shared structure, one residual.
    """
    xd, nd = _flat(20.0, 80.0), _flat(20.0, 80.0)
    ref = rx.MultiHistogramRefinement(rx.Structure(phases=[corundum()]),
                                      [_xray(), _neutron()])
    result = ref.fit([xd, nd], plan="profile_only")
    assert result.status in {"converged", "max_iter"}
    assert len(result.histograms) == 2
    kinds = [i.source.kind for i in ref.fitted_instruments]
    assert kinds == ["xray_cw", "neutron_cw"], (
        f"the two histograms did not keep their own radiation: {kinds}")

    # `HistogramResult` carries no instrument, so the radiation each histogram
    # was fitted under is not readable from the result at all -- only from the
    # refinement object. Noted here as a comment rather than an assertion:
    # this is the audit's one structural gap and it is issue #252's subject,
    # so an assertion pinning the field's absence would go red the moment
    # #252 lands, inside a test named for whether a mixed fit runs at all.


def test_each_histogram_scatters_off_its_own_amplitude():
    """#194 task 3: f(Q) on the X-ray histogram, b on the neutron one.

    Corundum ranks Al and O oppositely under the two radiations, so if both
    histograms shared one amplitude the two patterns would peak on the *same*
    reflection. They must not.

    This is checked on the compiled model rather than on a converged fit,
    because a fit can absorb a wrong amplitude into the scale and the ADPs and
    still converge — which is exactly the silent failure the audit is for.
    """
    structure = rx.Structure(phases=[corundum()])
    data = _flat(20.0, 90.0, 0.02)
    x = _y_calc(structure, _xray(), data)
    n = _y_calc(structure, _neutron(), data)

    assert np.isfinite(x).all() and np.isfinite(n).all()
    assert x.max() > 0.0 and n.max() > 0.0
    assert np.argmax(x) != np.argmax(n), (
        "the X-ray and neutron patterns peak on the same reflection — one of "
        "them is not using its own scattering amplitude")


def test_anomalous_dispersion_is_on_for_xray_and_structurally_absent_for_neutron():
    """#194 task 2, the correction the issue names first.

    `Source.dispersion` is on by default and is an X-ray core-level effect.
    On the neutron source it is not merely disabled but **structurally None**,
    so there is no state in which a mixed fit could apply f'/f'' to the
    neutron histogram.
    """
    assert _xray().source.dispersion is not None
    assert _neutron().source.dispersion is None

    xd, nd = _flat(20.0, 80.0), _flat(20.0, 80.0)
    ref = rx.MultiHistogramRefinement(rx.Structure(phases=[corundum()]),
                                      [_xray(), _neutron()])
    ref.fit([xd, nd], plan="profile_only")
    by_kind = {i.source.kind: i for i in ref.fitted_instruments}
    assert by_kind["xray_cw"].source.dispersion is not None
    assert by_kind["neutron_cw"].source.dispersion is None


def test_the_dispersion_diagnostic_is_not_wired_into_a_joint_fit_yet():
    """`DISPERSION_NEGLECTED` fires zero times here, and not because either
    histogram behaves correctly.

    The review on #281 asked for the exact count rather than `<= 1`, since
    that bound cannot tell "fired once, correctly" from "never fired at
    all". Measured: with the X-ray histogram's `dispersion` set to `None`
    and corundum's Al at this wavelength well past
    `DISPERSION_NEGLECT_FRAC` (fractional effect on scattering power ~3.3%,
    `refine.py::_dispersion_diagnostics`), a single-histogram
    `Refinement` on the same structure and instrument *does* raise it. A
    joint fit through `refine_multi`/`MultiHistogramRefinement` does not,
    on either histogram, at any count.

    That is because `multi.py`'s per-histogram diagnostics loop —
    `_absorption_diagnostics`, `_capillary_offset_diagnostics`,
    `_wavelength_calibration_diagnostics`, `_strain_flag_diagnostics`,
    `_size_flag_diagnostics` and the rest — never calls
    `_dispersion_diagnostics` at all, for either histogram's diagnostics or
    the fit's own. So `0` here is the honest count, and it is *not* the
    "neutron correctly abstains, X-ray correctly fires" result this test
    used to claim (`assert len(fired) <= 1`, which `0` also satisfies).
    Wiring `_dispersion_diagnostics` per histogram into the joint path is
    real follow-up work and a package-behaviour change, not done here —
    flagged to @yue-here as this file's one open question rather than
    fixed by this PR.
    """
    xray = _xray()
    xray = xray.model_copy(update={
        "source": xray.source.model_copy(update={"dispersion": None})})
    xd, nd = _flat(20.0, 80.0), _flat(20.0, 80.0)
    result = rx.refine_multi([xd, nd], rx.Structure(phases=[corundum()]),
                             [xray, _neutron()], plan="profile_only")
    fired = [d for d in result.diagnostics if d.code == "DISPERSION_NEGLECTED"]
    assert len(fired) == 0, (
        "DISPERSION_NEGLECTED now fires in a joint fit -- if `multi.py` was "
        "changed to wire `_dispersion_diagnostics` in, this test's docstring "
        "is the one that needs rewriting to state the intended per-histogram "
        "count (1, on the X-ray histogram only) rather than the gap")


def test_polarization_belongs_to_the_xray_histogram_alone():
    """Lorentz-polarization is an X-ray beam property.

    The neutron source does carry a `polarization` field, but pinned: value
    1.0 with `min == max == 1.0` and `vary=False`, so it is the unpolarized
    limit and there is no state a mixed fit could refine it into. That is a
    better design than omitting the field -- one `Source` shape, one LP
    expression -- and it is worth an assertion precisely because "the field is
    present" would otherwise read as "the correction applies".
    """
    xray_pol = _xray().source.polarization
    neutron_pol = _neutron().source.polarization

    # the neutron beam is pinned at the unpolarized limit and cannot leave it
    assert neutron_pol.value == 1.0
    assert neutron_pol.min == neutron_pol.max == 1.0
    assert not neutron_pol.vary

    # the X-ray beam is not pinned there: it carries a real monochromator
    # value with room to move, which is what makes the pin above a decision
    assert xray_pol.value != 1.0
    assert xray_pol.min < xray_pol.max


def test_the_structure_is_shared_and_the_instruments_are_not():
    """#194 task 3's other half: one crystal, two instruments.

    The point of a joint fit is that the *structure* is one object and the
    per-histogram machinery is not, so this asserts both directions — a shared
    cell that moved together, and profile terms that did not.
    """
    xd, nd = _flat(20.0, 80.0), _flat(20.0, 80.0)
    ref = rx.MultiHistogramRefinement(rx.Structure(phases=[corundum()]),
                                      [_xray(), _neutron()])
    ref.fit([xd, nd], plan="profile_only")
    assert ref.n_histograms == 2

    cells = [s.phases[0].cell.a.value for s in ref.fitted_structures]
    assert cells[0] == pytest.approx(cells[1]), (
        "the shared cell differs between histograms — the structure is not "
        "shared")

    ws = [i.profile.w.value for i in ref.fitted_instruments]
    assert ws[0] != ws[1], (
        "both histograms carry the same profile width; the instruments are "
        "supposed to be per-histogram")
