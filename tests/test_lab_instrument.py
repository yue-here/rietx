"""v0.2 lab-instrument physics: Kα doublet, displacement/transparency, FCJ.

Fast unit/property tests; the SRM 660c real-data acceptance lives in
``test_acceptance_srm660c.py`` (marked slow).
"""

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.model.corrections import displacement_shift_deg, transparency_shift_deg
from pxrdref.model.forward import compile_model
from pxrdref.model.profiles.fcj import (
    fcj_extent_deg,
    fcj_node_count,
    fcj_offsets_weights,
)
from pxrdref.model.profiles.pseudovoigt import pseudo_voigt
from pxrdref.params.vector import ParameterTable

CU_KA1, CU_KA2 = 1.5405929, 1.5444274


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _lab6_phase(a: float = 4.1568) -> pr.Phase:
    return pr.Phase(
        name="LaB6", space_group="P m -3 m", cell=pr.Cell.cubic(a),
        atoms=[
            pr.Atom(label="La", species="La", x=pr.Parameter(value=0.0),
                    y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                    biso=pr.Parameter(value=0.36, min=0.0, max=25.0)),
            pr.Atom(label="B", species="B", x=pr.Parameter(value=0.198),
                    y=pr.Parameter(value=0.5), z=pr.Parameter(value=0.5),
                    biso=pr.Parameter(value=0.28, min=0.0, max=25.0)),
        ],
        scale=pr.Parameter(value=5e-5, min=0.0, transform="softplus"),
    )


def _lab_instrument(**kw) -> pr.Instrument:
    ins = pr.Instrument.bragg_brentano(monochromator_two_theta=26.6, **kw)
    ins.profile.w.value = 2e-3
    ins.profile.x.value = 5e-3
    return ins


def _flat_pattern(lo=15.0, hi=90.0, step=0.02):
    tt = np.arange(lo, hi, step)
    return pr.PatternData(two_theta=tt.tolist(), intensity=np.full_like(tt, 10.0).tolist(),
                          sigma=np.full_like(tt, 1.0).tolist())


def _compiled(instrument=None, pattern=None, structure=None):
    structure = structure or pr.Structure(phases=[_lab6_phase()])
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
    structure = pr.Structure(phases=[_lab6_phase()])
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
        ins = pr.Instrument.bragg_brentano(radiation=name)
        got = [line.wavelength for line in ins.source.lines]
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
    ins = pr.Instrument.bragg_brentano()
    assert [line.wavelength for line in ins.source.lines] == [CU_KA1, CU_KA2]
    # ...and specifically *not* Bearden (1967), the other scale in circulation
    assert ins.source.lines[0].wavelength != 1.540562


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
        ins = pr.Instrument.bragg_brentano(radiation=f"{name}1")
        assert [line.wavelength for line in ins.source.lines] == [ka1]
        # the single line is line 0, hence structurally locked at weight 1
        assert ins.source.lines[0].weight.value == 1.0


def test_unknown_anode_lists_what_is_available():
    with pytest.raises(ValueError, match="unknown radiation 'NiKa'"):
        pr.Instrument.bragg_brentano(radiation="NiKa")
    with pytest.raises(ValueError, match="MoKa"):
        pr.Instrument.bragg_brentano(radiation="NiKa")


def test_doublet_defaults_hold_off_cu():
    """``ka2_ratio`` and the polarization default are anode-independent; the
    monochromator angle is not."""
    ins = pr.Instrument.bragg_brentano(radiation="MoKa", ka2_ratio=0.5)
    assert ins.source.lines[1].weight.value == 0.5   # 2j+1 degeneracy, any Z
    assert ins.source.polarization.value == 0.5      # unpolarized, no mono

    # graphite (002), d = 3.354 A: 2θ_m is a function of the anode, so the
    # 26.6° in the docstring is a *Cu* number and K moves with it
    for radiation, d in (("CuKa", 3.354), ("MoKa", 3.354)):
        lam = NIST_XRTE_DIRECT[radiation][0]
        tt_m = 2.0 * np.degrees(np.arcsin(lam / (2.0 * d)))
        ins = pr.Instrument.bragg_brentano(radiation=radiation,
                                           monochromator_two_theta=tt_m)
        k = 1.0 / (1.0 + np.cos(np.radians(tt_m)) ** 2)
        assert ins.source.polarization.value == pytest.approx(k)
    assert tt_m == pytest.approx(12.14, abs=0.02)     # Mo, vs 26.55 for Cu
    assert k == pytest.approx(0.511, abs=5e-4)


