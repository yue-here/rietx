"""The GSAS-I ``.EXP`` reader, against a real converged refinement.

``tests/data/FAP.EXP`` is GSAS's own fluorapatite fit — the file every constant
in ``test_acceptance_fap.py`` used to be read out of by hand — so the rows here
check the reader against a protocol somebody already verified independently.

**The load-bearing row is the last one.** ``REFN GDNFT`` states the number of
variables the refinement had, in words, in a record the reader does not use to
build anything; the refine flags are stated separately, spread across the cell
record, seven atom records, the background header, the scale record and the
profile header.  Reconstructing 28 from the flags is therefore a check of the
whole protocol recovery against a number the file states somewhere else — the
one assertion here that no single-field bug can pass.

Fixtures for the refusal rows are written inline rather than vendored: the
shapes they test (a magnetic phase, an unnamed profile function) are not in any
file this repo may carry, and a synthetic 80-column card is self-describing.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import rietx as rx
from rietx.io.projects.gsas import (
    CW_CENTIDEG_POWER,
    CW_PROFILE_COEFFICIENTS,
    GsasExpError,
    from_structure,
    read_gsas_exp,
    split_records,
    to_structure,
    write_gsas_exp,
)

DATA = Path(__file__).parent / "data"
FAP = DATA / "FAP.EXP"


@pytest.fixture(scope="module")
def fap():
    return read_gsas_exp(FAP)


# --------------------------------------------------------------- what it says

def test_overall_records(fap):
    assert fap.title == "fluoroapatite"
    assert fap.version == 6
    assert fap.rwp == pytest.approx(0.1005)
    assert fap.rp == pytest.approx(0.0766)
    assert fap.n_observations == 5750
    assert fap.n_variables == 28


def test_gdnft_is_reduced_chi_squared_not_its_root(fap):
    """The record says "Reduced CHI**2" in words, and it is not a GoF.

    Issue #103 brought this from a GSAS-II ``.gpx`` campaign, and this docstring
    used to add that ``Rvals['GOF']`` is the same convention.  It is not:
    WP-1118 measured GSAS-II's figure at ``sqrt(chisq / (Nobs - Nvars))``, which
    ``test_projects_gsas2.py`` now asserts on a real project.  The claim here is
    about this record alone, where the file states the words itself.
    """
    assert fap.reduced_chi2 == pytest.approx(3.224)


def test_phase_cell_and_esds(fap):
    (phase,) = fap.phases
    assert phase.name == "fap"
    assert phase.space_group == "P 63/m"
    assert phase.kind == 1
    cell = phase.cell
    assert cell.a == pytest.approx(9.371724)
    assert cell.c == pytest.approx(6.885867)
    assert (cell.alpha, cell.beta, cell.gamma) == (90.0, 90.0, 120.0)
    assert cell.esd_a == pytest.approx(3.6e-5)
    assert cell.esd_c == pytest.approx(3.7e-5)
    assert cell.refined is True
    # CELVOL is 2F15.3 in the file against the manual's printed 2F10.3, and
    # reading it at the printed width gives 52.0 -- a plausible number, so the
    # file is the authority and this row is what holds it there.
    assert cell.volume == pytest.approx(523.755)


def test_atoms_carry_the_files_own_refine_flags(fap):
    (phase,) = fap.phases
    assert [a.label for a in phase.atoms] == [
        "CA1", "CA2", "P3", "F4", "O5", "O6", "O7"]
    ca1 = phase.atoms[0]
    assert ca1.species == "CA"          # the file's spelling, not yet IUCr's
    assert (ca1.x, ca1.y, ca1.z) == pytest.approx((0.333333, 0.666667, 0.001913))
    assert ca1.occupancy == pytest.approx(1.0)
    assert ca1.multiplicity == 4
    assert ca1.uiso == pytest.approx(0.006079)
    assert ca1.uij is None and not ca1.anisotropic
    # 'I XU' on the B record: isotropic; occupancy held; coordinates and
    # displacement free.  A blank letter is the file saying held.
    assert (ca1.refine_xyz, ca1.refine_u, ca1.refine_occupancy) == (True, True, False)
    assert all(a.refine_xyz and a.refine_u and not a.refine_occupancy
               for a in phase.atoms)


def test_histogram_icons_is_read_by_column(fap):
    """``ICONS``' trailing fields are positional, and 0.5 is not the ratio.

    Both the polarization fraction and a Kα2/Kα1 ratio are conventionally 0.5,
    so a reader that took the wrong field would agree with the right one on
    this file and disagree on the next.  ``FAP.EXP`` states POLA and leaves
    KRATIO blank; ``INST_XRY.PRM`` beside it states POLA 0.7 *and* KRATIO 0.5
    in the same slots, which is what fixes the order.
    """
    (hist,) = fap.histograms
    assert hist.kind == "PXC"
    assert hist.wavelengths == pytest.approx((1.5405, 1.5443))
    assert hist.zero == 0.0 and hist.refine_zero is False
    assert hist.polarization == pytest.approx(0.5)
    assert hist.polarization_type == 0
    assert hist.ka2_ratio is None       # blank field: the file states no ratio
    assert hist.anode == "Cu"           # IRAD 3
    assert hist.data_file == "fap.xra"
    assert hist.bank == 1


def test_histogram_ranges_and_channel_counts(fap):
    (hist,) = fap.histograms
    # the degenerate 0-0 low-side pair GSAS always writes is not a region
    assert hist.excluded_regions == ((130.0, 1000.0),)
    assert hist.two_theta_range == pytest.approx((15.0, 129.98))
    assert hist.n_channels_used == 5750
    assert hist.n_channels_total == 5753
    assert hist.scale == pytest.approx(96.636) and hist.refine_scale is True


def test_background_is_carried_but_not_converted(fap):
    (hist,) = fap.histograms
    bkg = hist.background
    assert bkg.function == 5            # a reciprocal-Q expansion, not a polynomial
    assert bkg.n_coefficients == 3
    assert bkg.coefficients == pytest.approx((41.8073, 702.33, 3.40611))
    assert bkg.refined is True


def test_profile_names_come_from_the_function_type(fap):
    """Type 2's coefficient 4 is LX, and its 8 is shft rather than GP.

    The manual's own function-2 paragraph lists the eighteen coefficients twice
    and transposes positions 8 and 9 between the two lists.  GSAS's EXPEDT
    listing prints ``#8(shft)``, and this file's converged sample displacement
    sits at index 8, which is what settles it.
    """
    profile = fap.profile()
    assert profile.function == 2
    assert profile.n_coefficients == 18
    terms = profile.by_name()
    assert terms["LX"].index == 4
    assert terms["shft"].index == 8
    assert terms["GP"].index == 9
    assert terms["GU"].value == pytest.approx(2.0)
    assert terms["shft"].value == pytest.approx(4.90166)


def test_centidegree_conversion(fap):
    """A variance term is centideg², a width or a shift is centideg."""
    terms = fap.profile().by_name()
    assert terms["GU"].degrees == pytest.approx(2e-4)
    assert terms["GV"].degrees == pytest.approx(-2e-4)
    assert terms["GW"].degrees == pytest.approx(5e-4)
    assert terms["LX"].degrees == pytest.approx(0.0335183)
    assert terms["LY"].degrees == pytest.approx(0.0248803)
    assert terms["shft"].degrees == pytest.approx(0.0490166)
    # a compound unit is not converted, and says so rather than returning the
    # file's number as though it were degrees
    assert terms["L11"].degrees is None


def test_the_refined_profile_terms_are_the_protocol(fap):
    assert fap.profile().refined_names == ("LX", "LY", "shft")


def test_the_default_profile_is_the_instrument_files_starting_point(fap):
    """``HST``'s own ``PRCF`` set is where the histogram started, not where it
    ended; the refined values live on the ``HAP`` record."""
    (hist,) = fap.histograms
    (default,) = hist.default_profiles
    assert [t.value for t in default.terms] == pytest.approx(
        [2.0, -2.0, 5.0, 1.0, 1.0, 0.0])
    assert not any(t.refined for t in default.terms)


# ----------------------------------------------------------- what it builds

def test_to_structure_carries_the_flags_and_converts_uiso(fap):
    notes: list = []
    structure = to_structure(fap, diagnostics=notes)
    (phase,) = structure.phases
    assert phase.space_group == "P 63/m"
    assert phase.cell.a.vary is True and phase.cell.a.value == pytest.approx(9.371724)
    ca1 = phase.atoms[0]
    assert ca1.species == "Ca"          # normalised, and reported
    assert ca1.biso.value == pytest.approx(0.006079 * 8.0 * 3.141592653589793**2)
    assert ca1.biso.vary is True
    assert ca1.occ.vary is False
    assert any(n.code == "GSAS_EXP_SPECIES_NORMALISED" for n in notes)


def test_a_zero_freedom_site_does_not_get_a_vary_it_cannot_honour(fap):
    """GSAS's X flag means "as permitted by symmetry", and F4 has none.

    Carrying the flag onto x/y/z directly makes ``ParameterTable`` refuse the
    whole import of a file GSAS refined happily, so the flag goes through the
    site-symmetry basis GSAS was speaking about.
    """
    notes: list = []
    structure = to_structure(fap, diagnostics=notes)
    f4 = next(a for a in structure.phases[0].atoms if a.label == "F4")
    assert f4.x.vary is False
    assert f4.biso.vary is True         # the U flag is unaffected
    assert any(n.code == "GSAS_EXP_COORDINATES_SYMMETRY_FIXED" for n in notes)
    # and the structure is one the package will actually build a table for
    rx.Refinement(structure, rx.Instrument.bragg_brentano())


def test_the_recovered_protocol_reproduces_gsas_own_variable_count(fap):
    """21 structural + 1 scale + 3 background + 3 profile = the file's own 28.

    The flags are spread over eleven records and the count is stated in a
    twelfth that the reader never consults.  This is the row that no
    single-field misreading survives.
    """
    structure = to_structure(fap)
    ref = rx.Refinement(structure, rx.Instrument.bragg_brentano())
    structural = sum(1 for r in ref.parameters() if r.refinable and r.vary)
    assert structural == 21             # cell a and c, 12 coordinate DOFs, 7 Biso

    (hist,) = fap.histograms
    total = (structural
             + (1 if hist.refine_scale else 0)
             + (hist.background.n_coefficients if hist.background.refined else 0)
             + len(fap.profile().refined_names)
             + (1 if fap.hap[(1, 1)].refine_phase_fraction else 0))
    assert total == fap.n_variables == 28


# ------------------------------------------------------------- what it refuses

def _card(key: str, payload: str = "") -> str:
    return f"{key:<12}{payload:<68}"


def _exp(tmp_path: Path, name: str, *cards: str) -> Path:
    path = tmp_path / name
    path.write_text("\r\n".join(cards) + "\r\n", encoding="latin-1")
    return path


_MINIMAL = (
    _card("     VERSION", "    6"),
    _card("      DESCR ", "  a phase"),
    _card(" EXPR NPHAS ", "    1"),
    _card("CRS1    PNAM", "  one"),
    _card("CRS1  ABC   ", "  4.000000  4.000000  4.000000    Y    0"),
    _card("CRS1  ANGLES", "   90.0000   90.0000   90.0000"),
    _card("CRS1  SG SYM", "  P m -3 m"),
    _card("CRS1  AT  1A", "  NA        0.000000  0.000000  0.000000  1.000000NA1        1 000"),
    _card("CRS1  AT  1B", "  0.010000                                                    I  U"),
)


def test_a_file_with_no_experiment_records_is_refused_by_name(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("this is not a GSAS experiment file\n", encoding="utf-8")
    with pytest.raises(GsasExpError, match="holds no GSAS experiment records"):
        read_gsas_exp(path)


def test_an_empty_file_is_refused(tmp_path):
    path = tmp_path / "empty.EXP"
    path.write_bytes(b"")
    with pytest.raises(GsasExpError, match="the file is empty"):
        read_gsas_exp(path)


def test_records_without_line_terminators_still_read(tmp_path):
    """Some writers emit the 80-character cards with no line breaks at all."""
    path = tmp_path / "flat.EXP"
    path.write_text("".join(_MINIMAL), encoding="latin-1")
    model = read_gsas_exp(path)
    assert model.phases[0].name == "one"
    assert model.phases[0].cell.a == pytest.approx(4.0)


def test_a_record_after_the_terminator_is_still_read(tmp_path):
    path = _exp(tmp_path, "tail.EXP", *_MINIMAL,
                _card("ZZZZZZZZZZZZ", "  Last EXP file record"),
                _card("    HSTRY 17", " GENLES appended after the end marker"))
    model = read_gsas_exp(path)
    assert model.phases[0].name == "one"


def test_a_fractional_unit_cell_content_is_read_at_its_own_columns(tmp_path):
    """``CHMF`` is ``2X, A8, F10.2``, and this repo's one fixture hides it.

    Every content in ``FAP.EXP`` ends ``.00``, so a read two columns short
    still floats to the right number — ``'  CA            5.00'`` sliced at
    ``[8:18]`` is ``'        5.'``, which is 5.0.  A partially occupied site is
    where the offset shows, and it is the ordinary case for a solid solution.
    Found while writing the writer, which had to know the true columns.
    """
    cards = list(_MINIMAL) + [_card("CRS1  CHMF 1", "  NA            5.25")]
    model = read_gsas_exp(_exp(tmp_path, "content.EXP", *cards))
    assert model.phases[0].formula == (("NA", 5.25),)


def test_a_negative_uiso_is_read_with_its_bound_widened(tmp_path):
    """A real GSAS refinement reaches one and GSAS stores it, so the reader
    keeps the file's number, widens the floor to hold it and says so
    (PR #663)."""
    cards = list(_MINIMAL)
    cards[-1] = _card("CRS1  AT  1B",
                      " -0.010000                                                    I  U")
    path = _exp(tmp_path, "negative.EXP", *cards)
    model = read_gsas_exp(path)
    assert model.phases[0].atoms[0].uiso == pytest.approx(-0.01)
    diagnostics = []
    biso = to_structure(model, diagnostics=diagnostics).phases[0].atoms[0].biso
    b = -0.01 * 8 * math.pi ** 2
    assert (biso.value, biso.min) == (pytest.approx(b), pytest.approx(b))
    assert "BISO_BOUND_WIDENED" in [d.code for d in diagnostics]


def test_a_schema_refusal_is_converted_rather_than_leaked(tmp_path):
    """The class, not a third instance: no pydantic error reaches a caller.

    An occupancy of 40 is in no real file and is checked for by name nowhere.
    It must still come back naming the file (``io/CLAUDE.md`` § Refusals).
    """
    cards = list(_MINIMAL)
    cards[-2] = _card(
        "CRS1  AT  1A",
        "  NA        0.000000  0.000000  0.000000 40.000000NA1        1 000")
    path = _exp(tmp_path, "occupancy.EXP", *cards)
    with pytest.raises(GsasExpError, match="occupancy.EXP"):
        to_structure(read_gsas_exp(path))


def test_a_half_stated_two_theta_range_is_none_rather_than_half(tmp_path):
    """Both halves or neither, under a ``tuple[float, float] | None``.

    A ``TRNGE`` with one blank field used to hand back ``(None, 129.98)``, and
    a caller unpacking two floats got a ``None`` far from the record it came
    off (WP-1076's shape, found by the same review pass).
    """
    path = _exp(tmp_path, "trnge.EXP", *_MINIMAL,
                _card(" EXPR  HTYP1", "  PXC"),
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HST  1TRNGE ", "              129.9800"))
    histogram = read_gsas_exp(path).histogram(1)
    assert histogram.two_theta_range is None


def test_an_unnamed_profile_function_is_refused_rather_than_read_positionally(tmp_path):
    """Function 4's coefficient list is "14 to 27 … S400, etc." in the manual.

    Reading it under function 2's names would put ``LX`` on a coefficient that
    is ``ptec``, which is a plausible wrong width rather than an error.
    """
    path = _exp(tmp_path, "fn4.EXP", *_MINIMAL,
                _card(" EXPR  HTYP1", "  PXC"),
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HAP1 1PRCF  ", "    4   14   0.01000    0NNNNNNNNNNNNNN"),
                _card("HAP1 1PRCF 1", "   0.200000E+01   0.000000E+00   0.000000E+00   0.000000E+00"))
    with pytest.raises(GsasExpError, match="profile function 4"):
        read_gsas_exp(path)


def test_the_named_functions_all_have_a_unit_for_every_coefficient():
    """Every name in the coefficient table either converts or says it does not.

    A name reachable from :data:`CW_PROFILE_COEFFICIENTS` but absent from
    :data:`CW_CENTIDEG_POWER` returns ``degrees=None``, which is the honest
    answer only where the unit really is compound.  This pins which those are,
    so a new function type cannot quietly add a fourth.
    """
    named = {n for names in CW_PROFILE_COEFFICIENTS.values() for n in names}
    unconverted = sorted(named - set(CW_CENTIDEG_POWER))
    assert unconverted == ["L11", "L12", "L13", "L22", "L23", "L33"]


def test_a_magnetic_phase_is_refused_by_name(tmp_path):
    cards = list(_MINIMAL)
    cards[2] = _card(" EXPR NPHAS ", "    2")
    path = _exp(tmp_path, "mag.EXP", *cards)
    model = read_gsas_exp(path)
    assert model.phases[0].magnetic
    with pytest.raises(GsasExpError, match="magnetic"):
        to_structure(model)


def test_an_anisotropic_site_is_refused_until_a_file_settles_the_convention(tmp_path):
    cards = list(_MINIMAL)
    cards[-1] = _card(
        "CRS1  AT  1B",
        "  0.010000  0.010000  0.010000  0.000000  0.000000  0.000000  A  U")
    path = _exp(tmp_path, "aniso.EXP", *cards)
    model = read_gsas_exp(path)
    assert model.phases[0].atoms[0].anisotropic
    assert model.phases[0].atoms[0].uij == pytest.approx(
        (0.01, 0.01, 0.01, 0.0, 0.0, 0.0))
    with pytest.raises(GsasExpError, match="off-diagonal convention"):
        to_structure(model)


def test_a_multi_phase_file_refuses_to_pick_one(tmp_path):
    cards = [*_MINIMAL,
             _card("CRS2    PNAM", "  two"),
             _card("CRS2  ABC   ", "  5.000000  5.000000  5.000000    N    0"),
             _card("CRS2  ANGLES", "   90.0000   90.0000   90.0000"),
             _card("CRS2  SG SYM", "  P m -3 m"),
             _card("CRS2  AT  1A", "  CL        0.000000  0.000000  0.000000  1.000000CL1        1 000"),
             _card("CRS2  AT  1B", "  0.010000                                                    I  U")]
    cards[2] = _card(" EXPR NPHAS ", "    1    1")
    model = read_gsas_exp(_exp(tmp_path, "two.EXP", *cards))
    assert len(model.phases) == 2
    with pytest.raises(GsasExpError, match="pass phase=N"):
        to_structure(model)
    assert to_structure(model, phase=2).phases[0].name == "two"


def test_a_missing_atom_b_record_is_refused_rather_than_defaulted(tmp_path):
    path = _exp(tmp_path, "half.EXP", *_MINIMAL[:-1])
    with pytest.raises(GsasExpError, match="no matching 'B' record"):
        read_gsas_exp(path)


def test_a_phase_with_no_stated_type_is_refused_rather_than_assumed_nuclear(tmp_path):
    """``EXPR NPHAS`` is what says nuclear, magnetic or macromolecular.

    Defaulting an absent one to nuclear is WP-1076's defaulted lie, and it is
    the single answer that silences the magnetic refusal — whose whole argument
    is that the nuclear half would look complete.  So the type is ``None`` and
    the build refuses, while the cell and sites stay readable on the model.
    """
    cards = [c for c in _MINIMAL if not c.startswith(" EXPR NPHAS")]
    assert len(cards) == len(_MINIMAL) - 1
    model = read_gsas_exp(_exp(tmp_path, "no_nphas.EXP", *cards))
    assert model.phases[0].kind is None
    assert model.phases[0].cell.a == pytest.approx(4.0)   # still readable
    with pytest.raises(GsasExpError, match="no phase type"):
        to_structure(model)


def test_a_histogram_with_no_stated_type_keeps_its_coefficients_unnamed(tmp_path):
    """``HTYP`` is what says the profile function's coefficient order applies.

    Without it the numbers are still on the record and the histogram is still
    carried; what is declined is naming them under a constant-wavelength
    order nothing establishes.
    """
    path = _exp(tmp_path, "no_htyp.EXP", *_MINIMAL,
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HST  1PRCF1 ", "    2    6      0.01"),
                _card("HST  1PRCF11", "   0.200000E+01  -0.200000E+01   0.500000E+01   0.100000E+01"))
    model = read_gsas_exp(path)
    (hist,) = model.histograms
    assert hist.kind == ""
    assert hist.wavelengths == pytest.approx((1.5405, 1.5443))  # still read
    assert hist.default_profiles == ()                          # but not named
    assert any("states no HTYP" in line for line in model.unsupported)
    notes: list = []
    read_gsas_exp(path, diagnostics=notes)
    assert any(n.code == "GSAS_EXP_HISTOGRAM_NOT_READ" for n in notes)


def test_an_unreadable_coefficient_is_refused_rather_than_skipped(tmp_path):
    """Position is the name, so a dropped field renames every later one.

    Fortran writes a three-digit exponent without its ``E``, and ``float``
    cannot read that.  Skipping the field compacts the list: ``GV`` then takes
    ``GW``'s number, ``GW`` takes ``LX``'s, and the profile comes back one term
    short with plausible values under the wrong labels — the shape of wrongness
    this reader exists to prevent, and one nothing downstream can detect.
    """
    path = _exp(tmp_path, "shift.EXP", *_MINIMAL,
                _card(" EXPR  HTYP1", "  PXC"),
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HAP1 1PRCF  ", "    2    6   0.01000    0NNNYYN"),
                _card("HAP1 1PRCF 1",
                      "   0.200000E+01   0.200000-100   0.500000E+01   0.335183E+01"),
                _card("HAP1 1PRCF 2", "   0.248803E+01   0.000000E+00"))
    with pytest.raises(GsasExpError, match="is not a number"):
        read_gsas_exp(path)


def test_a_coefficient_after_a_gap_is_refused(tmp_path):
    """GSAS writes four to a record and leaves only the last record short.

    A value following a blank therefore cannot be laid out: either the blank is
    a coefficient or the value is in the wrong slot, and both readings rename
    everything after the gap.
    """
    path = _exp(tmp_path, "gap.EXP", *_MINIMAL,
                _card(" EXPR  HTYP1", "  PXC"),
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HAP1 1PRCF  ", "    2    6   0.01000    0NNNYYN"),
                _card("HAP1 1PRCF 1",
                      "   0.200000E+01                  0.500000E+01   0.335183E+01"),
                _card("HAP1 1PRCF 2", "   0.248803E+01   0.000000E+00"))
    with pytest.raises(GsasExpError, match="after a blank field"):
        read_gsas_exp(path)


def test_a_header_promising_more_coefficients_than_it_carries_is_refused(tmp_path):
    """``n_coefficients`` and ``terms`` may not disagree.

    Truncating to what is present hands back a profile whose header says
    eighteen and whose ``by_name()`` has four, so a lookup of a name the file
    itself promised raises a bare ``KeyError`` in the caller's code rather than
    here, where the file can be named.
    """
    path = _exp(tmp_path, "short.EXP", *_MINIMAL,
                _card(" EXPR  HTYP1", "  PXC"),
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HAP1 1PRCF  ", "    2   18   0.01000    0NNNYYNNYNNNNNNNNNN"),
                _card("HAP1 1PRCF 1",
                      "   0.200000E+01  -0.200000E+01   0.500000E+01   0.335183E+01"))
    with pytest.raises(GsasExpError, match="declares 18 profile coefficients"):
        read_gsas_exp(path)


def test_the_htyp_record_number_says_which_twelve_histograms_it_types(tmp_path):
    """``EXPR  HTYP2`` types histograms 13-24, not 1-12 over again.

    Reading every record onto 1-12 is silently wrong twice: histogram 13 gets
    no type at all, so its coefficients go unnamed, and histogram 1 is
    relabelled with histogram 13's radiation.
    """
    twelve = "  " + "".join(f"{'PXC':<3}  " for _ in range(12))
    path = _exp(tmp_path, "many.EXP", *_MINIMAL,
                _card(" EXPR  HTYP1", twelve),
                _card(" EXPR  HTYP2", "  PNT"),
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HST 13 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"))
    model = read_gsas_exp(path)
    assert {h.number: h.kind for h in model.histograms} == {1: "PXC", 13: "PNT"}


def test_a_single_crystal_histogram_does_not_get_powder_coefficient_names(tmp_path):
    """The gate is one predicate, and ``SXC``'s third letter is a ``C``.

    A histogram-level test that declined the set and a pair-level test that
    read it would name the refined coefficients — the ones that matter — under
    a powder function's order while reporting the histogram as not carried.
    """
    path = _exp(tmp_path, "sxc.EXP", *_MINIMAL,
                _card(" EXPR  HTYP1", "  SXC"),
                _card("HST  1 ICONS", "  1.540500  1.544300       0.0         0       0.5    0"),
                _card("HAP1 1PRCF  ", "    2    4   0.01000    0YYYY"),
                _card("HAP1 1PRCF 1",
                      "   0.200000E+01  -0.200000E+01   0.500000E+01   0.335183E+01"))
    model = read_gsas_exp(path)
    assert model.hap[(1, 1)].profile is None
    assert any("single-crystal" in line for line in model.unsupported)


def test_a_blank_cell_edge_is_refused_naming_the_field(tmp_path):
    """A blank optional field is an answer; a blank cell edge is not.

    Letting the ``None`` through means the failure lands in pydantic at
    ``to_structure``, naming neither the file nor the column it came from.
    """
    cards = [_card("CRS1  ABC   ", "  4.000000            4.000000    Y    0")
             if c.startswith("CRS1  ABC") else c for c in _MINIMAL]
    with pytest.raises(GsasExpError, match="states no b"):
        read_gsas_exp(_exp(tmp_path, "blank.EXP", *cards))


def test_an_unresolvable_space_group_is_refused_naming_the_phase(tmp_path):
    """gemmi's own message names neither the file nor which phase carried it."""
    cards = [c for c in _MINIMAL if not c.startswith("CRS1  SG SYM")]
    model = read_gsas_exp(_exp(tmp_path, "nosg.EXP", *cards))
    assert model.phases[0].cell.a == pytest.approx(4.0)   # still readable
    with pytest.raises(GsasExpError, match="space-group symbol"):
        to_structure(model)


def test_a_file_with_no_histograms_says_so_rather_than_asking_for_one(tmp_path):
    """"pass histogram=N" is no advice about a file that carries none."""
    model = read_gsas_exp(_exp(tmp_path, "nohist.EXP", *_MINIMAL))
    with pytest.raises(GsasExpError, match="states no histograms at all"):
        model.histogram()


def test_a_high_byte_in_a_title_does_not_split_its_card(tmp_path):
    """``str.splitlines`` breaks on ``\\x85``, which cp1252 spells ``…``.

    The sniff measures bytes, where that is not a line break, so a title
    carrying one would pass the sniff and then be split into two records with
    keys the file never wrote.
    """
    cards = [_card("      DESCR ", "  caf\x85 standard")
             if c.startswith("      DESCR") else c for c in _MINIMAL]
    model = read_gsas_exp(_exp(tmp_path, "nel.EXP", *cards))
    assert model.title == "caf\x85 standard"
    assert model.phases[0].cell.a == pytest.approx(4.0)


# ------------------------------- a setting the file states no way of settling

def _spinel_exp(tmp_path: Path, symbol: str) -> Path:
    """Spinel at origin choice 2's coordinates, which is how papers print it."""
    return _exp(
        tmp_path, "spinel.EXP",
        _card("     VERSION", "    6"),
        _card("      DESCR ", "  spinel"),
        _card(" EXPR NPHAS ", "    1"),
        _card("CRS1    PNAM", "  spinel"),
        _card("CRS1  ABC   ", "  8.080600  8.080600  8.080600    Y    0"),
        _card("CRS1  ANGLES", "   90.0000   90.0000   90.0000"),
        _card("CRS1  SG SYM", f"  {symbol}"),
        _card("CRS1  AT  1A", "  MG        0.125000  0.125000  0.125000  1.000000MG1        1 000"),
        _card("CRS1  AT  1B", "  0.010000                                                    I  U"),
        _card("CRS1  AT  2A", "  AL        0.500000  0.500000  0.500000  1.000000AL1        1 000"),
        _card("CRS1  AT  2B", "  0.010000                                                    I  U"),
        _card("CRS1  AT  3A", "  O         0.262400  0.262400  0.262400  1.000000O1         1 000"),
        _card("CRS1  AT  3B", "  0.010000                                                    I  U"),
    )


def test_a_bare_two_setting_symbol_is_reported_at_read(tmp_path):
    """A ``.EXP`` states ``SG SYM`` and no operators, so it cannot settle this.

    The fit reports it too, but a caller who only converts a model never runs
    one — which is the whole of issue #101.  The composition is the
    discriminator: origin choice 1 reads AB2O4 as A2BO4.
    """
    diagnostics: list = []
    read_gsas_exp(_spinel_exp(tmp_path, "F d -3 m"), diagnostics=diagnostics)
    found = [d for d in diagnostics
             if d.code == "SPACE_GROUP_SETTING_ASSUMED"]
    assert len(found) == 1
    assert found[0].level == "warning"
    assert found[0].where == ["phases.1.space_group"]
    assert "F d -3 m:1 → Al8 Mg16 O32" in found[0].message
    assert "F d -3 m:2 → Al16 Mg8 O32" in found[0].message


def test_naming_the_setting_in_the_file_silences_it(tmp_path):
    diagnostics: list = []
    read_gsas_exp(_spinel_exp(tmp_path, "F d -3 m:2"), diagnostics=diagnostics)
    assert [d for d in diagnostics
            if d.code == "SPACE_GROUP_SETTING_ASSUMED"] == []


def test_the_corroborating_fixture_names_a_group_held_once(tmp_path):
    """``FAP.EXP`` is ``P 63/m``, so the report must not fire on it."""
    diagnostics: list = []
    read_gsas_exp(FAP, diagnostics=diagnostics)
    assert [d for d in diagnostics if "SETTING" in d.code] == []


# --------------------------------------------------- the writer (WP-1118, #148)
#
# `from_structure` is the inverse of `to_structure`, so its test is a round trip
# through the reader above — the WP's own acceptance for a writer. What is new
# here and was not true of the `.inp` and `.pcr` writers is that the columns are
# **fixed**, so the round trip also tests every field's offset: a number written
# one column left comes back as a different number or as nothing at all.


def _round_trip(structure: rx.Structure, tmp_path: Path, name="out.EXP",
                **kwargs) -> rx.Structure:
    out = tmp_path / name
    rx.write_gsas_exp(structure, out, **kwargs)
    return to_structure(read_gsas_exp(out))


def _assert_parameter_equal(a: rx.Parameter, b: rx.Parameter):
    assert a.value == b.value and a.vary == b.vary


def _hexagonal(*, vary=True) -> rx.Structure:
    """One phase whose numbers all fit ten columns, so the trip is exact."""
    cell = rx.Cell(a=rx.Parameter(value=9.371724, min=1.0, vary=vary),
                   b=rx.Parameter(value=9.371724, min=1.0, vary=vary),
                   c=rx.Parameter(value=6.885867, min=1.0, vary=vary),
                   alpha=rx.Parameter(value=90.0, vary=vary),
                   beta=rx.Parameter(value=90.0, vary=vary),
                   gamma=rx.Parameter(value=120.0, vary=vary))
    atoms = [
        rx.Atom(label="Ca1", species="Ca",
                x=rx.Parameter(value=0.333333, vary=vary),
                y=rx.Parameter(value=0.666667, vary=vary),
                z=rx.Parameter(value=0.001913, vary=vary),
                occ=rx.Parameter(value=1.0, min=0.0, max=1.5, vary=False),
                biso=rx.Parameter(value=0.48, min=0.0, max=25.0, vary=vary)),
        rx.Atom(label="F4", species="F1-",
                x=rx.Parameter(value=0.0, vary=False),
                y=rx.Parameter(value=0.0, vary=False),
                z=rx.Parameter(value=0.25, vary=False),
                occ=rx.Parameter(value=0.5, min=0.0, max=1.5, vary=True),
                biso=rx.Parameter(value=1.09, min=0.0, max=25.0, vary=False)),
    ]
    return rx.Structure(phases=[rx.Phase(
        name="fap", space_group="P 63/m", cell=cell, atoms=atoms)])


def test_write_gsas_exp_round_trips_cell_atoms_and_refine_flags(tmp_path):
    """Exported and re-imported is the same structure, values exactly.

    ``%g`` descending from seventeen digits spends the whole ten-column field,
    so a value whose own ``repr`` fits crosses bit-identically — which is every
    number in this phase but the displacement, whose own row is below.  The
    flags are the payload: GSAS states one for the cell and one ``X`` letter
    for a site's coordinates, so this structure gives each group one answer and
    the trip has to return it.
    """
    structure = _hexagonal()
    back = _round_trip(structure, tmp_path)
    (orig,), (built,) = structure.phases, back.phases

    assert built.name == orig.name
    assert built.space_group == "P 63/m"
    for key in ("a", "b", "c", "alpha", "beta", "gamma"):
        _assert_parameter_equal(getattr(orig.cell, key), getattr(built.cell, key))
    assert len(built.atoms) == 2
    for oa, ba in zip(orig.atoms, built.atoms):
        assert (ba.label, ba.species) == (oa.label, oa.species)
        for key in ("x", "y", "z", "occ"):
            _assert_parameter_equal(getattr(oa, key), getattr(ba, key))
        assert ba.biso.vary == oa.biso.vary


def test_the_displacement_is_the_one_value_a_exp_cannot_carry_exactly(tmp_path):
    """And it is arithmetic, not a defect: GSAS stores ``Uiso``.

    ``Biso / 8π²`` is irrational in the decimal sense, so a ``biso`` of 0.48 —
    two characters — becomes a ``Uiso`` of 0.0060792710185… that no ten-column
    field can hold.  Ten columns give it about seven significant figures, which
    is 1e-7 of itself against an esd a refinement reports at ~1e-2, and it is
    two more figures than the six decimals real GSAS writes.  The writer says
    so rather than letting it pass: that is what ``GSAS_EXP_VALUE_NARROWED``
    is, and it fires once for the file rather than once per value.
    """
    diagnostics: list = []
    structure = _hexagonal()
    back = _round_trip(structure, tmp_path, diagnostics=diagnostics)

    got = back.phases[0].atoms[0].biso.value
    assert got != 0.48                         # not exact, and not pretended to be
    assert got == pytest.approx(0.48, rel=1e-6)

    (row,) = [d for d in diagnostics if d.code == "GSAS_EXP_VALUE_NARROWED"]
    assert row.level == "info"
    assert "phases.0.atoms.0.biso" in row.where
    # every other number in this phase fits its field, so only the two
    # displacements are named
    assert row.where == ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]


def test_two_phases_keep_their_own_records(tmp_path):
    """The `CRS<n>` keys and `EXPR NPHAS`' nine fields, which one phase cannot
    exercise: a phase number is part of every key in its block, and a phase
    whose type the `NPHAS` record does not state is what `to_structure` refuses
    on the way back in.  Selecting one is the caller's, following the reader's
    own rule, so both are asked for by number."""
    P = rx.Parameter

    def phase(name, a, label, species):
        return rx.Phase(
            name=name, space_group="Fm-3m", cell=rx.Cell.cubic(a, vary=True),
            atoms=[rx.Atom(label=label, species=species,
                           x=P(value=0.0), y=P(value=0.0), z=P(value=0.0),
                           occ=P(value=1.0, min=0.0, max=1.5),
                           biso=P(value=0.5, min=0.0, max=25.0, vary=True))])

    structure = rx.Structure(phases=[phase("Al", 4.0495, "Al1", "Al"),
                                     phase("NaCl", 5.64, "Na1", "Na")])
    out = tmp_path / "two.EXP"
    rx.write_gsas_exp(structure, out, title="two phases")
    model = read_gsas_exp(out)

    assert [(p.number, p.name, p.kind) for p in model.phases] == [
        (1, "Al", 1), (2, "NaCl", 1)]
    for number, original in zip((1, 2), structure.phases):
        built = to_structure(model, phase=number).phases[0]
        assert built.name == original.name
        _assert_parameter_equal(original.cell.a, built.cell.a)
        assert [(a.label, a.species) for a in built.atoms] == [
            (a.label, a.species) for a in original.atoms]
    with pytest.raises(GsasExpError, match="pass phase=N"):
        to_structure(model)


def test_a_held_structure_comes_back_held(tmp_path):
    """The other answer for every flag, since ``any()`` is how they merge."""
    back = _round_trip(_hexagonal(vary=False), tmp_path)
    (built,) = back.phases
    assert not any(getattr(built.cell, k).vary
                   for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    assert not built.atoms[0].x.vary and not built.atoms[0].biso.vary


def test_the_real_converged_refinement_survives_the_round_trip(tmp_path):
    """``FAP.EXP`` out through the writer and back in, against itself.

    A hand-built structure exercises the fields; GSAS's own converged file
    exercises the *values* — seven sites, a hexagonal cell and the refine
    protocol ``test_the_recovered_protocol_reproduces_gsas_own_variable_count``
    checks against the number the file states in words.
    """
    original = to_structure(read_gsas_exp(FAP))
    back = _round_trip(original, tmp_path, "fap_again.EXP")
    (orig,), (built,) = original.phases, back.phases
    assert built.space_group == orig.space_group
    for key in ("a", "b", "c", "alpha", "beta", "gamma"):
        _assert_parameter_equal(getattr(orig.cell, key), getattr(built.cell, key))
    assert len(built.atoms) == 7
    for oa, ba in zip(orig.atoms, built.atoms):
        assert (ba.label, ba.species) == (oa.label, oa.species)
        _assert_parameter_equal(oa.x, ba.x)
        _assert_parameter_equal(oa.occ, ba.occ)
        # Biso → Uiso → Biso is the one lossy step: ten columns hold a Uiso of
        # ~0.0067 to six figures, which is 1e-7 of itself against an esd of
        # ~1e-2.  The file's own Uiso is six decimals, so this beats GSAS.
        assert ba.biso.value == pytest.approx(oa.biso.value, rel=1e-6)
        assert ba.biso.vary == oa.biso.vary


def test_a_written_file_is_claimed_by_the_registry_as_a_gsas_exp(tmp_path):
    """The sniff measures the 80-column width, so the writer has to keep it."""
    out = tmp_path / "claimed.EXP"
    rx.write_gsas_exp(_hexagonal(), out, title="a written experiment")
    assert rx.identify_project_format(out).name == "gsas_exp"
    assert rx.read_project_model(out).stated.title == "a written experiment"


def test_every_card_is_exactly_eighty_columns(tmp_path):
    """The width is the format, not the presentation: GSAS fetched these
    records by direct access, and a short card shifts every field after it."""
    text = from_structure(_hexagonal())
    lines = text.split("\r\n")[:-1]
    assert lines and all(len(line) == 80 for line in lines)


def test_the_multiplicity_and_contents_are_derived_from_the_sites(tmp_path):
    """Two fields GSAS states that a ``Structure`` does not.

    ``F4`` sits on the 2-fold special position at ``(0, 0, ¼)`` and ``Ca1`` on
    the 4-fold one, so the orbit gives 2 and 4 — and ``CHMF`` is the occupancy
    summed over them, which is where the record's own columns get tested.
    """
    out = tmp_path / "contents.EXP"
    rx.write_gsas_exp(_hexagonal(), out)
    model = read_gsas_exp(out)
    (phase,) = model.phases
    assert [a.multiplicity for a in phase.atoms] == [4, 2]
    # in GSAS's own type spelling, as the atom records are (#555)
    assert phase.formula == (("CA", 4.0), ("F-1", 1.0))


def test_write_gsas_exp_writes_the_resolved_setting_not_the_bare_symbol(tmp_path):
    """A ``.EXP`` states its symbol and no operators, so a resolved setting
    that went out as a bare symbol would come back ambiguous — and the reader
    would rightly say so.  ``SG SYM`` takes the whole payload, so unlike a
    ``.pcr`` this format can spell every setting and no refusal is owed."""
    from rietx.crystallography.symmetry import get_spacegroup

    resolved = get_spacegroup("Fd-3m").xhm()
    assert ":" in resolved
    structure = rx.Structure(phases=[rx.Phase(
        name="spinel", space_group=resolved, cell=rx.Cell.cubic(8.0806),
        atoms=[rx.Atom(label="Mg1", species="Mg",
                       x=rx.Parameter(value=0.125), y=rx.Parameter(value=0.125),
                       z=rx.Parameter(value=0.125))])])
    out = tmp_path / "spinel.EXP"
    rx.write_gsas_exp(structure, out)
    assert resolved in out.read_text(encoding="latin-1")

    diagnostics: list = []
    model = read_gsas_exp(out, diagnostics=diagnostics)
    assert model.phases[0].space_group == resolved
    assert [d for d in diagnostics if "SETTING" in d.code] == []


def test_a_flag_that_is_narrower_than_the_model_merges_and_says_so(tmp_path):
    """GSAS states one flag for the cell and one for a site's coordinates.

    A structure whose members disagree cannot be written as it stands, and the
    choice is between freeing a parameter it holds and holding one it frees.
    Freeing carries more of the caller's protocol — the file still says "this
    cell refined" — so that is what is written, and the group is **named**
    rather than the caller finding out from GSAS.
    """
    structure = _hexagonal()
    phase = structure.phases[0]
    phase.cell.alpha.vary = False           # against a/b/c, which vary
    phase.atoms[0].z.vary = False           # against x/y, which vary

    diagnostics: list = []
    back = _round_trip(structure, tmp_path, diagnostics=diagnostics)

    (row,) = [d for d in diagnostics if d.code == "GSAS_EXP_REFINE_FLAG_MERGED"]
    assert row.level == "warning"
    assert row.where == ["phases.0.cell", "phases.0.atoms.0.xyz"]
    built = back.phases[0]
    assert built.cell.alpha.vary is True
    assert built.atoms[0].z.vary is True
    # a group that agreed is not named and is not changed
    assert built.atoms[1].x.vary is False


def test_write_gsas_exp_refuses_an_anisotropic_site(tmp_path):
    """``to_structure`` refuses one on the way in, because no file here settles
    GSAS's off-diagonal convention — so writing six numbers under a convention
    this module declines to read back is the same guess pointing the other
    way."""
    structure = _hexagonal()
    structure.phases[0].atoms[0].biso.vary = False   # the schema's own rule
    structure.phases[0].atoms[0].aniso = rx.AnisoU(
        u11=rx.Parameter(value=0.006, unit="A^2"),
        u22=rx.Parameter(value=0.006, unit="A^2"),
        u33=rx.Parameter(value=0.006, unit="A^2"),
        u12=rx.Parameter(value=0.003, unit="A^2"),
        u13=rx.Parameter(value=0.0, unit="A^2"),
        u23=rx.Parameter(value=0.0, unit="A^2"))
    with pytest.raises(ValueError, match="anisotropic"):
        from_structure(structure)


def test_write_gsas_exp_writes_a_negative_biso_that_reads_back(tmp_path):
    """GSAS stores a negative Uiso and the reader now keeps one, so the
    writer writes it rather than refusing (PR #663)."""
    structure = _hexagonal()
    atom = structure.phases[0].atoms[0]
    atom.biso.min = -1.0
    atom.biso.value = -0.1
    back = _round_trip(structure, tmp_path).phases[0].atoms[0].biso
    assert back.value == pytest.approx(-0.1, abs=1e-5)


def test_write_gsas_exp_refuses_a_non_finite_value(tmp_path):
    """``inf`` fits ten columns and reads back as a float.

    So a cell edge of infinity would round-trip *perfectly* into a structure
    nothing can refine — the one shape where a fixed-width field's tolerance is
    the hazard rather than the constraint.  Surfaced by the review pass on the
    ``.inp``/``.pcr`` writers, which left it as a design question; the answer
    is the same for all three.
    """
    structure = _hexagonal()
    structure.phases[0].cell.a.max = float("inf")
    structure.phases[0].cell.a.value = float("inf")
    with pytest.raises(ValueError, match="no GSAS field can state"):
        from_structure(structure)


@pytest.mark.parametrize("label, reason", [
    ("", "blank site label"),
    ("  ", "blank site label"),
    ("Ca1 ", "whitespace at one end"),
    ("Calcium1", None),                     # eight characters: the field holds it
    ("Calcium11", "characters against"),
])
def test_a_label_that_would_come_back_renamed_is_refused(label, reason):
    """A fixed-width field is read back **stripped**, so a name with an end
    space returns as a different name and a blank one returns as the species —
    GSAS's own fallback for a record that names none.  Space *inside* is fine,
    this format being columns rather than tokens, which is where it parts
    company with the ``.inp`` and ``.pcr`` writers."""
    structure = _hexagonal()
    structure.phases[0].atoms[0].label = label
    if reason is None:
        assert label in from_structure(structure)
        return
    with pytest.raises(ValueError, match=reason):
        from_structure(structure)


def test_a_label_may_hold_a_space_inside_it(tmp_path):
    """The other half of the row above, and the one that distinguishes a
    column format from a token one."""
    structure = _hexagonal()
    structure.phases[0].atoms[0].label = "Ca 1"
    back = _round_trip(structure, tmp_path)
    assert back.phases[0].atoms[0].label == "Ca 1"


def test_more_phases_than_the_format_can_type_is_refused():
    """``EXPR NPHAS`` holds nine ``I5`` fields, and a phase with no stated type
    is what ``to_structure`` refuses on the way back in — so a tenth phase
    would be written into a file that cannot be read."""
    one = _hexagonal().phases[0]
    structure = rx.Structure(phases=[one.model_copy(deep=True) for _ in range(10)])
    with pytest.raises(ValueError, match="EXPR NPHAS"):
        from_structure(structure)


def test_a_payload_that_would_overrun_its_card_is_refused():
    """80 characters is what GSAS fetched these records by, so a long title is
    a refusal rather than a truncation: a repair a writer cannot report is one
    it may not make."""
    with pytest.raises(ValueError, match="80-character width"):
        from_structure(_hexagonal(), title="x" * 80)


def test_a_line_break_in_a_payload_is_refused():
    """The other half of the record above, and the sharper one.

    A payload that overruns is caught by its length; one carrying a line break
    is the right length and still wrong, because :func:`split_records` splits
    on CR and LF — so the card is read back as two records under keys nothing
    wrote.  That is the accident that function's own docstring names from the
    reading side, arriving here through a ``title`` or a ``phase.name``.
    """
    with pytest.raises(ValueError, match="line break"):
        from_structure(_hexagonal(), title="one\nCRS1  ABCSIG")
    structure = _hexagonal()
    structure.phases[0].name = "one\rtwo"
    with pytest.raises(ValueError, match="line break"):
        from_structure(structure)


def test_a_character_latin_1_cannot_spell_is_refused():
    """A ``.EXP`` is a byte format and :func:`write_gsas_exp` encodes one, so a
    Greek α in a phase name has to be refused somewhere.  Here, naming the
    record and the character, rather than at the encode, where a
    ``UnicodeEncodeError`` names a byte offset into the finished file."""
    structure = _hexagonal()
    structure.phases[0].name = "α-quartz"
    with pytest.raises(ValueError, match="latin-1 cannot spell"):
        from_structure(structure)


def test_write_gsas_exp_is_reachable_at_the_top_level():
    assert rx.write_gsas_exp is write_gsas_exp


def test_every_numeric_field_carries_its_decimal_point():
    """The one mistake a round trip through this package cannot catch.

    A Fortran ``F`` or ``E`` edit descriptor supplies the decimal point from
    its own ``d`` when the input field has none, which is why punched data
    could leave it out.  So ``90`` in an ``F10.6`` field is 9e-5 to GSAS and
    90 to ``float()``, and every test here would pass while the file said
    something else to the program it is for.  Real ``.EXP`` and ``.prm`` files
    write ``0.333333`` and ``0.000000E+00``, which is the corroboration.  The
    integer fields — ``VERSION``, ``NATOM``, a site multiplicity, ``NPHAS`` —
    are ``I`` descriptors and rightly carry none, so they are written by ``%d``
    and never reach :func:`write_field`.
    """
    text = from_structure(_hexagonal(vary=False))
    records = dict(split_records(text))
    for key in ("CRS1  ABC   ", "CRS1  ANGLES"):
        for start in (0, 10, 20):
            assert "." in records[key][start:start + 10]
    for start in (10, 20, 30, 40):          # x, y, z, occupancy
        assert "." in records["CRS1  AT  1A"][start:start + 10]
    assert "." in records["CRS1  AT  1B"][0:10]


# ------------------------------------- a written field that is not a number

def test_a_blank_field_is_none_and_a_written_one_is_its_value(tmp_path):
    """Blank is "GSAS did not write this"; a well-formed field is its number."""
    path = _exp(tmp_path, "esds.EXP", *_MINIMAL,
                _card("CRS1  ABCSIG", "            0.000200"))
    cell = read_gsas_exp(path).phases[0].cell
    assert cell.esd_a is None
    assert cell.esd_b == pytest.approx(0.0002)
    assert cell.esd_c is None


def test_a_written_field_that_is_not_a_number_is_refused_not_absent(tmp_path):
    """A non-blank, unparsable field used to come back ``None``, which is also
    what a field GSAS left out reads as, so a misaligned or corrupt record
    arrived as a quietly missing value.  It is refused now, naming the file,
    the record, the card columns and the text.
    """
    path = _exp(tmp_path, "garbled.EXP", *_MINIMAL,
                _card("CRS1  ABCSIG", "  0.00X100  0.000200"))
    with pytest.raises(GsasExpError) as err:
        read_gsas_exp(path)
    message = str(err.value)
    assert message.startswith("garbled.EXP: ")
    assert "'CRS1  ABCSIG'" in message
    assert "columns 12-22" in message
    assert "'0.00X100'" in message


def test_a_number_spilling_over_its_field_reads_as_two_numbers(tmp_path):
    """The limit of any per-field rule, pinned so nobody assumes it is caught.

    A left-aligned ``46.60`` starting two columns before a 10-wide boundary
    reads as ``46`` in one field and ``.60`` in the next.  Both are numbers, so
    nothing refuses.  A split that leaves one half unreadable is refused.
    """
    path = _exp(tmp_path, "spill.EXP", *_MINIMAL,
                _card("CRS1  ABCSIG", "        46.60"))
    cell = read_gsas_exp(path).phases[0].cell
    assert cell.esd_a == 46.0
    assert cell.esd_b == pytest.approx(0.6)

    path = _exp(tmp_path, "spill_e.EXP", *_MINIMAL,
                _card("CRS1  ABCSIG", "   1.2345E+02"))
    with pytest.raises(GsasExpError, match=r"'1\.2345E' in columns 12-22"):
        read_gsas_exp(path)


def test_a_required_field_that_is_not_a_number_names_the_text(tmp_path):
    """A cell edge was refused already, but as "blank or is not a number"."""
    cards = list(_MINIMAL)
    cards[4] = _card("CRS1  ABC   ", "  4.000000  4.0O0000  4.000000    Y    0")
    with pytest.raises(GsasExpError, match=r"'4\.0O0000' in columns 22-32"):
        read_gsas_exp(_exp(tmp_path, "edge.EXP", *cards))


def test_preferred_orientation_is_read_at_the_columns_the_file_writes(fap):
    """``FAP.EXP``'s ``PREFO`` is five F10 fields, ``3X``, two letters, two I5.

    Read at a four-field layout, the flag was a digit of the fifth number and
    the integer was the letters ``NN``, which only :func:`_num` reading text as
    a blank field kept quiet.
    """
    rows = fap.hap[(1, 1)].preferred_orientation
    assert rows == ((1.0, (1.0, 0.0, 0.0), False, 0),)


# ------------------------------------------- a Fortran overflow is named

def _fap_with(tmp_path, name, key, start, width):
    """``FAP.EXP`` with one field overwritten by the asterisks Fortran writes
    for a value too wide for its edit descriptor.  ``start`` is the payload
    column, the card column less the 12-byte key.
    """
    lines = FAP.read_bytes().decode("latin-1").split("\r\n")
    (i,) = [n for n, ln in enumerate(lines) if ln.startswith(key)]
    col = 12 + start
    lines[i] = lines[i][:col] + "*" * width + lines[i][col + width:]
    path = tmp_path / name
    path.write_bytes("\r\n".join(lines).encode("latin-1"))
    return path


def test_an_overflowed_required_field_is_refused_as_an_overflow(tmp_path):
    """A cell edge of asterisks is not a misaligned record: GSAS had the value
    and ran out of columns.  Required, so refused, and the message says why.
    """
    path = _fap_with(tmp_path, "overflow.EXP", "CRS1  ABC   ", 10, 10)
    with pytest.raises(GsasExpError) as err:
        read_gsas_exp(path)
    message = str(err.value)
    assert message.startswith("overflow.EXP: ")
    assert "'CRS1  ABC'" in message and "columns 22-32" in message
    assert "Fortran overflow: the value was too wide for its F10 field" in message
    assert "misaligned" not in message and "corrupt" not in message


@pytest.mark.parametrize("key, start, what", [
    ("CRS1  ABCSIG", 10, "esd_b"),
    (" REFN RPOWD ", 0, "rwp"),
])
def test_an_overflowed_optional_field_is_absent_and_reported(tmp_path, key,
                                                             start, what):
    """An esd or the history Rwp: the reader tolerates its absence, so an
    overflow reads as ``None`` — and says so, because a silent ``None`` would
    read as the file having left the field out.
    """
    path = _fap_with(tmp_path, "overflow.EXP", key, start, 10)
    diagnostics: list = []
    model = read_gsas_exp(path, diagnostics=diagnostics)
    value = (model.phases[0].cell.esd_b if what == "esd_b" else model.rwp)
    assert value is None
    reference = read_gsas_exp(FAP)
    assert reference.phases[0].cell.esd_b is not None and reference.rwp
    found = [d for d in diagnostics if d.code == "GSAS_FIELD_OVERFLOW"]
    assert len(found) == 1
    (d,) = found
    assert d.level == "warning"
    assert d.where == [key.strip()]
    assert d.message.startswith("overflow.EXP: ")
    assert f"columns {12 + start}-{22 + start}" in d.message
    assert "Fortran overflow" in d.message
    # the rest of the file is read as it was
    assert model.phases[0].cell.a == reference.phases[0].cell.a
    assert not [d for d in _diagnostics(FAP) if d.code == "GSAS_FIELD_OVERFLOW"]


def _diagnostics(path):
    out: list = []
    read_gsas_exp(path, diagnostics=out)
    return out


# ------------------------------------------ the atom type's grammar (#555)
#
# GSAS writes a type as 'aasv_nnn' (Larson & Von Dreele 2004, EXPR ATYPnn,
# printed p. 182): symbol, valence sign and valence, then '_' and the isotope
# number. The reader used to strip the underscore and read 'NI+2_58' as a
# '+258' ion of natural Ni, reporting the rename as correct.

def _one_site(species: str) -> rx.Structure:
    return rx.Structure(phases=[rx.Phase(
        name="syn", space_group="Pm-3m", cell=rx.Cell.cubic(4.0),
        atoms=[rx.Atom(label="A1", species=species, x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                       biso=rx.Parameter(value=0.5, min=0.0, max=25.0))])])


def _with_type(tmp_path: Path, gsas_type: str) -> Path:
    """A written .EXP with the site's type field (A8, after two blanks) set by
    hand to GSAS's own spelling, in both the atom and the contents record."""
    out = tmp_path / "syn.EXP"
    rx.write_gsas_exp(_one_site("Ni"), out)
    lines = [line[:12] + f"  {gsas_type:<8}" + line[22:]
             if ("AT  1A" in line or "CHMF 1" in line) else line
             for line in out.read_text(encoding="utf-8").splitlines()]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


@pytest.mark.parametrize("gsas_type, species, b_fm", [
    ("NI+2_58", "58Ni2+", 14.4),
    ("LI+1_7", "7Li1+", -2.22),
    ("NI_58", "58Ni", 14.4),
    ("H_2", "2H", 6.671),
    ("NI", "Ni", 10.3),         # blank nnn: natural abundance, unchanged
])
def test_a_gsas_isotope_type_reads_as_that_isotope(tmp_path, gsas_type, species,
                                                   b_fm):
    from rietx.crystallography.neutron import b_coh
    diagnostics = []
    back = to_structure(read_gsas_exp(_with_type(tmp_path, gsas_type)),
                        diagnostics=diagnostics)
    atom = back.phases[0].atoms[0]
    assert atom.species == species
    assert b_coh(atom.species) == pytest.approx(b_fm)
    if "_" in gsas_type:
        (said,) = [d.message for d in diagnostics
                   if d.code == "GSAS_EXP_SPECIES_NORMALISED"]
        assert "isotope number" in said


@pytest.mark.parametrize("species, written", [
    ("Zr4+", "ZR+4"), ("O2-", "O-2"), ("Cu1+", "CU+1"), ("Mn", "MN"),
    ("7Li", "LI_7"), ("7Li1+", "LI+1_7"), ("D", "H_2"), ("60Ni", "NI_60"),
    ("157Gd", "GD_157"),
    # WP-1527: the atom rietx computes, the tabulated Cu1+ and the neutral Fe
    ("Cu+", "CU+1"), ("Na+", "NA+1"), ("Fe+", "FE"),
])
def test_the_writer_spells_the_manuals_type(tmp_path, species, written):
    """'aasv_nnn', symbol upper case and the valence sign-first with its
    number ('TI+4', printed p. 181). From the manual only: no GSAS run."""
    text = from_structure(_one_site(species))
    (atom,) = [r for r in text.splitlines() if "AT  1A" in r]
    (chmf,) = [r for r in text.splitlines() if "CHMF 1" in r]
    assert atom[12:22] == f"  {written:<8}"
    assert chmf[12:22] == f"  {written:<8}"
    back = _round_trip(_one_site(species), tmp_path)
    from rietx.crystallography.neutron import normalize_species
    assert (normalize_species(back.phases[0].atoms[0].species)
            == normalize_species(species))


@pytest.mark.parametrize("species, back, named", [
    ("Cu+", "Cu1+", False),   # the tabulated ion rietx computes (WP-1527)
    ("Fe+", "Fe", True),      # no Fe1+ in rietx's table: neutral Fe, named
])
def test_a_digitless_ion_is_written_as_the_atom_rietx_computes(
        tmp_path, species, back, named):
    """The maintainer's rule (WP-1527, 2026-10-03): no species is refused for
    its charge, and none is written as an atom rietx did not compute."""
    diagnostics: list = []
    out = tmp_path / "syn.EXP"
    write_gsas_exp(_one_site(species), out, diagnostics=diagnostics)
    assert to_structure(read_gsas_exp(out)).phases[0].atoms[0].species == back
    said = [d for d in diagnostics
            if d.code == "GSAS_EXP_SPECIES_WRITTEN_NEUTRAL"]
    assert [d.where for d in said] == (
        [["phases.0.atoms.0.species"]] if named else [])


@pytest.mark.parametrize("species, element", [("Cval", "C"), ("Siva", "Si")])
def test_the_writer_refuses_a_valence_label_as_one(species, element):
    """rietx scatters ``Cval``/``Siva`` from the Waasmaier-Kirfel table, so
    "not an element, an ion or an isotope" misdescribed them; the grammar has
    no valence label, so they are still refused (#572 review, follow-up 2)."""
    with pytest.raises(ValueError, match="valence-electron form factor") as exc:
        from_structure(_one_site(species))
    assert "not an element" not in str(exc.value)
    assert f"Write {element!r}" in str(exc.value)
