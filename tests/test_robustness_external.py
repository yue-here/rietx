"""WP-1028 regressions: robustness on data and CIFs we did not author.

One section per WP item, and every test here failed before its fix.  The
defects were measured on external files (COD entries, ICSD exports, the
PyWPEM CASES data) and are reproduced as synthetic minimal cases so the
suite carries no third-party data; the measured stories live in the WP file.
"""

from __future__ import annotations

from typing import get_args

import numpy as np
import pytest

from rietx import Instrument, Parameter, PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure

# ----------------------------------------------------------------------
# (a) species syntaxes that reject valid CIFs — at two lookups, not one
# ----------------------------------------------------------------------

NACL_CIF = """\
data_nacl
_symmetry_space_group_name_H-M 'F m -3 m'
_cell_length_a 5.6402
_cell_length_b 5.6402
_cell_length_c 5.6402
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Na1 {na} 0 0 0 1
Cl1 {cl} 0.5 0.5 0.5 1
"""


def _nacl_cif(tmp_path, na="Na", cl="Cl"):
    path = tmp_path / "nacl.cif"
    path.write_text(NACL_CIF.format(na=na, cl=cl), encoding="utf-8")
    return str(path)


def test_normalize_cif_species_covers_both_wild_forms_and_only_them():
    from rietx.crystallography.cif import normalize_cif_species

    label = "site label in the type-symbol column"
    sign = "sign-first charge"
    assert normalize_cif_species("O1") == ("O", label)
    assert normalize_cif_species("Cl1") == ("Cl", label)
    assert normalize_cif_species("CL1") == ("Cl", label)
    assert normalize_cif_species("O-2") == ("O2-", sign)
    assert normalize_cif_species("Ni+3") == ("Ni3+", sign)
    assert normalize_cif_species("Li+1") == ("Li1+", sign)
    # canonical forms are untouched — including the trailing-sign ion that
    # always read fine, and a bare element in any case the lookups handle
    assert normalize_cif_species("Cl1-") == ("Cl1-", None)
    assert normalize_cif_species("O2-") == ("O2-", None)
    assert normalize_cif_species("Na") == ("Na", None)
    # a symbol the table cannot help is never half-rewritten: it passes
    # through verbatim to fail with the lookup's own message
    assert normalize_cif_species("Wat") == ("Wat", None)
    assert normalize_cif_species("Xx1") == ("Xx1", None)
    # since #552 deuterium resolves (to hydrogen's f0), so `D1` is a site label
    # like `O1`; `T1` is a zeolite T-site, never read as tritium
    assert normalize_cif_species("D1") == ("D", label)
    assert normalize_cif_species("T1") == ("T1", None)


def test_the_spelling_hint_offers_only_a_rewrite_that_resolves():
    """The hint never sends a caller to edit a file for a spelling that fails too.

    ``species_spelling_hint`` and ``normalize_cif_species`` are one decision
    made once: the hint is the repair, phrased for a refusal that cannot make
    it.  A hint that only matched the *pattern* would offer ``Xx+2`` → ``Xx2+``
    (as unreadable as the input) and ``Og+2`` → ``Og2+`` (a real element with no
    row in either table) — advice that costs an edit and changes nothing.
    """
    from rietx.crystallography.cif import (
        normalize_cif_species,
        species_spelling_hint,
    )

    assert species_spelling_hint("Cu+1").endswith("Cu1+")
    assert species_spelling_hint("O-2").endswith("O2-")
    # pattern matches, candidate does not resolve — so no hint is offered
    assert species_spelling_hint("Xx+2") == ""
    assert species_spelling_hint("Og+2") == ""
    # forms the hint never claimed: a bare label and an unhelpable typo
    assert species_spelling_hint("O1") == ""
    assert species_spelling_hint("Wat") == ""
    # and the two functions cannot disagree about the same input
    for species in ("Cu+1", "O-2", "Xx+2", "Og+2", "O1", "Wat", "Na"):
        candidate, note = normalize_cif_species(species)
        offered = species_spelling_hint(species)
        assert bool(offered) is (note == "sign-first charge"), species
        assert not offered or offered.endswith(candidate), species


def test_site_label_type_symbols_normalise_at_read(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na1", cl="Cl1"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na", "Cl"]
    assert {d.code for d in diags} == {"CIF_SPECIES_NORMALISED"}
    assert all(d.level == "info" for d in diags)
    where = sorted(w for d in diags for w in d.where)
    assert where == ["phases.0.atoms.0.species", "phases.0.atoms.1.species"]


def test_sign_first_charges_normalise_keeping_the_ion(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na+1", cl="Cl-1"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na1+", "Cl1-"]
    assert len(diags) == 2
    assert all("sign-first charge" in d.message for d in diags)


def test_untouched_species_record_no_diagnostic(tmp_path):
    diags = []
    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na", cl="Cl1-"),
                                   diagnostics=diags)
    assert [a.species for a in structure.phases[0].atoms] == ["Na", "Cl1-"]
    assert diags == []


@pytest.mark.parametrize("dispersion_on", [True, False],
                         ids=["dispersion-on", "dispersion-none"])