def test_off_cu_instrument_round_trips_through_json():
    ins = pr.Instrument.bragg_brentano(radiation="AgKa", goniometer_radius_mm=240.0)
    back = pr.Instrument.model_validate_json(ins.model_dump_json())
    assert [line.wavelength for line in back.source.lines] == \
        list(NIST_XRTE_DIRECT["AgKa"])
    assert back.geometry.goniometer_radius_mm == 240.0


def test_peaks_move_to_the_anode_wavelength():
    """The forward model uses the table, not a cached Cu number: the same phase
    on Mo Kα puts its first peak where Bragg's law says."""
    structure = pr.Structure(phases=[_lab6_phase()])
    ins = pr.Instrument.bragg_brentano(radiation="MoKa")
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
    ins = pr.Instrument.debye_scherrer(wavelength=1.5405929)
    ins.geometry.sample_displacement.value = 0.5
    model, values = _compiled(instrument=ins)
    ins0 = pr.Instrument.debye_scherrer(wavelength=1.5405929)
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
    assert fcj_node_count(25.0, 0.08, 0.0, 0.03) == 0  # one zero aperture: off


def test_fcj_quadrature_matches_direct_singular_integral():
    """Independent check of the singularity-removing transform: integrate the
    FCJ density in 2φ-space (with its 1/√(2θ−2φ) endpoint singularity) on a
    dense grid and compare with the fixed-node ξ-quadrature."""
    two_theta, gamma, eta, sl, hl = 22.0, 0.07, 0.4, 0.035, 0.025
    tt = np.radians(two_theta)

    # dense direct integral in 2φ: D(2φ) = W(ξ(2φ)) · dξ/d2φ
    ext = float(fcj_extent_deg(np.array(two_theta), sl, hl))
    phi_deg = np.linspace(two_theta - ext, two_theta, 40_001)[1:-1]  # open interval
    phi = np.radians(phi_deg)
    xi = np.sqrt(np.maximum(np.cos(phi) ** 2 / np.cos(tt) ** 2 - 1.0, 0.0))
    dxi_dphi = np.abs(np.cos(phi) * np.sin(phi)) / (np.cos(tt) ** 2 * np.maximum(xi, 1e-30))
    w_overlap = np.clip(sl + hl - xi, 0.0, 2.0 * min(sl, hl))
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
    structure = pr.Structure(phases=[_lab6_phase()])
    instrument = _lab_instrument()
    pattern = _flat_pattern()
    frozen = compile_model(structure, instrument, pattern)
    assert int(frozen.phases[0].fcj_n.max()) == 0
    live = compile_model(structure, instrument, pattern,
                         free_paths={"instrument.geometry.axial_sl",
                                     "instrument.geometry.axial_hl"})
    assert int(live.phases[0].fcj_n.max()) > 0


# ---------------------------------------------------------------------------
# synthetic doublet round-trip
# ---------------------------------------------------------------------------

def test_synthetic_doublet_roundtrip():
    """Simulate a Bragg-Brentano CuKα pattern with known cell, displacement and
    Kα2 ratio; refine from a perturbed start and recover all three."""
    rng = np.random.default_rng(7)
    true_a, true_disp, true_ratio = 4.1568, -0.08, 0.47

    structure = pr.Structure(phases=[_lab6_phase(true_a)])
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
    data = pr.PatternData(two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0) / 20.0).tolist())

    start_structure = pr.Structure(phases=[_lab6_phase(true_a + 0.002)])
    start = _lab_instrument(ka2_ratio=0.5)
    start.geometry.axial_sl.value = 0.03
    start.geometry.axial_hl.value = 0.03
    ref = pr.Refinement(start_structure, start)
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
    data = pr.read_pdcif(path, block="_meas")
    assert len(data.two_theta) == 5332
    assert np.isclose(data.two_theta[0], 20.3001)
    assert np.isclose(data.two_theta[-1], 150.9081)
    # σ from the pdCIF least-squares weight: σ = 1/√w
    assert data.sigma is not None and np.all(np.asarray(data.sigma) > 0)
    # the _calc block must be selectable too, and differ from _meas
    calc = pr.read_pdcif(path, block="_calc")
    assert len(calc.two_theta) == 5332
    assert not np.allclose(calc.intensity, data.intensity)
    # default pick = first matching block (= _meas in this file)
    default = pr.read_pdcif(path)
    assert default.metadata["block"].endswith("_meas")
