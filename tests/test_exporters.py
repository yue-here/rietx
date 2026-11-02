"""WP-0309 exporters: reflection table, refinement CIF (values + esds), QPA table.

The refinement CIF is validated by round-tripping through the package's own
readers (``read_pdcif`` for the pattern, ``Structure.from_cif`` for the
structure) — export then re-read is the cheapest correctness test.
"""

from __future__ import annotations

import gemmi
import numpy as np
import pytest

from rietx import (
    Instrument,
    PatternData,
    Refinement,
    Structure,
    format_su,
    read_pdcif,
    reflection_table,
    write_qpa_table,
    write_reflection_table,
)
from rietx.crystallography.lattice import d_spacings
from rietx.io.exporters import ReflectionRow, qpa_table_csv
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.results import (
    MicroabsorptionCorrection,
    PhaseQuantity,
    QuantitativePhaseAnalysis,
)
from tests.test_schemas import make_lab6

WAVELENGTH_CU = 1.5405929


# ----------------------------------------------------------------------
# esd string formatter — the reference table (WP-0309's "genuine trap")
# ----------------------------------------------------------------------

# (value, esd, expected)  — two-significant-figure su, IUCr convention.
SU_REFERENCE = [
    (4.5937, 0.00025, "4.59370(25)"),        # the canonical cell-length case
    (0.006, 0.00012, "0.00600(12)"),
    (0.001, 0.0000031, "0.0010000(31)"),     # su finer than the value's default width
    (10.2513, 1.2e-5, "10.251300(12)"),
    (-4.5937, 0.00025, "-4.59370(25)"),      # negative value keeps its sign
    (1.23456, 0.0999, "1.23(10)"),           # decade boundary: 0.0999 rounds to 0.10
    (2.0, 0.00995, "2.000(10)"),             # decade boundary, deeper
    (98.76, 1.5, "98.8(15)"),                # esd >= 1
    (123.4, 2.5, "123.4(25)"),
    (12345.0, 250.0, "12340(250)"),          # esd >= 10, value loses precision
]


@pytest.mark.parametrize("value,esd,expected", SU_REFERENCE)
def test_format_su_reference_table(value, esd, expected):
    assert format_su(value, esd) == expected


def test_format_su_no_esd_is_a_plain_number():
    # a fixed parameter (esd None) must never imply an uncertainty it lacks
    assert format_su(0.005, None) == "0.005000"
    assert format_su(1.5, 0.0) == "1.500000"          # non-positive -> plain
    assert format_su(1.5, float("nan")) == "1.500000"  # non-finite -> plain
    assert format_su(0.005, None, decimals=3) == "0.005"


# ----------------------------------------------------------------------
# reflection table
# ----------------------------------------------------------------------


def _lab6_doublet_model():
    """A compiled LaB6 model under a Cu Kα1/Kα2 doublet (no fit needed)."""
    structure = make_lab6()
    ins = Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=200.0)
    tt = np.arange(20.0, 90.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0()), structure


def test_reflection_table_accounts_for_every_emission_line():
    model, values, structure = _lab6_doublet_model()
    rows = reflection_table(model, values, structure)
    assert rows, "expected reflections in 20-90 deg"

    # both emission lines are represented — never a lambda_1-only table
    lines = {r.line for r in rows}
    assert lines == {0, 1}

    # every hkl that appears for the primary line also appears for Ka2, and the
    # Ka2 peak sits at higher 2theta (longer wavelength, same d)
    by_line = {0: {}, 1: {}}
    for r in rows:
        by_line[r.line][(r.h, r.k, r.l)] = r
    assert set(by_line[0]) == set(by_line[1])
    for hkl, r1 in by_line[0].items():
        r2 = by_line[1][hkl]
        assert r2.two_theta > r1.two_theta          # doublet splits with tanθ
        assert r2.d == pytest.approx(r1.d)          # d is line-independent
        assert r2.wavelength > r1.wavelength


def test_reflection_table_fields_are_physical():
    model, values, structure = _lab6_doublet_model()
    rows = reflection_table(model, values, structure)
    assert all(isinstance(r, ReflectionRow) for r in rows)
    for r in rows:
        assert r.phase == "LaB6"
        assert r.multiplicity >= 1
        assert r.d > 0.0
        assert r.f_squared is not None and r.f_squared >= 0.0   # rietveld mode
        assert r.intensity >= 0.0
    # (1,0,0), (1,1,0), (1,1,1) of a P m -3 m cube have multiplicities 6, 12, 8
    prim = {(r.h, r.k, r.l): r for r in rows if r.line == 0}
    assert prim[(1, 0, 0)].multiplicity == 6
    assert prim[(1, 1, 0)].multiplicity == 12
    assert prim[(1, 1, 1)].multiplicity == 8


