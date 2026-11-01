"""Bounds and flags for the walking parameters the width caps do not cover.

WP-1311. The width caps (PR #144) own strain and size, and
``PHASE_UNCONSTRAINED`` plus ``cell_window`` own a walking cell. What is left
gets at most a bound from physics or a flag, never a tuned cap, and each
signal has to fire on its own motivating configuration while staying silent on
a healthy fit.

This module holds one section per item. Item 3 is the resolution-positivity
guard: U, V and W each legitimately go negative on a real instrument, so the
constraint is on the Caglioti quadratic as a whole, and a fit that leaves the
physical set does not raise — ``gaussian_fwhm`` clamps Γ_G² to a floor and the
forward model reports a resolution four orders finer than any goniometer.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.model.forward import compile_model
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2, gaussian_fwhm
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import Instrument
from rietx.schemas.pattern import PatternData
from rietx.strategy.staged import (
    FLAT_DIRECTION_RHO,
    GAUSSIAN_RESOLUTION_PATHS,
    LINDEMANN_RHO,
    RESOLUTION_CONE_TOL,
    biso_melting_bound,
    check_biso_plausible,
    check_hump_width,
    check_resolution_positive,
    check_resolution_supported,
)
from tests.test_schemas import make_lab6

#: the configuration from PR #115's review — every value schema-legal
#: (u ∈ [-0.05, 1], v ∈ [-0.5, 0.5], w ∈ [1e-8, 1]) and the quadratic negative
#: across an ordinary scan.
COLLAPSED = {"u": 0.05, "v": -0.5, "w": 0.001}

#: a real lab resolution function. V is **negative**, which is the usual sign
#: of a focusing geometry and exactly what this guard must not report.
HEALTHY_NEGATIVE_V = {"u": 0.02, "v": -0.012, "w": 0.008}


#: the test fixture's own wavelength; nothing here depends on its value.
WAVELENGTH = 1.5406


def _state(*, u=0.0, v=0.0, w=1e-3, lo=15.0, hi=110.0, step=0.05):
    """A compiled LaB6 model over a flat pattern at a given resolution."""
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = None      # declared, never inherited
    ins.profile.u.value = u
    ins.profile.v.value = v
    ins.profile.w.value = w
    tt = np.arange(lo, hi, step)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 200.0).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return table, model


# ----------------------------------------------------------------------
# item 3 — the resolution function is a variance
# ----------------------------------------------------------------------
def test_the_collapsed_resolution_function_is_reported():
    """The motivating configuration, and what it actually does.

    The issue described the collapse as happening "at 157°". It happens
    everywhere: the quadratic's roots sit at 0.229° and 168.577° 2θ, so Γ_G²
    is negative at every point of an ordinary scan and Γ_G is the 1e-4° floor
    throughout.
    """
    table, model = _state(**COLLAPSED)
    findings = check_resolution_positive(table, model)

    assert [f.code for f in findings] == ["RESOLUTION_NOT_POSITIVE"]
    finding = findings[0]
    assert finding.paths == ("instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.w")
    assert finding.value < 0.0
    # every fitted point, not a high-angle tail
    assert f"{model.tt.size} of {model.tt.size} fitted points" in str(finding)

    # and the forward model really is reporting the floor rather than raising
    gamma = np.asarray(gaussian_fwhm(0.5 * model.tt, **COLLAPSED))
    assert np.allclose(gamma, _MIN_GAMMA_G2 ** 0.5)


def test_a_negative_v_on_a_healthy_instrument_is_silent():
    """The guard's whole point: the constraint is coupled, not per-parameter.

    A negative V is ordinary on a focusing geometry. Reporting it would make
    the guard fire on most real lab instruments.
    """
    table, model = _state(**HEALTHY_NEGATIVE_V)
    tan = np.tan(np.radians(0.5 * model.tt))
    g2 = (HEALTHY_NEGATIVE_V["u"] * tan * tan
          + HEALTHY_NEGATIVE_V["v"] * tan + HEALTHY_NEGATIVE_V["w"])
    assert g2.min() > 0.0, "fixture no longer exercises a positive quadratic"

    assert check_resolution_positive(table, model) == []


def test_zero_is_inside_the_physical_set():
    """U = V = 0 with W on its floor is an instrument with almost no Gaussian
    broadening.

    W's floor is the clamp itself (WP-1938 D7), so Γ_G² sits exactly on it,
    and a fit can stop there.  A two-sided test would fire on it — the
    ``STEPHENS_CONE_TOL`` lesson (WP-0601) one seam over.
    """
    table, model = _state(u=0.0, v=0.0, w=_MIN_GAMMA_G2)
    assert check_resolution_positive(table, model) == []


def test_the_tolerance_is_relative_and_one_sided():
    """A dip of a few ulp is the two association orders disagreeing.

    ``gaussian_fwhm`` and this guard build the same quadratic in different
    orders, so the bar has to sit above their disagreement and below anything
    physical.
    """
    table, model = _state(u=0.0, v=0.0, w=_MIN_GAMMA_G2)
    tiny = -0.5 * RESOLUTION_CONE_TOL
    table.entries[table._paths["instrument.profile.w"]].value = tiny
    assert check_resolution_positive(table, model) == []

    table.entries[table._paths["instrument.profile.w"]].value = -1e-6
    assert [f.code for f in check_resolution_positive(table, model)] == [
        "RESOLUTION_NOT_POSITIVE"]


def test_the_guard_is_silent_without_a_model():
    """The ``check_stephens_positive`` convention: no fitted axis, no claim.

    The range is what makes the question answerable — a dip outside the
    measured angles is unobservable, and flagging it would be a claim the data
    cannot support.
    """
    table, _model = _state(**COLLAPSED)
    assert check_resolution_positive(table, None) == []


def test_the_range_is_the_fitted_one_not_all_of_theta():
    """A quadratic that only dips outside the scan is not this fit's problem."""
    # roots at 0.229 deg and 168.577 deg 2theta; a scan inside them is bad
    # everywhere, a scan is never outside both, so build the complement case
    # directly: positive over 15-110 deg, negative past the upper root.
    u, v, w = 0.05, -0.5, 0.001
    wide = _state(u=u, v=v, w=w, lo=15.0, hi=110.0)[1]
    tan = np.tan(np.radians(0.5 * wide.tt))
    assert (u * tan * tan + v * tan + w).max() < 0.0

    # the same coefficients over a range above the upper root are positive
    table, model = _state(u=u, v=v, w=w, lo=169.5, hi=175.0, step=0.05)
    tan = np.tan(np.radians(0.5 * model.tt))
    assert (u * tan * tan + v * tan + w).min() > 0.0
    assert check_resolution_positive(table, model) == []


