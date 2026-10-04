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
b_O = 5.803 fm, Sears 1992 as gemmi's ``neutron92`` gives them), which makes
"did this histogram use the right amplitude?" a question about which peak is
tallest rather than about a tolerance.

**The audit is a table, keyed on the source kind** (:data:`RADIATION_KEYED`):
one row per correction that must key on a histogram's own radiation, a probe
reading the *joint fit's own* compiled state for that histogram, and the
answer each kind must give.  A new radiation-keyed term joins with one row
(WP-1327's magnetic term is the row that proved the shape), and a new source
kind fails :func:`test_every_row_answers_for_every_source_kind` until every row
says what it does there.  Three things the table is not: the radiation-keyed
*diagnostics*, which WP-1344 placed on the histogram that owns each (pinned
below at their exact count, ``multi.DIAGNOSTIC_SCOPES`` the rule); the
λ-keyed size normalisation, which is WP-1131's and tested in
``test_multi_histogram.py``; and anything a single
histogram already tests, since the question here is only whether the stack
keeps each histogram's answer its own.

#194's third ask, whether the shared-vs-per-histogram split holds when the two
histograms weight the structure factor differently, is measured last: one
corundum truth recovered through both weightings, and the esds showing which
histogram bought which site.
"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.scattering import MAGNETIC_SOURCE_KINDS
from rietx.schemas.instrument import Dispersion
from rietx.schemas.structure import Moment

CORUNDUM_CELL = (4.758877, 4.758877, 12.992880)
LAM_X, LAM_N = 1.5406, 2.0780

#: corundum's two free coordinates and two ADPs as the synthetic truth; the
#: coordinates are the room-temperature structure's, the Biso round numbers
TRUTH = {"phases.0.atoms.0.z": 0.35216, "phases.0.atoms.1.x": 0.30642,
         "phases.0.atoms.0.biso": 0.35, "phases.0.atoms.1.biso": 0.45}


def corundum(z_al: float = 0.35216, x_o: float = 0.30642,
             b_al: float = 0.3, b_o: float = 0.3,
             scale: float = 1.0) -> rx.Phase:
    P = rx.Parameter
    a, _, c = CORUNDUM_CELL
    return rx.Phase(
        name="Al2O3", space_group="R -3 c :H",
        cell=rx.Cell(a=P(value=a), b=P(value=a), c=P(value=c),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=120.0)),
        scale=P(value=scale, min=0.0, transform="softplus"),
        atoms=[
            rx.Atom(label="Al", species="Al", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=z_al), biso=P(value=b_al, min=0.0, max=5.0)),
            rx.Atom(label="O", species="O", x=P(value=x_o),
                    y=P(value=0.0), z=P(value=0.25),
                    biso=P(value=b_o, min=0.0, max=5.0)),
        ])


def mnf2() -> rx.Phase:
    """MnF₂, rutile P 4₂/mnm, BNS 136.499, Mn on 2a with 4.6 μ_B along c.

    Erickson (1953), *Phys. Rev.* **90**, 779 — the structure
    ``test_magnetic.py`` already carries, repeated here so this file's one
    magnetic row stands alone.  Its strongest magnetic line, (1 0 0), is
    systematically absent in P 4₂/mnm, so the moment is visible only as a
    line the nuclear model cannot make.
    """
    P = rx.Parameter
    a, c = 4.8734, 3.3099

    def atom(label, xyz, moment=None):
        return rx.Atom(label=label, species=label, x=P(value=xyz[0]),
                       y=P(value=xyz[1]), z=P(value=xyz[2]),
                       biso=P(value=0.4, min=0.0, max=5.0), moment=moment)

    return rx.Phase(
        name="MnF2", space_group="P 42/m n m",
        cell=rx.Cell(a=P(value=a), b=P(value=a), c=P(value=c),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=90.0)),
        scale=P(value=1.0, min=0.0, transform="softplus"),
        atoms=[atom("Mn", (0.0, 0.0, 0.0),
                    Moment.from_values((0.0, 0.0, 4.6), "Mn2+", vary=True)),
               atom("F", (0.3050, 0.3050, 0.0))],
        magnetic_symmetry="136.499")