def test_reflection_table_lebail_has_no_structure_factor():
    structure = make_lab6()
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    tt = np.arange(3.0, 24.0, 0.01)
    pattern = PatternData(two_theta=tt.tolist(), intensity=[100.0] * len(tt))
    model = compile_model(structure, ins, pattern, mode="lebail")
    table = ParameterTable(structure, ins)
    rows = reflection_table(model, table.decode(table.x0()), structure)
    assert rows
    # Le Bail intensity is extracted, not computed from |F|²
    assert all(r.f_squared is None for r in rows)


def test_write_reflection_table_csv_round_trips(tmp_path):
    model, values, structure = _lab6_doublet_model()
    rows = reflection_table(model, values, structure)
    out = tmp_path / "refl.csv"
    write_reflection_table(rows, out)

    text = out.read_text(encoding="utf-8").splitlines()
    header = text[0].split(",")
    assert header[:6] == ["phase", "line", "wavelength", "h", "k", "l"]
    assert header[-1] == "component"
    assert len(text) - 1 == len(rows)                # one data row per reflection row
    for line in text[1:]:
        assert line.split(",")[-1] == "total"        # no magnetic width here

    # a .tsv suffix switches the delimiter
    out_tsv = tmp_path / "refl.tsv"
    write_reflection_table(rows, out_tsv)
    assert "\t" in out_tsv.read_text(encoding="utf-8").splitlines()[0]


# ----------------------------------------------------------------------
# reflection table -- the magnetic component split (WP-1343)
# ----------------------------------------------------------------------


def _mnf2_rows(**kw):
    """Compile an MnF2 model through the WP-1343 fixture and export its
    reflection table alongside the model/values, for the tests below."""
    from tests.test_magnetic_width import _mnf2, _state

    ph = _mnf2(**kw)
    model, _table, values = _state(ph, moving=None)
    structure = Structure(phases=[ph])
    rows = reflection_table(model, values, structure)
    return model, values, rows