def test_normalised_species_compile_under_both_dispersion_settings(
        tmp_path, dispersion_on):
    # the defect fired at the first stage compile, from *two* lookups —
    # resolve_dispersion with the block on, normalize_species either way —
    # so the fix is asserted at compile, under both settings
    from rietx.model.forward import compile_model

    structure = Structure.from_cif(_nacl_cif(tmp_path, na="Na+1", cl="Cl1"))
    structure.phases[0].scale.value = 5e-3
    ins = Instrument.bragg_brentano(radiation="CuKa")
    if not dispersion_on:
        ins.source.dispersion = None
    tt = np.arange(20.0, 60.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    compile_model(structure, ins, pattern, mode="rietveld")


# ----------------------------------------------------------------------
# (a′) a bad species in a *hand-built* structure is named at the compile
#      boundary — the phase, the atom index and the label, for both halves of
#      the affected population.  This is the WP-1036 story's other end: a CIF
#      is repaired at read (normalize_cif_species, recorded), but a structure
#      assembled in code never passed a reader, so the two X-ray form-factor
#      lookups at compile are the authority.  They fire two lines apart and
#      each names only the species; the wrapper names where it is.
# ----------------------------------------------------------------------
def _hand_structure(species, *, label="A1", space_group="P 1"):
    """A one-atom structure with a chosen species, built in code, not read."""
    return Structure(phases=[Phase(
        name="Trirutile", space_group=space_group, cell=Cell.cubic(5.0),
        scale=Parameter(value=5e-3),
        atoms=[Atom(label=label, species=species, x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0))])])