def test_the_hump_guard_abstains_exactly_where_this_one_speaks():
    """The hand-off ``check_hump_width``'s docstring promises.

    It abstains when the instrument width has collapsed to the floor, saying
    the unphysical instrument "is a separate, more fundamental defect and not
    this guard's to name". Nothing named it until this guard. The two must not
    both be silent on the same model.
    """
    table, model = _state(**COLLAPSED)
    assert check_hump_width(table, model) == []  # abstains, declares nothing
    assert check_resolution_positive(table, model), "nobody named the defect"


def test_the_finding_reaches_the_diagnostics_with_its_three_paths():
    """Every guard Diagnostic carries its paths in ``where`` (root CLAUDE.md).

    All three, because the constraint is on the quadratic: a client offering
    "fix this" has to reach the coefficient that is wrong, and which one that
    is cannot be read off the sum.
    """
    from rietx.refine import _guard_diagnostics
    from rietx.strategy.staged import GuardReport

    table, model = _state(**COLLAPSED)
    report = GuardReport()
    report.nonpositive_resolution = check_resolution_positive(table, model)

    diags = [d for d in _guard_diagnostics(report)
             if d.code == "RESOLUTION_NOT_POSITIVE"]
    assert len(diags) == 1
    assert diags[0].level == "warning"
    assert diags[0].where == ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.w"]
    assert diags[0].value == pytest.approx(
        report.nonpositive_resolution[0].value)