def test_reflection_table_width_off_matches_the_unsplit_computation():
    """(c) Regression: a phase whose magnetic width is off still gets exactly
    one "total" row per (line, reflection), numerically identical to calling
    the model's own primitives directly -- the code path the split must
    leave untouched.
    """
    model, values, rows = _mnf2_rows()                # both widths at 0
    assert not model.mag_split(0)
    assert rows
    assert {r.component for r in rows} == {"total"}

    cp = model.phases[0]
    cell = tuple(values[f"phases.0.cell.{k}"]
                for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = d_spacings(cp.reflections.index, *cell)
    f2 = model._nuclear_f2(0, d, values, cell)
    peaks = model.phase_peaks(0, values)
    expect = []
    for il, (pos, _g, _e, intensity) in enumerate(peaks):
        for j in range(len(cp.reflections.hkl)):
            if not np.isfinite(pos[j]):
                continue
            expect.append((il, int(cp.reflections.hkl[j][0]),
                          int(cp.reflections.hkl[j][1]),
                          int(cp.reflections.hkl[j][2]),
                          float(f2[j]), float(intensity[j])))
    got = [(r.line, r.h, r.k, r.l, r.f_squared, r.intensity) for r in rows]
    assert got == expect


def test_a_total_row_f_squared_is_nuclear_only_and_the_docstring_says_so():
    """Issue #613.  MnF2's (1 0 0) is a nuclear absence of P4_2/mnm and a
    magnetic line under 136.499: on its "total" row ``f_squared`` is 0 while
    ``intensity`` is among the largest in the table.  The docstring said
    ``intensity`` is built from ``f_squared``; it now says that on a magnetic
    phase the column is the nuclear |F|^2 alone."""
    model, values, rows = _mnf2_rows()
    assert not model.mag_split(0)
    (r100,) = [r for r in rows if r.line == 0
               and sorted(map(abs, (r.h, r.k, r.l))) == [0, 0, 1]
               and r.l == 0]
    assert r100.component == "total"
    assert r100.f_squared == 0.0
    line0 = sorted((r.intensity for r in rows if r.line == 0), reverse=True)
    assert r100.intensity >= line0[2] > 0.0       # among the three largest
    doc = " ".join(ReflectionRow.__doc__.split())
    assert "``f_squared`` is the **nuclear** ⟨|F_N|²⟩ alone" in doc
    assert "issue #613" in doc


def test_reflection_table_nuclear_plus_magnetic_equals_width_off_intensity():
    """(a) With `magnetic_lor_strain` non-zero, sum(nuclear + magnetic) per
    (line, reflection) equals the width-off export's `intensity` to 1e-9
    relative -- the components are separable by construction (phase_peaks'
    own docstring claim, exercised directly in
    test_magnetic_width.test_the_two_components_sum_to_the_unsplit_intensity).
    """
    split_model, _sv, split_rows = _mnf2_rows(strain=0.15)
    plain_model, _pv, plain_rows = _mnf2_rows()
    assert split_model.mag_split(0)
    assert not plain_model.mag_split(0)
    assert {r.component for r in split_rows} == {"nuclear", "magnetic"}

    plain_by_key = {(r.line, r.h, r.k, r.l): r.intensity for r in plain_rows}
    summed: dict[tuple, float] = {}
    for r in split_rows:
        key = (r.line, r.h, r.k, r.l)
        summed[key] = summed.get(key, 0.0) + r.intensity
    assert set(summed) == set(plain_by_key)
    for key, total in summed.items():
        assert total == pytest.approx(plain_by_key[key], rel=1e-9), key


def test_reflection_table_pure_magnetic_row_carries_finite_intensity():
    """(b) A magnetic-only reflection (WP-1343's own classifier) exports a
    `component="magnetic"` row with finite, non-zero intensity -- the bug's
    own failure mode was every such row reading intensity ~= 0.
    """
    from rietx.report.magnetic import _classified_reflections

    model, values, rows = _mnf2_rows(strain=0.15)
    assert model.mag_split(0)

    _ip, mag_rows, _nuc_rows, _pos, _fwhm = next(iter(
        _classified_reflections(model, values)))
    assert len(mag_rows)
    hkl = model.phases[0].reflections.hkl[mag_rows[0]]
    key = tuple(int(x) for x in hkl)

    magnetic_row = next(r for r in rows if r.component == "magnetic"
                        and r.line == 0 and (r.h, r.k, r.l) == key)
    assert np.isfinite(magnetic_row.intensity)
    assert magnetic_row.intensity > 0.0

    # the nuclear row for the same reflection carries (near) zero intensity --
    # the deliberate "no nuclear structure factor here" reading, not the bug
    nuclear_row = next(r for r in rows if r.component == "nuclear"
                       and r.line == 0 and (r.h, r.k, r.l) == key)
    assert nuclear_row.intensity == pytest.approx(0.0, abs=1e-8)


# ----------------------------------------------------------------------
# QPA table
# ----------------------------------------------------------------------


def _two_phase_qpa(*, microabsorption=False, skipped=None):
    phases = [
        PhaseQuantity(name="corundum", weight_fraction=0.6,
                      weight_fraction_stderr=0.01, scale=1e-4, cell_mass=611.8,
                      cell_volume=254.8, zmv=1.559e5),
        PhaseQuantity(name="fluorite", weight_fraction=0.4,
                      weight_fraction_stderr=0.01, scale=8e-5, cell_mass=312.3,
                      cell_volume=163.0, zmv=5.09e4),
    ]
    micro = None
    if microabsorption:
        phases[0].weight_fraction_corrected = 0.58
        phases[0].mu_r = 0.03
        phases[0].brindley_tau = 0.98
        phases[0].particle_radius_um = 5.0
        micro = MicroabsorptionCorrection(wavelength=WAVELENGTH_CU, mu_mean_cm=125.0)
    return QuantitativePhaseAnalysis(phases=phases, microabsorption=micro,
                                     microabsorption_skipped=skipped)


def test_qpa_table_carries_crystalline_only_caveat(tmp_path):
    qpa = _two_phase_qpa()
    out = tmp_path / "qpa.csv"
    write_qpa_table(qpa, out)
    text = out.read_text(encoding="utf-8")

    # the scope caveat is in the file itself, not just the API docstring
    assert "CRYSTALLINE" in text
    assert "crystalline_only=True" in text
    comments = [ln for ln in text.splitlines() if ln.startswith("#")]
    assert comments, "caveats must be written as leading comments"

    body = [ln for ln in text.splitlines() if not ln.startswith("#")]
    assert body[0].split(",")[:2] == ["phase", "weight_fraction"]
    assert len(body) - 1 == 2                          # two phase rows
    assert "corundum" in text and "fluorite" in text


def test_qpa_table_reports_microabsorption_status():
    corrected = qpa_table_csv(_two_phase_qpa(microabsorption=True))
    assert "Brindley" in corrected
    assert "0.58" in corrected                          # corrected fraction column
    assert "mu_r" in corrected

    skipped = qpa_table_csv(_two_phase_qpa(skipped="radii missing on 1 of 2 phases"))
    assert "skipped" in skipped
    assert "radii missing" in skipped


# ----------------------------------------------------------------------
# refinement CIF — export then re-read through the package's own readers
# ----------------------------------------------------------------------

TRUE_A = 4.15660
TRUE_ZERO = 0.008
TRUE_SCALE = 5e-4
TRUE_W = 2.5e-4
EXCLUDED = (20.0, 20.05)


@pytest.fixture(scope="module")
def fitted_lab6():
    """A converged single-phase LaB6 fit — its structure carries refined esds."""
    truth = make_lab6()
    truth.phases[0].cell.a.value = TRUE_A
    truth.phases[0].cell.b.value = TRUE_A
    truth.phases[0].cell.c.value = TRUE_A
    truth.phases[0].scale.value = TRUE_SCALE
    ins_t = Instrument.debye_scherrer(wavelength=0.4139)
    ins_t.zero_shift.value = TRUE_ZERO
    ins_t.profile.w.value = TRUE_W
    ins_t.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 1.5)])

    tt = np.arange(3.0, 24.0, 0.005)
    grid = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins_t, grid, mode="rietveld")
    table = ParameterTable(truth, ins_t)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(7)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    # an interior excluded region, so the CIF's pattern loop has measured
    # points the fit did not use (WP-1933 C-d)
    data = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist(),
                       excluded_regions=[EXCLUDED])

    structure = make_lab6()
    structure.phases[0].cell.a.value = TRUE_A + 0.004
    structure.phases[0].cell.b.value = TRUE_A + 0.004
    structure.phases[0].cell.c.value = TRUE_A + 0.004
    structure.phases[0].scale.value = TRUE_SCALE * 1.8
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.profile.w.value = TRUE_W * 2.0
    ins.background = BackgroundChebyshev.with_terms(3)

    ref = Refinement(structure, ins, history=False)
    result = ref.fit(data, plan="mccusker_default")
    assert result.status == "converged"
    return ref, result, data