def _compile(structure, *, dispersion_on=True):
    from rietx.model.forward import compile_model

    ins = Instrument.bragg_brentano(radiation="CuKa")
    if not dispersion_on:
        ins.source.dispersion = None
    tt = np.arange(20.0, 60.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    return compile_model(structure, ins, pattern, mode="rietveld")


@pytest.mark.parametrize("dispersion_on", [True, False],
                         ids=["dispersion-on", "dispersion-none"])
@pytest.mark.parametrize("species", [
    "Cu+1", "O-2", "Ni+3",   # sign-first, what ICSD exports and TOPAS writes
    "Wat", "Cu++", "Cu 1+",  # not readable as a symbol plus optional charge
])
def test_a_malformed_species_is_named_at_compile(species, dispersion_on):
    """Whichever lookup gets there first, the refusal names phase, atom, label.

    Both lookups run at the first stage compile — ``resolve_dispersion`` with
    the block on, ``normalize_species`` either way — and each raises naming the
    species alone.  The wrapper prefixes the phase name, the atom index and the
    label, so the caller learns which atom of which phase to fix, under both
    dispersion settings.
    """
    with pytest.raises(ValueError) as excinfo:
        _compile(_hand_structure(species, label="A1"), dispersion_on=dispersion_on)
    message = str(excinfo.value)
    assert "Trirutile" in message, "the phase is not named"
    assert "A1" in message, "the atom label is not named"
    assert "atom 0" in message, "the atom index is not named"
    assert repr(species) in message, "the offending species is not quoted"


@pytest.mark.parametrize("dispersion_on", [True, False],
                         ids=["dispersion-on", "dispersion-none"])
def test_a_sign_first_charge_is_told_the_right_spelling_at_compile(dispersion_on):
    """The commonest wild form carries its fix into the refusal, either way."""
    with pytest.raises(ValueError, match=r"Cu1\+"):
        _compile(_hand_structure("Cu+1"), dispersion_on=dispersion_on)
    with pytest.raises(ValueError, match=r"O2-"):
        _compile(_hand_structure("O-2"), dispersion_on=dispersion_on)


@pytest.mark.parametrize("dispersion_on", [True, False],
                         ids=["dispersion-on", "dispersion-none"])
def test_a_well_formed_symbol_with_no_table_row_is_also_named(dispersion_on):
    """The other half of the population: ``Xx`` reads as a symbol and has no row.

    A schema-level well-formedness check would pass ``Xx`` (it is spelled like a
    species) and leave this half to raise the old anonymous ``KeyError`` naming
    neither atom nor phase.  At the compile boundary both halves are named the
    same way, so a caller with a bad species cannot land on a worse message by
    luck of whether the typo happened to spell a real element.
    """
    with pytest.raises(ValueError) as excinfo:
        _compile(_hand_structure("Xx", label="A1"), dispersion_on=dispersion_on)
    message = str(excinfo.value)
    assert "Trirutile" in message and "atom 0" in message and "A1" in message
    assert repr("Xx") in message


def test_sign_first_charge_reproduction_names_the_first_bad_atom_at_compile():
    """The cross-code reproduction: TOPAS/ICSD sign-first ``Mg+2`` / ``O-2``.

    A hand-built MgO with these labels was refused at *compile* by
    ``normalize_element`` with a bare ``KeyError: cannot read an element symbol
    from species 'Mg+2'`` — raised at compile time, naming neither the atom nor
    the phase.  Now the first atom the lookups choke on is named, with the
    spelling that resolves.
    """
    structure = Structure(phases=[Phase(
        name="MgO", space_group="P 1", cell=Cell.cubic(4.212),
        scale=Parameter(value=5e-3),
        atoms=[
            Atom(label="Mg1", species="Mg+2", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="O1", species="O-2", x=Parameter(value=0.5),
                 y=Parameter(value=0.5), z=Parameter(value=0.5)),
        ])])
    with pytest.raises(ValueError) as excinfo:
        _compile(structure)
    message = str(excinfo.value)
    assert "MgO" in message
    assert "Mg1" in message and "atom 0" in message   # the first bad atom
    assert "'Mg+2'" in message
    assert "Mg2+" in message                           # the spelling that works


def test_a_fault_that_is_no_atoms_species_is_re_raised_untouched():
    """A failure that belongs to no atom keeps its original message.

    The compile boundary catches ``(KeyError, ValueError)`` around the two
    lookups, but not every such error is a bad species: the emission-line
    dispersion-edge guard raises ``ValueError`` naming a *valid* element and two
    wavelengths, because one structure factor cannot serve both across an edge.
    The locator must not dress that up as an atom's fault — it re-walks the
    atoms, finds every species resolves, and re-raises the original object
    unchanged.  Pinned on the locator directly so it does not depend on which
    anode straddles which edge.
    """
    from rietx.model.forward import _reraise_species_fault

    phase = _hand_structure("Fe").phases[0]       # a valid, tabulated species
    sentinel = ValueError(
        "Fe dispersion differs by 3.4 e between the source's 1.79 A and "
        "1.62 A lines: an absorption edge lies between them")
    with pytest.raises(ValueError) as excinfo:
        _reraise_species_fault(phase, None, (1.79, 1.62), sentinel)
    assert excinfo.value is sentinel              # untouched, not re-wrapped


def test_an_edge_fault_is_not_pinned_on_a_later_unrelated_atom():
    """The dispersion walk runs the edge guard, so it stops at the real species.

    ``dispersion.resolve`` checks two things per species — the primary line and
    the emission-line edge guard over the secondary lines — and it was the
    *guard* that refused here.  A re-walk that checked only ``dispersion(sym,
    lams[0])`` resolves ``Fe`` at 1.79 Å happily, falls through the atom the
    compile actually choked on, and reaches ``Xx1``, which has no dispersion
    data at all: the source's absorption edge then comes back as an atom's
    spelling, with the wrong atom named and the real reason gone.  Running the
    guard finds ``Fe`` first, recognises a fault that is no atom's, and
    re-raises the compile's own object — the single-atom sibling above cannot
    see this, because with one atom there is no later atom to fall through to.
    """
    from rietx.model.forward import _reraise_species_fault
    from rietx.schemas.instrument import Dispersion

    phase = Phase(
        name="P", space_group="P 1", cell=Cell.cubic(5.0),
        scale=Parameter(value=5e-3),
        atoms=[
            Atom(label="Fe1", species="Fe", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="Xx1", species="Xx", x=Parameter(value=0.5),
                 y=Parameter(value=0.5), z=Parameter(value=0.5)),
        ])
    sentinel = ValueError(
        "Fe dispersion differs by 3.4 e between the source's 1.79 A and "
        "1.62 A lines: an absorption edge lies between them")
    with pytest.raises(ValueError) as excinfo:
        _reraise_species_fault(phase, Dispersion(), (1.79, 1.62), sentinel)
    assert excinfo.value is sentinel              # untouched, not re-wrapped
    assert "Xx1" not in str(excinfo.value)        # and not blamed on atom 1


def test_an_xray_compile_names_the_atom_its_own_lookup_choked_on():
    """The X-ray re-walk follows the compile's two passes, so it names ``Og1``.

    ``compile_model`` resolves dispersion over the *whole* phase first and only
    then compiles the sites (``normalize_species``); the two are separate
    passes, dispersion first.  ``D`` used to read as hydrogen for dispersion
    (zero, no exception) while the Waasmaier-Kirfel table carried no ``D`` row,
    so a re-walk that checked both lookups per atom stopped at atom 0 and blamed
    ``D`` for a form-factor row it never needed — while the real fault the
    compile raised on is atom 1's ``Og`` (Z = 118), which has no dispersion data
    at all, so ``resolve_dispersion`` never reached the site compile for *any*
    atom.  Same misattribution the neutron round found, one table over.  The
    two-pass re-walk names atom 1 (``Og1``) with the dispersion table's own
    reason.  Since #552 ``D`` resolves in both tables (an isotope is its element
    to X-rays), and every element the dispersion table holds has a form-factor
    row, so no species now separates the two passes; the test still pins that
    the fault lands on ``Og1`` and not on ``D``.

    Dispersion-on only: with ``dispersion=None`` there is a single lookup and no
    pass to get out of order — ``D`` is then genuinely the first fault, and
    ``test_a_well_formed_symbol_with_no_table_row_is_also_named`` covers it.
    """
    structure = Structure(phases=[Phase(
        name="Trirutile", space_group="P 1", cell=Cell.cubic(5.0),
        scale=Parameter(value=5e-3),
        atoms=[
            Atom(label="D1", species="D", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="Og1", species="Og", x=Parameter(value=0.5),
                 y=Parameter(value=0.5), z=Parameter(value=0.5)),
        ])])
    with pytest.raises(ValueError) as excinfo:
        _compile(structure, dispersion_on=True)
    message = str(excinfo.value)
    assert "atom 1" in message and "'Og1'" in message   # the real fault, not D
    assert "'Og'" in message
    assert "Cromer-Liberman" in message                 # the table actually consulted
    assert "D1" not in message                           # the zero-dispersion atom is not blamed
    assert "Waasmaier" not in message                    # nor the form-factor table it never reached


# (a″) the same boundary on a neutron source, which resolves a *third* table.
#      ``compile_phase_sites`` now takes ``neutron=``: a neutron_cw source reads
#      bound coherent scattering lengths (``neutron.b_coh``, keyed by nuclide),
#      not X-ray form factors.  The locator must re-walk whichever table the
#      compile consulted — re-walking the X-ray table on a neutron compile stops
#      at the first nuclide the X-ray table cannot read (``2H``) and blames it
#      for a fault in a table this compile never touched.
# ----------------------------------------------------------------------
def _neutron_structure(first_species, first_label, *, second="Xx",
                       second_label="Q1", name="D2O"):
    """A two-atom structure: a nuclide the X-ray table cannot read, then a fault.

    The first atom is readable by the neutron table and *not* by the X-ray one
    (``2H``, ``157Gd``); the second is the atom that actually has no row.  An
    X-ray re-walk would stop at the first; a neutron re-walk reaches the second.
    """
    return Structure(phases=[Phase(
        name=name, space_group="P 1", cell=Cell.cubic(5.0),
        scale=Parameter(value=5e-3),
        atoms=[
            Atom(label=first_label, species=first_species, x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label=second_label, species=second, x=Parameter(value=0.5),
                 y=Parameter(value=0.5), z=Parameter(value=0.5)),
        ])])


def _compile_neutron(structure):
    from rietx.model.forward import compile_model

    ins = Instrument.constant_wavelength_neutron(wavelength=1.5, fwhm_deg=0.3)
    tt = np.arange(20.0, 60.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    return compile_model(structure, ins, pattern, mode="rietveld")


@pytest.mark.parametrize("nuclide, nuclide_label", [
    ("2H", "D1"), ("157Gd", "Gd1"),   # readable by b_coh, refused by the X-ray table
])
def test_a_neutron_compile_names_the_atom_its_own_table_choked_on(
        nuclide, nuclide_label):
    """The locator follows the radiation, so it names ``Q1`` and not the nuclide.

    ``2H``/``157Gd`` resolve against ``neutron.b_coh`` (that is the headline
    neutron case: a table that has always had b(2H)); ``Xx`` is the atom with no
    row.  An X-ray re-walk would refuse ``2H`` for "no Waasmaier-Kirfel
    coefficients" — wrong atom, wrong label, and a reason true of a table this
    compile never consulted, which also hides the real fault.  The neutron
    re-walk names atom 1 (``Q1``) with the neutron table's own reason.
    """
    with pytest.raises(ValueError) as excinfo:
        _compile_neutron(_neutron_structure(nuclide, nuclide_label))
    message = str(excinfo.value)
    assert "atom 1" in message and "'Q1'" in message   # the real fault, not the nuclide
    assert "'Xx'" in message
    assert "neutron scattering length" in message       # the table actually consulted
    assert nuclide_label not in message                 # the nuclide is not blamed
    assert "Waasmaier" not in message                   # nor the X-ray table it never touched


def test_a_neutron_compile_names_the_atom_its_own_parse_pass_choked_on():
    """The neutron re-walk follows ``compile_phase_sites``' two passes, not one.

    ``compile_phase_sites`` parses every atom's species first
    (``neutron_normalize_species`` in the site loop) and only then looks every
    atom up (``neutron_b_coh`` for the b vector) — two passes, parse first.
    ``Xx`` parses as a symbol and has no Sears row; ``123`` does not parse at
    all.  So the compile raises in pass one on atom 1, while a single re-walk
    over ``b_coh`` — which parses and looks up in one call — stops at atom 0
    and reports a missing scattering length, a table pass one never reached.
    Same misattribution the X-ray arm had, one table over: the two-pass re-walk
    names atom 1 with the parser's own reason.
    """
    with pytest.raises(ValueError) as excinfo:
        _compile_neutron(_neutron_structure("Xx", "A0", second="123",
                                            second_label="A1"))
    message = str(excinfo.value)
    assert "atom 1" in message and "'A1'" in message  # the real fault, not Xx
    assert "'123'" in message
    assert "cannot read a species" in message         # the pass that refused
    assert "Xx" not in message                        # the parseable atom is not blamed
    assert "scattering length" not in message         # nor the table pass one never reached


@pytest.mark.parametrize("spelling", ["Cu+1", "Fe+3"])
def test_a_sign_first_charge_compiles_on_a_neutron_source(spelling):
    """The neutron parser accepts the sign-first charge the X-ray tables refuse.

    ``neutron.normalize_species`` discards either charge spelling and keeps the
    nuclide, so ``Cu+1`` resolves to ``Cu`` and compiles — it is not a fault on
    this radiation.  The locator must not manufacture one, nor append the
    sign-first spelling hint (``Cu1+``), which is an X-ray-table artifact: on a
    table that accepted the spelling, naming a rewrite of it would be false.
    """
    structure = Structure(phases=[Phase(
        name="cell", space_group="P 1", cell=Cell.cubic(3.6),
        scale=Parameter(value=5e-3),
        atoms=[Atom(label="M1", species=spelling, x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0))])])
    _compile_neutron(structure)   # compiles clean; no raise, no hint


# ----------------------------------------------------------------------
# (j) a symmetry-fixed angle an external CIF reports is corrected and named,
#     where a reader has a diagnostics channel and ParameterTable does not
# ----------------------------------------------------------------------

ORTHO_CIF = """\
data_ortho
_symmetry_space_group_name_H-M 'P m m m'
_cell_length_a 5.0
_cell_length_b 6.0
_cell_length_c 7.0
_cell_angle_alpha 90
_cell_angle_beta {beta}
_cell_angle_gamma 90
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Na1 Na 0 0 0 1
"""


def _ortho_cif(tmp_path, beta):
    path = tmp_path / "ortho.cif"
    path.write_text(ORTHO_CIF.format(beta=beta), encoding="utf-8")
    return str(path)


def test_a_reported_refined_angle_is_corrected_and_named(tmp_path):
    # the realistic external case: an experimenter quoting a refined
    # beta = 90.002(3) under an orthorhombic symbol is reporting a
    # measurement, not making a mistake — and before this it raised at the
    # first parameters()/set_vary/stage compile rather than refining
    from rietx.params.vector import ParameterTable

    diags = []
    structure = Structure.from_cif(_ortho_cif(tmp_path, 90.002),
                                   diagnostics=diags)
    assert structure.phases[0].cell.beta.value == 90.0
    assert [d.code for d in diags] == ["CIF_CELL_ANGLE_CORRECTED"]
    assert diags[0].where == ["phases.0.cell.beta"]
    assert "90.002" in diags[0].message and "+0.002" in diags[0].message
    # and the correction is what lets the model reach a table at all
    ParameterTable(structure, Instrument.bragg_brentano(radiation="CuKa"))


def test_a_structural_disagreement_is_left_alone_and_still_raises(tmp_path):
    # a monoclinic beta under an orthorhombic symbol: the symbol and the angle
    # contradict each other, and which is wrong is not a reader's call
    from rietx.params.vector import ParameterTable

    diags = []
    structure = Structure.from_cif(_ortho_cif(tmp_path, 93.2), diagnostics=diags)
    assert structure.phases[0].cell.beta.value == pytest.approx(93.2)
    assert diags == []
    with pytest.raises(ValueError, match="fixes beta"):
        ParameterTable(structure, Instrument.bragg_brentano(radiation="CuKa"))


def test_an_exact_angle_is_neither_touched_nor_reported(tmp_path):
    diags = []
    structure = Structure.from_cif(_ortho_cif(tmp_path, 90.0), diagnostics=diags)
    assert structure.phases[0].cell.beta.value == 90.0
    assert diags == []


def test_the_correction_band_separates_a_report_from_a_mis_declaration():
    from rietx.crystallography.cif import CIF_ANGLE_CORRECT_MAX_DEG
    from rietx.crystallography.symmetry import SYMMETRY_ANGLE_TOL_DEG

    # wide enough to cover a refined-and-reported angle, and strictly above
    # the tolerance that decides whether there is anything to correct at all
    assert SYMMETRY_ANGLE_TOL_DEG < CIF_ANGLE_CORRECT_MAX_DEG
    # narrow enough that the 3.2° case WP-1036 found in the wild is excluded
    assert CIF_ANGLE_CORRECT_MAX_DEG < 3.2


# ----------------------------------------------------------------------
# (b) generate_reflections refuses a petabyte grid before allocating it
# ----------------------------------------------------------------------


def test_a_collapsed_cell_is_refused_before_the_grid_is_allocated():
    # the real case allocated 2.35 PiB and killed the process; the guard has
    # to fire before np.meshgrid, so the test's only budget is the raise
    from rietx.crystallography.symmetry import generate_reflections

    with pytest.raises(ValueError, match="grid points") as err:
        generate_reflections("P 1", (56800.0, 56800.0, 72600.0,
                                     90.0, 90.0, 90.0),
                             wavelength=1.5406, two_theta_max=120.0)
    # the message names the cell and the likely cause, not just the size
    assert "56800" in str(err.value)
    assert "collapsed or mis-scaled" in str(err.value)


def test_the_grid_limit_clears_every_physical_cell():
    from rietx.crystallography.symmetry import MAX_HKL_GRID_POINTS, generate_reflections

    # a 100 Å protein-scale cell at d_min ≈ 1 Å implies a 201³ grid — the
    # refusal must sit far above any physical powder problem, so pin the
    # limit against that arithmetic, and enumerate a small P1 cell for real
    assert 201 ** 3 < MAX_HKL_GRID_POINTS
    refl = generate_reflections("P 1", (25.0, 25.0, 25.0, 90.0, 90.0, 90.0),
                                wavelength=1.5406, two_theta_max=40.0)
    assert len(refl.hkl) > 0


# ----------------------------------------------------------------------
# (c) a fit that is nowhere near the data says so, instead of "converged"
# (d) a stage that stopped on its budget says so, instead of nothing
# ----------------------------------------------------------------------


def _nacl_pattern(tmp_path, *, cell_error=0.0):
    """A synthetic NaCl pattern, and a structure whose cell is off by a factor.

    ``cell_error=0.03`` reproduces §(c): a starting cell 3 % off puts every
    reflection outside the window it was compiled with.
    """
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    truth = Structure.from_cif(_nacl_cif(tmp_path))
    truth.phases[0].scale.value = 20.0
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 4e-3
    tt = np.arange(25.0, 75.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0()))
    # counting noise, so the exact-cell case is a *fit* rather than an
    # identity — a zero residual makes several statistics degenerate
    y = np.random.default_rng(20281028).poisson(np.maximum(y, 1.0)).astype(float)
    pattern = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    start = Structure.from_cif(_nacl_cif(tmp_path))
    start.phases[0].scale.value = 20.0
    for name in ("a", "b", "c"):
        p = getattr(start.phases[0].cell, name)
        p.value *= 1.0 + cell_error
    return start, ins, pattern


