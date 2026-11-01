"""v0.2 lab-instrument physics: Kα doublet, displacement/transparency, FCJ.

Fast unit/property tests; the SRM 660c real-data acceptance lives in
``test_acceptance_srm660c.py`` (marked slow).
"""

from functools import lru_cache

import numpy as np
import pytest

import rietx as rx
from rietx.model.corrections import displacement_shift_deg, transparency_shift_deg
from rietx.model.forward import compile_model
from rietx.model.profiles import fcj as fcj_module
from rietx.model.profiles.fcj import (
    fcj_extent_deg,
    fcj_node_count,
    fcj_offsets_weights,
)
from rietx.model.profiles.pseudovoigt import pseudo_voigt
from rietx.params.vector import ParameterTable

CU_KA1, CU_KA2 = 1.5405929, 1.5444274


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _lab6_phase(a: float = 4.1568) -> rx.Phase:
    return rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(a),
        atoms=[
            rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                    biso=rx.Parameter(value=0.36, min=0.0, max=25.0)),
            rx.Atom(label="B", species="B", x=rx.Parameter(value=0.198),
                    y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5),
                    biso=rx.Parameter(value=0.28, min=0.0, max=25.0)),
        ],
        scale=rx.Parameter(value=5e-5, min=0.0, transform="softplus"),
    )


def _lab_instrument(**kw) -> rx.Instrument:
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6, **kw)
    ins.profile.w.value = 2e-3
    ins.profile.x.value = 5e-3
    return ins


def _flat_pattern(lo=15.0, hi=90.0, step=0.02):
    tt = np.arange(lo, hi, step)
    return rx.PatternData(two_theta=tt.tolist(), intensity=np.full_like(tt, 10.0).tolist(),
                          sigma=np.full_like(tt, 1.0).tolist())


def _compiled(instrument=None, pattern=None, structure=None):
    structure = structure or rx.Structure(phases=[_lab6_phase()])
    instrument = instrument or _lab_instrument()
    pattern = pattern or _flat_pattern()
    model = compile_model(structure, instrument, pattern)
    table = ParameterTable(structure, instrument)
    return model, table.decode(table.x0())


# ---------------------------------------------------------------------------
# Kα1/Kα2 per-line Bragg dispersion
# ---------------------------------------------------------------------------

def test_doublet_positions_follow_bragg_dispersion():
    """Splitting must equal 2·tanθ·Δλ/λ (radians) — growing with angle, never
    a fixed offset."""
    model, values = _compiled()
    peaks = model.phase_peaks(0, values)
    assert len(peaks) == 2
    pos1, pos2 = peaks[0][0], peaks[1][0]
    split = pos2 - pos1
    theta = np.radians(pos1 / 2.0)
    expected = np.degrees(2.0 * np.tan(theta) * (CU_KA2 - CU_KA1) / CU_KA1)
    # the tanθ law is the first-order expansion of exact per-line Bragg
    # positions — agreement to ~0.2% over the range confirms the splitting is
    # dispersive, not a fixed Δ2θ
    assert np.allclose(split, expected, rtol=2e-3)
    # and it really grows: last in-range splitting ≫ first
    assert split[-1] > 2.0 * split[0]


def test_doublet_intensity_ratio_scales_ka2_only():
    model, values = _compiled()
    base = {**values, "instrument.source.lines.1.weight": 0.5}
    half = {**values, "instrument.source.lines.1.weight": 0.25}
    i1_base, i1_half = model.phase_peaks(0, base)[1][3], model.phase_peaks(0, half)[1][3]
    i0_base, i0_half = model.phase_peaks(0, base)[0][3], model.phase_peaks(0, half)[0][3]
    assert np.allclose(i1_half, 0.5 * i1_base)
    assert np.allclose(i0_half, i0_base)


def test_line0_weight_always_fixed():
    structure = rx.Structure(phases=[_lab6_phase()])
    instrument = _lab_instrument()
    instrument.source.lines[0].weight.vary = True  # user error: must be ignored
    table = ParameterTable(structure, instrument)
    assert "instrument.source.lines.0.weight" not in table.free_paths
    hits = table.set_vary(["instrument.source.lines.*.weight"], True)
    assert "instrument.source.lines.0.weight" not in hits
    assert "instrument.source.lines.1.weight" in hits


# ---------------------------------------------------------------------------
# the anode table (WP-0507)
# ---------------------------------------------------------------------------

#: Transcribed a second time, by hand, from the NIST X-ray Transition Energies
#: Database (SRD 128) "direct experimental" column — KL3 = Kα1, KL2 = Kα2 —
#: which is the Deslattes et al. (2003) evaluation.  Duplicating the table is
#: the point: a test that imported ``_RADIATIONS`` would assert nothing about
#: the transcription, only that a dict is a dict.
NIST_XRTE_DIRECT = {
    "CrKa": (2.2897260, 2.2936510),
    "FeKa": (1.9360410, 1.9399730),
    "CoKa": (1.7889960, 1.7928350),
    "CuKa": (1.5405929, 1.5444274),
    "MoKa": (0.70931715, 0.713607),
    "AgKa": (0.55942178, 0.5638131),
}


def test_every_anode_matches_its_cited_source():
    for name, (ka1, ka2) in NIST_XRTE_DIRECT.items():
        ins = rx.Instrument.bragg_brentano(radiation=name)
        got = [line.wavelength.value for line in ins.source.lines]
        assert got == [ka1, ka2], name


def test_cu_pair_is_unchanged_by_the_anode_extension():
    """The scale anchor.

    Every other anode is trusted because it comes from the *same column* of the
    same evaluation as Cu, and the Cu pair in that column is byte-for-byte the
    Hölzer (1997) peak values this package has shipped since v0.2 (the scale of
    the NIST SRM 660c certificate, which the acceptance suite refines against).
    If this fails, the table was re-sourced and every cell in ``tests/data``
    moved with it.
    """
    ins = rx.Instrument.bragg_brentano()
    assert [line.wavelength.value for line in ins.source.lines] == [CU_KA1, CU_KA2]
    # ...and specifically *not* Bearden (1967), the other scale in circulation
    assert ins.source.lines[0].wavelength.value != 1.540562