def test_refinement_cif_round_trips_through_readers(fitted_lab6, tmp_path):
    ref, result, data = fitted_lab6
    out = tmp_path / "refinement.cif"
    ref.write_cif(out)
    text = out.read_text(encoding="utf-8")

    # 1. the structure re-reads through the small-molecule reader with the
    #    refined cell intact
    back = Structure.from_cif(str(out))
    a_fit = ref.fitted_structure.phases[0].cell.a.value
    assert back.phases[0].cell.a.value == pytest.approx(a_fit, abs=1e-5)
    assert len(back.phases[0].atoms) == 2

    # a refined cell length carries a standard uncertainty in value(su) notation
    a_esd = result.parameter("phases.0.cell.a").stderr
    assert a_esd is not None
    assert "_cell_length_a" in text
    assert "(" in text.split("_cell_length_a")[1].split("\n")[0]

    # 2. the observed pattern re-reads through read_pdcif: every measured
    #    point, the excluded ones included, as the counts they were
    pat = read_pdcif(out)
    assert len(pat.two_theta) == len(data.two_theta) > len(result.two_theta)
    np.testing.assert_allclose(pat.two_theta, data.two_theta, rtol=1e-8)  # 8 figures
    np.testing.assert_array_equal(pat.intensity, data.intensity)

    # 3. refinement metadata is present
    assert "_diffrn_radiation_wavelength" in text
    assert "_pd_proc_ls_prof_wR_factor" in text        # Rwp
    assert "TCHZ" in text                              # profile description
    assert "Chebyshev" in text                         # background description


def test_the_pattern_loop_weights_the_unfitted_points_zero(fitted_lab6, tmp_path):
    """Every measured point is deposited, and ``_pd_proc_ls_weight`` says which
    the fit used: 1/σ² of the fit's σ, else 0, with no calculated value there.
    Counts with no stated σ go out as ``_pd_meas_counts_total``, on the
    measured, uncorrected grid; the excluded stretch is stated in words."""
    ref, result, data = fitted_lab6
    out = tmp_path / "w.cif"
    ref.write_cif(out)
    block = gemmi.cif.read(str(out)).sole_block()
    tt = np.array([float(v) for v in block.find_loop("_pd_meas_2theta_scan")])
    w = np.array([float(v) for v in block.find_loop("_pd_proc_ls_weight")])
    calc = list(block.find_loop("_pd_calc_intensity_total"))
    excluded = w == 0.0
    n_out = len(data.two_theta) - len(result.two_theta)
    assert excluded.sum() == n_out > 0
    assert np.all((tt[excluded] >= EXCLUDED[0] - 1e-9) & (tt[excluded] <= EXCLUDED[1]))
    np.testing.assert_allclose(w[~excluded], 1.0 / np.asarray(result.sigma) ** 2,
                               rtol=1e-7)
    assert all(calc[i] == "." for i in np.flatnonzero(excluded))
    assert block.find_loop("_pd_meas_counts_total")
    assert not block.find_loop("_pd_proc_2theta_corrected")
    assert block.find_value("_pd_meas_number_of_points") == str(len(data.two_theta))
    assert block.find_value("_pd_proc_number_of_points") == str(len(result.two_theta))
    assert f"20.05 deg ({n_out} points)" in " ".join(
        block.find_value("_pd_proc_info_excluded_regions").split())
    d = np.array([float(v) for v in block.find_loop("_pd_proc_d_spacing")])
    lam = ref.instrument.source.primary_wavelength
    np.testing.assert_allclose(d, lam / (2 * np.sin(np.radians(tt) / 2)), rtol=1e-7)