# ----------------------------------------------------------------------
# item 2 — a large B is evidence about the model, so it is flagged not capped
# ----------------------------------------------------------------------
def test_the_bound_is_the_papers_arithmetic():
    """B_melt = 8π²ρ²(√2·v)^(2/3), Gilvarry (1956) eqs (1), (8) and (9).

    Written out here independently of the implementation, because the whole
    value of a quoted threshold is that it is the source's number and not a
    number that happens to look like it.
    """
    volume, n_atoms = 255.0, 30          # corundum, 8.50 Å³ per atom
    v = volume / n_atoms
    expected = 8.0 * np.pi ** 2 * LINDEMANN_RHO ** 2 * (np.sqrt(2.0) * v) ** (2 / 3)

    assert biso_melting_bound(volume, n_atoms) == pytest.approx(expected)
    assert biso_melting_bound(volume, n_atoms) == pytest.approx(4.57, abs=0.01)


def test_the_bound_moves_with_packing_so_no_constant_would_do():
    """A fixed threshold would be wrong at one end of the ordinary range.

    Over 8.5–22.4 Å³ per atom — corundum to NaCl, both perfectly ordinary —
    the bound moves by nearly a factor of two, which is why the guard computes
    it per phase instead of declaring a number.
    """
    corundum = biso_melting_bound(255.0, 30)
    nacl = biso_melting_bound(5.6402 ** 3, 8)
    assert corundum == pytest.approx(4.57, abs=0.01)
    assert nacl == pytest.approx(8.72, abs=0.01)
    assert nacl / corundum > 1.8


def test_a_degenerate_cell_gets_no_opinion():
    """No volume, no length scale, no claim — never a finding by accident."""
    assert biso_melting_bound(0.0, 5) == float("inf")
    assert biso_melting_bound(100.0, 0) == float("inf")


def test_an_ordinary_biso_is_silent_and_a_molten_one_is_reported():
    table, model = _state()
    bound = biso_melting_bound(4.1566 ** 3, 7)

    # the fixture's own starting B, an ordinary 0.5 Å²
    assert check_biso_plausible(table, model) == []

    path = "phases.0.atoms.0.biso"
    table.entries[table._paths[path]].value = 1.5 * bound
    findings = check_biso_plausible(table, model)
    assert [f.code for f in findings] == ["BISO_UNUSUALLY_LARGE"]
    assert findings[0].paths == (path,)
    assert findings[0].value == pytest.approx(1.5 * bound)
    assert "1.5× the" in str(findings[0])
    assert "Lindemann" in str(findings[0])


def test_with_no_ceiling_the_melting_bound_is_what_flags_a_large_b():
    """Why this guard exists at all, stated as a test.

    ``Atom.biso`` has no ceiling (WP-1534; it capped at 25 Å² before), so
    this flag is the only thing that remarks on a large B.  On every ordinary
    structure it fires below 10 Å², where the 25 Å² cap bounded nothing
    physical.
    """
    from rietx.schemas.common import Parameter
    from rietx.schemas.structure import Atom

    zero = Parameter(value=0.0)
    assert Atom(label="X", species="Si", x=zero, y=zero, z=zero).biso.max == float("inf")
    for volume, n_atoms in ((255.0, 30), (4.1566 ** 3, 7), (5.6402 ** 3, 8)):
        assert biso_melting_bound(volume, n_atoms) < 10.0


def test_the_biso_guard_is_silent_without_a_model():
    """The ``check_stephens_positive`` convention, again: no model, no claim."""
    table, _model = _state()
    table.entries[table._paths["phases.0.atoms.0.biso"]].value = 50.0
    assert check_biso_plausible(table, None) == []


def test_the_biso_finding_reaches_the_diagnostics():
    from rietx.refine import _guard_diagnostics
    from rietx.strategy.staged import GuardReport

    table, model = _state()
    table.entries[table._paths["phases.0.atoms.0.biso"]].value = 50.0
    report = GuardReport()
    report.large_biso = check_biso_plausible(table, model)

    diags = [d for d in _guard_diagnostics(report)
             if d.code == "BISO_UNUSUALLY_LARGE"]
    assert len(diags) == 1
    assert diags[0].level == "warning"
    assert diags[0].where == ["phases.0.atoms.0.biso"]
    assert diags[0].value == pytest.approx(50.0)