def test_doublet_splitting_grows_with_atomic_number():
    """Δλ/λ is the 2p spin-orbit splitting, which grows steeply with Z.

    A property no single value can check: it catches a row transcribed into the
    wrong anode, or a Kα1/Kα2 pair swapped, in a way per-value equality cannot
    (both would still be "some number near the right wavelength").
    """
    order = ["CrKa", "FeKa", "CoKa", "CuKa", "MoKa", "AgKa"]  # ascending Z
    rel = []
    for name in order:
        ka1, ka2 = NIST_XRTE_DIRECT[name]
        assert ka1 < ka2, f"{name}: Kα1 (KL3) is the higher-energy line"
        rel.append((ka2 - ka1) / ka1)
    assert rel == sorted(rel)
    assert rel[0] == pytest.approx(1.71e-3, rel=0.01)   # Cr
    assert rel[-1] == pytest.approx(7.85e-3, rel=0.01)  # Ag


def test_ka1_only_variants_are_derived_from_the_doublets():
    for name, (ka1, _) in NIST_XRTE_DIRECT.items():
        ins = rx.Instrument.bragg_brentano(radiation=f"{name}1")
        assert [line.wavelength.value for line in ins.source.lines] == [ka1]
        # the single line is line 0, hence structurally locked at weight 1
        assert ins.source.lines[0].weight.value == 1.0


def test_unknown_anode_lists_what_is_available():
    with pytest.raises(ValueError, match="unknown radiation 'NiKa'"):
        rx.Instrument.bragg_brentano(radiation="NiKa")
    with pytest.raises(ValueError, match="MoKa"):
        rx.Instrument.bragg_brentano(radiation="NiKa")


def test_doublet_defaults_hold_off_cu():
    """``ka2_ratio`` and the polarization default are anode-independent; the
    monochromator angle is not."""
    ins = rx.Instrument.bragg_brentano(radiation="MoKa", ka2_ratio=0.5)
    assert ins.source.lines[1].weight.value == 0.5   # 2j+1 degeneracy, any Z
    assert ins.source.polarization.value == 0.5      # unpolarized, no mono

    # graphite (002), d = 3.354 A: 2θ_m is a function of the anode, so the
    # 26.6° in the docstring is a *Cu* number and K moves with it
    for radiation, d in (("CuKa", 3.354), ("MoKa", 3.354)):
        lam = NIST_XRTE_DIRECT[radiation][0]
        tt_m = 2.0 * np.degrees(np.arcsin(lam / (2.0 * d)))
        ins = rx.Instrument.bragg_brentano(radiation=radiation,
                                           monochromator_two_theta=tt_m)
        k = 1.0 / (1.0 + np.cos(np.radians(tt_m)) ** 2)
        assert ins.source.polarization.value == pytest.approx(k)
    assert tt_m == pytest.approx(12.14, abs=0.02)     # Mo, vs 26.55 for Cu
    assert k == pytest.approx(0.511, abs=5e-4)


def test_off_cu_instrument_round_trips_through_json():
    ins = rx.Instrument.bragg_brentano(radiation="AgKa", goniometer_radius_mm=240.0)
    back = rx.Instrument.model_validate_json(ins.model_dump_json())
    assert [line.wavelength.value for line in back.source.lines] == \
        list(NIST_XRTE_DIRECT["AgKa"])
    assert back.geometry.goniometer_radius_mm == 240.0


def test_peaks_move_to_the_anode_wavelength():
    """The forward model uses the table, not a cached Cu number: the same phase
    on Mo Kα puts its first peak where Bragg's law says."""
    structure = rx.Structure(phases=[_lab6_phase()])
    ins = rx.Instrument.bragg_brentano(radiation="MoKa")
    ins.profile.w.value = 2e-3
    model, values = _compiled(instrument=ins, pattern=_flat_pattern(5.0, 60.0),
                              structure=structure)
    pos = model.phase_peaks(0, values)[0][0]
    lam = NIST_XRTE_DIRECT["MoKa"][0]
    expected = 2.0 * np.degrees(np.arcsin(lam / (2.0 * 4.1568)))  # LaB6 (100)
    assert pos[0] == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# Bragg-Brentano position aberrations
# ---------------------------------------------------------------------------

def test_displacement_shift_formula():
    # −(2s/R)·cosθ radians; s=+0.1 mm, R=217.5 mm, θ=15°
    got = displacement_shift_deg(np.array(15.0), 0.1, 217.5)
    expected = np.degrees(-2.0 * 0.1 / 217.5 * np.cos(np.radians(15.0)))
    assert np.isclose(float(got), expected)
    # cosθ signature: shrinks toward high angle
    assert abs(float(displacement_shift_deg(np.array(80.0), 0.1, 217.5))) < abs(expected)


def test_transparency_shift_formula():
    got = transparency_shift_deg(np.array(90.0), 1e-3)  # sin(2θ)=1 at 2θ=90
    assert np.isclose(float(got), np.degrees(-1e-3))
    assert np.isclose(float(transparency_shift_deg(np.array(180.0), 1e-3)), 0.0, atol=1e-12)


def test_displacement_moves_compiled_peaks():
    model, values = _compiled()
    pos0 = model.phase_peaks(0, values)[0][0]
    shifted = {**values, "instrument.geometry.sample_displacement": -0.08}
    pos1 = model.phase_peaks(0, shifted)[0][0]
    theta = np.radians(pos0 / 2.0)
    expected = np.degrees(-2.0 * (-0.08) / 217.5 * np.cos(theta))
    assert np.allclose(pos1 - pos0, expected, rtol=1e-2)


def test_debye_scherrer_ignores_displacement():
    ins = rx.Instrument.debye_scherrer(wavelength=1.5405929)
    ins.geometry.sample_displacement.value = 0.5
    model, values = _compiled(instrument=ins)
    ins0 = rx.Instrument.debye_scherrer(wavelength=1.5405929)
    model0, values0 = _compiled(instrument=ins0)
    np.testing.assert_allclose(model.phase_peaks(0, values)[0][0],
                               model0.phase_peaks(0, values0)[0][0])


# ---------------------------------------------------------------------------
# Finger-Cox-Jephcoat axial asymmetry
# ---------------------------------------------------------------------------

def _fcj_composite(x, two_theta, gamma, eta, sl, hl, n_nodes):
    phi, omega = fcj_offsets_weights(two_theta, sl, hl, n_nodes)
    return omega @ pseudo_voigt(x[None, :] - phi[:, None], gamma, eta)