def test_a_stated_sigma_rides_in_parentheses_and_reads_back(fitted_lab6, tmp_path):
    """A pattern whose file stated σ writes ``_pd_meas_intensity_total`` as
    ``value(su)``, and ``read_pdcif`` takes σ from there."""
    from rietx.io.exporters import write_refinement_cif

    ref, result, _data = fitted_lab6
    sigma = np.sqrt(np.maximum(result.y_obs, 1.0)) * 1.5
    measured = PatternData(two_theta=result.two_theta, intensity=result.y_obs,
                           sigma=sigma.tolist())
    out = tmp_path / "s.cif"
    write_refinement_cif(result, ref.fitted_structure, ref.fitted_instrument, out,
                         pattern=measured)
    block = gemmi.cif.read(str(out)).sole_block()
    assert "(" in block.find_loop("_pd_meas_intensity_total")[0]
    back = read_pdcif(out)
    # two significant figures of su survive the file
    np.testing.assert_allclose(back.sigma, sigma, rtol=0.05)


def test_a_pattern_that_was_not_fitted_is_refused(fitted_lab6):
    from rietx.io.exporters import refinement_cif_doc

    ref, result, _data = fitted_lab6
    shifted = PatternData(two_theta=(np.asarray(result.two_theta) + 1e-3).tolist(),
                          intensity=result.y_obs)
    with pytest.raises(ValueError, match="not the one this result was fitted to"):
        refinement_cif_doc(result, ref.fitted_structure, ref.fitted_instrument,
                           pattern=shifted)


def test_the_experiment_and_refinement_items(fitted_lab6):
    """The items a reader needs beside the numbers: the probe, the method, the
    geometry, every emission line with its weight, the restraint count, the
    last shift over su, the absorption applied or ``none``, extinction on the
    phase's block, and profile text in lines checkCIF reads (≤ 80 columns)
    naming the shape the fit computed and every value with its su."""
    from rietx.io.exporters import refinement_cif_doc
    from tests.test_cif_registry import _lab_variant

    ref, result, _data = fitted_lab6
    block = refinement_cif_doc(result, ref.fitted_structure, ref.fitted_instrument)[0]
    assert block.find_value("_diffrn_radiation_probe") == "x-ray"
    assert block.find_value("_pd_calc_method").strip("'") == "Rietveld Refinement"
    assert "Debye-Scherrer" in block.find_value("_pd_instr_geometry")
    assert block.find_value("_diffrn_radiation_wavelength") is not None
    assert block.find_value("_refine_ls_number_restraints") == "0"
    assert float(block.find_value("_refine_ls_shift/su_max")) == pytest.approx(
        result.statistics.max_shift_over_esd)
    assert block.find_value("_exptl_absorpt_correction_type") == "none"
    assert block.find_value("_refine_ls_extinction_coef") is None
    profile = gemmi.cif.as_string(block.find_value("_pd_proc_ls_profile_function"))
    assert "TCHZ" in profile
    w = result.parameter("instrument.profile.w")
    assert f"W={format_su(w.value, w.stderr)}" in profile
    for tag in ("_pd_proc_ls_profile_function", "_pd_proc_ls_background_function",
                "_pd_proc_ls_special_details"):
        lines = gemmi.cif.as_string(block.find_value(tag)).splitlines()
        assert lines and max(len(line) for line in lines) <= 80, tag

    lab, structure, instrument = _lab_variant(result, ref)
    instrument.profile.shape = "voigt"
    block = refinement_cif_doc(lab, structure, instrument)[0]
    rows = list(block.find(["_diffrn_radiation_wavelength",
                            "_diffrn_radiation_wavelength_id",
                            "_diffrn_radiation_wavelength_wt"]))
    assert [row[1] for row in rows] == ["1", "2"]
    assert float(rows[0][2]) == 1.0 and 0.0 < float(gemmi.cif.as_number(rows[1][2])) < 1.0
    assert block.find_value("_exptl_absorpt_correction_type") == "cylinder"
    assert "Rouse" in block.find_value("_exptl_absorpt_process_details")
    assert block.find_value("_refine_ls_extinction_coef") is not None
    profile = gemmi.cif.as_string(block.find_value("_pd_proc_ls_profile_function"))
    assert profile.startswith("Voigt") and "TCHZ" not in profile