# max_iter = 1 is what truncates a one-parameter stage now that the budget is
# max_iter x NFEV_PER_ITERATION rather than max_iter x n_params (WP-1109): the
# constant multiplier *loosens* the cap below four free parameters and tightens
# it above, and this stage frees exactly one.  The row is about the status, not
# the number — either exit must still report MODEL_FAR_FROM_DATA.  The
# truncated row runs TRF: the scale is linear, and the LM driver solves it in
# two evaluations, inside any budget (WP-1938).
@pytest.mark.parametrize("max_iter, expect_status, solver",
                         [(1, "max_iter", "trf"), (50, "converged", None)])
def test_a_fit_nowhere_near_the_data_is_reported_however_the_solver_exited(
        tmp_path, max_iter, expect_status, solver):
    # the defect is the *converged* row: the refinement does not error, it
    # returns status="converged" and a batch caller believes it
    from rietx import Refinement
    from rietx.optimize.least_squares import DEFAULT_SOLVER
    from rietx.strategy.staged import Stage

    start, ins, pattern = _nacl_pattern(tmp_path, cell_error=0.03)
    ref = Refinement(start, ins, solver=solver or DEFAULT_SOLVER)
    result = ref.run_stage(pattern, Stage(name="scale",
                                          turn_on=["phases.*.scale"],
                                          max_iter=max_iter))

    assert result.status == expect_status
    far = [d for d in result.diagnostics if d.code == "MODEL_FAR_FROM_DATA"]
    assert len(far) == 1
    assert far[0].level == "error"
    # the cause is *measured*, not asserted: with every reflection outside its
    # frozen window the calculated pattern is nearly all background
    assert "above-background intensity" in far[0].message
    assert "2θ range" in far[0].suggestion