def test_fcj_weights_normalised_and_unit_area():
    phi, omega = fcj_offsets_weights(25.0, 0.03, 0.025, 32)
    assert np.isclose(omega.sum(), 1.0)
    assert np.all(phi <= 25.0 + 1e-12)  # below 90°: smear to LOW angle only
    # area conservation: compare to the symmetric pV on the same grid so the
    # (identical) Lorentzian tail truncation cancels
    x = np.arange(23.0, 27.0, 0.001)
    comp = _fcj_composite(x, 25.0, 0.08, 0.4, 0.03, 0.025, 32)
    sym = pseudo_voigt(x - 25.0, 0.08, 0.4)
    assert np.isclose(np.trapezoid(comp, x), np.trapezoid(sym, x), rtol=1e-3)


def test_fcj_asymmetry_direction_flips_at_90():
    x_lo = np.arange(23.0, 27.0, 0.001)
    lo = _fcj_composite(x_lo, 25.0, 0.08, 0.4, 0.03, 0.03, 32)
    centroid_lo = np.trapezoid(lo * x_lo, x_lo) / np.trapezoid(lo, x_lo)
    assert centroid_lo < 25.0 - 1e-3  # tail to low angle below 90°

    x_hi = np.arange(138.0, 142.0, 0.001)
    hi = _fcj_composite(x_hi, 140.0, 0.08, 0.4, 0.03, 0.03, 32)
    centroid_hi = np.trapezoid(hi * x_hi, x_hi) / np.trapezoid(hi, x_hi)
    assert centroid_hi > 140.0 + 1e-3  # and to high angle above 90°


def test_fcj_zero_apertures_reduce_to_symmetric():
    x = np.arange(24.0, 26.0, 0.001)
    comp = _fcj_composite(x, 25.0, 0.08, 0.4, 0.0, 0.0, 16)
    np.testing.assert_allclose(comp, pseudo_voigt(x - 25.0, 0.08, 0.4), rtol=1e-12)
    assert fcj_node_count(25.0, 0.08, 0.0, 0.0) == 0
    # one zero aperture still smears the peak (WP-1953): only both is off
    assert fcj_node_count(25.0, 0.08, 0.0, 0.03) > 0
    assert fcj_node_count(25.0, 0.08, 0.03, 0.0) > 0


@pytest.mark.parametrize("sl", [0.035, 0.0])
def test_one_zero_aperture_is_the_limit_of_a_vanishing_one(sl):
    """WP-1953: the profile at H/L = 0 is its H/L → 0⁺ limit, and S/L and H/L
    trade places.  Until then one zero aperture gave the symmetric peak, a
    jump at the bound LM's exact step lands on: χ² 92 250 → 793 600 on
    ``test_e8``'s axial stage, and a 400-evaluation crawl beside it."""
    x = np.arange(21.0, 22.5, 0.002)
    other = 0.035 if sl == 0.0 else 0.0
    at_zero = _fcj_composite(x, 22.0, 0.07, 0.4, sl, other, 24)
    swapped = _fcj_composite(x, 22.0, 0.07, 0.4, other, sl, 24)
    np.testing.assert_allclose(swapped, at_zero, rtol=0, atol=1e-14 * at_zero.max())
    gaps = []
    for h in (1e-4, 1e-6, 1e-8):
        near = (_fcj_composite(x, 22.0, 0.07, 0.4, sl + h, other, 24) if sl == 0.0
                else _fcj_composite(x, 22.0, 0.07, 0.4, sl, h, 24))
        gaps.append(np.max(np.abs(near - at_zero)) / at_zero.max())
    assert gaps[-1] < 1e-7
    assert gaps[0] > gaps[1] > gaps[2]
    sym = pseudo_voigt(x - 22.0, 0.07, 0.4)
    assert np.max(np.abs(at_zero - sym)) > 0.05 * sym.max()


@pytest.mark.parametrize("sl, hl", [(0.035, 0.025), (0.035, 0.0), (0.0, 0.035)])
def test_fcj_quadrature_matches_direct_singular_integral(sl, hl):
    """Independent check of the singularity-removing transform: integrate the
    FCJ density in 2φ-space (with its 1/√(2θ−2φ) endpoint singularity) on a
    dense grid and compare with the fixed-node ξ-quadrature.  With one
    aperture at zero the weight is the trapezoid's limit, uniform over
    [0, s + h] (WP-1953)."""
    two_theta, gamma, eta = 22.0, 0.07, 0.4
    tt = np.radians(two_theta)

    # dense direct integral in 2φ: D(2φ) = W(ξ(2φ)) · dξ/d2φ
    ext = float(fcj_extent_deg(np.array(two_theta), sl, hl))
    phi_deg = np.linspace(two_theta - ext, two_theta, 40_001)[1:-1]  # open interval
    phi = np.radians(phi_deg)
    xi = np.sqrt(np.maximum(np.cos(phi) ** 2 / np.cos(tt) ** 2 - 1.0, 0.0))
    dxi_dphi = np.abs(np.cos(phi) * np.sin(phi)) / (np.cos(tt) ** 2 * np.maximum(xi, 1e-30))
    w_overlap = (np.clip(sl + hl - xi, 0.0, 2.0 * min(sl, hl)) if min(sl, hl) > 0.0
                 else (xi < sl + hl).astype(float))
    density = w_overlap * dxi_dphi

    x = np.arange(two_theta - 1.5, two_theta + 1.0, 0.005)
    direct = np.trapezoid(density[:, None] * pseudo_voigt(x[None, :] - phi_deg[:, None],
                                                          gamma, eta), phi_deg, axis=0)
    direct /= np.trapezoid(density, phi_deg)

    n = fcj_node_count(two_theta, gamma, sl, hl)
    quad = _fcj_composite(x, two_theta, gamma, eta, sl, hl, n)
    assert np.max(np.abs(quad - direct)) < 0.01 * np.max(direct)


def test_fcj_residual_smooth_in_axial_parameters():
    """The frozen-node design must give a smooth response to S/L (no jumps),
    or FD Jacobians break.  Probe the low-angle tail, where the aberration
    weight actually lives, and require the second differences of the response
    curve to be far below its first differences."""
    x = np.array([21.80, 21.88, 21.95])  # tail points below a 22.0° peak

    def second_diff_max(n_samples):
        # scan strictly above hl = 0.03: the overlap trapezoid has a genuine
        # C⁰ kink where S/L crosses H/L (min(s,h) switches branch) — inherent
        # to FCJ, not to our quadrature — so smoothness holds piecewise
        sls = np.linspace(0.0305, 0.045, n_samples)
        vals = np.array([_fcj_composite(x, 22.0, 0.07, 0.4, s, 0.03, 24) for s in sls])
        return np.abs(np.diff(vals, 2, axis=0)).max(axis=0)

    # C¹ smoothness ⇒ second differences scale as O(h²): halving the step
    # must shrink them ~4×; a discontinuity/kink would leave them O(h⁰)/O(h¹)
    coarse, fine = second_diff_max(41), second_diff_max(81)
    assert np.all(fine < 0.4 * coarse)