def test_a_cubic_cell_volume_esd_is_three_a_squared_sigma_a(fitted_lab6):
    """V = a³ with one free length, so σ(V) = 3a²σ(a) exactly, and the
    refinement CIF's ``_cell_volume`` carries it."""
    from rietx.io.exporters import refinement_cif_doc

    ref, result, _data = fitted_lab6
    (row,) = result.cell_volumes
    a = result.parameter("phases.0.cell.a")
    assert row.volume == pytest.approx(a.value ** 3, rel=1e-12)
    assert row.stderr == pytest.approx(3 * a.value ** 2 * a.stderr, rel=1e-9)
    block = refinement_cif_doc(result, ref.fitted_structure, ref.fitted_instrument)[0]
    assert block.find_value("_cell_volume") == format_su(row.volume, row.stderr)


def test_the_atom_types_state_the_dispersion_the_fit_used(fitted_lab6):
    """f′ and f″ at the source's wavelength, the forward model's own numbers;
    none where the fit applied none (checkCIF's PLAT981/PLAT986)."""
    from rietx.crystallography.dispersion import resolve
    from rietx.io.exporters import refinement_cif_doc

    ref, result, _data = fitted_lab6
    instrument = ref.fitted_instrument
    block = refinement_cif_doc(result, ref.fitted_structure, instrument)[0]
    rows = {r[0]: r for r in block.find(["_atom_type_symbol",
                                         "_atom_type_scat_dispersion_real",
                                         "_atom_type_scat_dispersion_imag",
                                         "_atom_type_scat_dispersion_source"])}
    lam = tuple(line.wavelength.value for line in instrument.source.lines)
    for atom in ref.fitted_structure.phases[0].atoms:
        f = resolve([atom.species], lam)[atom.species]
        row = rows[atom.species]
        assert float(row[1]) == round(f.real, 4) and float(row[2]) == round(f.imag, 4)
        assert "Cromer" in row[3]

    declined = instrument.model_copy(deep=True)
    declined.source.dispersion = None
    block = refinement_cif_doc(result, ref.fitted_structure, declined)[0]
    assert not block.find_loop("_atom_type_scat_dispersion_real")


def test_the_reflection_loop_lists_each_reflection_once(fitted_lab6, tmp_path):
    """``_refln``: one row per reflection at the primary line, hkl, the phase's
    id, d and |F|² as the reflection table computes them."""
    ref, _result, _data = fitted_lab6
    out = tmp_path / "refl.cif"
    ref.write_cif(out)
    block = gemmi.cif.read(str(out)).sole_block()
    written = list(block.find(["_refln_index_h", "_refln_index_k", "_refln_index_l",
                               "_pd_refln_phase_id", "_refln_d_spacing",
                               "_refln_F_squared_calc"]))
    rows = [r for r in ref.reflection_table() if r.line == 0]
    assert len(written) == len(rows) > 0
    for w, r in zip(written, rows, strict=True):
        assert (int(w[0]), int(w[1]), int(w[2])) == (r.h, r.k, r.l)
        assert w[3] == "1"
        assert gemmi.cif.as_number(w[4]) == pytest.approx(r.d, rel=1e-15)
        assert gemmi.cif.as_number(w[5]) == pytest.approx(r.f_squared, rel=1e-15)


def test_a_le_bail_cell_volume_carries_its_esd(fitted_lab6):
    """σ(V) in every mode: a Le Bail cell is refined as surely as a Rietveld
    one, and its scaffold atoms take nothing from it."""
    _ref, _result, data = fitted_lab6
    structure = make_lab6()
    ref = Refinement(structure, Instrument.debye_scherrer(wavelength=0.4139),
                     history=False)
    result = ref.fit(data, mode="lebail", plan="mccusker_default")
    (row,) = result.cell_volumes
    a = result.parameter("phases.0.cell.a")
    assert a.stderr is not None
    assert row.stderr == pytest.approx(3 * a.value ** 2 * a.stderr, rel=1e-9)


def test_every_line_of_a_refinement_cif_fits_in_80_columns(fitted_lab6, tmp_path):
    """checkCIF's PLAT802 counts each longer record: a type row carrying f′
    and f″ at seventeen digits, and the excluded-regions sentence, both drew it."""
    ref, _result, _data = fitted_lab6
    out = tmp_path / "w.cif"
    ref.write_cif(out)
    long = [line for line in out.read_text(encoding="utf-8").splitlines()
            if len(line) > 80]
    assert long == []