def _xray() -> rx.Instrument:
    # declared, not inherited: the pinned bars below and the table's
    # "dispersion: yes for xray_cw" row must not ride on today's default
    ins = rx.Instrument.debye_scherrer(LAM_X)
    ins.source.dispersion = Dispersion()
    return ins


def _neutron() -> rx.Instrument:
    return rx.Instrument.constant_wavelength_neutron(LAM_N, fwhm_deg=0.3)


def _flat(lo: float, hi: float, step: float = 0.05) -> rx.PatternData:
    tt = np.arange(lo, hi, step)
    return rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.ones_like(tt).tolist())


def _short_plan():
    """One three-iteration stage: enough to compile every histogram."""
    from rietx.strategy.staged import RefinementPlan, Stage

    return RefinementPlan(stages=[Stage("scale", ["phases.*.scale"],
                                        max_iter=3)])


def _y_calc(structure, instrument, data) -> np.ndarray:
    """y_calc at the stored values, through the seam a fit uses."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    model = compile_model(structure, instrument, data)
    table = ParameterTable(structure, instrument)
    return model.evaluate(table.decode(table.x0()))


def _synthetic(structure, instrument, lo: float, hi: float, step: float,
               peak: float, *, seed: int, zero: float = 0.0
               ) -> tuple[rx.PatternData, float]:
    """Poisson counts from ``structure`` on ``instrument``, and the true scale.

    The phase scale is set so the strongest channel holds ``peak`` counts
    over a flat 50, and returned, so a fit's per-histogram scale has a truth
    to be compared with.  ``structure`` is not modified.
    """
    grid = _flat(lo, hi, step)
    instrument = instrument.model_copy(deep=True)
    instrument.zero_shift.value = zero
    scale = peak / _y_calc(structure, instrument, grid).max()
    scaled = structure.model_copy(deep=True)
    scaled.phases[0].scale.value = scale
    y = _y_calc(scaled, instrument, grid) + 50.0
    counts = np.random.default_rng(seed).poisson(y).astype(float)
    return (rx.PatternData(two_theta=grid.two_theta, intensity=counts.tolist()),
            scale)


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


def test_a_deuterated_structure_goes_on_both_histograms():
    """Issue #552: one ``Structure`` carrying ``D`` compiles on an X-ray
    histogram, which sees hydrogen, and on a neutron one, which sees ²H.

    Before #552 the X-ray compile refused it ("no Waasmaier-Kirfel
    coefficients for species 'D'"), so a deuterated sample could not be
    refined jointly at all. The positive arm is the neutron pattern moving
    (b flips sign, −3.739 → +6.671 fm); the negative arm is the X-ray pattern
    **not** moving by a bit.
    """
    P = rx.Parameter

    def nickel_hydride(h: str) -> rx.Structure:
        return rx.Structure(phases=[rx.Phase(
            name="NiH", space_group="F m -3 m", cell=rx.Cell.cubic(3.72),
            scale=P(value=1.0, min=0.0, transform="softplus"),
            atoms=[rx.Atom(label="Ni", species="Ni", x=P(value=0.0),
                           y=P(value=0.0), z=P(value=0.0),
                           biso=P(value=0.4, min=0.0, max=5.0)),
                   rx.Atom(label="H", species=h, x=P(value=0.5),
                           y=P(value=0.5), z=P(value=0.5),
                           biso=P(value=0.9, min=0.0, max=5.0))])])

    grid = _flat(20.0, 120.0)
    xray = {h: _y_calc(nickel_hydride(h), _xray(), grid) for h in ("H", "D", "2H")}
    neutron = {h: _y_calc(nickel_hydride(h), _neutron(), grid)
               for h in ("H", "D", "2H")}
    assert np.array_equal(xray["H"], xray["D"])
    assert np.array_equal(xray["H"], xray["2H"])
    assert np.array_equal(neutron["D"], neutron["2H"])
    assert np.max(np.abs(neutron["D"] - neutron["H"])) > 0.1 * np.max(neutron["H"])

    ref = rx.MultiHistogramRefinement(nickel_hydride("D"), [_xray(), _neutron()])
    result = ref.fit([_flat(20.0, 120.0), _flat(20.0, 120.0)], plan=_short_plan())
    assert result.status in {"converged", "max_iter"}
    assert len(result.histograms) == 2


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


# ------------------------------------------------------- the audit table ---
def _source_kinds() -> set[str]:
    """Every radiation an ``Instrument`` can carry, read off its union."""
    union = rx.Instrument.model_fields["source"].annotation
    return {arm.model_fields["kind"].default for arm in typing.get_args(union)}


#: One instrument per source kind, each declaring a capillary so the
#: absorption row has something to estimate.  A new kind needs a line here
#: before the table can ask it anything.
INSTRUMENT_FOR_KIND: dict[str, Callable[[], rx.Instrument]] = {
    "xray_cw": lambda: rx.Instrument.debye_scherrer(
        LAM_X, capillary_radius_mm=0.15),
    "neutron_cw": lambda: rx.Instrument.constant_wavelength_neutron(
        LAM_N, fwhm_deg=0.3, capillary_radius_mm=3.0),
}


@dataclass(frozen=True)
class Keyed:
    """One correction that must key on the histogram's own radiation.

    ``probe(joint, h)`` reads what the joint fit actually built for histogram
    ``h`` (its compiled model, its table, its instrument) and returns whether
    the correction is in force there; ``expect`` is the answer each source
    kind must give.
    """

    name: str
    probe: Callable[[rx.MultiHistogramRefinement, int], bool]
    expect: dict[str, bool]


def _entry(joint, h: int, path: str):
    return next(e for e in joint.mtable.tables[h].entries if e.path == path)


RADIATION_KEYED = [
    # b (fm, no s dependence) against f₀(s): the amplitude itself
    Keyed("scattering amplitude is b, not f0(s)",
          lambda j, h: all(cp.sites.b_coh is not None
                           for cp in j._models[h].phases),
          {"xray_cw": False, "neutron_cw": True}),
    # f′ + i·f″ is an X-ray core-level effect, on by default since v1.0
    Keyed("anomalous dispersion f' + i f''",
          lambda j, h: any(cp.sites.f_anom is not None
                           for cp in j._models[h].phases),
          {"xray_cw": True, "neutron_cw": False}),
    # K is the Thomson cross-section's; a neutron's is pinned at 1 and locked
    Keyed("polarisation K refinable",
          lambda j, h: not _entry(j, h, "instrument.polarization").locked,
          {"xray_cw": True, "neutron_cw": False}),
    # WP-1327: the moment couples to a neutron's own moment and nothing else's
    Keyed("magnetic structure factor built",
          lambda j, h: j._models[h].phases[1].magnetic is not None,
          {"xray_cw": False, "neutron_cw": True}),
    # Both kinds estimate a µR from composition since WP-1132, each off its
    # own table (McMaster photoabsorption, Sears cross-sections), so the rows
    # key on which table was read rather than on whether a µR exists
    Keyed("capillary muR read off the McMaster (X-ray) table",
          lambda j, h: _mu_r_is_from_table(j, h, "xray_cw"),
          {"xray_cw": True, "neutron_cw": False}),
    Keyed("capillary muR read off the Sears (neutron) table",
          lambda j, h: _mu_r_is_from_table(j, h, "neutron_cw"),
          {"xray_cw": False, "neutron_cw": True}),
    # #543: Brindley's µ read the X-ray table on every histogram, so on the
    # neutron one a sub-percent correction moved the fractions by the X-ray µ
    Keyed("Brindley mu read off the McMaster (X-ray) table",
          lambda j, h: _brindley_mu_is_from_table(j, h, "xray_cw"),
          {"xray_cw": True, "neutron_cw": False}),
    Keyed("Brindley mu read off the Sears (neutron) table",
          lambda j, h: _brindley_mu_is_from_table(j, h, "neutron_cw"),
          {"xray_cw": False, "neutron_cw": True}),
]

#: Every phase of the joint fixture carries a radius, so each histogram's QPA
#: runs Brindley's correction (it needs all of them) and the rows above can ask
#: which table it read.
BRINDLEY_RADIUS_UM = 2.0


def _mu_r_is_from_table(joint, h: int, table_kind: str) -> bool:
    """Whether histogram ``h``'s compiled µR is the one ``table_kind`` gives.

    Recomputed on a fresh copy of the fixture's specimen at its starting
    values, which is what the joint fit estimates from at construction.
    """
    from rietx.optimize.qpa import estimate_capillary_mu_r
    from rietx.params.vector import ParameterTable
    got = joint.fitted_instruments[h].geometry.mu_r
    if got is None:
        return False
    structure = rx.Structure(phases=[corundum(), mnf2()])
    ins = INSTRUMENT_FOR_KIND[joint.mtable.instruments[h].source.kind]()
    table = ParameterTable(structure, ins)
    want, _ = estimate_capillary_mu_r(
        structure, table.decode(table.x0()), ins.source.primary_wavelength,
        ins.geometry.capillary_radius_mm, ins.geometry.packing_fraction,
        source_kind=table_kind)
    return want is not None and bool(np.isclose(got, want, rtol=1e-12))


def _brindley_mu_is_from_table(joint, h: int, table_kind: str) -> bool:
    """Whether histogram ``h``'s Brindley µ per phase is ``table_kind``'s.

    The want side calls the two tables' own functions by name, not
    ``LINEAR_ATTENUATION_BY_SOURCE``, so an entry filed under the wrong kind
    fails here.  The fixture frees only the scales, so the cells and
    compositions are the stored ones.
    """
    from rietx.crystallography.attenuation import linear_attenuation
    from rietx.crystallography.neutron import linear_attenuation_neutron
    from rietx.crystallography.symmetry import resolve_group
    from rietx.optimize.qpa import phase_zmv

    qpa = joint.result_.histograms[h].qpa
    if qpa is None or qpa.microabsorption is None:
        return False
    lam = joint.mtable.instruments[h].source.primary_wavelength
    for phase, row in zip(joint.mtable.structures[h].phases, qpa.phases,
                          strict=True):
        cell = tuple(getattr(phase.cell, n).value
                     for n in ("a", "b", "c", "alpha", "beta", "gamma"))
        zmv = phase_zmv(resolve_group(phase.space_group, phase.symmetry_operations),
                        cell, [(a.species, a.x.value, a.y.value, a.z.value,
                                a.occ.value) for a in phase.atoms])
        want = (linear_attenuation(zmv.element_counts, zmv.cell_volume, lam)
                if table_kind == "xray_cw" else
                linear_attenuation_neutron(zmv.species_counts, zmv.cell_volume,
                                           lam))
        if not np.isclose(row.mu_cm, want, rtol=1e-9):
            return False
    return True


@pytest.fixture(scope="module")
def every_kind_jointly():
    """One joint fit, one histogram per source kind, both phases shared.

    Flat data and one short stage: the probes read what was *compiled* for
    each histogram, which the fit builds whatever the data say, so solving
    for longer would buy nothing (``profile_only`` spends 400 iterations
    here fitting a constant).
    """
    kinds = sorted(INSTRUMENT_FOR_KIND)
    phases = [corundum(), mnf2()]
    for phase in phases:
        phase.particle_radius_um = BRINDLEY_RADIUS_UM
    joint = rx.MultiHistogramRefinement(
        rx.Structure(phases=phases),
        [INSTRUMENT_FOR_KIND[k]() for k in kinds])
    joint.fit([_flat(20.0, 80.0) for _ in kinds], plan=_short_plan())
    return joint, kinds


def test_every_row_answers_for_every_source_kind():
    """The table's columns are the package's radiations, both ways.

    A new ``Source`` arm fails here until each row says what it does there,
    which is the point of keying the audit on the kind rather than writing
    one check per pair of radiations.
    """
    kinds = _source_kinds()
    assert set(INSTRUMENT_FOR_KIND) == kinds
    for row in RADIATION_KEYED:
        assert set(row.expect) == kinds, row.name


def test_the_magnetic_row_is_the_forward_models_own_dispatch():
    """The row's column is ``MAGNETIC_SOURCE_KINDS``, not a second copy of it."""
    row = next(r for r in RADIATION_KEYED if r.name.startswith("magnetic"))
    assert {k for k, on in row.expect.items() if on} == MAGNETIC_SOURCE_KINDS