def test_fcj_windows_and_nodes_allocated_when_axial_free():
    """Starting from axial = 0, compiling with the axial paths free must still
    allocate quadrature nodes (else the FD column is exactly zero)."""
    structure = rx.Structure(phases=[_lab6_phase()])
    instrument = _lab_instrument()
    pattern = _flat_pattern()
    frozen = compile_model(structure, instrument, pattern)
    assert int(frozen.phases[0].fcj_n.max()) == 0
    live = compile_model(structure, instrument, pattern,
                         moving_paths={"instrument.geometry.axial_sl",
                                     "instrument.geometry.axial_hl"})
    assert int(live.phases[0].fcj_n.max()) > 0


def test_one_aperture_pinned_at_zero_still_sizes_nodes():
    """WP-1953: S/L positive beside H/L = 0, neither free, is a live
    aberration and compiles nodes, as does S/L freed alone beside H/L = 0
    (the QPA protocol's ``lines_axial``).  Both at zero and fixed compiles
    none."""
    structure = rx.Structure(phases=[_lab6_phase()])
    pattern = _flat_pattern()
    instrument = _lab_instrument()
    instrument.geometry.axial_sl.value = 0.03
    instrument.geometry.axial_hl.value = 0.0
    assert int(compile_model(structure, instrument, pattern,
                             moving_paths=set()).phases[0].fcj_n.max()) > 0
    instrument.geometry.axial_sl.value = 0.0
    assert int(compile_model(structure, instrument, pattern,
                             moving_paths=set()).phases[0].fcj_n.max()) == 0
    assert int(compile_model(
        structure, instrument, pattern,
        moving_paths={"instrument.geometry.axial_sl"}).phases[0].fcj_n.max()) > 0


def _rutile_axial(axial: float, free: bool) -> rx.Refinement:
    """Synthetic rutile with S/L = H/L = ``axial``, free or fixed (#774)."""
    P = rx.Parameter
    cell = rx.Cell(a=P(value=4.5937), b=P(value=4.5937), c=P(value=2.9587),
                   alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0))
    atoms = [rx.Atom(label="Ti", species="Ti", x=P(value=0.0), y=P(value=0.0),
                     z=P(value=0.0)),
             rx.Atom(label="O", species="O", x=P(value=0.3053), y=P(value=0.3053),
                     z=P(value=0.0))]
    st = rx.Structure(phases=[rx.Phase(name="rutile", space_group="P42/mnm",
                                       scale=P(value=8e-3), cell=cell, atoms=atoms)])
    ins = rx.Instrument.bragg_brentano()
    ins.profile.w.value = 8e-3
    g = ins.geometry
    g.axial_sl.value = g.axial_hl.value = axial
    g.axial_sl.vary = g.axial_hl.vary = free
    return rx.Refinement(st, ins)


@pytest.mark.parametrize("axial", [0.01, 0.05])
def test_predict_does_not_depend_on_the_free_set_for_positive_axial(axial):
    """#774: the node count follows the axial *values*, so the same model
    predicts the same pattern whether or not S/L, H/L are free — below the
    sizing floor (0.01) as well as above it (0.05)."""
    tt = np.arange(15.0, 80.0, 0.02)
    y_fixed = _rutile_axial(axial, False).predict(tt)
    y_free = _rutile_axial(axial, True).predict(tt)
    assert np.max(np.abs(y_free - y_fixed)) <= 1e-12 * np.max(y_fixed)


def test_axial_nodes_below_the_floor_match_whether_free_or_fixed():
    from rietx.model.forward import AXIAL_SIZING_FLOOR
    grid = np.arange(15.0, 80.0, 0.02)
    pat = rx.PatternData(two_theta=grid.tolist(),
                         intensity=np.ones_like(grid).tolist())
    counts = []
    for free in (False, True):
        r = _rutile_axial(0.01, free)
        moving = ({"instrument.geometry.axial_sl", "instrument.geometry.axial_hl"}
                  if free else set())
        counts.append(compile_model(r.structure, r.instrument, pat,
                                    moving_paths=moving).phases[0].fcj_n)
    assert 0.01 < AXIAL_SIZING_FLOOR
    assert np.array_equal(counts[0], counts[1]) and counts[0].max() > 0


def test_axial_free_at_zero_nodes_do_not_change_the_pattern(monkeypatch):
    """The floor kept for a ratio refined off zero: at zero the kernel is the
    identity, so the floored *node count* leaves ``predict()`` unchanged.  The
    window half-width is a separate matter (``fcj_extent_deg`` is neutralised
    here) and is not covered by this claim."""
    import rietx.model.forward as fwd
    monkeypatch.setattr(fwd, "fcj_extent_deg", lambda pos, sl, hl: np.zeros_like(pos))
    tt = np.arange(15.0, 80.0, 0.02)
    y_fixed = _rutile_axial(0.0, False).predict(tt)
    y_free = _rutile_axial(0.0, True).predict(tt)
    assert np.max(np.abs(y_free - y_fixed)) <= 1e-14 * np.max(y_fixed)


# ---------------------------------------------------------------------------
# FCJ quadrature error over the claimed domain (WP-2002, B10)
# ---------------------------------------------------------------------------
#
# B10 (ruled 2026-10-19): a numerical setting is tier 1 once a test bounds its
# error over the domain it claims.  One test per constant of
# ``fcj_node_count``, each over the cases that constant decides.  A case's
# error is max |y_n - y_ref| / max y_ref.  n is the count the rule picks, and
# y_ref is the same quadrature at max(512, 4n) nodes.  Below extent/FWHM 10,
# 512 nodes sit within 2e-7 of the peak of a reference doubled until it moved
# by under 1e-8 (measured, WP-2002).
# The arithmetic is numpy's ``fcj_offsets_weights`` and ``pseudo_voigt``.  The
# compiled kernels draw the same images through ``fcj_offsets_weights_batch``,
# so the error is theirs too.  No fit runs and no compiled tier is reached.