def test_refinement_result_arrays_are_faithful(fitted_lab6, tmp_path):
    """The calc/background columns are written too, not just obs."""
    ref, result, data = fitted_lab6
    out = tmp_path / "r.cif"
    ref.write_cif(out)
    text = out.read_text(encoding="utf-8")
    assert "_pd_calc_intensity_total" in text
    assert "_pd_proc_intensity_bkg_calc" in text


def test_a_le_bail_cif_states_no_composition_from_its_scaffold(fitted_lab6):
    """Outside rietveld the atoms stand in for a structure nobody supplied, so
    the refinement CIF states the cell and the setting and no formula, Z, Mr,
    density or atom types read off them (WP-1319's review)."""
    from rietx.io.exporters import refinement_cif_doc

    ref, result, _data = fitted_lab6
    chemistry = ("_chemical_formula_sum", "_chemical_formula_weight",
                 "_cell_formula_units_Z", "_exptl_crystal_density_diffrn",
                 "_atom_type_symbol")
    for mode, stated in (("rietveld", True), ("lebail", False), ("pawley", False)):
        doc = refinement_cif_doc(result.model_copy(update={"mode": mode}),
                                 ref.fitted_structure, ref.fitted_instrument)
        block = doc[0]
        assert all((block.find_value(t) is not None
                    or bool(block.find_loop(t))) is stated for t in chemistry), mode
        assert block.find_value("_space_group_name_H-M_alt") is not None
        assert block.find_value("_cell_volume") is not None
        # ...and marks its sites as the dummies they are (#756 § 2.1)
        flags = set(block.find_loop("_atom_site_calc_flag"))
        assert flags == (set() if stated else {"dum"}), mode


def test_refinement_cif_carries_the_geom_loops(fitted_lab6, tmp_path):
    """``_geom_bond`` / ``_geom_contact`` / ``_geom_angle``, resolvable as written.

    Two things beyond "the tags are present".  A ``site_symmetry`` code is an
    index into a *listed* operation order, so the block must also carry
    ``_space_group_symop_operation_xyz`` — without it the codes point at
    whatever order a reader's own expansion of the H-M symbol produced.  And
    the table lists every atom's whole environment while a CIF lists a bond
    once, so the exporter drops one direction: LaB6's B–La rows must not be in
    the file beside its La–B ones.
    """
    ref, result, data = fitted_lab6
    out = tmp_path / "geom.cif"
    ref.write_cif(out)
    doc = gemmi.cif.read(str(out))
    block = doc.sole_block()

    ops = list(block.find_loop("_space_group_symop_operation_xyz"))
    assert ops and ops[0].strip("'\"") == "x,y,z"      # the code 'n' = 1
    ids = [int(v) for v in block.find_loop("_space_group_symop_id")]
    assert ids == list(range(1, len(ops) + 1))

    bonds = list(block.find(["_geom_bond_atom_site_label_1",
                             "_geom_bond_atom_site_label_2",
                             "_geom_bond_distance",
                             "_geom_bond_site_symmetry_2"]))
    assert bonds, "LaB6 has B–B bonds"
    # esds ride inside the value, the notation every other refined number here
    # uses; a code names an operation the loop above lists (or is a plain '.')
    for row in bonds:
        assert "(" in row[2]
        code = row[3]
        assert code == "." or 1 <= int(code.split("_")[0]) <= len(ops)

    pairs = {(row[0], row[1]) for row in bonds}
    assert not any((b, a) in pairs for a, b in pairs if a != b)

    angles = list(block.find(["_geom_angle_atom_site_label_1",
                              "_geom_angle_atom_site_label_2",
                              "_geom_angle_atom_site_label_3",
                              "_geom_angle"]))
    assert angles
    text = out.read_text(encoding="utf-8")
    assert "_geom_contact_distance" in text
    # the value tag is the bare '_geom_angle' the dictionary aliases, never a
    # '_geom_angle_value' invented by prefixing
    assert "_geom_angle_value" not in text
    # a symmetry code is part of the key, so it is never unknown; bonded rows
    # are flagged for publication and contacts are not; the method is stated
    for tag in ("_geom_bond_site_symmetry_2", "_geom_contact_site_symmetry_2",
                "_geom_angle_site_symmetry_3"):
        assert "?" not in list(block.find_loop(tag)), tag
    assert set(block.find_loop("_geom_bond_publ_flag")) == {"yes"}
    assert set(block.find_loop("_geom_contact_publ_flag")) == {"no"}
    assert set(block.find_loop("_geom_angle_publ_flag")) == {"yes"}
    assert "full covariance" in " ".join(
        block.find_value("_geom_special_details").split())