@pytest.mark.xdist_group("joint-radiation-table")
@pytest.mark.parametrize("row", RADIATION_KEYED, ids=lambda r: r.name)
def test_each_histogram_of_a_joint_fit_keys_on_its_own_radiation(
        every_kind_jointly, row):
    """#194 task 2: each correction applies to one kind and no-ops on the rest.

    Read off the joint fit's own compiled models and tables — never off an
    instrument built beside it — because the failure this audits is the
    stack handing one histogram another's physics.
    """
    joint, kinds = every_kind_jointly
    got = {kind: row.probe(joint, h) for h, kind in enumerate(kinds)}
    assert got == row.expect


def test_the_shared_moment_is_measured_by_the_neutron_histogram_alone():
    """The magnetic row, end to end: a joint fit refines a moment.

    The moment is shared (it is the specimen's), so the X-ray histogram
    carries the column too — and contributes no gradient to it, because its
    model never builds the term.  Freed from 3.5 μ_B against synthetic
    X-ray and neutron patterns of the 4.6 μ_B truth, it comes back at the
    truth within its esd.
    """
    from rietx.strategy.staged import PLAN_PRESETS, Stage

    truth = rx.Structure(phases=[mnf2()])
    xd, _ = _synthetic(truth, _xray(), 15.0, 120.0, 0.02, 1e4, seed=1)
    nd, _ = _synthetic(truth, rx.Instrument.constant_wavelength_neutron(
        2.4, fwhm_deg=0.3), 10.0, 150.0, 0.05, 1e4, seed=2)
    start = rx.Structure(phases=[mnf2()])
    start.phases[0].atoms[0].moment = Moment.from_values(
        (0.0, 0.0, 3.5), "Mn2+", vary=True)
    plan = PLAN_PRESETS["mccusker_structural"]()
    plan.stages.append(Stage("moment", ["phases.*.atoms.*.moment.*"]))
    joint = rx.MultiHistogramRefinement(start, [
        _xray(), rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.3)])
    result = joint.fit([xd, nd], plan=plan)

    assert result.status == "converged"
    assert [m.phases[0].magnetic is not None for m in joint._models] == [
        False, True]
    row = next(p for p in result.parameters if ".moment." in p.path)
    assert not row.path.startswith("hist."), "the moment is the specimen's"
    assert row.stderr is not None and row.stderr > 0
    assert abs(row.value - 4.6) < 4 * row.stderr, (row.value, row.stderr)