#: σ/peak at the strongest peak of each family's most precise pattern in
#: tests/data, from the file's own σ (WP-2002): ``FAP.XRA`` at 31.86°
#: (19 693 counts) for lab Bragg-Brentano, ``11BM_NAC.fxye`` at 11.82° for a
#: synchrotron.
_SIGMA_OVER_PEAK = {"lab": 7.2e-3, "synchrotron": 1.75e-3}
#: The bar, in units of the peak maximum, is a tenth of that noise.  At the
#: maximum it adds 1 % to the point's expected χ².  SRM 660c's (100) is the
#: anchor: its 39 shipped nodes leave 6.3e-4 of the peak (0.046 σ of that file),
#: and a refit with every reflection at 512 nodes moved no parameter by more
#: than 0.04 esd.
_FCJ_BAR = {family: 0.1 * v for family, v in _SIGMA_OVER_PEAK.items()}
#: The claimed domain.  Lab apertures span help.py's typical 0.01-0.05 for
#: each ratio: equal (the trapezoid's kink at s = h), unequal, and one at zero
#: (the uniform limit; the profile is symmetric in S/L and H/L).  Synchrotron
#: apertures stay under 0.005.  FWHM runs 0.03-0.3° on a lab instrument and
#: 0.003-0.03° on a synchrotron.  2θ runs from 2°, where |tan 2θ| caps ξ, to
#: 160°, across the flip at 90°.
_FCJ_DOMAIN = {
    "lab": (((0.025, 0.025), (0.05, 0.05), (0.037, 0.025), (0.05, 0.01), (0.05, 0.0)),
            (0.03, 0.07, 0.15, 0.3)),
    "synchrotron": (((0.003, 0.003), (0.005, 0.002), (0.005, 0.0)), (0.003, 0.01, 0.03)),
}
_FCJ_TT = (2.0, 3.0, 5.0, 6.5, 8.0, 10.0, 15.0, 22.0, 30.0, 45.0, 60.0, 75.0, 85.0, 89.0,
           91.0, 105.0, 120.0, 140.0, 160.0)
_FCJ_ETA = (0.0, 0.5, 1.0)


def _fcj_ratio(two_theta, fwhm, sl, hl):
    return float(fcj_extent_deg(np.array(two_theta), sl, hl)) / fwhm


def _fcj_tt_at_ratio(target, fwhm, sl, hl, above_90):
    """The 2θ on one side of 90° where extent/FWHM falls just under ``target``.

    The extent falls monotonically to zero at 90° from either side, so this
    bisects between 90° and that side's end of the claimed domain
    (``_FCJ_TT``).  Where the ratio stays under ``target`` all the way, it
    returns the domain's end, a point the grid already holds."""
    near, far = (90.0, _FCJ_TT[-1]) if above_90 else (90.0, _FCJ_TT[0])
    for _ in range(60):
        mid = 0.5 * (near + far)
        if _fcj_ratio(mid, fwhm, sl, hl) < target:
            near = mid
        else:
            far = mid
    return near


def _fcj_mix(x, two_theta, fwhm, sl, hl, n):
    """The Lorentzian and Gaussian composites at n nodes.  pV is linear in η,
    so every η is a mix of these two."""
    if n == 0:
        d = x - two_theta
        return pseudo_voigt(d, fwhm, 1.0), pseudo_voigt(d, fwhm, 0.0)
    phi, omega = fcj_offsets_weights(two_theta, sl, hl, n)
    d = x[None, :] - phi[:, None]
    return omega @ pseudo_voigt(d, fwhm, 1.0), omega @ pseudo_voigt(d, fwhm, 0.0)


def _fcj_constants(closing=False):
    m = fcj_module
    if closing:
        return (m.CLOSING_NODES_PER_FWHM, m.CLOSING_MIN_NODES, m.CLOSING_MAX_NODES,
                m.CLOSING_SKIP_EXTENT_FWHM_RATIO)
    return (m.NODES_PER_FWHM, m.MIN_NODES, m.MAX_NODES, m.SKIP_EXTENT_FWHM_RATIO)


@lru_cache(maxsize=4)
def _fcj_domain_cases(constants, closing=False):
    """Every case as (family, region, 2θ, S/L, H/L, FWHM, extent/FWHM, n,
    {η: error}).  The region names the constant that decides n.

    Each (apertures, FWHM) also gets the 2θ on either side of 90° where
    ``SKIP_EXTENT_FWHM_RATIO`` and ``MIN_NODES`` each stop deciding, because
    each one's error is largest there.  ``constants`` keys the cache, so a
    patched constant builds its own table."""
    per_fwhm, n_min, n_max, skip = constants
    rows = []
    for family, (apertures, fwhms) in _FCJ_DOMAIN.items():
        for (sl, hl), fwhm in ((a, f) for a in apertures for f in fwhms):
            tts = set(_FCJ_TT)
            for above in (False, True):
                tts.add(_fcj_tt_at_ratio(0.999 * skip, fwhm, sl, hl, above))
                tts.add(_fcj_tt_at_ratio((n_min - 4) / per_fwhm, fwhm, sl, hl, above))
            for tt in sorted(tts):
                ratio = _fcj_ratio(tt, fwhm, sl, hl)
                n = fcj_node_count(tt, fwhm, sl, hl, closing=closing)
                uncapped = int(np.ceil(4.0 + per_fwhm * ratio))
                region = ("skip" if n == 0 else "min" if uncapped <= n_min
                          else "cap" if uncapped > n_max else "rule")
                ext = ratio * fwhm
                x = np.arange(tt - ext - 6 * fwhm, tt + ext + 6 * fwhm, fwhm / 20)
                ref = _fcj_mix(x, tt, fwhm, sl, hl, max(512, 4 * n))
                got = _fcj_mix(x, tt, fwhm, sl, hl, n)
                err = {}
                for eta in _FCJ_ETA:
                    r = eta * ref[0] + (1 - eta) * ref[1]
                    y = eta * got[0] + (1 - eta) * got[1]
                    err[eta] = float(np.max(np.abs(y - r)) / r.max())
                rows.append((family, region, tt, sl, hl, fwhm, ratio, n, err))
    return rows