def test_the_cif_torsion_loop_round_trips_the_table(fitted_lab6, tmp_path):
    """``_geom_torsion`` reads back as the table's rows (WP-1815).

    Each row the table holds comes back from the file with its four labels,
    four symmetry codes, its value and its su, in the table's order, under the
    bare ``_geom_torsion`` value tag the dictionary aliases, flagged ``no``
    for publication.  ``_geom_special_details`` names torsion angles among the
    propagated quantities only where a written torsion carries an su.  A table
    from before schema 0.60 (``torsions=None``) writes no loop.
    """
    import re

    from rietx.io.exporters import refinement_cif_doc

    def parse_su(cell: str) -> tuple[float, float | None]:
        # ``1.234(12)``: the su's digits sit in the value's last decimals
        m = re.fullmatch(r"(-?\d+(?:\.(\d*))?)(?:\((\d+)\))?", cell)
        assert m, cell
        if m[3] is None:
            return float(m[1]), None
        return float(m[1]), int(m[3]) * 10.0 ** -len(m[2] or "")

    ref, result, _data = fitted_lab6
    torsions = [t for t in result.geometry.torsions if t.phase_index == 0]
    assert torsions, "LaB6's B6 octahedra and their links form bonded chains"
    # every LaB6 torsion is symmetry-fixed (no su), so the su branch and the
    # su sentence need rows that carry one: give every other row an esd
    assert all(t.stderr is None for t in torsions)
    out = tmp_path / "plain.cif"
    ref.write_cif(out)
    plain = " ".join(gemmi.cif.read(str(out)).sole_block()
                     .find_value("_geom_special_details").split())
    assert "torsion" not in plain, "no written torsion carries an su"
    torsions = [t.model_copy(update={"stderr": 0.0137 * (k + 1)}) if k % 2 else t
                for k, t in enumerate(torsions)]
    result = result.model_copy(update={"geometry": result.geometry.model_copy(
        update={"torsions": torsions})})
    out = tmp_path / "torsions.cif"
    out.write_text(refinement_cif_doc(result, ref.fitted_structure,
                                      ref.fitted_instrument).as_string(),
                   encoding="utf-8")
    block = gemmi.cif.read(str(out)).sole_block()
    rows = list(block.find([
        *(f"_geom_torsion_atom_site_label_{k}" for k in range(1, 5)),
        "_geom_torsion",
        *(f"_geom_torsion_site_symmetry_{k}" for k in range(1, 5)),
        "_geom_torsion_publ_flag"]))
    assert len(rows) == len(torsions)
    for row, t in zip(rows, torsions, strict=True):
        assert [row[k] for k in range(4)] == [t.atom_1, t.atom_2, t.atom_3, t.atom_4]
        assert [row[k] for k in range(5, 9)] == [
            t.symmetry_1, t.symmetry_2, t.symmetry_3, t.symmetry_4]
        assert row[9] == "no"
        value, su = parse_su(row[4])
        assert -180.0 < value <= 180.0
        assert value == pytest.approx(t.angle, abs=su or 1e-9)
        assert (su is None) == (t.stderr is None)
        if su is not None:
            # format_su rounds the su to two significant digits
            assert su == pytest.approx(t.stderr, rel=0.1)
    text = out.read_text(encoding="utf-8")
    assert "_geom_torsion_value" not in text and "_geom_torsion_angle" not in text
    details = " ".join(block.find_value("_geom_special_details").split())
    assert "torsion angles" in details

    old = result.model_copy(update={"geometry": result.geometry.model_copy(
        update={"torsions": None})})
    old_block = refinement_cif_doc(old, ref.fitted_structure,
                                   ref.fitted_instrument).sole_block()
    assert not old_block.find_loop("_geom_torsion")
    assert "torsion" not in " ".join(
        old_block.find_value("_geom_special_details").split())


def test_refinement_helpers_smoke(fitted_lab6, tmp_path):
    """The three Refinement convenience methods all produce files."""
    ref, result, data = fitted_lab6
    ref.write_reflection_table(tmp_path / "refl.csv")
    ref.write_cif(tmp_path / "s.cif")
    ref.write_qpa_table(tmp_path / "qpa.csv")
    for name in ("refl.csv", "s.cif", "qpa.csv"):
        assert (tmp_path / name).stat().st_size > 0

    rows = ref.reflection_table()
    assert rows and all(r.phase == "LaB6" for r in rows)
    # single synchrotron line -> only line 0
    assert {r.line for r in rows} == {0}
