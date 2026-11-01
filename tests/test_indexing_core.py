"""WP-1020 — the Q-space core: the quadratic form, the subspaces, the FoM panel.

Three of these tests are the WP's own acceptance criteria and are written to fail
loudly rather than drift:

* the **derived** metric-subspace dimensions must equal the cell degrees of
  freedom ``params.vector`` has tabulated since v0.1 — the derivation has to
  reproduce the tabulation, or one of the two is wrong;
* recovery of (A..F) from true assignments must be **exact** (1e-10), which is
  the linearity claim the whole design rests on, checked rather than asserted;
* a **paired** figure-of-merit test: M₂₀ is invariant under a unimodular setting
  change, and F_N is explicitly *not* invariant under a zero shift.  The second
  half turns a documented blind spot into a tested one, which is the only way a
  blind spot stays true.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.crystallography.lattice import cell_volume
from rietx.crystallography.symmetry import cell_constraints, generate_reflections, get_spacegroup
from rietx.indexing.fom import (
    FOM_N,
    borda_scores,
    f_n,
    fom_panel,
    fom_panel_disagrees,
    indexed_fraction,
    lattice_group,
    m20,
    match_lines,
    predicted_lines,
    predicted_seen_fraction,
)
from rietx.indexing.qspace import (
    af_from_cell,
    cell_esds,
    cell_from_af,
    cell_jacobian,
    design_matrix,
    metric_basis,
    refine_candidate,
    sigma_effective,
)
from rietx.schemas.indexing import (
    METRIC_DOF,
    PEAK_MIN_USABLE_LINES,
    FigureOfMerit,
    q_esd_of_two_theta,
    q_of_two_theta,
)

LAM = 1.5405929
CELLS = {
    "cubic": ("P m -3 m", (4.1566, 4.1566, 4.1566, 90.0, 90.0, 90.0)),
    "tetragonal": ("P 4/m m m", (3.7842, 3.7842, 9.5146, 90.0, 90.0, 90.0)),
    "hexagonal": ("P 6/m m m", (9.4166, 9.4166, 6.8745, 90.0, 90.0, 120.0)),
    "trigonal": ("P -3 m 1", (4.7591, 4.7591, 12.9894, 90.0, 90.0, 120.0)),
    "orthorhombic": ("P m m m", (7.0, 8.0, 9.0, 90.0, 90.0, 90.0)),
    "monoclinic": ("P 1 2/m 1", (8.875, 16.408, 7.137, 90.0, 93.84, 90.0)),
    "triclinic": ("P -1", (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)),
}


def _lines(system: str, two_theta_max: float = 90.0):
    """(hkl, Q, 2θ) of a known cell — the assignment an engine would produce."""
    sg, cell = CELLS[system]
    refl = generate_reflections(sg, cell, LAM, two_theta_max)
    q = 1.0 / np.asarray(refl.d) ** 2
    order = np.argsort(q)
    q = q[order]
    tt = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q) / 2.0))
    return np.asarray(refl.hkl)[order], q, tt, cell


# ----------------------------------------------------------------------
# The quadratic form and its subspaces
# ----------------------------------------------------------------------
def test_metric_subspace_matches_the_refinement_sides_cell_constraints():
    """The derived subspace must reproduce ``cell_constraints``'s cell ties.

    Two independent statements of the same crystallography: the refinement side
    ties b←a and fixes angles per setting, while indexing derives the invariant
    metric directions from the operators by exact rational algebra.  If they ever
    disagree, one of them is wrong — and the derivation is the one that stays
    right in a non-standard setting.

    **The dimension is checked last and on its own is worthless** (WP-1036).
    Before that WP this test compared ``6 − len(ties) − len(fixed)`` against
    ``METRIC_DOF`` and nothing else, and it passed while ``params.vector`` held
    the wrong angle for a c-unique monoclinic symbol (4 free either way) and the
    wrong lengths for a rhombohedral-axes R group (2 either way).  So the real
    assertion is the one below it: the cell each setting's constraints *describe*
    has its metric inside the derived span, and a cell that breaks one of those
    constraints falls outside it.
    """
    for system, dof in METRIC_DOF.items():
        symbol, cell = CELLS[system]
        constraints = cell_constraints(get_spacegroup(symbol))
        basis = metric_basis(system)

        names = ("a", "b", "c", "alpha", "beta", "gamma")
        values = dict(zip(names, cell))
        for dependent, source in constraints.ties.items():
            assert values[dependent] == values[source], (
                f"{system}: the fixture cell violates its own tie "
                f"{dependent}←{source}")
        for angle, target in constraints.fixed_angles.items():
            assert values[angle] == target, (
                f"{system}: fixture {angle}={values[angle]}, symmetry says {target}")

        af = af_from_cell(cell)
        coef, *_ = np.linalg.lstsq(basis.T, af, rcond=None)
        assert np.allclose(basis.T @ coef, af, atol=1e-12), (
            f"{system}: a cell obeying cell_constraints lies outside metric_basis")

        # and a cell that breaks a constraint must leave the span, or the
        # subspace is not constraining what the tie claims it constrains
        for name in names:
            if name not in constraints.ties and name not in constraints.fixed_angles:
                continue
            broken = dict(values)
            broken[name] = values[name] * 1.03 if name in ("a", "b", "c") \
                else values[name] + 3.0
            af_bad = af_from_cell(tuple(broken[k] for k in names))
            coef, *_ = np.linalg.lstsq(basis.T, af_bad, rcond=None)
            assert not np.allclose(basis.T @ coef, af_bad, atol=1e-9), (
                f"{system}: breaking {name} stays inside metric_basis, so the "
                f"constraint on it is not the one the subspace encodes")

        assert basis.shape[0] == dof, f"{system}: derived {basis.shape[0]}, METRIC_DOF {dof}"


def test_metric_basis_is_integer_and_spans_the_true_cell():
    """The basis is an exact integer nullspace, and the true metric lies in it."""
    for system, (_sg, cell) in CELLS.items():
        basis = metric_basis(system)
        assert np.allclose(basis, np.round(basis))
        af = af_from_cell(cell)
        # projection onto the subspace must return the vector itself
        coef, *_ = np.linalg.lstsq(basis.T, af, rcond=None)
        assert np.allclose(basis.T @ coef, af, atol=1e-12), system


def test_design_matrix_reproduces_inv_d_squared():
    """``M @ (A..F)`` is the same number ``inv_d_squared`` computes."""
    for system in CELLS:
        hkl, q, _tt, cell = _lines(system)
        got = design_matrix(hkl) @ af_from_cell(cell)
        assert np.allclose(got, q, rtol=1e-12)


def test_exact_linear_recovery_of_the_metric():
    """**The linearity claim, checked.**  With true assignments and no noise the
    solve is exact — 1e-10 on the cell — in every system."""
    for system in CELLS:
        hkl, q, tt, cell = _lines(system)
        fit = refine_candidate(q, np.full_like(q, 1e-6), hkl, system=system)
        assert np.allclose(fit.cell, cell, atol=1e-10), (
            f"{system}: {fit.cell} against {cell}")
        assert fit.chi2_red < 1e-12
        assert fit.volume == pytest.approx(float(cell_volume(*cell)), rel=1e-12)


def test_cell_jacobian_is_analytic_and_agrees_with_finite_differences():
    """∂cell/∂(A..F) by hand against central differences — the delta-method
    covariance is used to *decide* cell equality, so its accuracy is part of a
    decision rather than of a report."""
    for system, (_sg, cell) in CELLS.items():
        af = af_from_cell(cell)
        ana = cell_jacobian(af)
        fd = np.zeros((6, 6))
        for p in range(6):
            h = 1e-8 * max(abs(af[p]), 1e-3)
            lo, hi = af.copy(), af.copy()
            lo[p] -= h
            hi[p] += h
            fd[:, p] = (np.array(cell_from_af(hi))
                        - np.array(cell_from_af(lo))) / (2.0 * h)
        scale = np.maximum(np.abs(fd), 1e-6)
        assert np.max(np.abs(ana - fd) / scale) < 1e-4, system


def test_non_positive_definite_metric_raises():
    """A metric with a non-positive eigenvalue is not a lattice, and an engine
    that has wandered there is told rather than handed a NaN cell."""
    with pytest.raises(ValueError, match="not a lattice"):
        cell_from_af(np.array([1.0, -1.0, 1.0, 0.0, 0.0, 0.0]))


def test_cell_esds_scale_with_the_input_covariance():
    hkl, q, _tt, cell = _lines("orthorhombic")
    af = af_from_cell(cell)
    cov = np.diag(np.full(6, 1e-10))
    esd_a = cell_esds(af, cov)
    esd_b = cell_esds(af, 4.0 * cov)
    assert np.allclose(esd_b, 2.0 * esd_a, rtol=1e-12)
    assert np.all(esd_a[:3] > 0)


def test_sigma_effective_adds_the_systematic_in_quadrature():
    hkl, q, tt, cell = _lines("cubic")
    esd = q_esd_of_two_theta(tt, np.full_like(tt, 0.002), LAM)
    plain = sigma_effective(esd, tt, LAM, 0.0)
    floored = sigma_effective(esd, tt, LAM, 0.002)
    assert np.allclose(plain, esd)
    assert np.allclose(floored, np.sqrt(2.0) * esd, rtol=1e-12)


# ----------------------------------------------------------------------
# The shift column
# ----------------------------------------------------------------------
@pytest.mark.parametrize("template,amplitude", [
    ("constant", 0.05),
    ("cos_theta", 0.08),
    ("sin_2theta", 0.04),
])
def test_shift_column_recovers_an_injected_aberration(template, amplitude):
    """A candidate refined with the wrong positions gets the *wrong cell*; with
    the shift column it gets both back.

    The size of the effect is the point: 0.05-0.08° is small next to a FWHM and
    large next to σ(2θ), so the cell moves by far more than its esd if the shift
    is ignored.  That is why WP-1019's template choice is carried into the
    candidate refinement rather than left as a report field.
    """
    from rietx.indexing.quality import shift_template_basis

    hkl, q, tt, cell = _lines("monoclinic", two_theta_max=110.0)
    shifted = tt + amplitude * shift_template_basis(tt)[template]
    q_shift = q_of_two_theta(shifted, LAM)
    esd = q_esd_of_two_theta(shifted, np.full_like(shifted, 0.002), LAM)

    naive = refine_candidate(q_shift, esd, hkl, system="monoclinic")
    assert np.max(np.abs(np.array(naive.cell[:3]) - np.array(cell[:3]))) > 1e-3

    fixed = refine_candidate(q_shift, esd, hkl, system="monoclinic",
                             two_theta=shifted, wavelength=LAM,
                             shift_template=template)
    assert fixed.shift_coefficient == pytest.approx(amplitude, rel=2e-3)
    assert np.allclose(fixed.cell, cell, atol=2e-5)
    assert fixed.chi2_red < naive.chi2_red
    assert fixed.shift_esd > 0.0


def test_underdetermined_system_raises_rather_than_returning_a_cell():
    hkl, q, _tt, _cell = _lines("triclinic")
    with pytest.raises(ValueError, match="cannot determine"):
        refine_candidate(q[:4], np.full(4, 1e-4), hkl[:4], system="triclinic")


@pytest.mark.parametrize("af", [
    (0.10842207029868996, 0.0, 0.020401079871357843, 0.0, 0.05444080748121834, 0.0),
    (0.1832223251700092, 0.0, 0.0204081229733431, 0.0, 0.09523818855212737, 0.0),
    (0.08118109359915754, 0.0, 0.020408111413012586, 0.0, 0.027210605492824242, 0.0),
])
def test_a_metric_direction_no_line_constrains_raises_whatever_the_rounding(af):
    """Twenty h0l lines leave a monoclinic B unconstrained, so the fit raises.

    The solve leaves B at about ±1e-17, not at 0.  A negative value was always
    refused as not positive definite; a positive one passed and returned
    all-NaN cell esds (macOS arm64: the first two rows), which a synthetic hR
    search with three impurity lines carried to spglib as ``symprec=nan``.
    The metrics are the dichotomy engine's, from that search.
    """
    hkl = np.array([(h, 0, ell) for h in range(-3, 4) for ell in range(0, 6)
                    if (h, ell) != (0, 0) and not (ell == 0 and h < 0)][:20])
    q = design_matrix(hkl) @ np.asarray(af)
    q = q * (1.0 + 1e-5 * np.sin(np.arange(len(q))))
    with pytest.raises(ValueError):
        refine_candidate(q, 1e-4 * q, hkl, system="monoclinic")


# ----------------------------------------------------------------------
# Figures of merit
# ----------------------------------------------------------------------
def _panel_inputs(system: str = "cubic", two_theta_max: float = 90.0,
                  esd_deg: float = 0.005):
    hkl, q, tt, cell = _lines(system, two_theta_max)
    esd_tt = np.full_like(tt, esd_deg)
    return q, q_esd_of_two_theta(tt, esd_tt, LAM), tt, esd_tt, cell


def test_m20_is_finite_and_large_for_a_perfect_cell():
    """The precision floor, and why it is not an epsilon.

    ⟨ΔQ⟩ → 0 on a cell that fits within fp noise, so an unfloored M₂₀ is
    infinite and a zero-guarded one is **zero** — which ranks a perfect cell
    last.  Flooring at the median σ(Q) gives a large finite value whose size is
    set by the data's own precision.
    """
    q, q_esd, tt, esd_tt, cell = _panel_inputs()
    _hkl, q_pred = predicted_lines(cell, "cubic", "P", LAM, 90.0)
    got = m20(q, q_esd, q_pred)
    assert np.isfinite(got.value) and got.value > 100.0
    assert got.mean_discrepancy < float(np.median(q_esd))
    # ten times worse data, ten times smaller M20 — the floor is the precision
    coarse = m20(q, 10.0 * q_esd, q_pred)
    assert coarse.value == pytest.approx(got.value / 10.0, rel=1e-9)


def test_m20_is_invariant_under_a_unimodular_setting_change():
    """A setting change is not a different lattice, so no figure of merit may
    move.  M₂₀ lives in Q and the Q set is identical, so this is exact."""
    from rietx.indexing.ambiguity import transform_cell

    q, q_esd, tt, esd_tt, cell = _panel_inputs("triclinic")
    t = np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=np.int64)
    assert round(float(np.linalg.det(t))) == 1
    other = transform_cell(cell, t)

    _h1, q_a = predicted_lines(cell, "triclinic", "P", LAM, 90.0)
    _h2, q_b = predicted_lines(other, "triclinic", "P", LAM, 90.0)
    a, b = m20(q, q_esd, q_a), m20(q, q_esd, q_b)
    assert a.value == pytest.approx(b.value, rel=1e-9)
    assert a.n_possible == b.n_possible


def test_f_n_is_not_invariant_under_a_zero_shift():
    """The documented blind spot, made a test.

    F_N lives in 2θ, so shifting every observed position by a constant — exactly
    what an unmodelled zero-point error does — changes it, while a Q-space figure
    computed on the same lattice would report the mismatch.  A blind spot that is
    only documented is one refactor from being false.
    """
    q, q_esd, tt, esd_tt, cell = _panel_inputs()
    _hkl, q_pred = predicted_lines(cell, "cubic", "P", LAM, 90.0)
    tt_pred = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q_pred) / 2.0))

    honest = f_n(tt, esd_tt, tt_pred)
    shifted = f_n(tt + 0.05, esd_tt, tt_pred)
    assert shifted.value < 0.5 * honest.value
    assert shifted.mean_discrepancy > 10.0 * max(honest.mean_discrepancy, 1e-12)


def test_a_big_cell_indexes_everything_and_the_panel_says_so():
    """The measured §D failure, reproduced: ``indexed_fraction`` alone ranks a
    wrong cell **first**, and the panel with the reverse direction in it does not.

    The impostor here is a large triclinic cell plus three impurity lines the
    truth cannot index — which is the shape of the real case (a 390-line phase
    indexing 83.7 % of the observed intensity against the truth's 79.2 %).
    """
    # σ(2θ) = 0.02° — PeakList.from_positions' *assumed* value, i.e. exactly the
    # published-peak-list case §D was measured on.  The window a coarse σ opens is
    # what lets a large cell have a line near everything.
    q, q_esd, tt, esd_tt, cell = _panel_inputs(esd_deg=0.02)
    impurity_q = np.array([0.11, 0.27, 0.53])
    q_all = np.sort(np.concatenate([q, impurity_q]))
    esd_all = np.interp(q_all, q, q_esd)
    tt_all = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q_all) / 2.0))
    esd_tt_all = np.full_like(tt_all, 0.02)
    inten = np.linspace(100.0, 10.0, len(q_all))

    impostor = (12.4, 12.6, 13.1, 88.0, 92.0, 97.0)
    panels, indexed = [], []
    for candidate, system in ((cell, "cubic"), (impostor, "triclinic")):
        panels.append(fom_panel(q_all, esd_all, inten, tt_all, esd_tt_all,
                                candidate, system, "P", LAM))
        _h, q_pred = predicted_lines(candidate, system, "P", LAM,
                                     float(tt_all.max()))
        indexed.append(indexed_fraction(q_all, esd_all, q_pred).value)
        seen = predicted_seen_fraction(q_all, esd_all, q_pred).value
        print(f"{system}: indexed {indexed[-1]:.3f} seen {seen:.4f}")

    # the forward direction alone prefers the impostor …
    assert indexed[1] >= indexed[0]
    # … and the panel does not
    scores = borda_scores(panels)
    assert scores[0] > scores[1]
    assert fom_panel_disagrees(panels)


def test_the_matching_window_and_the_measurement_are_separate_inputs():
    """``q_match`` widens the coverage members and must not touch M₂₀ or F_N.

    WP-1026: the panel matched at the *fitted* σ while the engines that produced
    the candidates matched at σ ⊕ the systematic allowance, so on a pattern with an
    uncorrected displacement every candidate scored near zero coverage and was
    refuted by ``indexed_fraction_low`` whatever its merit.  The split is
    CLAUDE.md's rule one rank up: a fitted σ is the right *weight* and the wrong
    *matching window*.  M₂₀ and F_N use σ only to floor their mean discrepancy —
    a statement about what the measurement resolves — so an assumed allowance must
    never reach them.
    """
    # 120° so the list clears PEAK_MIN_USABLE_LINES (22 lines) and the classical
    # members are in the panel at all — WP-1043 drops them below twenty
    q, q_esd, tt, esd_tt, cell = _panel_inputs(two_theta_max=120.0,
                                               esd_deg=0.002)
    # every line displaced by 0.05° 2θ, which is 11 × the fitted σ: the corundum
    # regime, where the truth indexes nothing inside its own error bars
    tt_off = tt + 0.05
    q_off = q_of_two_theta(tt_off, LAM)
    inten = np.ones_like(q_off)
    q_match = sigma_effective(q_esd, tt_off, LAM, 0.05)

    tight = fom_panel(q_off, q_esd, inten, tt_off, esd_tt, cell, "cubic", "P", LAM)
    wide = fom_panel(q_off, q_esd, inten, tt_off, esd_tt, cell, "cubic", "P", LAM,
                     q_match=q_match)
    by_name = {f.name: f.value for f in tight}, {f.name: f.value for f in wide}
    assert by_name[0]["indexed_fraction"] < 0.1, by_name[0]["indexed_fraction"]
    assert by_name[1]["indexed_fraction"] > 0.9, by_name[1]["indexed_fraction"]
    assert by_name[1]["predicted_seen_fraction"] > by_name[0]["predicted_seen_fraction"]
    # the two classical figures are untouched: they never saw the window
    assert by_name[1]["m20"] == pytest.approx(by_name[0]["m20"])
    assert by_name[1]["f_n"] == pytest.approx(by_name[0]["f_n"])
    # and the default is the identity, which is what every published comparison uses
    assert [f.value for f in fom_panel(q_off, q_esd, inten, tt_off, esd_tt, cell,
                                       "cubic", "P", LAM, q_match=q_esd)] == \
        [f.value for f in tight]


def test_every_figure_of_merit_carries_its_blind_spot():
    # 120° so all seven members are present (22 lines ≥ PEAK_MIN_USABLE_LINES)
    q, q_esd, tt, esd_tt, cell = _panel_inputs(two_theta_max=120.0)
    panel = fom_panel(q, q_esd, np.ones_like(q), tt, esd_tt, cell, "cubic", "P",
                      LAM)
    assert [f.name for f in panel] == [
        "m20", "f_n", "indexed_fraction", "indexed_intensity_fraction",
        "predicted_seen_fraction", "m_rev", "m_sym"]
    for f in panel:
        assert isinstance(f, FigureOfMerit)
        assert f.blind_spot, f.name
        assert f.k_sigma > 0
    round_tripped = [FigureOfMerit.model_validate_json(f.model_dump_json())
                     for f in panel]
    assert [f.blind_spot for f in round_tripped] == [f.blind_spot for f in panel]


def test_below_twenty_lines_the_panel_shrinks_by_the_same_members_uniformly():
    """WP-1043: scoring is the panel's precondition, never the search's.

    Below :data:`PEAK_MIN_USABLE_LINES` the classical figures are not the
    published quantities (an M on 14 lines is not M₂₀), so they are **absent
    with a reason** — never computed at a different N, never silently zero —
    and the members that remain are the same for every candidate, which is
    what lets Borda still rank.
    """
    from rietx.indexing.fom import panel_undefined

    q, q_esd, tt, esd_tt, cell = _panel_inputs()          # 14 lines at 90°
    assert len(q) < PEAK_MIN_USABLE_LINES
    panel = fom_panel(q, q_esd, np.ones_like(q), tt, esd_tt, cell, "cubic", "P",
                      LAM)
    assert [f.name for f in panel] == [
        "indexed_fraction", "indexed_intensity_fraction",
        "predicted_seen_fraction", "m_rev", "m_sym"]

    undefined = panel_undefined(len(q))
    assert set(undefined) == {"m20", "f_n"}
    for reason in undefined.values():
        assert str(len(q)) in reason and str(PEAK_MIN_USABLE_LINES) in reason
    # at the bar, nothing is undefined and the panel is whole again
    assert panel_undefined(PEAK_MIN_USABLE_LINES) == {}


def test_the_laue_multiplicity_is_the_orbit_it_claims_to_count():
    """``laue_multiplicity`` is a fast rewrite of an existing definition, so it is
    checked **against that definition** and not against a table.

    ``crystallography.symmetry.reflection_orbits`` builds the orbit explicitly,
    one python set per reflection; this builds every orbit at once and counts by
    sorting an integer encoding.  A wrong encoding, a missed Friedel mate or a
    duplicated centring copy would all show up as a disagreement here — and each
    of them silently halves or doubles ``N^cal``, which both new figures divide
    by.
    """
    from rietx.crystallography.symmetry import reflection_orbits
    from rietx.indexing.fom import laue_multiplicity
    from rietx.indexing.qspace import trial_hkl

    rng = np.random.default_rng(1030)
    for system, centring in (("cubic", "P"), ("cubic", "F"), ("hexagonal", "P"),
                             ("trigonal", "R"), ("tetragonal", "I"),
                             ("orthorhombic", "C"), ("monoclinic", "P"),
                             ("triclinic", "P")):
        hkl = trial_hkl(4, centring)
        sub = hkl[rng.choice(len(hkl), size=min(60, len(hkl)), replace=False)]
        mine = laue_multiplicity(sub, system, centring)
        theirs = np.array([len(o) for o in reflection_orbits(
            lattice_group(system, centring), sub)])
        assert np.array_equal(mine, theirs), (system, centring)


def test_n_cal_counts_orbits_and_is_not_rounded():
    """Σ 1/m over a complete orbit is exactly 1, so ``N^cal`` over an orbit-closed
    enumeration is an **integer** — which is the self-check that catches a wrong
    multiplicity, since a halved or doubled m makes it fractional.

    It is stored and used as a float anyway, because the enumeration box is a cube
    in hkl and a hexagonal orbit does not preserve max|h| ((110) → (-120)), so a
    box can cut an orbit and a fraction is then the honest answer.
    """
    from rietx.indexing.fom import lattice_reflections, n_cal

    cell = (8.875, 16.408, 7.137, 90.0, 93.84, 90.0)
    _hkl, q, m = lattice_reflections(cell, "monoclinic", "P", LAM, 40.0,
                                     multiplicity=True)
    count = n_cal(q, m, 0.0, float(q.max()))
    # 000 is included exactly when the window reaches down to zero
    assert count == pytest.approx(round(count), abs=1e-9)
    assert n_cal(q, m, 0.0, float(q.max())) - n_cal(
        q, m, 1e-12, float(q.max())) == pytest.approx(1.0, abs=1e-9)
    # and it really is the orbit count: every reflection of one orbit shares a Q
    assert round(count) == len(np.unique(np.round(q, 12))) + 1


def test_the_reversed_figure_separates_a_supercell_far_harder_than_m20():
    """The reason Oishi-Tomiyasu (2013) is worth implementing at all.

    A supercell indexes every observed line, so the forward figures can only
    punish it through the *density* of lines it allows — and M₂₀ does that
    weakly.  ``M^Rev`` averages each **predicted** line's distance to the nearest
    observation with weight 1/m, so a cell predicting a forest of lines nobody
    saw is penalised in the numerator rather than the denominator.

    Measured here on a doubled orthorhombic axis: M₂₀ separates the truth from the
    supercell by **1.7-1.9×** and ``predicted_seen_fraction`` by 1.8-1.9×, while
    ``M^Rev`` separates them by **64-74×**.  The assertion is deliberately on the
    *ratio of margins*, not on the values, so it survives a change to either
    figure's floor.
    """
    truth = (7.0, 8.0, 9.0, 90.0, 90.0, 90.0)
    refl = generate_reflections("P m m m", truth, LAM, 45.0)
    tt = np.sort(np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d)))))
    q = q_of_two_theta(tt, LAM)
    q_esd = np.full(len(q), 1e-5)

    def panel(cell):
        return {f.name: f.value for f in
                fom_panel(q, q_esd, np.ones_like(q), tt, np.full(len(tt), 0.001),
                          cell, "orthorhombic", "P", LAM)}

    good = panel(truth)
    for label, super_cell in (("c×2", (7.0, 8.0, 18.0, 90.0, 90.0, 90.0)),
                              ("a×2", (14.0, 8.0, 9.0, 90.0, 90.0, 90.0))):
        bad = panel(super_cell)
        # the supercell really does index everything — that is the trap
        assert bad["indexed_fraction"] == pytest.approx(1.0), label
        m20_margin = good["m20"] / bad["m20"]
        rev_margin = good["m_rev"] / bad["m_rev"]
        assert 1.5 < m20_margin < 2.5, (label, m20_margin)
        assert rev_margin > 20.0 * m20_margin, (label, rev_margin, m20_margin)
        assert good["m_sym"] > bad["m_sym"], label


def test_lattice_group_is_absence_free_and_carries_the_centring():
    assert lattice_group("cubic") == "P m -3 m"
    assert lattice_group("cubic", "F") == "F m -3 m"
    assert lattice_group("trigonal", "R") == "R -3 m"
    with pytest.raises(ValueError):
        lattice_group("rhombic")
    # a centred lattice allows fewer lines than its primitive namesake
    _h1, q_p = predicted_lines((5.4309,) * 3 + (90.0,) * 3, "cubic", "P", LAM, 90.0)
    _h2, q_f = predicted_lines((5.4309,) * 3 + (90.0,) * 3, "cubic", "F", LAM, 90.0)
    assert len(q_f) < len(q_p)


def test_match_lines_uses_each_lines_own_sigma():
    """Per-line σ, not one global window — the contract the whole peak list
    exists to establish."""
    q_obs = np.array([0.10, 0.20])
    q_pred = np.array([0.1005, 0.2005])
    tight = np.array([1e-5, 1e-5])
    loose = np.array([1e-5, 1e-3])
    idx_tight, _ = match_lines(q_obs, tight, q_pred)
    idx_loose, _ = match_lines(q_obs, loose, q_pred)
    assert idx_tight.tolist() == [-1, -1]
    assert idx_loose.tolist() == [-1, 1]


def test_borda_shares_the_rank_of_tied_candidates():
    """**Ties must not be broken by array position** (found by WP-1021).

    Two of the five panel members are fractions that saturate at 1.0, so on a
    well-explained pattern most candidates tie on them.  The old
    ``argsort(argsort)`` gave tied entries distinct ranks in input order, injecting
    up to N−1 points of ordering noise per tied member — measured, that put two
    derivative lattices above a truth that beat them on *every* member.  Here the
    first candidate is better on one member and tied on the other; sharing the tie
    is the only way its single real win decides the ranking.
    """
    def panel(a, b):
        return [FigureOfMerit(name="x", value=a, n_lines=1, n_possible=1,
                              k_sigma=3.0),
                FigureOfMerit(name="y", value=b, n_lines=1, n_possible=1,
                              k_sigma=3.0)]

    scores = borda_scores([panel(2.0, 1.0), panel(1.0, 1.0), panel(1.0, 1.0)])
    assert scores[0] > scores[1]
    assert scores[1] == scores[2], "tied candidates must score equally"
    # a non-finite member ranks worst rather than best
    worst = borda_scores([panel(float("nan"), 1.0), panel(1.0, 1.0)])
    assert worst[0] < worst[1]


def _member(name, value):
    return FigureOfMerit(name=name, value=value, n_lines=1, n_possible=1,
                         k_sigma=3.0)


def test_the_log_sum_reads_the_margin_where_borda_reads_only_the_winner():
    """The NAC defect, reduced to its arithmetic (WP-1041).

    The measured shape on 11-BM NAC: the wrong candidate takes four members, two
    of them by 0.4 % and 0.01 %, and loses one by 516×.  Borda spends one whole
    point on a win of any size, so four hairlines outvote a rout.  These are
    those margins, not the NAC values — the acceptance row owns those.
    """
    from rietx.indexing.fom import _log_sum_scores

    names = ["a", "b", "c", "d", "e"]
    near_wins = [_member(n, v) for n, v in
                 zip(names, [1.004, 1.0001, 1.02, 1.01, 1.0])]
    one_rout = [_member(n, v) for n, v in
                zip(names, [1.0, 1.0, 1.0, 1.0, 516.0])]

    borda = borda_scores([near_wins, one_rout])
    assert borda[0] > borda[1], "the premise: Borda leads with the near-winner"

    logs = _log_sum_scores([near_wins, one_rout])
    assert logs[1] > logs[0], "the fix: one 516x separation outweighs four hairlines"


def test_a_raw_log_sum_weights_each_member_by_its_dynamic_range():
    """Why the log-sum is measured but **not wired** (WP-1041).

    Summing raw logs spends influence in proportion to how far a member's values
    spread across the candidate set, and the panel's members do not spread alike.
    This is certified corundum's shape, in the small: one candidate wins four
    members by the ~1.2-1.5× a bounded fraction can move, the other wins one
    wide-range member by 12×, and the wide member takes it — there on a subcell
    that could not index 12 of the observed lines.

    Borda gets this case *right* for the wrong reason (it cannot see margins at
    all), which is why the corpus scores them 5 of 6 apiece.  The trap to
    remember is that the fix is not "use magnitudes": it is that a margin is
    comparable **within** a member and not across members.
    """
    from rietx.indexing.fom import _log_sum_scores

    names = ["m20", "f_n", "indexed_fraction", "indexed_intensity_fraction",
             "m_rev"]
    broad_range_winner = [_member(n, v) for n, v in
                          zip(names, [15.32, 10.88, 0.7818, 0.8333, 29.99])]
    four_narrow_wins = [_member(n, v) for n, v in
                        zip(names, [22.52, 16.05, 0.9273, 0.9844, 2.483])]

    assert borda_scores([four_narrow_wins, broad_range_winner])[0] > \
        borda_scores([four_narrow_wins, broad_range_winner])[1], \
        "Borda counts four wins against one"

    logs = _log_sum_scores([four_narrow_wins, broad_range_winner])
    assert logs[1] > logs[0], (
        "one 12x win on the widest-ranging member outweighs four wins on "
        "members that cannot move that far — the measured corundum failure")


def test_the_log_sum_does_not_depend_on_any_members_units():
    """Rescaling a member shifts every candidate equally, so the order holds.

    This is the property that made *ranks* attractive and the reason a plain
    weighted sum was refused: the panel mixes a ratio, an inverse-degrees
    quantity and three fractions, and there is no data on which to set weights.
    A log-sum keeps unit-invariance and, unlike a rank, keeps the margin too.
    """
    from rietx.indexing.fom import _log_sum_scores

    rng = np.random.default_rng(1041)
    names = ["m20", "f_n", "indexed_fraction"]
    panels = [[_member(n, float(v)) for n, v in zip(names, row)]
              for row in rng.uniform(0.1, 40.0, size=(6, 3))]
    base = _log_sum_scores(panels)

    for k, factor in enumerate((1e-6, 3.5, 2.4e5)):
        scaled = [[_member(f.name, f.value * factor if i == k else f.value)
                   for i, f in enumerate(p)] for p in panels]
        moved = _log_sum_scores(scaled)
        assert np.argsort(-moved).tolist() == np.argsort(-base).tolist()
        # and the shift is the same constant for every candidate
        assert np.allclose(moved - base, np.log(factor))


def test_the_aggregate_drops_the_member_that_is_a_product_of_two_others():
    """``m_sym`` is ``M̃ₙ × M^Rev``, so in logs it re-adds ``m_rev`` exactly.

    Borda could not see this — a rank aggregation is blind to one member being a
    monotone function of others — so the exclusion arrives with the log-sum.

    The identity is **re-derived here from the module's public pieces** rather
    than read back off the value that computed it, because it is the whole
    argument for the exclusion.  Note the factor is ``M̃ₙ``, the forward figure on
    the *reversed* window and denominator — **not** the panel's ``m20``, which
    uses de Wolff's own window and the distinct-line count.  On this fp-exact
    fixture the two happen to coincide; on real data they do not (11-BM NAC:
    ``m_sym / m_rev`` = 1.15 against an ``m20`` of 1.43).
    """
    from rietx.indexing.fom import (
        _AGGREGATE_EXCLUDES,
        _log_sum_scores,
        lattice_reflections,
        n_cal,
        nearest_discrepancy,
        trimmed_mean,
    )

    assert _AGGREGATE_EXCLUDES == frozenset({"m_sym"})

    q, q_esd, tt, esd_tt, cell = _panel_inputs()
    panel = fom_panel(q, q_esd, np.ones_like(q), tt, esd_tt, cell, "cubic", "P",
                      LAM)
    by = {f.name: f.value for f in panel}
    assert by["m_rev"] > 0.0 and by["m_sym"] > 0.0

    # M̃ₙ, derived independently: same window, same 1/m denominator
    order = np.argsort(q)[:20]
    obs, esd = q[order], q_esd[order]
    _hkl, pred, mult = lattice_reflections(
        cell, "cubic", "P", LAM, float(np.max(tt)), multiplicity=True)
    q_i = float(pred[np.argmin(np.abs(pred - obs[0]))])
    q_n = float(pred[np.argmin(np.abs(pred - obs[-1]))])
    lo, hi = (q_i, q_n) if q_i <= q_n else (q_n, q_i)
    count = n_cal(pred, mult, lo, hi)
    delta_fwd = trimmed_mean(nearest_discrepancy(obs, pred), 0)
    tilde = ((q_n - q_i) / (2.0 * count)) / max(delta_fwd, float(np.median(esd)))

    assert by["m_sym"] == pytest.approx(tilde * by["m_rev"], rel=1e-9), (
        "m_sym is M̃ₙ x M^Rev by construction — that product is why keeping it "
        "in a log-sum counts the reversed direction twice")

    # and the aggregate acts on that: the member is absent from what it sums
    with_sym = [[*panel]]
    without = [[f for f in panel if f.name != "m_sym"]]
    assert _log_sum_scores(with_sym)[0] == pytest.approx(_log_sum_scores(without)[0])


def test_a_silent_member_does_not_collapse_every_score_to_minus_infinity():
    """A member every candidate scores zero on carries no information.

    Taking its log would send every score to ``-inf`` and destroy the ranking the
    other members had already decided, so it is skipped.  A zero on a member
    where *someone* scored still floors, and still ranks worst.
    """
    from rietx.indexing.fom import _log_sum_scores

    silent = [[_member("a", 0.0), _member("b", 2.0)],
              [_member("a", 0.0), _member("b", 1.0)]]
    scores = _log_sum_scores(silent)
    assert np.all(np.isfinite(scores))
    assert scores[0] > scores[1]

    floored = _log_sum_scores([[_member("a", 1.0)], [_member("a", 0.0)],
                              [_member("a", float("nan"))]])
    assert floored[0] > floored[1]
    assert floored[1] == pytest.approx(floored[2]), (
        "a zero and a figure that could not be computed are both 'worst'")


def test_predicted_lines_counts_distinct_lines_not_orbits():
    """A coincidence is one line (found by WP-1021).

    Cubic 333 and 511 both give Q = 27A: two orbits, one 2θ, one thing to observe.
    Counting them twice inflates every FoM denominator on exactly the
    high-symmetry large cells the panel has to judge — measured, 470 orbits
    against 208 distinct lines for a 17 Å cubic cell.  Low-symmetry cells have no
    coincidences to merge, and that asymmetry is what identifies the difference as
    coincidence rather than a different counting rule.
    """
    from rietx.crystallography.symmetry import generate_reflections

    for system, expect_fewer in (("cubic", True), ("triclinic", False)):
        sg, cell = CELLS[system]
        orbits = len(generate_reflections(sg, cell, LAM, 90.0).d)
        _hkl, q = predicted_lines(cell, system, "P", LAM, 90.0)
        assert (len(q) < orbits) is expect_fewer, system
        assert len(np.unique(np.round(q, 9))) == len(q), system


def test_the_figures_of_merit_tolerate_what_the_search_tolerated():
    """``n_unindexed`` is one number shared by the search and the score.

    Measured on a tetragonal list with one impurity line: with a plain mean the
    truth scored M₂₀ = 13.2 against 62.5 for an a√5 supercell whose extra
    reflections happen to cover the impurity, and the supercell won the ranking
    while showing 28 % of its own predicted lines against the truth's 100 %.
    Trimming the same one line the search was allowed to leave unindexed reverses
    it — and the trim is *reported*, because it buys a new blind spot.
    """
    q, q_esd, tt, esd_tt, cell = _panel_inputs("tetragonal", two_theta_max=70.0)
    q_all = np.sort(np.append(q, 0.1177))          # a line no lattice here indexes
    esd_all = np.interp(q_all, q, q_esd)
    _hkl, q_pred = predicted_lines(cell, "tetragonal", "P", LAM, 70.0)

    plain = m20(q_all, esd_all, q_pred)
    trimmed = m20(q_all, esd_all, q_pred, n_unindexed=1)
    assert trimmed.value > 3.0 * plain.value
    assert trimmed.mean_discrepancy < plain.mean_discrepancy
    assert "trimmed by 1 line" in trimmed.blind_spot
    assert "trimmed" not in plain.blind_spot


def test_fom_n_is_twenty_lines():
    """Both figures are scored on twenty lines; a longer list must not silently
    change the figure's meaning.

    Twenty is de Wolff's definition for M₂₀ and this package's own choice for
    F_N, which Smith & Snyder define for general N (WP-1436)."""
    q, q_esd, tt, esd_tt, cell = _panel_inputs("triclinic")
    assert len(q) > FOM_N
    _hkl, q_pred = predicted_lines(cell, "triclinic", "P", LAM, 90.0)
    assert m20(q, q_esd, q_pred).n_lines == FOM_N
    assert f_n(tt, esd_tt, tt).n_lines == FOM_N


def test_a_derived_candidate_cell_never_trips_the_symmetry_angle_check():
    """The indexer must not refuse its own answers (WP-1036).

    ``validate_by_lebail`` builds a ``ParameterTable`` from every candidate, and
    that now calls ``check_cell_angles``, which refuses a fixed angle more than
    ``SYMMETRY_ANGLE_TOL_DEG`` from the value symmetry demands.  The reason this
    is safe rather than lucky: ``refine_candidate`` solves A..F *inside*
    ``metric_basis``, so a derived cell satisfies its system's angle constraints
    to round-off — measured 1.4e-14 deg, a 7e10 margin on the 1e-3 deg bar.  A
    tolerance chosen anywhere near the conversion noise would turn every
    hexagonal candidate into a validation crash.
    """
    from rietx.crystallography.symmetry import SYMMETRY_ANGLE_TOL_DEG, check_cell_angles

    worst = 0.0
    for system, (symbol, cell) in CELLS.items():
        if system == "triclinic":
            continue  # nothing is fixed, so there is nothing to trip
        hkl, q, _tt, _cell = _lines(system)
        fit = refine_candidate(q, np.full_like(q, 1e-6), hkl, system=system)
        angles = dict(zip(("alpha", "beta", "gamma"), fit.cell[3:]))
        check_cell_angles(get_spacegroup(symbol), angles)  # must not raise
        for name, target in cell_constraints(
                get_spacegroup(symbol)).fixed_angles.items():
            worst = max(worst, abs(angles[name] - target))
    assert worst < SYMMETRY_ANGLE_TOL_DEG / 1e6, (
        f"derived angles deviate by {worst:.3e} deg, within a factor 1e6 of the "
        f"{SYMMETRY_ANGLE_TOL_DEG} deg bar — the margin this test exists to keep")
