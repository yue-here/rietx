"""WP-1510 — what the chemist knows reaches the search: a formula's volume.

Three things are pinned.  A formula-unit volume is Hofmann's (2002) sum of
average atomic volumes, with its esd.  ``SearchSpec.from_formula`` turns it
into a volume ceiling the caller declares (a ceiling only since WP-2030).  And
``index_pattern(formula=...)`` records the formula units each candidate holds,
judging and removing nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rietx.crystallography.atomic_volume import (
    HOFMANN_VOLUMES,
    VOLUME_RATIO_BOUNDS,
    formula_unit_volume,
)
from rietx.indexing import index_pattern
from rietx.indexing.diagnostics import candidate_diagnostics
from rietx.indexing.engines import DEFAULT_MIN_VOLUME, SearchSpec
from rietx.schemas.indexing import CellCandidate
from tests.test_indexing_engines import synthetic_peaks

#: Benzoic acid, C7H6O2, from Hofmann's Table 2 at 298 K:
#: 7 × 13.87 + 6 × 5.08 + 2 × 11.39 Å³, and eq. (13)'s esd
#: 7 × 0.05 + 6 × 0.04 + 2 × 0.17 Å³.
BENZOIC = "C7H6O2"
BENZOIC_V = 150.35
BENZOIC_ESD = 0.93


def test_a_formula_unit_volume_is_hofmanns_sum_with_its_esd():
    volume, esd = formula_unit_volume(BENZOIC)
    assert volume == pytest.approx(BENZOIC_V, abs=1e-9)
    assert esd == pytest.approx(BENZOIC_ESD, abs=1e-9)
    # a CIF _chemical_formula_sum reads the same
    assert formula_unit_volume("C7 H6 O2") == (volume, esd)
    # eq. (1): (1 + ᾱT)/(1 + ᾱ·298 K) with ᾱ = 0.95e-4 K⁻¹, so 1.8 % smaller
    # at 100 K, and the expansion term now adds to the esd
    cold, cold_esd = formula_unit_volume(BENZOIC, temperature=100.0)
    assert cold == pytest.approx(BENZOIC_V * (1 + 0.95e-2) / (1 + 0.95e-4 * 298))
    assert cold_esd > BENZOIC_ESD * cold / BENZOIC_V
    # Kempster & Lipson's rule puts 18 Å³ on each non-hydrogen atom, and the
    # table lands near it
    assert 15.0 < volume / 9 < 18.0


def test_an_element_with_no_mean_error_has_no_esd():
    assert HOFMANN_VOLUMES["Am"] == (17.0, None)
    volume, esd = formula_unit_volume("AcCl3")
    assert volume == pytest.approx(74.0 + 3 * 25.8)
    assert esd is None


@pytest.mark.parametrize("formula,expected", [
    ("CH3CH2OH", {"C": 2, "H": 6, "O": 1}),
    ("Cu(C2H3O2)2", {"Cu": 1, "C": 4, "H": 6, "O": 4}),
    ("CuSO4·5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
])
def test_brackets_and_adducts_count(formula, expected):
    volume, _ = formula_unit_volume(formula)
    assert volume == pytest.approx(
        sum(n * HOFMANN_VOLUMES[el][0] for el, n in expected.items()))


@pytest.mark.parametrize("formula,named", [
    ("He", "no average volume for He"),
    ("Xx2", "'Xx' is not an element"),
    ("C(H2", "never closed"),
    ("", "empty part"),
])
def test_a_formula_the_table_cannot_read_raises_naming_why(formula, named):
    with pytest.raises(ValueError, match=named):
        formula_unit_volume(formula)


def test_the_window_is_a_ceiling_of_z_units_at_hofmanns_upper_bound():
    # WP-2030, ruled on #1121: a ceiling only, for every formula
    low, high = VOLUME_RATIO_BOUNDS
    assert (low, high) == (0.8, 1.25)
    spec = SearchSpec.from_formula(BENZOIC, z=4, max_d_axis=32.0)
    assert spec.min_volume == DEFAULT_MIN_VOLUME
    assert spec.max_volume == pytest.approx(4 * BENZOIC_V * 1.25)
    assert spec.max_d_axis == 32.0
    # only the largest z sets the ceiling; the smallest narrows nothing
    ranged = SearchSpec.from_formula(BENZOIC, z=(2, 8))
    assert (ranged.min_volume, ranged.max_volume) == pytest.approx(
        (DEFAULT_MIN_VOLUME, 8 * BENZOIC_V * 1.25))
    # the pair's minimum is validated and then ignored: the same spec for any
    # minimum, as the docstring says
    assert SearchSpec.from_formula(BENZOIC, z=(4, 8)) == SearchSpec.from_formula(
        BENZOIC, z=(1, 8))
    # no Z: the window narrows nothing
    bare = SearchSpec.from_formula(BENZOIC)
    assert (bare.min_volume, bare.max_volume) == (DEFAULT_MIN_VOLUME, None)
    assert bare == SearchSpec()
    # a floor is the caller's to declare beside the formula
    floored = SearchSpec.from_formula(BENZOIC, z=4, min_volume=400.0)
    assert floored.min_volume == 400.0
    with pytest.raises(ValueError, match="sets max_volume"):
        SearchSpec.from_formula(BENZOIC, z=4, max_volume=900.0)
    # a ceiling under the floor would search nothing, and says so
    with pytest.raises(ValueError, match="below the 15 Å³ floor"):
        SearchSpec.from_formula("H2", z=1)
    with pytest.raises(ValueError, match="below the 800 Å³ floor"):
        SearchSpec.from_formula(BENZOIC, z=4, min_volume=800.0)
    # an explicit None names the field, not a bare TypeError from the comparison
    with pytest.raises(ValueError, match="min_volume"):
        SearchSpec.from_formula(BENZOIC, z=4, min_volume=None)


@pytest.mark.parametrize("z", [0, (4, 2), 2.5])
def test_a_z_that_is_not_a_whole_count_raises(z):
    with pytest.raises(ValueError, match="whole number"):
        SearchSpec.from_formula(BENZOIC, z=z)


def _candidate(volume: float) -> CellCandidate:
    a = volume ** (1.0 / 3.0)
    return CellCandidate(cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(0.0,) * 6,
                         system="cubic", volume=volume)


def test_no_diagnostic_judges_the_number_of_formula_units():
    # WP-2030: INDEX_Z_NOT_INTEGER is withdrawn; candidate_diagnostics reads no
    # formula, so a cell of 2.5 formula units carries nothing about it
    diags = candidate_diagnostics(_candidate(2.5 * BENZOIC_V))
    assert [d.code for d in diags if "Z_NOT" in d.code] == []
    with pytest.raises(TypeError):
        candidate_diagnostics(_candidate(2.5 * BENZOIC_V), formula=BENZOIC)


def test_index_pattern_records_the_formula_units_and_keeps_the_candidate():
    # methanol's 45.58 Å³ against the synthetic cubic cell's 71.8 Å³: 1.58
    # formula units, recorded on every candidate, the true cell still ranked
    peaks, true_cell = synthetic_peaks("cubic")
    spec = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                      max_volume=1500.0, shift_allowance_deg=1e-9)
    res = index_pattern(peaks, spec=spec, preset="full",
                        engines=("trial_error",), formula="CH3OH")
    truth = next(c for c in res.candidates
                 if c.cell[0] == pytest.approx(true_cell[0], rel=1e-3))
    v_fu, _ = formula_unit_volume("CH3OH")
    assert truth.formula_units == pytest.approx(truth.volume / v_fu)
    assert truth.formula_units == pytest.approx(1.58, abs=0.01)
    assert all(c.formula_units == pytest.approx(c.volume / v_fu)
               for c in res.candidates)
    assert not any("Z_NOT" in d.code for c in res.candidates
                   for d in c.diagnostics)
    # no formula: nothing recorded, and nothing claims it was
    bare = index_pattern(peaks, spec=spec, preset="full",
                         engines=("trial_error",))
    assert [c.formula_units for c in bare.candidates] == [None] * len(bare.candidates)
    assert [c.cell for c in bare.candidates] == [c.cell for c in res.candidates]


def test_index_pattern_refuses_a_bad_formula_before_any_work():
    peaks, _ = synthetic_peaks("cubic")
    with pytest.raises(ValueError, match="not an element"):
        index_pattern(peaks, formula="Qq2")


# ----------------------------------------------------------------------
# WP-2030: the window and the formula units against known cells, measured
# ----------------------------------------------------------------------
def _volume(a, b, c, al=90.0, be=90.0, ga=90.0):
    import math

    ca, cb, cg = (math.cos(math.radians(x)) for x in (al, be, ga))
    return a * b * c * math.sqrt(1 - ca * ca - cb * cb - cg * cg + 2 * ca * cb * cg)


_DATA = Path(__file__).parent / "data"
#: NIST certifies SRM 640c's and SRM 676a's cells at 22.5 °C
#: (``tests/data/README.md``, both certificates).
_NIST_CERTIFIED_K = 273.15 + 22.5


def _gallery(key: str) -> float:
    """The volume of a cell in ``tests/indexing_gallery.TRUTHS``, the tree's
    one copy of the round-robin and standards cells: imported, not retyped."""
    from tests.indexing_gallery import TRUTHS

    return _volume(*TRUTHS[key][0])


def _si640c() -> float:
    from tests.test_acceptance_si640c import A_CERT

    return _volume(A_CERT, A_CERT, A_CERT)


def _cif(name: str) -> tuple[int, float, float]:
    """(Z, V, T) as a vendored COD CIF states them: ``_cell_formula_units_Z``,
    ``_cell_volume`` and the cell's measurement temperature (the
    diffraction temperature where the file gives no other), else 298 K."""
    import re

    text = (_DATA / name).read_text(encoding="utf-8")

    def item(tag):
        m = re.search(rf"^{tag}\s+'?([-0-9.]+)", text, re.M)
        return None if m is None else float(m.group(1))

    t = item("_cell_measurement_temperature") or item("_diffrn_ambient_temperature")
    return int(item("_cell_formula_units_Z")), item("_cell_volume"), t or 298.0


#: Known cells, each with its source: ``(formula, Z, V_true Å³, T K, organic)``.
#: The inorganic rows are every inorganic standard in ``tests/data/`` with a
#: certified, published or cross-code cell (``tests/data/README.md`` and
#: ``tests/indexing_gallery.py`` name each), plus halite.  The organic and
#: metal-organic rows are the published cells in ``tests/data/`` and one more.
#: Each value is read from where the tree already holds it, the gallery, the
#: SRM 640c test or a vendored CIF, never retyped.  T is the cell's own
#: temperature where its source states one, else 298 K.
KNOWN_CELLS: dict[str, tuple[str, int, float, float, bool]] = {
    # NIST SRM 660c certificate, nist_srm660c_100a.cif's _meas block, at 20.85 °C
    "LaB6": ("LaB6", 1, _gallery("lab6"), 294.0, False),
    # NIST SRM 640c certificate, a = 5.4311946 Å at 22.5 °C
    "Si": ("Si", 8, _si640c(), _NIST_CERTIFIED_K, False),
    # NIST SRM 676a certificate, a = 4.759355, c = 12.99231 Å at 22.5 °C
    "corundum": ("Al2O3", 6, _gallery("corundum"), _NIST_CERTIFIED_K, False),
    # 11-BM NAC's cell (gallery); Z from COD 1000236 (cod_1000236.cif,
    # Courbion & Férey 1988, J. Solid State Chem.)
    "NAC": ("Na2Ca3Al2F14", _cif("cod_1000236.cif")[0], _gallery("nac"), 298.0, False),
    # GSAS's converged cell in FAP.EXP (cross-code)
    "fluorapatite": ("Ca5P3O12F", 2, _gallery("fap"), 298.0, False),
    # the IUCr CPD round robin's literature cells (indexing_gallery.SPECIMENS)
    "zincite": ("ZnO", 2, _gallery("zincite"), 298.0, False),
    "zircon": ("ZrSiO4", 4, _gallery("zircon"), 298.0, False),
    "brucite": ("Mg(OH)2", 1, _gallery("brucite"), 298.0, False),
    "magnetite": ("Fe3O4", 8, _gallery("magnetite"), 298.0, False),
    "fluorite": ("CaF2", 4, _gallery("fluorite"), 298.0, False),
    # COD 9003308 (cod_9003308.cif): Walker et al. (2004), Am. Mineral. 89,
    # 204, a = 5.6401 Å at 25 °C
    "halite": ("NaCl", *_cif("cod_9003308.cif"), False),
    # cubic BN in 11BM_LaB6_cBN_mg2044: TOPAS's cell (test_acceptance_lab6_cbn.py)
    "cBN": ("BN", 4, _volume(3.616463, 3.616463, 3.616463), 295.0, False),
    # GSAS-II's converged cells in the vendored tutorial projects
    "anglesite": ("PbSO4", 4, _volume(8.480443, 5.398619, 6.960131), 298.0, False),
    "hausmannite": ("Mn3O4", 4, _volume(5.763447, 5.763447, 9.452202), 10.0, False),
    "LCMO": ("La0.8Ca0.2MnO3", 4, _volume(5.482827, 5.466795, 7.724880), 50.0, False),
    # COD 9007744 (cod_9007744.cif, Acta Cryst. C 1990), which states no
    # temperature
    "YBCO": ("Ba2 Cu2.941 O6.822 Y", *_cif("cod_9007744.cif"), False),
    # COD 2104364 (cod_2104364.cif) at 100 K
    "paracetamol": ("C8H9NO2", *_cif("cod_2104364.cif"), True),
    # COD 7252065 (cod_7252065.cif) at 298 K: Rajput & Dalvi (2026),
    # CrystEngComm, doi:10.1039/D6CE00164E
    "benzoic acid": ("C7H6O2", *_cif("cod_7252065.cif"), True),
    # Bergmann, Le Bail, Shirley & Zlokazov (2004), Z. Kristallogr. 219, 783
    "bethanechol chloride": ("C7H17ClN2O2", 4,
                             _volume(8.875, 16.408, 7.137, 90.0, 93.84, 90.0), 298.0, True),
    # COD 4002052 (cod_4002052.cif) at 273 K: HKUST-1, a porous framework
    # written without its pore contents
    "HKUST-1": ("C18H6Cu3O12", *_cif("cod_4002052.cif"), True),
    # COD 4003235 (cod_4003235.cif) at 293 K, a hybrid lead iodide
    "hybrid iodide": ("C10H36I10N4Pb3", *_cif("cod_4003235.cif"), True),
}

#: Measured (WP-2030, 2026-10-23; unchanged by part 2, which moved no volume):
#: V_true / (Z × V_est), the ratio Hofmann (2002, § 3) marks unusual outside
#: 0.8-1.25.  Every inorganic cell but halite's lies under 0.8, at 0.375-0.649,
#: and nine of them under 0.57, the edge of his § 3 (i), "Z entered wrongly".
#: That is why the shipped window's floor excluded all but halite, and why
#: part 2 dropped it for every formula (ruled on #1121, 2026-10-24).  HKUST-1
#: lies above 1.25 the other way: its formula leaves the pores' contents out,
#: his § 3 (ii).
MEASURED: dict[str, float] = {
    "LaB6": 0.523, "Si": 0.537, "corundum": 0.375, "NAC": 0.637,
    "fluorapatite": 0.568, "zincite": 0.473, "zircon": 0.593, "brucite": 0.591,
    "magnetite": 0.541, "fluorite": 0.605, "halite": 0.866, "cBN": 0.472,
    "anglesite": 0.649, "hausmannite": 0.571, "LCMO": 0.488, "YBCO": 0.523,
    "paracetamol": 1.000, "benzoic acid": 1.026, "bethanechol chloride": 1.014,
    "HKUST-1": 2.283, "hybrid iodide": 1.044,
}
#: The one known cell the ceiling does not hold: a framework written without
#: what fills its pores.
ABOVE_THE_CEILING = {"HKUST-1"}


@pytest.mark.parametrize("name", sorted(KNOWN_CELLS))
def test_every_known_cell_lies_inside_its_window(name):
    """WP-2030's acceptance: the true cell inside ``from_formula``'s window at
    its true Z, for every inorganic and organic cell measured, and nothing
    narrowed at ``z=None``."""
    formula, z, v_true, t, _organic = KNOWN_CELLS[name]
    v_fu, _ = formula_unit_volume(formula, t)
    assert v_true / (z * v_fu) == pytest.approx(MEASURED[name], abs=5e-4)
    spec = SearchSpec.from_formula(formula, z=z, temperature=t)
    inside = spec.min_volume <= v_true <= spec.max_volume
    assert inside is (name not in ABOVE_THE_CEILING)
    bare = SearchSpec.from_formula(formula, temperature=t)
    assert (bare.min_volume, bare.max_volume) == (DEFAULT_MIN_VOLUME, None)


def test_the_fluorapatite_window_holds_its_cell():
    # the WP's case: 1.10.0's window was 738-1153 Å³ and missed this cell
    spec = SearchSpec.from_formula("Ca5P3O12F", z=2)
    v_true = KNOWN_CELLS["fluorapatite"][2]
    assert 523 < v_true < 524
    assert spec.min_volume <= v_true <= spec.max_volume
    assert spec.max_volume == pytest.approx(1153.0, abs=1.0)


@pytest.mark.parametrize("name", sorted(KNOWN_CELLS))
def test_the_formula_units_of_a_known_cell_bound_its_z_from_below(name):
    """``formula_units`` is Z × the measured ratio: a correct inorganic cell
    reads 0.4-0.9 of its Z, which no whole-number test can tell from a wrong
    Z (the maintainer on #1121).  The ceiling still bounds Z from below,
    Z ≥ formula_units / 1.25, on every cell it holds."""
    formula, z, v_true, t, _organic = KNOWN_CELLS[name]
    v_fu, _ = formula_unit_volume(formula, t)
    units = _candidate(v_true).volume / v_fu
    assert units == pytest.approx(z * MEASURED[name], rel=1e-3)
    assert (z >= units / VOLUME_RATIO_BOUNDS[1]) is (name not in ABOVE_THE_CEILING)


# ----------------------------------------------------------------------
# WP-2030: a hydrate written with a full stop
# ----------------------------------------------------------------------
def test_a_full_stop_hydrate_is_refused_naming_the_raised_dot():
    # read as a decimal it would be CuS O4.5 H10 O5, 39 % low (WP-1510's review)
    with pytest.raises(ValueError, match="·") as err:
        formula_unit_volume("CuSO4.5H2O")
    assert "the count 4.5" in str(err.value)
    assert "CuSO4 · 5H2O" in str(err.value)


@pytest.mark.parametrize("formula,expected", [
    # a count under 1 cannot be the first half of an adduct: no formula
    # writes a count of zero
    ("Mg0.5SiO3", {"Mg": 0.5, "Si": 1, "O": 3}),
    ("CuSO4·5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
    ("CuSO4·2.5H2O", {"Cu": 1, "S": 1, "O": 6.5, "H": 5}),
    # a space after the decimal count, as a CIF _chemical_formula_sum writes it
    ("Fe2.95 O4", {"Fe": 2.95, "O": 4}),
    ("Ba2 Cu2.941 O6.822 Y", {"Ba": 2, "Cu": 2.941, "O": 6.822, "Y": 1}),
    # doped oxides and cathodes written with no spaces: a decimal count whose
    # tail is not an adduct molecule reads one way (the 1.9.0 reading)
    ("Fe2.95O4", {"Fe": 2.95, "O": 4}),
    ("Li1.05Mn1.95O4", {"Li": 1.05, "Mn": 1.95, "O": 4}),
    ("Fe1.05S", {"Fe": 1.05, "S": 1}),
    ("Li1.2Mn0.54Ni0.13Co0.13O2",
     {"Li": 1.2, "Mn": 0.54, "Ni": 0.13, "Co": 0.13, "O": 2}),
    ("Ca9.5(PO4)6F2", {"Ca": 9.5, "P": 6, "O": 24, "F": 2}),
    ("Sr1.5La0.5MnO4", {"Sr": 1.5, "La": 0.5, "Mn": 1, "O": 4}),
    ("Ba2Cu2.941O6.822Y", {"Ba": 2, "Cu": 2.941, "O": 6.822, "Y": 1}),
])
def test_a_formula_that_reads_one_way_is_unchanged(formula, expected):
    volume, _ = formula_unit_volume(formula)
    assert volume == pytest.approx(
        sum(n * HOFMANN_VOLUMES[el][0] for el, n in expected.items()))


@pytest.mark.parametrize("formula", [
    "Na2CO3.10H2O", "CuSO4.5 H2O", "MgSO4.7 H2O", "CuSO4.5H2O·H2O",
    "CoCl2.6H2O", "ZnSO4.6NH3",
    # any whitespace before the molecule, and inside it: a copy from a PDF or a
    # web page brings a non-breaking space, and a CIF sum writes H2 O
    "CuSO4.5  H2O", "CuSO4.5\u00a0H2O", "CuSO4.5 H2 O", "CuSO4.5\tH2O",
    "CuSO4.5 \u00a0H2 O ", "CoCl2.6 H2 O"])
def test_every_full_stop_that_reads_two_ways_is_refused(formula):
    with pytest.raises(ValueError, match="reads two ways"):
        formula_unit_volume(formula)


# ----------------------------------------------------------------------
# WP-2030: the result records the formula it read
# ----------------------------------------------------------------------
def test_the_result_records_the_formula_and_temperature_it_checked():
    from rietx.schemas.indexing import IndexingResult

    peaks, _ = synthetic_peaks("cubic")
    spec = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                      max_volume=1500.0, shift_allowance_deg=1e-9)
    res = index_pattern(peaks, spec=spec, preset="full",
                        engines=("trial_error",), formula="CH3OH",
                        temperature=150.0)
    assert (res.formula, res.temperature) == ("CH3OH", 150.0)
    back = IndexingResult.model_validate_json(res.model_dump_json())
    assert (back.formula, back.temperature) == ("CH3OH", 150.0)

    # no formula: no check was made, and nothing claims one was
    bare = index_pattern(peaks, spec=spec, preset="full",
                         engines=("trial_error",))
    assert (bare.formula, bare.temperature) == (None, None)
    with pytest.raises(ValueError, match="needs a formula"):
        IndexingResult.model_validate({**bare.model_dump(), "temperature": 298.0})

    # the abstention path records it too: four lines support no search
    short = peaks.model_copy(update={"peaks": peaks.peaks[:4]})
    abstained = index_pattern(short, spec=spec, formula="CH3OH")
    assert abstained.candidates == []
    assert (abstained.formula, abstained.temperature) == ("CH3OH", 298.0)


def test_the_cli_hands_the_formula_to_index_pattern(monkeypatch, capsys):
    import rietx.indexing as indexing
    from rietx.cli import main

    seen = {}

    class _Result:
        def __str__(self):
            return "stub"

        def best_or_none(self):
            return None

    def fake(**kwargs):
        seen.update(kwargs)
        return _Result()

    monkeypatch.setattr(indexing, "index_pattern", fake)
    pattern = str(Path(__file__).parent / "data" / "qarr" / "zincite.prn")
    rc = main(["index", pattern, "--wavelength", "1.5405929",
               "--formula", "ZnO", "--temperature", "100"])
    assert rc == 1
    assert (seen["formula"], seen["temperature"]) == ("ZnO", 100.0)
    main(["index", pattern, "--wavelength", "1.5405929"])
    assert (seen["formula"], seen["temperature"]) == (None, 298.0)