def test_the_dispersion_diagnostic_fires_on_the_xray_histogram_alone():
    """`DISPERSION_NEGLECTED` fires once, on the X-ray histogram only.

    The exact count, as the review on #281 asked, since `<= 1` cannot tell
    "fired once, correctly" from "never fired at all" — which is what this
    test used to pin: `multi.py` never called `_dispersion_diagnostics`, so a
    joint fit raised it at no count while a single-histogram `Refinement` on
    the same structure and instrument raised it once (corundum's Al at this
    wavelength carries ~3.3 % of its scattering power in f′, past
    `DISPERSION_NEGLECT_FRAC`).  WP-1344 placed it: the code asks one
    histogram's source, so it is that histogram's (`multi.DIAGNOSTIC_SCOPES`),
    the neutron histogram abstains, and the top-level list stays clear of it.
    `tests/test_multi_diagnostics.py` carries the siblings and the meta-test.
    """
    xray = _xray()
    xray = xray.model_copy(update={
        "source": xray.source.model_copy(update={"dispersion": None})})
    xd, nd = _flat(20.0, 80.0), _flat(20.0, 80.0)
    result = rx.refine_multi([xd, nd], rx.Structure(phases=[corundum()]),
                             [xray, _neutron()], plan="profile_only")
    assert [d.code for d in result.diagnostics].count("DISPERSION_NEGLECTED") == 0
    assert [[d.code for d in h.diagnostics].count("DISPERSION_NEGLECTED")
            for h in result.histograms] == [1, 0]


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