def _assert_fcj_bar(family, region, eta, closing=False):
    rows = [r for r in _fcj_domain_cases(_fcj_constants(closing), closing)
            if r[0] == family and r[1] == region]
    if not rows:
        # the constant decides no case of this family's domain, so it meets
        # the bar there; a strict xfail cell then turns red, its cue to go
        return
    _, _, tt, sl, hl, fwhm, ratio, n, err = max(rows, key=lambda r: r[8][eta])
    bar = _FCJ_BAR[family]
    assert err[eta] <= bar, (
        f"{family}, eta {eta}: {n} nodes leave {err[eta]:.2e} of the peak maximum at "
        f"2theta {tt:.2f}, S/L {sl}, H/L {hl}, FWHM {fwhm} (extent/FWHM {ratio:.3g}); "
        f"the bar is {bar:.2e}, a tenth of sigma/peak {_SIGMA_OVER_PEAK[family]:.2e}")


def _fcj_cells(failing):
    """(family, η) cells.  A measured failure is a strict xfail carrying its
    numbers, so a constant that comes to pass turns it red."""
    return [pytest.param(family, eta, id=f"{family}-eta{eta}",
                         marks=([pytest.mark.xfail(strict=True, reason=failing[family, eta])]
                                if (family, eta) in failing else []))
            for family in _FCJ_DOMAIN for eta in _FCJ_ETA]


#: Measured worst errors where the shipped constants fail (WP-2002).  The set
#: NODES_PER_FWHM 12, MIN_NODES 10, MAX_NODES 1024, SKIP_EXTENT_FWHM_RATIO 3e-4
#: meets both bars over a finer grid of this domain (8 500 cases): worst 1.6e-4
#: lab, 9.9e-5 synchrotron.
_SKIP_FAILS = {
    (family, eta): (f"SKIP_EXTENT_FWHM_RATIO 0.02: a peak drawn symmetric just under it is "
                    f"off by {e} of its maximum (bar {_FCJ_BAR[family]:.2e}); the error "
                    f"is about 0.48 x extent/FWHM, so the ratio must sit under "
                    f"{_FCJ_BAR[family] / 0.48:.1e}")
    for family in _FCJ_DOMAIN for eta, e in ((0.0, 9.5e-3), (0.5, 8.9e-3), (1.0, 8.7e-3))}
_MIN_FAILS = {
    ("lab", 1.0): "MIN_NODES 8: 7.9e-4 at extent/FWHM 0.667, one aperture at zero (bar 7.2e-4)",
    ("synchrotron", 0.5): "MIN_NODES 8: 3.9e-4 at extent/FWHM 0.667 (bar 1.75e-4)",
    ("synchrotron", 1.0): "MIN_NODES 8: 7.9e-4 at extent/FWHM 0.667 (bar 1.75e-4)",
}
_RULE_FAILS = {
    ("lab", 0.5): "NODES_PER_FWHM 6: 2.4e-3 at 30 deg, extent/FWHM 4.1, 29 nodes (bar 7.2e-4)",
    ("lab", 1.0): "NODES_PER_FWHM 6: 5.6e-3 at 30 deg, extent/FWHM 4.1, 29 nodes (bar 7.2e-4)",
    ("synchrotron", 0.0): "NODES_PER_FWHM 6: 3.2e-4 at extent/FWHM 0.82, 9 nodes (bar 1.75e-4)",
    ("synchrotron", 0.5): "NODES_PER_FWHM 6: 2.0e-3 at 2 deg, extent/FWHM 6.9 (bar 1.75e-4)",
    ("synchrotron", 1.0): "NODES_PER_FWHM 6: 4.7e-3 at 2 deg, extent/FWHM 6.9 (bar 1.75e-4)",
}
_CAP_FAILS = {
    **{("lab", eta): (f"MAX_NODES 64 binds past extent/FWHM 10 (below about 6.2 deg at "
                      f"S/L = H/L = 0.025, FWHM 0.07): {e} at 3 deg, extent/FWHM 70 "
                      f"(bar 7.2e-4)")
       for eta, e in ((0.0, 0.26), (0.5, 0.24), (1.0, 0.21))},
    ("synchrotron", 0.5): "MAX_NODES 64: 4.2e-4 at 2 deg, extent/FWHM 13.5 (bar 1.75e-4)",
    ("synchrotron", 1.0): "MAX_NODES 64: 9.9e-4 at 2 deg, extent/FWHM 13.5 (bar 1.75e-4)",
}


@pytest.mark.xdist_group("fcj-domain")
@pytest.mark.parametrize("family, eta", _fcj_cells(_SKIP_FAILS))
def test_fcj_skip_ratio_meets_the_bar(family, eta):
    """``SKIP_EXTENT_FWHM_RATIO``: a peak drawn symmetric below the ratio."""
    _assert_fcj_bar(family, "skip", eta)


@pytest.mark.xdist_group("fcj-domain")
@pytest.mark.parametrize("family, eta", _fcj_cells(_MIN_FAILS))
def test_fcj_min_nodes_meets_the_bar(family, eta):
    """``MIN_NODES``: the floor, where the extent is under (MIN_NODES − 4)
    / NODES_PER_FWHM FWHM."""
    _assert_fcj_bar(family, "min", eta)


@pytest.mark.xdist_group("fcj-domain")
@pytest.mark.parametrize("family, eta", _fcj_cells(_RULE_FAILS))
def test_fcj_nodes_per_fwhm_meets_the_bar(family, eta):
    """``NODES_PER_FWHM``: n = ⌈4 + NODES_PER_FWHM · extent/FWHM⌉ between the
    floor and the cap."""
    _assert_fcj_bar(family, "rule", eta)


@pytest.mark.xdist_group("fcj-domain")
@pytest.mark.parametrize("family, eta", _fcj_cells(_CAP_FAILS))
def test_fcj_max_nodes_meets_the_bar(family, eta):
    """``MAX_NODES``: the cap, which binds on large extents at low angle."""
    _assert_fcj_bar(family, "cap", eta)


@pytest.mark.slow  # 18-20 s serial for the 24 cells, on the fcj-domain worker
@pytest.mark.xdist_group("fcj-domain")
@pytest.mark.parametrize("region", ["skip", "min", "rule", "cap"])
@pytest.mark.parametrize("family, eta", _fcj_cells({}))
def test_the_closing_node_rule_meets_the_bar(family, eta, region):
    """The closing rule (``CLOSING_NODES_PER_FWHM`` 12, ``CLOSING_MIN_NODES`` 10,
    ``CLOSING_MAX_NODES`` 1024, ``CLOSING_SKIP_EXTENT_FWHM_RATIO`` 3e-4), which
    ``compile_model`` takes at windows finer than the declared stages', over the
    domain the four tests above fail on (WP-2002, the seventh round's Q2).
    The declared stages keep the rule above, since the closing stage computes
    the answer.  Measured 2026-10-21 over a finer grid of this domain (8 500
    cases): worst 1.6e-4 lab and 9.9e-5 synchrotron, 0.25 and 0.81 of the
    bars.  Made to fail on 2026-10-21 with ``CLOSING_NODES_PER_FWHM`` patched
    to 6."""
    _assert_fcj_bar(family, region, eta, closing=True)