def test_a_negative_biso_is_reported_and_zero_is_not():
    """The low side, which a reader reaches by keeping a file's B < 0.  Zero
    is the default floor, where ``BOUND_HIT`` already speaks."""
    from rietx.refine import _guard_diagnostics
    from rietx.strategy.staged import GuardReport, check_biso_negative

    table, model = _state()
    path = "phases.0.atoms.0.biso"
    table.entries[table._paths[path]].value = 0.0
    assert check_biso_negative(table, model) == []
    assert check_biso_negative(table, None) == []

    table.entries[table._paths[path]].value = -0.16
    findings = check_biso_negative(table, model)
    assert [f.code for f in findings] == ["BISO_NEGATIVE"]
    assert findings[0].paths == (path,)
    assert findings[0].value == pytest.approx(-0.16)

    diags = _guard_diagnostics(GuardReport(negative_biso=findings))
    assert [(d.code, d.level, d.where) for d in diags] == [
        ("BISO_NEGATIVE", "warning", [path])]


# ----------------------------------------------------------------------
# item 5 — |ρ| = 1.000 is a rank statement, not a strong correlation
# ----------------------------------------------------------------------
def _guard_with(rho: float, threshold: float = 0.98):
    """A GuardReport from a real table whose first two free columns correlate."""
    from types import SimpleNamespace

    from rietx.strategy.staged import check_guards

    table = _state()[0]
    table.set_vary(["phases.0.cell.*", "phases.0.scale",
                    "instrument.zero_shift"], True)
    free = list(table.free_paths)
    assert len(free) >= 2, free
    corr = np.eye(len(free))
    corr[0, 1] = corr[1, 0] = rho
    outcome = SimpleNamespace(correlation=corr, jac=None, theta=table.x0())
    return check_guards(table, outcome, threshold, model=None), free[:2]


def test_the_threshold_is_the_precision_the_message_prints():
    """Not a chosen number: ρ is rendered to three decimals, so the bar is the
    half-width of that rounding and the claim is one the message can support.
    """
    assert FLAT_DIRECTION_RHO == 1.0 - 5e-4

    from rietx.strategy.staged import GuardFinding

    rendered = str(GuardFinding.correlation("a", "b", FLAT_DIRECTION_RHO))
    assert "ρ=+1.000" in rendered, "the bar and the format have drifted apart"
    just_under = str(GuardFinding.correlation("a", "b", FLAT_DIRECTION_RHO - 1e-4))
    assert "ρ=+0.999" in just_under


def test_a_strong_correlation_is_not_a_flat_direction():
    """ρ = 0.99 is what HIGH_CORRELATION is for, and nothing more is claimed."""
    report, _free = _guard_with(0.99)
    assert [f.code for f in report.high_correlations] == ["HIGH_CORRELATION"]
    assert report.flat_directions == []


def test_a_flat_direction_is_reported_beside_its_correlation():
    """Beside, never instead: the SEQUENTIAL_PERSISTENT_FINDING precedent.

    Replacing the row would silence a HIGH_CORRELATION that existing consumers
    count, so the sharper finding rides alongside the one it sharpens.
    """
    report, free = _guard_with(-1.0)
    assert [f.code for f in report.high_correlations] == ["HIGH_CORRELATION"]
    assert [f.code for f in report.flat_directions] == ["FLAT_DIRECTION"]

    flat = report.flat_directions[0]
    assert flat.paths == (free[0], free[1])
    assert flat.value == pytest.approx(-1.0)
    assert "does not separate them" in str(flat)


def test_the_sign_is_kept_because_a_domain_label_is_not_a_magnitude():
    """ρ = −1.000 and ρ = +1.000 are the same rank statement, and the sign
    still says which way the two move together. It is reported, not discarded.
    """
    minus = _guard_with(-1.0)[0].flat_directions[0]
    plus = _guard_with(1.0)[0].flat_directions[0]
    assert minus.value < 0 < plus.value
    assert "-1.000" in str(minus) or "−1.000" in str(minus)


