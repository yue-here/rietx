"""A FullProf ``Jbt = ±1`` phase, read or refused by name (WP-1328).

Every magnetic fixture here is **written by hand from the FullProf manual's
own statement of the format** — the Jbt/Isy/Nvk entries of the phase control
line, LINE 23/24's ``Nsym Cen Laue MagMat`` and ``SYMM``/``MSYM`` pairs, and
LINE 25's four-line magnetic atom (``Atom Typ Mag Vek X Y Z Biso Occ Rx Ry
Rz``, codewords, ``Ix Iy Iz beta11 beta22 beta33 MagPh``, codewords). No
FullProf source was opened and no file from any database was used: the
structures are synthetic (one Fe³⁺ site at a general position), so every
number below is this file's own. The header and profile block come from
``test_projects_fullprof``'s fixture writer, reused rather than restated.

One fixture per stance: read in the magnetic cell (Jbt = 1, and Jbt = −1 on
an orthogonal cell), and each refusal — the Fourier-component forms, a
basis-function phase, a moment matrix that is not an axial action, a phase
with no nuclear counterpart in its cell, and a scale the counterpart does not
share.
"""

import math

import pytest

from rietx.io.projects.fullprof import (
    FullProfPcrError,
    magnetic_reading,
    read_fullprof_pcr,
    to_structure,
)
from tests.test_projects_fullprof import _pcr, _phase

#: A monoclinic cell with β obtuse, and an orthorhombic one, both unequal-edged.
_MONO = "   5.200000   6.900000   8.400000  90.000000 100.000000  90.000000"
_ORTHO = "   5.200000   6.900000   8.400000  90.000000  90.000000  90.000000"
_NO_CODES = "    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000"

#: One Fe and one O at general positions, so Occ = 1 (multiplicity over the
#: general multiplicity) and the moment is unconstrained by site symmetry.
_NUCLEAR_SITES = """\
Fe     FE+3    0.13000  0.27000  0.41000  0.40000   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O      O-2     0.31000  0.07000  0.19000  0.50000   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00"""

#: P 1 21/c 1 with the two-fold and the glide primed: MSYM is ε·det(R)·R with
#: ε = −1 on those two, +1 on the identity and the inversion.
_P21C_PRIMED = """\
!Nsym Cen Laue MagMat
   4   1   2   1
!
SYMM x, y, z
MSYM u, v, w, 0.0
SYMM -x, y+1/2, -z+1/2
MSYM u, -v, w, 0.0
SYMM -x, -y, -z
MSYM u, v, w, 0.0
SYMM x, -y+1/2, z+1/2
MSYM u, -v, w, 0.0
!
"""

#: P 21 21 21, every operation unprimed (det R = +1, so MSYM = R).
_P212121 = """\
!Nsym Cen Laue MagMat
   4   1   3   1
!
SYMM x, y, z
MSYM u, v, w, 0.0
SYMM -x+1/2, -y, z+1/2
MSYM -u, -v, w, 0.0
SYMM -x, y+1/2, -z+1/2
MSYM -u, v, -w, 0.0
SYMM x+1/2, -y+1/2, -z
MSYM u, -v, -w, 0.0
!
"""

#: k = (0, 0, 0): the structure stated in its magnetic cell.
_K0 = """\
   0.000000   0.000000   0.000000
       0.00       0.00       0.00"""


def _moment_atom(r=(1.5, -2.0, 2.5), codes=(81.0, 91.0, 101.0),
                 imaginary=(0.0, 0.0, 0.0), magph=0.0, biso="0.40000",
                 xyz="0.13000 0.27000 0.41000", species="MFE3") -> str:
    ix, iy, iz = imaginary
    return (f"Fe     {species}  1  0  {xyz} {biso}  1.00000  "
            f"{r[0]:.5f} {r[1]:.5f} {r[2]:.5f}\n"
            f"                      0.00    0.00    0.00    0.00     0.00  "
            f"{codes[0]:.2f} {codes[1]:.2f} {codes[2]:.2f}\n"
            f"     {ix:.3f}   {iy:.3f}   {iz:.3f}   0.000   0.000   0.000  "
            f"{magph:.5f}\n"
            f"      0.00    0.00    0.00    0.00    0.00    0.00     0.00")