def test_the_closing_node_rule_serves_every_compile_finer_than_the_declared_stages():
    """A ``closing_window_tol`` loosened past 1e-3 for speed keeps the closing
    node rule, and the declared stages' 2 % keeps its own (WP-2002,
    2026-10-22).  The line sat at ``CLOSING_WINDOW_TOL`` before, so 1.5e-3
    sampled the asymmetry at the declared rule, 7.8x the lab bar."""
    from rietx.model.forward import CLOSING_WINDOW_TOL, WINDOW_AREA_TOL
    from tests.test_acceptance_qpa_roundrobin import corundum_phase, qarr_instrument

    structure = rx.Structure(phases=[corundum_phase()])
    ins = qarr_instrument()
    ins.geometry.axial_sl.value = 0.03
    tt = np.arange(20.0, 140.0, 0.02)
    grid = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())

    def nodes(tol):
        return compile_model(structure, ins, grid, window_area_tol=tol).phases[0].fcj_n

    # a reflection past the scan's end whose narrower window holds no point has
    # no nodes at either rule, so only reflections with points in both compare
    closing = nodes(CLOSING_WINDOW_TOL)
    for tol in (5e-3, 0.0199):
        looser = nodes(tol)
        both = (looser > 0) & (closing > 0)
        assert both.sum() > 0.9 * (closing > 0).sum()
        assert np.array_equal(looser[both], closing[both]), tol
    declared = nodes(WINDOW_AREA_TOL)
    both = (declared > 0) & (closing > 0)
    assert np.all(declared[both] <= closing[both]) and declared[both].sum() < closing[both].sum()


# ---------------------------------------------------------------------------
# AXIAL_SIZING_FLOOR over the claimed domain (WP-2002, B10)
# ---------------------------------------------------------------------------
#
# A stage that frees S/L or H/L from zero compiles its quadrature nodes and its
# windows as if both were AXIAL_SIZING_FLOOR, then solves on that model however
# far the ratios walk.  The claimed domain is where they may walk to in one
# stage: help.py's typical 0.01-0.05 for each ratio, equal, unequal and one at
# zero.  cpd-1a's QPA protocol frees S/L alone from zero and ends its
# ``lines_axial`` stage at 0.041.  On that stage the frozen model and one
# compiled at the stage's end differ by up to 0.31 σ at 87.3° (converged
# windows, WINDOW_AREA_TOL 5e-5; measured WP-2002), against 0.000 σ with the
# floor at 0.06.  The next stage recompiles, so the floor reaches the answer
# only through the path: the two floors' fixed points differ by 0.16 esd at a
# χ² 0.008 apart, and one floor at 0.05 makes the protocol fits 1.25-1.8×
# slower (LaB6, FAP, cpd-1a), since the floor also applies by value to every
# positive ratio under it.
#
# Two errors, each held only where the node rule at the reached ratios meets
# its own bar, so that the rule's failures (the tests above) are not counted
# against the floor:
#
# 1. quadrature: the profile at the reached ratios on the floor's node count,
#    against 512 nodes, in units of the peak maximum, against the lab bar;
# 2. window: the area the reached profile loses outside a window sized at the
#    floor, against WINDOW_AREA_TOL, the bound every window claims.
#
# Made to fail once each (2026-10-21) by patching AXIAL_SIZING_FLOOR to 0.05 in
# the module before the cases were built: both tests turned XPASS(strict).

_AXIAL_REACHED = ((0.01, 0.01), (0.02, 0.02), (0.03, 0.03), (0.05, 0.05), (0.04, 0.0),
                  (0.05, 0.0), (0.04, 0.02), (0.05, 0.01))
_AXIAL_FWHM = (0.03, 0.07, 0.15, 0.3)
_AXIAL_TT = (3.0, 8.0, 15.0, 22.0, 30.0, 45.0, 60.0, 75.0, 85.0, 95.0, 120.0, 140.0, 160.0)


def _kept_pv(c, fwhm, eta, a, b):
    """Area of the unit pseudo-Voigt centred at ``c`` on [a, b]."""
    from scipy.special import erf
    k = 2.0 * np.sqrt(np.log(2.0))
    ua, ub = (a - c) / fwhm, (b - c) / fwhm
    lor = (np.arctan(2.0 * ub) - np.arctan(2.0 * ua)) / np.pi
    return eta * lor + (1.0 - eta) * 0.5 * (erf(k * ub) - erf(k * ua))


@lru_cache(maxsize=4)
def _axial_floor_cases(floor, slack, tol):
    """Every case as (S/L, H/L, FWHM, 2θ, η, n floor, n reached, quadrature
    error at each, area lost to each window).  The arguments key the cache,
    so a patched constant builds its own table."""
    from rietx.model.forward import window_fwhm_mult
    rows = []
    for (sl, hl) in _AXIAL_REACHED:
        for fwhm in _AXIAL_FWHM:
            for tt in _AXIAL_TT:
                n_floor = fcj_node_count(tt, fwhm, floor, floor)
                # compiled where the stage ended, the floor still applies by value
                n_reach = fcj_node_count(tt, fwhm, max(sl, floor), max(hl, floor))
                ext = float(fcj_extent_deg(np.array(tt), sl, hl))
                x = np.arange(tt - ext - 6 * fwhm, tt + ext + 6 * fwhm, fwhm / 20)
                n_ref = max(512, 4 * n_reach)
                ref = _fcj_mix(x, tt, fwhm, sl, hl, n_ref)
                at_floor = _fcj_mix(x, tt, fwhm, sl, hl, n_floor)
                at_reach = _fcj_mix(x, tt, fwhm, sl, hl, n_reach)
                phi, om = fcj_offsets_weights(tt, sl, hl, n_ref)
                halves = [float(fcj_extent_deg(np.array(tt), a, b))
                          for a, b in ((floor, floor), (max(sl, floor), max(hl, floor)))]
                for eta in _FCJ_ETA:
                    r = eta * ref[0] + (1 - eta) * ref[1]
                    err = [float(np.max(np.abs(eta * g[0] + (1 - eta) * g[1] - r)) / r.max())
                           for g in (at_floor, at_reach)]
                    k = float(window_fwhm_mult(np.float64(eta)))
                    lost = [1.0 - float(om @ _kept_pv(phi, fwhm, eta, tt - h, tt + h))
                            for h in (k * fwhm + slack + e for e in halves)]
                    rows.append((sl, hl, fwhm, tt, eta, n_floor, n_reach, *err, *lost))
    return rows