def test_the_bar_sits_below_the_zero_scale_attractor_not_above_it():
    # Rwp = 1 is exactly "no better than y_calc = 0", and driving the scale to
    # zero is the escape a windowed-out model converges to — measured 0.99999
    # on the reproduction above, so a threshold at 1.0 misses it by 1e-5
    from rietx.refine import MODEL_FAR_FROM_DATA_RWP

    assert MODEL_FAR_FROM_DATA_RWP < 0.99999
    # and still far above an honestly bad Rietveld fit (0.2-0.5 measured)
    assert MODEL_FAR_FROM_DATA_RWP > 0.5


def test_a_fit_on_the_data_reports_neither_robustness_diagnostic(tmp_path):
    from rietx import Refinement
    from rietx.strategy.staged import Stage

    start, ins, pattern = _nacl_pattern(tmp_path)          # exact cell
    ref = Refinement(start, ins)
    result = ref.run_stage(pattern, Stage(name="scale",
                                          turn_on=["phases.*.scale"],
                                          max_iter=20))

    assert result.statistics.rwp < 0.01
    codes = {d.code for d in result.diagnostics}
    assert "MODEL_FAR_FROM_DATA" not in codes
    assert "STAGE_MAX_ITER" not in codes


# ----------------------------------------------------------------------
# (e) March-Dollase r cannot reach zero and divide the residual
# ----------------------------------------------------------------------