# ----------------------------------------------- the weighting, measured ---
def _value_esd(result, path: str) -> tuple[float, float]:
    row = next(p for p in result.parameters if p.path == path)
    return row.value, row.stderr


@pytest.fixture(scope="module")
def two_weightings():
    """One corundum truth seen through f(Q) and through b, fitted three ways.

    Synthetic X-ray (15-120°, 2·10⁴ counts) and neutron (10-150°, 5·10³)
    patterns of one structure, each with its own scale and zero shift; the
    fit starts with every coordinate and ADP off the truth.
    """
    truth = rx.Structure(phases=[corundum(
        z_al=TRUTH["phases.0.atoms.0.z"], x_o=TRUTH["phases.0.atoms.1.x"],
        b_al=TRUTH["phases.0.atoms.0.biso"],
        b_o=TRUTH["phases.0.atoms.1.biso"])])
    xd, s_x = _synthetic(truth, _xray(), 15.0, 120.0, 0.02, 2e4,
                         seed=1, zero=0.01)
    nd, s_n = _synthetic(truth, _neutron(), 10.0, 150.0, 0.05, 5e3,
                         seed=11, zero=-0.03)

    def start():
        return rx.Structure(phases=[corundum(z_al=0.3530, x_o=0.3050,
                                             b_al=0.6, b_o=0.7)])

    plan = "mccusker_structural"
    joint = rx.refine_multi([xd, nd], start(), [_xray(), _neutron()], plan=plan)
    alone = [rx.Refinement(start(), ins, history=False).fit(d, plan=plan)
             for ins, d in ((_xray(), xd), (_neutron(), nd))]
    return joint, alone, {"hist.0.phases.0.scale": s_x,
                          "hist.1.phases.0.scale": s_n,
                          "hist.0.instrument.zero_shift": 0.01,
                          "hist.1.instrument.zero_shift": -0.03}