def _axial_rows():
    from rietx.model import forward
    return _axial_floor_cases(forward.AXIAL_SIZING_FLOOR, forward.WINDOW_MIN_DEG,
                              forward.WINDOW_AREA_TOL)


@pytest.mark.xdist_group("axial-floor-domain")
@pytest.mark.xfail(strict=True, reason=(
    "AXIAL_SIZING_FLOOR 0.02: refined from zero to S/L = H/L = 0.05, 15 nodes leave 0.27 of "
    "the peak maximum at 140 deg, FWHM 0.03 (64 nodes at the reached ratios: 1.8e-4; bar "
    "7.2e-4); 313 of the 1019 cases the reached count passes fail, from S/L = H/L = 0.03 "
    "(2.8e-2) and S/L 0.04 beside H/L 0 (6.4e-3) up"))
def test_axial_floor_quadrature_meets_the_bar_over_the_reached_ratios():
    """The floor's node count serves the ratios a stage may reach from zero
    wherever the count at the reached ratios does."""
    bar = _FCJ_BAR["lab"]
    held = [r for r in _axial_rows() if r[8] <= bar]
    sl, hl, fwhm, tt, eta, n_f, n_r, err, err_r, *_ = max(held, key=lambda r: r[7])
    assert err <= bar, (
        f"{n_f} nodes sized at the floor leave {err:.2e} of the peak maximum at S/L {sl}, "
        f"H/L {hl}, FWHM {fwhm}, 2theta {tt}, eta {eta} ({n_r} at the reached ratios: "
        f"{err_r:.1e}); the bar is {bar:.2e}")


@pytest.mark.xdist_group("axial-floor-domain")
@pytest.mark.xfail(strict=True, reason=(
    "AXIAL_SIZING_FLOOR 0.02: a window sized at the floor loses 0.195 of a peak refined from "
    "zero to S/L = H/L = 0.05 (8 deg, FWHM 0.03, eta 0), 0.054 at 0.03 each; 55 of 1248 "
    "cases over the bound WINDOW_AREA_TOL 0.02"))
def test_axial_floor_window_holds_the_area_bound_over_the_reached_ratios():
    """A window sized at the floor keeps all but ``WINDOW_AREA_TOL`` of the
    reached profile wherever a window sized at the reached ratios does."""
    from rietx.model.forward import WINDOW_AREA_TOL
    held = [r for r in _axial_rows() if r[10] <= WINDOW_AREA_TOL]
    sl, hl, fwhm, tt, eta, *_, lost, lost_r = max(held, key=lambda r: r[9])
    assert lost <= WINDOW_AREA_TOL, (
        f"a window sized at the floor loses {lost:.3f} of the area at S/L {sl}, H/L {hl}, "
        f"FWHM {fwhm}, 2theta {tt}, eta {eta} ({lost_r:.4f} sized at the reached ratios)")


# ---------------------------------------------------------------------------
# synthetic doublet round-trip
# ---------------------------------------------------------------------------

def test_synthetic_doublet_roundtrip():
    """Simulate a Bragg-Brentano CuKα pattern with known cell, displacement and
    Kα2 ratio; refine from a perturbed start and recover all three."""
    rng = np.random.default_rng(7)
    true_a, true_disp, true_ratio = 4.1568, -0.08, 0.47

    structure = rx.Structure(phases=[_lab6_phase(true_a)])
    instrument = _lab_instrument(ka2_ratio=true_ratio)
    instrument.geometry.sample_displacement.value = true_disp
    instrument.geometry.axial_sl.value = 0.03
    instrument.geometry.axial_hl.value = 0.03
    # zero (constant) and displacement (cosθ) only decorrelate when the scan
    # reaches high angle — the same reason lab calibrations run to 150° 2θ
    pattern0 = _flat_pattern(18.0, 148.0, 0.02)
    model = compile_model(structure, instrument, pattern0)
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0())) + 50.0
    y_noisy = rng.poisson(np.maximum(y, 1.0) * 20.0) / 20.0
    data = rx.PatternData(two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0) / 20.0).tolist())

    start_structure = rx.Structure(phases=[_lab6_phase(true_a + 0.002)])
    start = _lab_instrument(ka2_ratio=0.5)
    start.geometry.axial_sl.value = 0.03
    start.geometry.axial_hl.value = 0.03
    ref = rx.Refinement(start_structure, start)
    result = ref.fit(data, plan="lab_bragg_brentano")

    assert result.status == "converged"
    assert result.statistics.rwp < 0.05
    a = ref.fitted_structure.phases[0].cell.a.value
    disp = ref.fitted_instrument.geometry.sample_displacement.value
    ratio = ref.fitted_instrument.source.lines[1].weight.value
    assert abs(a - true_a) < 2e-4
    assert abs(disp - true_disp) < 0.02
    assert abs(ratio - true_ratio) < 0.03


# ---------------------------------------------------------------------------
# pdCIF reader
# ---------------------------------------------------------------------------

def test_read_pdcif_srm660c():
    from pathlib import Path
    path = Path(__file__).parent / "data" / "nist_srm660c_100a.cif"
    data = rx.read_pdcif(path, block="_meas")
    assert len(data.two_theta) == 5332
    assert np.isclose(data.two_theta[0], 20.3001)
    assert np.isclose(data.two_theta[-1], 150.9081)
    # σ from the pdCIF least-squares weight: σ = 1/√w
    assert data.sigma is not None and np.all(np.asarray(data.sigma) > 0)
    # the _calc block must be selectable too, and differ from _meas
    calc = rx.read_pdcif(path, block="_calc")
    assert len(calc.two_theta) == 5332
    assert not np.allclose(calc.intensity, data.intensity)
    # default pick = first matching block (= _meas in this file)
    default = rx.read_pdcif(path)
    assert default.metadata["block"].endswith("_meas")