def test_the_march_factor_is_what_a_zero_r_destroys():
    # A = r²cos²α + sin²α/r, term = A^(−3/2).  At r = 0 the bracket is inf off
    # the axis (→ term 0, silently wrong) and 0 *on* it (→ NaN), and every
    # derivative column is NaN — so the residual is garbage and nothing raises
    from rietx.model.preferred_orientation import march_term, march_term_and_dr

    cos2 = np.array([0.0, 0.5, 1.0])
    with np.errstate(divide="ignore", invalid="ignore"):
        term = march_term(cos2, 0.0)
        _, dterm = march_term_and_dr(cos2, 0.0)
    assert np.isnan(term[-1])          # scattering vector along the axis
    assert np.all(np.isnan(dterm))     # the whole Jacobian column


def test_a_zero_bound_is_repaired_even_when_it_comes_from_a_stored_document():
    # the broken bound outlives the default: a project or history node written
    # before the fix carries min=0.0 explicitly
    from rietx import Parameter
    from rietx.schemas.structure import MARCH_R_MIN, PreferredOrientation

    po = PreferredOrientation(
        axis=(0, 0, 1),
        r=Parameter(value=0.8, vary=True, min=0.0, transform="softplus"))
    # the pole floor, and no ceiling (WP-2002)
    assert (po.r.min, po.r.max) == (MARCH_R_MIN, np.inf)
    assert po.r.value == pytest.approx(0.8)      # the value is not disturbed

    back = PreferredOrientation.model_validate_json(po.model_dump_json())
    assert back.r.min == MARCH_R_MIN

    # a positive bound a caller chose is left alone — it already maps to a
    # finite internal bound, so the underflow cannot happen there
    tight = PreferredOrientation(
        axis=(0, 0, 1),
        r=Parameter(value=0.8, min=0.5, max=2.0, transform="softplus"))
    assert (tight.r.min, tight.r.max) == (0.5, 2.0)


def test_the_march_bound_holds_through_the_parameter_table():
    from rietx import Instrument, Parameter
    from rietx.params.vector import ParameterTable
    from rietx.schemas.structure import MARCH_R_MIN, PreferredOrientation
    from tests.test_coordinates import make_rutile

    s = make_rutile()
    s.phases[0].preferred_orientation = PreferredOrientation(
        axis=(0, 0, 1),
        r=Parameter(value=1.0, vary=True, min=0.0, transform="softplus"))
    table = ParameterTable(s, Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["*"], False)
    table.set_vary(["phases.*.preferred_orientation.r"], True)

    lo, hi = table.bounds()
    k = table.free_paths.index("phases.0.preferred_orientation.r")
    # the solver sees a finite lower bound, so it can no longer reach a zero r;
    # nothing bounds it above (WP-2002)
    assert np.isfinite(lo[k]) and hi[k] == np.inf
    x = table.x0().copy()
    x[k] = lo[k]
    assert table.decode(x)["phases.0.preferred_orientation.r"] == \
        pytest.approx(MARCH_R_MIN)