@pytest.mark.xdist_group("joint-two-weightings")
def test_one_structure_answers_to_both_weightings(two_weightings):
    """#194 task 3: the shared-vs-per-histogram split, where it can fail.

    The two histograms weight the structure factor oppositely (corundum's
    Al outscatters its O for X-rays and the reverse for neutrons), so a
    shared coordinate is pulled by two different sensitivities.  Every
    shared parameter must land on the one truth, and every per-histogram
    one on its own histogram's truth — two scales 3.5× apart and two zero
    shifts of opposite sign, none of them leaking into the other histogram.
    Measured over seeds 1-3 on macOS arm64: the largest |Δ|/esd was 1.21;
    on Linux x86_64 (seed 1) it was 0.91.
    """
    joint, _alone, per_histogram = two_weightings
    assert joint.status == "converged"
    for path, truth in {**TRUTH, **per_histogram}.items():
        value, esd = _value_esd(joint, path)
        assert esd is not None and esd > 0, path
        assert abs(value - truth) < 3 * esd, (path, value, truth, esd)


@pytest.mark.xdist_group("joint-two-weightings")
def test_the_neutron_histogram_buys_the_oxygen_and_not_the_aluminium(
        two_weightings):
    """What a joint X-ray + neutron fit is *for*, read off the esds.

    Alone, the neutron pattern determines z(Al) about 3× worse than the
    X-ray pattern does and x(O) about as well, so jointly the X-ray keeps
    the aluminium (esd ×0.94-0.97 of its own) while the oxygen gains
    (×0.64-0.68).  Seeds 1-3 on macOS arm64; Linux x86_64 (seed 1) gives
    0.955 and 0.660, and neutron/X-ray 3.62 and 0.993 (ratio 3.64); CI's
    py3.11 job gave 0.887 and 0.622.  The absolute joint ratios move by
    ~0.07 across builds, so the claim is pinned as the *asymmetry*
    joint_al / joint_o, which held at 1.38-1.45 on every one of them; the
    absolute floor under joint_al only rules out the aluminium gaining as
    much as the oxygen does.  A stack that handed both histograms one
    amplitude could not produce this asymmetry: the two sensitivities
    would be one, and the ratio would sit near 1.
    """
    joint, (x_alone, n_alone), _ = two_weightings
    ratios = {}
    for path in ("phases.0.atoms.0.z", "phases.0.atoms.1.x"):
        esd_j = _value_esd(joint, path)[1]
        esd_x = _value_esd(x_alone, path)[1]
        esd_n = _value_esd(n_alone, path)[1]
        ratios[path] = (esd_j / esd_x, esd_n / esd_x)
    (joint_al, n_al), (joint_o, n_o) = (ratios["phases.0.atoms.0.z"],
                                        ratios["phases.0.atoms.1.x"])
    assert n_al / n_o > 2.5, ratios
    assert joint_o < 0.8 and joint_al > 0.8, ratios
    assert joint_al / joint_o > 1.25, ratios