def test_the_flat_finding_reaches_the_diagnostics():
    from rietx.refine import _guard_diagnostics

    report, free = _guard_with(-1.0)
    diags = [d for d in _guard_diagnostics(report) if d.code == "FLAT_DIRECTION"]
    assert len(diags) == 1
    assert diags[0].level == "warning"
    assert diags[0].where == [free[0], free[1]]
    assert "ρ=-1.000" in diags[0].message


def test_the_two_codes_do_not_evict_each_other_in_the_dedup():
    """Both are keyed by pair; before WP-1311 the key was the pair alone.

    A flat pair produces one of each, so a pair-only key would have dropped
    whichever arrived second and the loss would be silent.
    """
    from rietx.refine import _dedup_high_correlations
    from rietx.schemas.results import Diagnostic

    where = ["instrument.profile.axial_sl", "instrument.profile.axial_hl"]
    hits = {
        ("HIGH_CORRELATION", frozenset(where)): [
            ("widths", Diagnostic(level="warning", code="HIGH_CORRELATION",
                                  message="hi", where=where, value=-1.0))],
        ("FLAT_DIRECTION", frozenset(where)): [
            ("widths", Diagnostic(level="warning", code="FLAT_DIRECTION",
                                  message="flat", where=where, value=-1.0))],
    }
    codes = sorted(d.code for d in _dedup_high_correlations(hits))
    assert codes == ["FLAT_DIRECTION", "HIGH_CORRELATION"]


def test_each_pair_keyed_code_is_capped_on_its_own_budget():
    """Finding 9 of this WP's review pass: FLAT_DIRECTION bypassed the cap.

    Every flat pair emits both codes at |ρ| ≈ 1, so a shared budget would have
    them evict each other on a key that cannot separate them. Separate budgets
    mean each list is bounded and neither decides the other's contents.
    """
    from rietx.schemas.results import (
        HIGH_CORRELATION_MAX,
        Diagnostic,
        _cap_high_correlation,
    )

    n = HIGH_CORRELATION_MAX + 4
    rows = []
    for i in range(n):
        pair = [f"a.{i}", f"b.{i}"]
        rows.append(Diagnostic(level="warning", code="HIGH_CORRELATION",
                               message=f"hc{i}", where=pair, value=-1.0))
        rows.append(Diagnostic(level="warning", code="FLAT_DIRECTION",
                               message=f"fd{i}", where=pair, value=-1.0))

    capped = _cap_high_correlation(rows)
    codes = [d.code for d in capped]
    assert codes.count("HIGH_CORRELATION") == HIGH_CORRELATION_MAX
    assert codes.count("FLAT_DIRECTION") == HIGH_CORRELATION_MAX
    assert codes.count("HIGH_CORRELATION_OMITTED") == 1
    assert codes.count("FLAT_DIRECTION_OMITTED") == 1

    omitted = {d.code: d.value for d in capped if d.code.endswith("_OMITTED")}
    assert omitted["HIGH_CORRELATION_OMITTED"] == pytest.approx(4.0)
    assert omitted["FLAT_DIRECTION_OMITTED"] == pytest.approx(4.0)


def test_the_cap_leaves_a_short_list_alone():
    """Below the budget nothing is rewritten, and no OMITTED row appears."""
    from rietx.schemas.results import Diagnostic, _cap_high_correlation

    rows = [Diagnostic(level="warning", code="FLAT_DIRECTION",
                       message="fd", where=["a", "b"], value=-1.0)]
    assert _cap_high_correlation(rows) == rows


# ----------------------------------------------------------------------
# item 4 (#102) — U, V, W refined on data that does not determine them
# ----------------------------------------------------------------------
def _resolution_state(*, u, v, w, x, y, free=True):
    """A compiled model at a given resolution, with U, V, W freed or held."""
    table, model = _state(u=u, v=v, w=w)
    table.entries[table._paths["instrument.profile.x"]].value = x
    table.entries[table._paths["instrument.profile.y"]].value = y
    if free:
        table.set_vary(list(GAUSSIAN_RESOLUTION_PATHS), True)
    return table, model