def test_the_march_factor_and_its_column_are_finite_on_the_floor():
    """The floor is a pole guard: at ``MARCH_R_MIN`` the factor and its
    r-derivative are finite at every angle, so LM landing exactly on the bound
    (WP-1938) meets a defined model and a live column."""
    from rietx.model.preferred_orientation import march_term_and_dr
    from rietx.schemas.structure import MARCH_R_MIN

    cos2 = np.linspace(0.0, 1.0, 10001)
    term, dterm = march_term_and_dr(cos2, MARCH_R_MIN)
    assert np.all(np.isfinite(term)) and np.all(np.isfinite(dterm))
    assert np.all(term > 0.0) and np.all(dterm != 0.0)
    # with a margin of more than a hundred decades below fp64's overflow
    assert np.abs(dterm).max() < 1e30


# ----------------------------------------------------------------------
# (i) the background envelope is extrapolated to the data edges, and a line
#     standing on extrapolated background says so
# ----------------------------------------------------------------------


def test_the_envelope_no_longer_clamps_flat_below_its_first_knot():
    # the mechanism: each knot's x is its window's *centre*, so the first sits
    # half a window inside the data and np.interp clamps flat below it.  On a
    # falling background that clamp is far under the truth and the whole first
    # half-window reads as positive net
    from rietx.background.diagnostics import background_envelope, envelope_measured_span

    tt = np.arange(5.0, 60.0, 0.02)
    truth = 1000.0 * np.exp(-(tt - 5.0) / 25.0)      # a falling background
    env = background_envelope(tt, truth)
    lo, _ = envelope_measured_span(tt)

    assert lo > tt[0] + 1.0              # the first knot really is inside
    # the envelope tracks the falling truth at the very first channel rather
    # than sitting at the first knot's (much lower) level
    assert env[0] == pytest.approx(truth[0], rel=0.05)
    assert env[0] > truth[np.searchsorted(tt, lo)]


def test_extrapolating_to_the_edges_only_extends():
    from rietx.background.diagnostics import _extrapolate_to_edges

    xs, ys = [2.0, 4.0, 6.0], [10.0, 8.0, 6.0]
    x2, y2 = _extrapolate_to_edges(list(xs), list(ys), 1.0, 7.0)
    assert x2 == [1.0, 2.0, 4.0, 6.0, 7.0]
    assert y2 == pytest.approx([11.0, 10.0, 8.0, 6.0, 5.0])

    # an edge already covered by a knot is left alone — a no-op, not a duplicate
    same_x, same_y = _extrapolate_to_edges(list(xs), list(ys), 2.0, 6.0)
    assert (same_x, same_y) == (xs, ys)


def test_a_line_on_extrapolated_background_is_flagged_and_still_usable():
    # report, don't refuse: the component is real intensity, just measured
    # against a background nobody observed, so the flag is deliberately not in
    # PEAK_UNUSABLE_FLAGS and is not a reuse of position_at_bound
    from rietx.schemas.indexing import PEAK_UNUSABLE_FLAGS, PeakFlag

    assert "background_extrapolated" in get_args(PeakFlag)
    assert "background_extrapolated" not in PEAK_UNUSABLE_FLAGS


def test_the_measured_span_matches_the_envelope_knots():
    # the two must not drift apart: the span is where interpolation happens,
    # which is exactly the first and last window centres
    from rietx.background.diagnostics import envelope_measured_span

    tt = np.arange(5.0, 150.0, 0.02)
    lo, hi = envelope_measured_span(tt)
    assert tt[0] < lo < tt[0] + 3.0
    assert tt[-1] - 3.0 < hi <= tt[-1]


# ----------------------------------------------------------------------
# (g) the Le Bail partition hands out the observed excess exactly once
# ----------------------------------------------------------------------