# -------------------- the radiation-keyed diagnostics, on their own histogram ---
def _yb_oxide() -> rx.Phase:
    """A rock-salt 'YbO' — a vehicle for one Yb site, not a real phase."""
    P = rx.Parameter
    a = 4.88
    return rx.Phase(
        name="YbO", space_group="F m -3 m",
        cell=rx.Cell(a=P(value=a), b=P(value=a), c=P(value=a),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=90.0)),
        scale=P(value=1.0, min=0.0, transform="softplus"),
        atoms=[rx.Atom(label="Yb", species="Yb", x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0), biso=P(value=0.3)),
               rx.Atom(label="O", species="O", x=P(value=0.5),
                       y=P(value=0.5), z=P(value=0.5), biso=P(value=0.3))])


def _as3plus_corundum() -> rx.Phase:
    """Corundum with its Al site labelled ``As3+``, an ion the X-ray table lacks."""
    phase = corundum()
    phase.atoms[0].species = "As3+"
    return phase


@pytest.mark.parametrize("code, phase, owner", [
    ("NEUTRON_RESONANT_ABSORBER", _yb_oxide, "neutron_cw"),
    ("SPECIES_FALLBACK_NEUTRAL", _as3plus_corundum, "xray_cw"),
])
def test_the_other_radiation_keyed_diagnostics_fire_on_their_own_histogram(
        code, phase, owner):
    """The two siblings of ``DISPERSION_NEGLECTED`` above, placed by WP-1344.

    Each is raised by a single-histogram ``Refinement`` on the histogram
    whose radiation it belongs to — measured here as the control.  This test
    used to pin a joint fit over the same structure and both instruments at
    no count, because ``multi.py`` called none of the three radiation-keyed
    helpers.  WP-1344 placed them (``multi.DIAGNOSTIC_SCOPES``): each asks
    one histogram's source, so a joint fit raises it once, on the ``owner``
    histogram only, and never at the top level.
    """
    structure = rx.Structure(phases=[phase()])
    by_kind = {"xray_cw": _xray, "neutron_cw": _neutron}
    alone = rx.Refinement(structure.model_copy(deep=True), by_kind[owner](),
                          history=False).fit(_flat(20.0, 80.0),
                                             plan=_short_plan())
    assert [d.code for d in alone.diagnostics].count(code) == 1

    instruments = [_xray(), _neutron()]
    joint = rx.refine_multi([_flat(20.0, 80.0), _flat(20.0, 80.0)],
                            structure, instruments, plan=_short_plan())
    assert [d.code for d in joint.diagnostics].count(code) == 0
    assert [[d.code for d in h.diagnostics].count(code)
            for h in joint.histograms] == [
        int(inst.source.kind == owner) for inst in instruments]