def _nuclear(sg="P 1 21/c 1", cell=_MONO, name="FeO_synth"):
    return _phase(name=name, nat=2, sg=sg, atoms=_NUCLEAR_SITES, cell=cell,
                  cell_codes=_NO_CODES)


def _magnetic(symmetry=_P21C_PRIMED, cell=_MONO, jbt=1, atom=None, nvk=1,
              k=_K0, scale="5.0000", isy=-1):
    block = _phase(name="FeO_mag", nat=1, jbt=jbt, isy=isy, sg="P -1",
                   symmetry=symmetry, atoms=atom or _moment_atom(), cell=cell,
                   cell_codes=_NO_CODES, nvk=nvk, scale=scale)
    return block + ("\n" + k if nvk else "")


def _build(tmp_path, *phases, **kw):
    model = read_fullprof_pcr(_pcr(tmp_path, "mag.pcr", *phases))
    diagnostics: list = []
    return model, to_structure(model, diagnostics=diagnostics, **kw), diagnostics


def _refused(tmp_path, *phases, match):
    model = read_fullprof_pcr(_pcr(tmp_path, "mag.pcr", *phases))
    with pytest.raises(FullProfPcrError, match=match) as err:
        to_structure(model)
    assert "cannot be read" in str(err.value)
    assert "nuclear_only=True" in str(err.value)       # the way out, named
    return str(err.value)


# ---------------------------------------------------------------- read