#: a high-resolution synchrotron line: narrow, and Lorentzian-dominated, which
#: is the character McCusker's § Synchrotron warns about by name.
SYNCHROTRON = dict(u=1e-4, v=-5e-5, w=2e-5, x=8e-3, y=2e-3)

#: a constant-wavelength neutron instrument: broad and Gaussian-dominated,
#: where the same paper says U, V and W "are easily determined".
CW_NEUTRON = dict(u=0.15, v=-0.20, w=0.12, x=1e-4, y=1e-4)


def test_the_synchrotron_case_the_paper_names_is_reported():
    table, model = _resolution_state(**SYNCHROTRON)
    findings = check_resolution_supported(table, model)

    assert [f.code for f in findings] == ["RESOLUTION_UNCONSTRAINED"]
    finding = findings[0]
    assert finding.paths == GAUSSIAN_RESOLUTION_PATHS
    assert 0.0 < finding.value < 0.5, "the Gaussian should carry the minority"
    assert "predominantly Lorentzian" in str(finding)
    assert "U, V, W" in str(finding)


def test_a_neutron_instrument_is_silent():
    """The other half of the same paragraph, and the reason there is no
    threshold on width here: on a CW neutron instrument the profile is
    Gaussian-dominated and the same three parameters are well determined, so
    a size test would have to be wrong for one technique or the other.
    """
    table, model = _resolution_state(**CW_NEUTRON)
    assert check_resolution_supported(table, model) == []


def test_holding_the_profile_is_the_remedy_not_the_fault():
    """The paper's own prescription is to fix them at the instrumental values.

    Firing on a held profile would flag the remedy, which is the failure mode
    WP-1073 hit when a geometry-blind map suggested a force-fixed parameter.
    """
    table, model = _resolution_state(**SYNCHROTRON, free=False)
    assert not any(p in set(table.free_paths) for p in GAUSSIAN_RESOLUTION_PATHS)
    assert check_resolution_supported(table, model) == []


def test_freeing_one_of_the_three_names_that_one():
    table, model = _resolution_state(**SYNCHROTRON, free=False)
    table.set_vary(["instrument.profile.w"], True)
    findings = check_resolution_supported(table, model)
    assert findings[0].paths == ("instrument.profile.w",)
    assert str(findings[0]).startswith("W refined on")


def test_the_guard_is_silent_without_a_model_or_a_free_term():
    table, model = _resolution_state(**SYNCHROTRON)
    assert check_resolution_supported(table, None) == []

    held, model_held = _resolution_state(**SYNCHROTRON, free=False)
    assert check_resolution_supported(held, model_held) == []


def test_the_verdict_tracks_the_majority_across_the_boundary():
    """"Predominantly" is a comparison, so the guard must agree with the
    majority it claims to be reading, on both sides of the crossing.

    Asserted against an independent count rather than against the guard's own
    source: a test that reads the implementation cannot fail when the
    implementation is wrong (tests/CLAUDE.md, the guards that go quiet).
    """
    from rietx.model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm

    seen = set()
    for x in (1e-4, 1e-3, 8e-3, 2e-2, 5e-2, 0.08, 0.12, 0.2, 0.4):
        table, model = _resolution_state(u=0.02, v=-0.012, w=0.008,
                                         x=x, y=0.0)
        theta = 0.5 * model.tt
        g = np.asarray(gaussian_fwhm(theta, 0.02, -0.012, 0.008))
        lo = np.asarray(lorentzian_fwhm(theta, x, 0.0))
        majority_lorentzian = int((lo > g).sum()) * 2 > model.tt.size

        fired = bool(check_resolution_supported(table, model))
        assert fired == majority_lorentzian, (
            f"x={x}: guard said {fired}, the count says {majority_lorentzian}")
        seen.add(majority_lorentzian)

    assert seen == {True, False}, "the sweep never crossed the boundary"