def _lebail_partition_ratio(n_phases, *, n_cycles=3):
    """Σ (calculated Bragg) / Σ (observed above background) after partitioning.

    A partition hands out each channel's excess exactly once, so this is 1.0
    at any phase count.  Before the fix the denominator was built per phase,
    so every phase claimed the whole excess in its own windows and the ratio
    settled above 1 wherever phases overlap.
    """
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from tests.test_qpa import _caf2_phase, make_lab6

    s = make_lab6()
    if n_phases > 1:
        s.phases.append(_caf2_phase())
    for phase in s.phases:
        phase.scale.value = 1.0
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 5e-3
    tt = np.arange(20.0, 80.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    truth = compile_model(s, ins, blank, mode="rietveld")
    t0 = ParameterTable(s, ins)
    y = truth.evaluate(t0.decode(t0.x0()))

    pattern = PatternData(two_theta=tt.tolist(), intensity=y.tolist())
    model = compile_model(s, ins, pattern, mode="lebail")
    table = ParameterTable(s, ins)
    values = table.decode(table.x0())
    net = np.asarray(model.y_obs) - model.background(values)
    model.lebail_update(values, n_cycles=n_cycles)
    bragg = model.evaluate(values) - model.background(values)
    return float(bragg.sum() / net.sum())


def test_the_lebail_partition_is_a_partition_at_two_phases():
    # the defect: the denominator spanned one phase, so two overlapping phases
    # were each issued the same counts — measured 1.79x on this pattern
    assert _lebail_partition_ratio(2) == pytest.approx(1.0, abs=1e-6)


def test_the_single_phase_partition_is_unchanged():
    # one phase has nothing to overlap with, so the fix must be a no-op here
    assert _lebail_partition_ratio(1) == pytest.approx(1.0, abs=1e-6)


def test_an_unseeded_background_hands_the_pedestal_to_the_reflections():
    # (h): auto_background picks the knot spacing but starts every coefficient
    # at 0.0, and the first lebail_update runs before the background has ever
    # been fitted — so the partition is handed max(y_obs − 0, 0).  This is a
    # caller-protocol requirement (the skill's §2, and its measurement in
    # references/judging.md), pinned rather than
    # fixed: seeding every background would change where every fit starts
    from rietx.background.auto import auto_background
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from tests.test_qpa import make_lab6

    s = make_lab6()
    s.phases[0].scale.value = 1.0
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 5e-3
    tt = np.arange(20.0, 80.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    t0 = ParameterTable(s, ins)
    peaks = compile_model(s, ins, blank, mode="rietveld").evaluate(t0.decode(t0.x0()))
    y = peaks + 5.0 * peaks.max()          # background 5× the strongest peak
    pattern = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    ins.background = auto_background(pattern).background
    assert all(c.value == 0.0 for c in ins.background.coefficients)

    model = compile_model(s, ins, pattern, mode="lebail")
    table = ParameterTable(s, ins)
    values = table.decode(table.x0())
    assert np.max(model.background(values)) == 0.0
    model.lebail_update(values, n_cycles=1)
    claimed = (model.evaluate(values) - model.background(values)).sum()
    assert claimed > 100.0 * peaks.sum()   # measured ~571×


def test_the_overcount_is_a_fixed_point_not_a_runaway():
    # worth pinning because the WP filed this as "inflate one another without
    # bound": the ratio is the same after 1 cycle and after 8, so what the
    # partition does is converge to the *wrong* answer, not diverge
    assert _lebail_partition_ratio(2, n_cycles=1) == \
        pytest.approx(_lebail_partition_ratio(2, n_cycles=8), abs=1e-6)


# ----------------------------------------------------------------------
# (f) QPA degrades to a diagnostic instead of raising from _build_result
# ----------------------------------------------------------------------


def _decoded(structure):
    from rietx.params.vector import ParameterTable

    table = ParameterTable(structure,
                           Instrument.debye_scherrer(wavelength=1.5406))
    return table.decode(table.x0())


def test_a_single_phase_is_a_hundred_percent_whatever_its_scale_did(tmp_path):
    # the computation should never have been on the critical path here: one
    # phase is 100 % by definition, and the scale is a brightness
    from rietx.optimize.qpa import compute_qpa

    structure = Structure.from_cif(_nacl_cif(tmp_path))
    structure.phases[0].scale.value = 0.0
    qpa = compute_qpa(structure, _decoded(structure))

    assert qpa is not None
    assert [r.weight_fraction for r in qpa.phases] == [1.0]
    # σ(W) stays absent: the fraction is a definition, not a measurement
    assert qpa.phases[0].weight_fraction_stderr is None


def test_a_dead_scale_in_a_mixture_returns_no_qpa_rather_than_raising(tmp_path):
    from rietx.optimize.qpa import compute_qpa

    structure = Structure.from_cif(_nacl_cif(tmp_path))
    structure.phases.append(
        Structure.from_cif(_nacl_cif(tmp_path)).phases[0].model_copy(deep=True))
    structure.phases[1].name = "phase_2"
    for phase in structure.phases:
        phase.scale.value = 0.0

    assert compute_qpa(structure, _decoded(structure)) is None


def test_the_missing_qpa_arrives_as_a_diagnostic_naming_the_dead_scales(
        tmp_path):
    from rietx.refine import _qpa_unavailable_diagnostics

    structure = Structure.from_cif(_nacl_cif(tmp_path))
    structure.phases.append(
        Structure.from_cif(_nacl_cif(tmp_path)).phases[0].model_copy(deep=True))
    structure.phases[1].name = "phase_2"
    values = _decoded(structure) | {"phases.0.scale": 0.0,
                                    "phases.1.scale": 0.0}

    diags = _qpa_unavailable_diagnostics(structure, values)
    assert [d.code for d in diags] == ["QPA_UNAVAILABLE"]
    assert diags[0].where == ["phases.0.scale", "phases.1.scale"]
    assert "belongs in the model" in diags[0].suggestion


def test_a_stage_that_stopped_on_its_budget_is_surfaced_as_a_diagnostic():
    # StageResult.status has always carried "max_iter"; what was missing is a
    # diagnostic, because the *result's* status is the last stage's and can
    # still read "converged"
    from rietx.refine import _max_iter_diagnostics
    from rietx.schemas.results import StageResult

    def stage(name, status):
        return StageResult(name=name, status=status, n_iterations=1,
                           cost_initial=1.0, cost_final=1.0)

    assert _max_iter_diagnostics([stage("scale", "converged")]) == []

    one = _max_iter_diagnostics([stage("scale", "converged"),
                                 stage("profile", "max_iter")])
    assert [d.code for d in one] == ["STAGE_MAX_ITER"]
    assert "'profile'" in one[0].message and "iteration budget" in one[0].message

    both = _max_iter_diagnostics([stage("scale", "max_iter"),
                                  stage("profile", "max_iter")])
    assert "'scale', 'profile'" in both[0].message
    assert "iteration budgets" in both[0].message