def test_a_jbt1_phase_in_its_magnetic_cell_is_read_onto_its_nuclear_phase(
        tmp_path):
    """One Structure phase, carrying the file's magnetic group as an operator
    list and the Fe moment in crystal-axis μ_B exactly as written — the
    manual's "components along the crystallographic axis …, in units of Bohr
    magnetons", on "a basis of unit vectors along the crystallographic unit
    cell", which is magCIF's crystal-axis basis."""
    model, structure, diags = _build(tmp_path, _nuclear(), _magnetic())
    (phase,) = structure.phases
    assert phase.name == "FeO_synth"
    assert phase.magnetic_symmetry.operations == [
        "x,y,z,+1", "-x,y+1/2,-z+1/2,-1", "-x,-y,-z,+1", "x,-y+1/2,z+1/2,-1"]
    fe, o = phase.atoms
    assert fe.moment.values() == (1.5, -2.0, 2.5)
    assert fe.moment.ion == "Fe3+" and fe.moment.vary
    assert o.moment is None
    (read,) = [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_READ"]
    assert read.level == "info"
    assert "moments on 1 of 2 sites" in read.message
    assert read.where == ["phases.0.magnetic_symmetry",
                          "phases.0.atoms.0.moment"]
    assert not [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_OMITTED"]


def test_a_jbt_minus1_phase_on_an_orthogonal_cell_converts_the_spherical_form(
        tmp_path):
    """Jbt = −1 states (M, φ, θ): φ from X, θ from Z, degrees. On an
    orthogonal cell the frame is the cell's own axes whichever way the manual
    means it, so the conversion is the plain spherical one."""
    atom = _moment_atom(r=(3.0, 30.0, 60.0))
    _, structure, _ = _build(
        tmp_path, _nuclear(sg="P 21 21 21", cell=_ORTHO),
        _magnetic(symmetry=_P212121, cell=_ORTHO, jbt=-1, atom=atom))
    got = structure.phases[0].atoms[0].moment.values()
    t, p = math.radians(60.0), math.radians(30.0)
    assert got == pytest.approx((3 * math.sin(t) * math.cos(p),
                                 3 * math.sin(t) * math.sin(p),
                                 3 * math.cos(t)), abs=1e-12)


def test_a_partly_freed_moment_is_said_to_come_in_whole(tmp_path):
    """Jbt = −1 with only M coded — modulus refined, direction held — reads
    with the whole moment free (a Moment carries one flag), and the read
    diagnostic says so, naming the site and the columns the file freed."""
    atom = _moment_atom(r=(3.0, 30.0, 60.0), codes=(81.0, 0.0, 0.0))
    _, structure, diags = _build(
        tmp_path, _nuclear(sg="P 21 21 21", cell=_ORTHO),
        _magnetic(symmetry=_P212121, cell=_ORTHO, jbt=-1, atom=atom))
    assert structure.phases[0].atoms[0].moment.vary
    (read,) = [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_READ"]
    assert "frees only part of the moment at 'Fe' (M free)" in read.message
    assert "whole moment free" in read.message


def test_a_fully_freed_or_held_moment_adds_no_partial_clause(tmp_path):
    for codes in ((81.0, 91.0, 101.0), (0.0, 0.0, 0.0)):
        _, _, diags = _build(tmp_path, _nuclear(),
                             _magnetic(atom=_moment_atom(codes=codes)))
        (read,) = [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_READ"]
        assert "only part of the moment" not in read.message


def test_the_read_diagnostic_names_the_bns_number_only_when_there_is_one(
        tmp_path, monkeypatch):
    """A named group prints its BNS number; an unnamed one (``identification``'s
    ``named=False``, whose ``bns_number`` is the placeholder ``"unnamed"``)
    prints spglib's reason instead of a number it does not have."""
    from rietx.crystallography.magnetic import operators

    _, _, diags = _build(tmp_path, _nuclear(), _magnetic())
    (read,) = [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_READ"]
    assert "(BNS 14." in read.message

    def unnamed(group, *a, **kw):
        return operators.MagneticIdentification(
            named=False, group_id=None, operations=(), closest_type="P 1 21/c 1",
            reason="spglib did not match the list")

    monkeypatch.setattr(operators, "identification", unnamed)
    _, _, diags = _build(tmp_path, _nuclear(), _magnetic())
    (read,) = [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_READ"]
    assert "BNS" not in read.message
    assert ("not a tabulated magnetic space group: spglib did not match the "
            "list") in read.message


def test_nuclear_only_still_omits_a_readable_magnetic_phase(tmp_path):
    """The caller's declared choice outranks the reading."""
    _, structure, diags = _build(tmp_path, _nuclear(), _magnetic(),
                                 nuclear_only=True)
    assert structure.phases[0].magnetic_symmetry is None
    assert [d.code for d in diags].count("FULLPROF_MAGNETIC_PHASE_OMITTED") == 1


# ------------------------------------------------------------- refused


@pytest.mark.parametrize("atom_kw, match", [
    ({"imaginary": (0.5, 0.0, 0.0)}, r"imaginary component Ix = 0\.5.*Fourier"),
    ({"magph": 0.25}, r"MagPh = 0\.25.*Fourier"),
])
def test_the_fourier_component_form_is_refused_by_name(tmp_path, atom_kw, match):
    """S_k = ½(R_k + i I_k)·exp(−2πi MagPh): an imaginary part or a phase is a
    moment stated as a Fourier amplitude, not one real moment per site."""
    _refused(tmp_path, _nuclear(), _magnetic(atom=_moment_atom(**atom_kw)),
             match=match)


def test_a_propagation_vector_other_than_zero_is_refused_by_name(tmp_path):
    k = """\
   0.500000   0.000000   0.000000
       0.00       0.00       0.00"""
    _refused(tmp_path, _nuclear(), _magnetic(k=k),
             match=r"propagation vector \(0\.5, 0\.0, 0\.0\).*Fourier-component")


def test_an_msym_phase_is_refused_by_name(tmp_path):
    symmetry = _P21C_PRIMED.replace("SYMM -x, -y, -z\nMSYM u, v, w, 0.0",
                                    "SYMM -x, -y, -z\nMSYM u, v, w, 0.5")
    _refused(tmp_path, _nuclear(), _magnetic(symmetry=symmetry),
             match=r"magnetic phase 0\.5")


def test_a_moment_matrix_that_is_not_an_axial_action_is_refused(tmp_path):
    """The manual allows any matrix; only ±det(R)·R is a Shubnikov operation."""
    symmetry = _P21C_PRIMED.replace("SYMM -x, y+1/2, -z+1/2\nMSYM u, -v, w",
                                    "SYMM -x, y+1/2, -z+1/2\nMSYM -u, -v, w")
    _refused(tmp_path, _nuclear(), _magnetic(symmetry=symmetry),
             match=r"not ±det\(R\)·R")


def test_a_basis_function_phase_is_refused_by_name(tmp_path):
    symmetry = """\
! Nsym   Cen  Laue Ireps N_Bas
     1     1      1    -1     1
! Real(0)-Imaginary(1) indicator for Ci
  0
!
SYMM x, y, z
BASR     1     0     0
BASI     0     0     0
!
"""
    _refused(tmp_path, _nuclear(), _magnetic(symmetry=symmetry, isy=-2),
             match=r"Isy = -2 states basis functions")


def test_a_magnetic_phase_with_no_nuclear_phase_in_its_cell_is_refused(tmp_path):
    """A nuclear phase in the chemical cell beside a magnetic one stated in a
    doubled cell: the moments have no site to land on in this Structure."""
    doubled = "  10.400000   6.900000   8.400000  90.000000 100.000000  90.000000"
    _refused(tmp_path, _nuclear(), _magnetic(cell=doubled),
             match=r"0 nuclear phases of this file share its cell")


def test_a_magnetic_scale_the_nuclear_phase_does_not_share_is_refused(tmp_path):
    """Two scales, one built phase: the moments would come out scaled."""
    message = _refused(tmp_path, _nuclear(), _magnetic(scale="20.0000"),
                       match=r"Scale x f\^2 is 20 and 'FeO_synth''s is 5")
    assert "scaled by 2" in message


def test_a_magnetic_phase_with_no_sites_is_refused_by_name(tmp_path):
    """Nat = 0 under Jbt = 1: no moment to place. Refused as a reason naming
    the file and the phase, never ``max()`` on an empty list."""
    empty = _phase(name="FeO_mag", nat=0, jbt=1, isy=-1, sg="P -1",
                   symmetry=_P21C_PRIMED, atoms="", cell=_MONO,
                   cell_codes=_NO_CODES, nvk=1) + "\n" + _K0
    message = _refused(tmp_path, _nuclear(), empty,
                       match=r"'FeO_mag' \(Jbt 1, Isy -1, 0 sites\) — it states "
                             r"no magnetic site")
    assert "mag.pcr" in message


def test_an_unparsable_counterpart_symbol_is_refused_by_name(tmp_path):
    """gemmi's ``ValueError`` on the counterpart's symbol becomes a reason, so
    ``to_structure`` refuses naming the file and the phase."""
    model = read_fullprof_pcr(_pcr(tmp_path, "m.pcr", _nuclear(sg="Q 9 z"),
                                   _magnetic()))
    reason = magnetic_reading(model, model.magnetic_phases[0])
    assert isinstance(reason, str)
    assert "counterpart 'FeO_synth' does not build" in reason
    assert "Q 9 z" in reason
    message = _refused(tmp_path, _nuclear(sg="Q 9 z"), _magnetic(),
                       match=r"'FeO_mag' .* counterpart 'FeO_synth' does not "
                             r"build")
    assert "mag.pcr" in message


def test_jbt_minus1_on_an_oblique_cell_is_refused(tmp_path):
    _refused(tmp_path, _nuclear(),
             _magnetic(jbt=-1, atom=_moment_atom(r=(3.0, 30.0, 60.0))),
             match=r"Jbt = -1 .* not\s+orthogonal")


def test_magnetic_reading_returns_the_reason_rather_than_raising(tmp_path):
    """The refusal sentence is data, so a caller can ask before building."""
    model = read_fullprof_pcr(_pcr(tmp_path, "m.pcr", _nuclear(),
                                   _magnetic(scale="20.0000")))
    reason = magnetic_reading(model, model.magnetic_phases[0])
    assert isinstance(reason, str) and "Scale" in reason


# ------------------------------------------------- Jbt ±10: one combined phase
#
# The manual's Jbt = ±10 (p. 90) is a phase that "can contain nuclear and
# magnetic contributions", its atoms in LINE 25b (p. 105): `Atom Typ Mag Vek X
# Y Z Biso Occ N_t Spc` and five codewords, then — where N_t = ±1 — `Rx Ry Rz
# Ix Iy Iz MagPh` (or the spherical form) and seven codewords. A site with a
# moment names its magnetic form factor in Typ, from which "the program
# extracts internally the Fermi length symbol", so it reads as the element.
# The positive arm writes the structure above both ways and asks for one
# Structure; the twin's nuclear Fe is therefore spelled `FE`, the element the
# combined phase's `MFE3` names.
#
# The combined spelling is FullProf's own, measured with fp2k 8.20 on exactly
# these files (O spelled `O` for its neutron table): the symbol `P -1` only
# generates reflections, the SYMM list is the structure's group, Nvk = 0, and
# Jbt = -10 reads its spherical moment under N_t = 1. So written, the pair and
# the combined phase gave one calculated pattern to 0.05 counts of 5976 (0.09
# of 4985 for the spherical pair), where a `P 1 21/c 1` symbol lost the
# magnetic (001) and a stated k = 0 lost the whole magnetic part.

_TWIN_SITES = _NUCLEAR_SITES.replace("FE+3", "FE  ")


def _combined_sites(moment=("1.50000", "-2.00000", "2.50000"), n_t=1, mag=1,
                    codes=("81.00", "91.00", "101.00"), magph="0.00000",
                    imaginary="0.00000  0.00000  0.00000", tail="") -> str:
    m1, m2, m3 = moment
    c1, c2, c3 = codes
    lines = [f"Fe     MFE3    {mag}  0  0.13000  0.27000  0.41000  0.40000   "
             f"1.00000   {n_t}   0",
             "                  0.00     0.00     0.00     0.00      0.00"]
    if n_t:
        lines += [f"   {m1}  {m2}  {m3}  {imaginary}  {magph}{tail}",
                  f"     {c1}    {c2}   {c3}     0.00     0.00     0.00     0.00"]
    lines += ["O      O-2     0  0  0.31000  0.07000  0.19000  0.50000   "
              "1.00000   0   0",
              "                  0.00     0.00     0.00     0.00      0.00"]
    return "\n".join(lines)


def _combined(jbt=10, isy=-1, sg="P -1", symmetry=_P21C_PRIMED,
              cell=_MONO, atoms=None, nvk=0, k=_K0):
    block = _phase(name="FeO_synth", nat=2, jbt=jbt, isy=isy, sg=sg,
                   symmetry=symmetry, atoms=atoms or _combined_sites(),
                   cell=cell, cell_codes=_NO_CODES, nvk=nvk,
                   atom_header="!Atom Typ Mag Vek X Y Z Biso Occ N_t Spc")
    return block + ("\n" + k if nvk else "")


def _pair(**magnetic_kw):
    nuclear = _phase(name="FeO_synth", nat=2,
                     sg=magnetic_kw.pop("sg", "P 1 21/c 1"),
                     atoms=_TWIN_SITES, cell=magnetic_kw.get("cell", _MONO),
                     cell_codes=_NO_CODES)
    return nuclear, _magnetic(**magnetic_kw)


def test_jbt_10_reads_to_the_structure_of_its_jbt_0_plus_jbt_1_pair(tmp_path):
    """The positive arm: one structure written as a nuclear phase and the
    Jbt = 1 phase restating it, and as one Jbt = 10 phase, is one Structure —
    group, sites, moments and refine flags."""
    _, pair, _ = _build(tmp_path, *_pair())
    model, combined, diags = _build(tmp_path, _combined())
    assert combined.model_dump(mode="json") == pair.model_dump(mode="json")
    (phase,) = combined.phases
    assert phase.atoms[0].moment.values() == (1.5, -2.0, 2.5)
    assert phase.atoms[0].species == "Fe" and model.phases[0].atoms[0].species_raw == "MFE3"
    (read,) = [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_READ"]
    assert "one nuclear phase carrying its own moments" in read.message
    assert read.where == ["phases.0.magnetic_symmetry", "phases.0.atoms.0.moment"]


def test_jbt_minus_10_reads_the_spherical_moment_as_its_jbt_minus_1_pair(tmp_path):
    """Jbt = −10 states (M, φ, θ) as Jbt = −1 does, under N_t = 1 (fp2k
    8.20's spelling, not the manual's N_t = −1); on an orthogonal cell both read
    to one Structure, the moment to 1e-12 in crystal axes."""
    _, pair, _ = _build(tmp_path, *_pair(
        sg="P 21 21 21", symmetry=_P212121, cell=_ORTHO, jbt=-1,
        atom=_moment_atom(r=(3.0, 30.0, 60.0))))
    _, combined, _ = _build(tmp_path, _combined(
        jbt=-10, symmetry=_P212121, cell=_ORTHO,
        atoms=_combined_sites(moment=("3.00000", "30.00000", "60.00000"))))
    got = combined.phases[0].atoms[0].moment.values()
    assert got == pytest.approx(pair.phases[0].atoms[0].moment.values(), abs=1e-12)
    t, p = math.radians(60.0), math.radians(30.0)
    assert got == pytest.approx((3 * math.sin(t) * math.cos(p),
                                 3 * math.sin(t) * math.sin(p),
                                 3 * math.cos(t)), abs=1e-12)
    assert combined.model_dump(mode="json") == pair.model_dump(mode="json")


def test_a_flipped_moment_component_changes_the_prediction(tmp_path):
    """The negative arm: the read moments reach the pattern. Flipping one
    component of the one moment changes predict(); a reader that dropped or
    mis-slotted the moment line would leave it unchanged."""
    import numpy as np

    import rietx as rx

    def predicted(moment):
        _, structure, _ = _build(tmp_path, _combined(
            atoms=_combined_sites(moment=moment)))
        instrument = rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.3)
        return np.asarray(rx.Refinement(structure, instrument).predict(
            np.arange(8.0, 120.0, 0.05)))

    base = predicted(("1.50000", "-2.00000", "2.50000"))
    flipped = predicted(("1.50000", "2.00000", "2.50000"))
    assert np.max(np.abs(flipped - base)) > 1e-3 * np.max(base)
    assert np.array_equal(base, predicted(("1.50000", "-2.00000", "2.50000")))


def test_a_jbt_10_phase_with_no_moment_is_a_nuclear_phase(tmp_path):
    """LINE 25b "could be also used for X-rays, in such case Mag and Vek should
    be zero for all the atoms": with no moment and no magnetic symmetry it
    reads as its Jbt = 0 twin."""
    sites = _combined_sites(n_t=0, mag=0).replace("MFE3", "FE  ")
    _, twin, _ = _build(tmp_path, _pair()[0])
    _, combined, _ = _build(tmp_path, _combined(isy=0, symmetry="", atoms=sites,
                                                sg="P 1 21/c 1"))
    assert combined.model_dump(mode="json") == twin.model_dump(mode="json")


def test_the_moment_lines_trailing_marker_is_not_a_column(tmp_path):
    """FullProf's own hobk.pcr ends a LINE 25b moment line with `<-MagPar`
    and no comment marker; the seven numbers before it are the line."""
    _, structure, _ = _build(tmp_path, _combined(
        atoms=_combined_sites(tail=" <-MagPar")))
    assert structure.phases[0].atoms[0].moment.values() == (1.5, -2.0, 2.5)


def test_nuclear_only_builds_a_combined_phase_without_its_moments(tmp_path):
    _, structure, diags = _build(tmp_path, _combined(), nuclear_only=True)
    assert structure.phases[0].atoms[0].moment is None
    assert structure.phases[0].magnetic_symmetry is None
    (omitted,) = [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_OMITTED"]
    assert "Jbt 10" in omitted.message and omitted.where == ["phases.0"]


#: Three of P 1 21/c 1's four operators: not closed under composition.
_NOT_A_GROUP = """\
!Nsym Cen Laue MagMat
   3   1   2   1
!
SYMM x, y, z
MSYM u, v, w, 0.0
SYMM -x, y+1/2, -z+1/2
MSYM u, -v, w, 0.0
SYMM -x, -y, -z
MSYM u, v, w, 0.0
!
"""


@pytest.mark.parametrize("kw, match", [
    # k != 0: the propagation-vector form, pointed at its own work package.
    ({"nvk": 1,
      "k": "   0.500000   0.000000   0.000000\n       0.00       0.00       0.00"},
     "propagation vector.*#757"),
    # k = 0 stated: fp2k 8.20 then computes no magnetic part (measured).
    ({"nvk": 1}, "Nvk = 1 with k = 0"),
    # A symbol whose glide extinguishes the magnetic (001) (measured).
    ({"sg": "P 1 21/c 1"}, "extinguishes reflections its lattice allows"),
    # An operator list that is not a group.
    ({"symmetry": _NOT_A_GROUP}, "not closed under composition"),
    # Mag and N_t disagree on whether the site carries a moment.
    ({"atoms": _combined_sites(mag=0)}, "Mag = 0 and N_t = 1"),
    # A moment and no magnetic symmetry at all.
    ({"isy": 0, "symmetry": ""}, "no magnetic symmetry"),
    # The Fourier-component form, as for Jbt = 1.
    ({"atoms": _combined_sites(imaginary="0.50000  0.00000  0.00000")},
     "imaginary component Ix"),
])
def test_a_combined_phase_outside_the_model_is_refused_by_name(
        tmp_path, kw, match):
    model = read_fullprof_pcr(_pcr(tmp_path, "mag.pcr", _combined(**kw)))
    with pytest.raises(FullProfPcrError, match=match) as err:
        to_structure(model)
    assert "Jbt = ±10 phase is a nuclear phase" in str(err.value) or \
        "Jbt = ±1 phase" in str(err.value)
    assert "nuclear_only=True" in str(err.value)


def test_time_reversal_flags_are_read_and_their_order_refused(tmp_path):
    """LINE 23a's flags follow "the same [order] as in CODFIL.out" (p. 96):
    read, so the walk lands on the atoms, and refused at the build, since the
    order is FullProf's output's and not the file's."""
    block = _combined(isy=0, sg="P 1 21/c 1",
                      symmetry="! Time Reversal Operations\n 1 -1 1 -1\n")
    block = block.replace("P 1 21/c 1               <--Space group symbol",
                          "P 1 21/c 1          Magnetic symmetry below")
    model = read_fullprof_pcr(_pcr(tmp_path, "mag.pcr", block))
    assert model.phases[0].time_reversal == (1, -1, 1, -1)
    assert model.phases[0].space_group_raw == "P 1 21/c 1"
    with pytest.raises(FullProfPcrError, match="CODFIL|order FullProf lists"):
        to_structure(model)


def test_a_mag_comment_beside_listed_operators_is_refused_at_read(tmp_path):
    block = _combined().replace("P -1               <--Space group symbol",
                                "P -1                Mag")
    with pytest.raises(FullProfPcrError, match="two statements of one magnetic"):
        read_fullprof_pcr(_pcr(tmp_path, "mag.pcr", block))


@pytest.mark.parametrize("n_t", [-1, 2, 3, 4])
def test_a_combined_site_with_an_unsettled_line_count_is_refused_at_read(
        tmp_path, n_t):
    block = _combined(atoms=_combined_sites(n_t=n_t))
    with pytest.raises(FullProfPcrError, match=f"N_t = {n_t}"):
        read_fullprof_pcr(_pcr(tmp_path, "mag.pcr", block))