def test_a_tied_term_cannot_buy_silence():
    """``moving_paths``, never ``free_paths`` (root CLAUDE.md).

    A tie carries its coefficient on the free column it follows, so a term
    reaching the fit through one is refined on this pattern without ever being
    a column of θ. It is exactly as undetermined as a free one, so asking which
    entries are *columns* would let a tie hide the very case this guard is for.
    """
    table, model = _resolution_state(**SYNCHROTRON, free=False)
    table.set_vary(["instrument.profile.v"], True)

    # tie U to the free V: U is now not a column, but it moves
    from rietx.params.vector import AffineTie

    table.set_tie("instrument.profile.u",
                  AffineTie(terms=(("instrument.profile.v", 1.0),), const=0.0))
    assert "instrument.profile.u" not in set(table.free_paths)
    assert "instrument.profile.u" in set(table.moving_paths)

    findings = check_resolution_supported(table, model)
    assert [f.code for f in findings] == ["RESOLUTION_UNCONSTRAINED"]
    assert "instrument.profile.u" in findings[0].paths


def test_the_finding_reaches_the_diagnostics_naming_the_remedy():
    from rietx.refine import _guard_diagnostics
    from rietx.strategy.staged import GuardReport

    table, model = _resolution_state(**SYNCHROTRON)
    report = GuardReport()
    report.unsupported_resolution = check_resolution_supported(table, model)

    diags = [d for d in _guard_diagnostics(report)
             if d.code == "RESOLUTION_UNCONSTRAINED"]
    assert len(diags) == 1
    assert diags[0].where == list(GAUSSIAN_RESOLUTION_PATHS)
    # the remedy the paper prescribes, named as the workflow that implements it
    assert "lab_calibrate" in diags[0].suggestion
    assert "load_instrument_profile" in diags[0].suggestion


# ----------------------------------------------------------------------
# WP-2002: the occupancy has no ceiling, and a flag meets a value above 1
# ----------------------------------------------------------------------
def _lab6_with_occupancy(occ_true: float):
    """A synthetic LaB6 pattern whose La site scatters as ``occ_true`` La."""
    import rietx as rx

    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    structure.phases[0].atoms[0].occ.value = occ_true
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = None      # declared, never inherited
    tt = np.arange(15.0, 110.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 20.0
    rng = np.random.default_rng(3)
    data = PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())
    start = make_lab6()
    start.phases[0].scale.value = 3e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = None
    return rx.Refinement(start, ins, history=False), data


def test_an_occupancy_above_one_refines_and_is_reported():
    """The B9 ruling end to end: "Unlimited occupancy is fine.  We can give a
    warning."  A La site scattering as 2.2 La, the mineralogist's Fe-on-Mg
    number, refines past the old 1.5 ceiling to its value, and the result says
    so, naming the path and the value.  Measured 2026-10-20, darwin/arm64
    ``[dev]``: 2.251 ± 0.055."""
    import rietx as rx

    ref, data = _lab6_with_occupancy(2.2)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("occ", ["phases.0.atoms.0.occ"])])
    result = ref.fit(data, plan=plan)
    occ = result.parameter("phases.0.atoms.0.occ")
    assert occ.value > 1.5 and occ.at_bound is not True
    assert occ.value == pytest.approx(2.2, abs=4 * occ.stderr)
    [flag] = [d for d in result.diagnostics if d.code == "OCCUPANCY_ABOVE_ONE"]
    # an info record: noise alone puts a free full site above 1 half the time
    assert (flag.level, flag.where, flag.value) == (
        "info", ["phases.0.atoms.0.occ"], occ.value)
    assert "esd above a full site" in flag.message
    assert "site scattering" in flag.suggestion


def test_the_occupancy_flag_is_silent_at_one_and_on_a_held_value():
    """Strictly above 1, and only an occupancy the fit moved: a held value is
    the caller's own statement."""
    from rietx.refine import _occupancy_flag_diagnostics

    structure = make_lab6()
    path = "phases.0.atoms.0.occ"
    assert _occupancy_flag_diagnostics({path: 1.0}, {path}, structure) == []
    assert _occupancy_flag_diagnostics({path: 1.2}, set(), structure) == []
    [above] = _occupancy_flag_diagnostics({path: 1.2}, {path}, structure,
                                          {path: 0.05})
    assert above.value == 1.2 and "4.0 esd above a full site" in above.message
    # no esd to quote: the plain statement
    [plain] = _occupancy_flag_diagnostics({path: 1.2}, {path}, structure)
    assert "more than a full site" in plain.message
