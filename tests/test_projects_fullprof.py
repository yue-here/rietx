"""The FullProf ``.pcr`` project reader.

Every fixture here is written inline, per ``io/CLAUDE.md``: a text format's lines
are self-describing, so a literal in the test says more than a writer that
shares constants with the parser could.

**The real files are not committed.** The corpus this reader was written against
is six ``.pcr`` files from the maintainer's own archive, which are the owner's
data and are not this repo's to vendor. So the fixtures below are *minimal
synthetic* files that exercise one grammar branch each, and the provenance is
carried as a **quotation in a comment**: every line, every codeword and every
count in them was copied out of a named real file at a named line, so a reader
can check where each came from without the file being here. The real-file
verification is a manual check, recorded in the session report; ``ATTRIBUTION.md``
§ Format specifications records what the format facts were read from.

The failure mode this reader exists to prevent is not a crash but a *wrong
number with nothing raised*, so the assertions are about the tri-state and the
counts, not only the values:

* a **codeword** carries which refined parameter drives a value *and the sign*,
  so ``11.00`` and ``-11.00`` on two sublattices are the antiferromagnetic
  constraint and a reader that recorded only "refined" would lose the physics;
* a **count** the file declares is asserted against the lines parsed, because a
  ``.pcr`` is positional and has no keyword to resynchronise on — a dropped
  atom or background point silently reinterprets everything after it;
* a **refusal** is asserted by its message, because the whole scope claim of
  this reader is "handles X, refuses Y *by name*".
"""

import re
from pathlib import Path

import pytest

import rietx as rx
from rietx.crystallography.symmetry import get_spacegroup
from rietx.io.projects.fullprof import (
    FullProfPcrError,
    _strip,
    atom_tie_recoverability,
    cell_parameter_ties,
    decode_codeword,
    from_structure,
    normalize_space_group,
    normalize_species,
    nuclear_parameter_ties,
    occupancy_factor,
    read_fullprof_pcr,
    to_structure,
    write_fullprof_pcr,
)
from rietx.schemas.instrument import NeutronSource

# --------------------------------------------------------------- the fixtures
#
# One header, three phase blocks and a trailing range line, assembled per test.
# Every line is quoted from `corpus file 2` (a three-phase magnetic neutron CW
# refinement) unless the comment says otherwise, with the background
# cut from 51 points to 2 and the excluded regions from 2 to 1 so the fixture
# stays readable. The `!` header comments are kept verbatim *because they are
# what a real file has* — nothing here reads them, which is trap 2.

#: corpus file 2:1-14, :16-18 (two of 51 background points), :69-70 (one
#: of two excluded regions), :74 and :76-77.
_HEADER = """\
COMM 60 K
! Current global Chi2 (Bragg contrib.) =      5.144
! Files => DAT-file: sample.dat,  PCR-file: another
!Job Npr Nph Nba Nex Nsc Nor Dum Iwg Ilo Ias Res Ste Nre Cry Uni Cor Opt Aut
   {job}   7   {nph}   2   1   0   0   0   0   0   0   0   0   0   0   0   0   0   0
!
!Ipr Ppl Ioc Mat Pcr Ls1 Ls2 Ls3 NLI Prf Ins Rpa Sym Hkl Fou Sho Ana
   0   0   1   2   2   0   4   0   0   1   0  -1   1   0   0   1   0
!
! Lambda1  Lambda2    Ratio    Bkpos    Wdt    Cthm     muR   AsyLim   Rpolarz  2nd-muR -> Patt# 1
 2.077100 2.077100  0.50000   70.000  4.0000  0.0000  0.2160  160.00    0.0000  0.2160
!
!NCY  Eps  R_at  R_an  R_pr  R_gl     Thmin       Step       Thmax    PSD    Sent0
 45  0.05  0.85  0.85  0.85  0.85      3.0000   0.050000   166.2000   0.000   0.000
!
!2Theta/TOF/E(Kev)   Background  for Pattern#  1
        12.9000       952.8345         91.00
        16.4000       977.2739        101.00
!
! Excluded regions (LowT  HighT) for Pattern#  1
        0.00        9.00
!
      61    !Number of refined parameters
!
!  Zero    Code    SyCos    Code   SySin    Code  Lambda     Code MORE ->Patt# 1
 -0.03994  601.0  0.00000    0.0  0.00000    0.0 2.370100    0.00   0
"""

#: corpus file 2:88-95 — the four trirutile sites, each a value line and
#: a codeword line, with the `#color cyan` annotation the real file carries.
_PHASE_SITES = """\
Cr     CR      0.00000  0.00000  0.31111  0.21111   0.50000   0   0   0    1  #color cyan
                  0.00     0.00     0.00     0.00      0.00
W      W       0.00000  0.00000  0.00000  0.22222   0.25000   0   0   0    1  #color cyan
                  0.00     0.00     0.00     0.00      0.00
O1     O       0.33333  0.33333  0.00000  0.24444   0.50000   0   0   0    1  #color cyan
                  0.00     0.00     0.00     0.00      0.00
O2     O       0.35555  0.35555  0.36666  0.17777   1.00000   0   0   0    1  #color cyan
                  0.00     0.00     0.00     0.00      0.00"""

#: corpus file 2:96-108. The cell codewords `51 51 61` are the tetragonal
#: tie: a and b are driven by parameter 5, c by parameter 6.
_PROFILE = """\
!-------> Profile Parameters for Pattern #  1
!  Scale        Shape1      Bov      Str1      Str2      Str3   Strain-Model
  {scale}       0.00000   0.00000   0.00000   0.00000   0.00000       0
    {scale_code}     0.000     0.000     0.000     0.000     0.000
!       U         V          W           X          Y        GauSiz   LorSiz Size-Model
   0.400000  -0.200000   0.100000   0.000000   0.000000   0.000000   0.000000    0
     21.000     31.000     41.000      0.000      0.000      0.000      0.000
!     a          b         c        alpha      beta       gamma      #Cell Info
{cell}
{cell_codes}
!  Pref1    Pref2      Asy1     Asy2     Asy3     Asy4      S_L      D_L
  0.00000  0.00000  0.02000  0.00000  0.00000  0.00000  0.03000  0.03000
     0.00     0.00    81.00     0.00     0.00     0.00     0.00     0.00"""

_PHASE_CELL = "   5.000000   5.000000   9.000000  90.000000  90.000000  90.000000"
_PHASE_CELL_CODES = "   51.00000   51.00000   61.00000    0.00000    0.00000    0.00000"

#: corpus file 2:78-84, :86-87.
_PHASE_TEMPLATE = """\
!-------------------------------------------------------------------------------
!  Data for PHASE number:   {labelled}  ==> Current R_Bragg for Pattern#  1:     {r_bragg}
!-------------------------------------------------------------------------------
{name}
!
!Nat Dis {third} Pr1 Pr2 Pr3 Jbt Irf Isy Str Furth       ATZ    Nvk Npr More
   {nat}   {dis}   {third_value} 0.0 0.0 1.0   {jbt}   {irf}  {isy}   {strn}   {furth}        963.500   {nvk}   7   {more}
!
{sg}               <--Space group symbol
{symmetry}{atom_header}
{atoms}
{profile}"""

_NUCLEAR_ATOM_HEADER = (
    "!Atom   Typ       X        Y        Z     Biso       Occ     In Fin N_t Spc /Codes")

#: corpus file 2:157-158 for `Isy = -1` (Rx/Ry/Rz then Ix/Iy/Iz) and
#: corpus file 1:166-167 for `Isy = -2` (C1..C3 then C4..C9). Same columns,
#: different physical meaning — which is why nothing here reads the header.
_MAGNETIC_ATOM_HEADER = (
    "!Atom   Typ  Mag Vek    X      Y      Z       Biso    Occ      Rx      Ry      Rz\n"
    "!     Ix     Iy     Iz    beta11  beta22  beta33    MagPh")


def _phase(*, name="Trirutile", nat=4, jbt=0, isy=0, irf=0, dis=0, strn=0, furth=0,
           nvk=0, more=0, third_value=0, sg="P 42/m n m", symmetry="",
           atoms=_PHASE_SITES, atom_header=None, cell=_PHASE_CELL,
           cell_codes=_PHASE_CELL_CODES, scale="5.0000",
           scale_code="71.00000", labelled=1, r_bragg="1.79") -> str:
    """One phase block. ``third_value`` is the ``Ang``/``Mom`` column (trap 2)."""
    magnetic = jbt == 1
    return _PHASE_TEMPLATE.format(
        labelled=labelled, r_bragg=r_bragg, name=name, nat=nat, dis=dis,
        third="Mom" if magnetic else "Ang", third_value=third_value, jbt=jbt,
        irf=irf, isy=isy, strn=strn, furth=furth, nvk=nvk, more=more, sg=sg,
        symmetry=symmetry,
        atom_header=(_MAGNETIC_ATOM_HEADER if magnetic and atom_header is None
                     else _NUCLEAR_ATOM_HEADER if atom_header is None
                     else atom_header),
        atoms=atoms,
        profile=_PROFILE.format(scale=scale, scale_code=scale_code, cell=cell,
                                cell_codes=cell_codes))


#: corpus file 2:145-155, cut from four SYMM/MSYM pairs to two.
_ISY_MINUS_1_SYMMETRY = """\
!Nsym Cen Laue MagMat
   2   1   1   1
!
SYMM X, Y, Z
MSYM  u, v, w,0.000
SYMM Y, X, -Z+1
MSYM -u,-v, w,0.000
!
"""

#: corpus file 2:159-162 — one magnetic site, four lines. The `11.00`
#: codeword on Ry is parameter 1: the ordered moment.
_ISY_MINUS_1_ATOM = """\
CR     MCR3  1  0  0.00000 0.00000 0.31111 0.21111  1.00000   0.000   3.000   0.000
                      0.00    0.00    0.00    0.00     0.00    0.00   11.00    0.00
     0.000   0.000   0.000   0.000   0.000   0.000  0.00000
      0.00    0.00    0.00    0.00    0.00    0.00     0.00"""

#: corpus file 1:145-164, cut from three SYMM blocks to two. Ireps = -2, so
#: each SYMM carries **two** BASR/BASI pairs, and N_Bas = 4 makes each of them
#: 3 x 4 = 12 numbers. Both counts are the invariant this fixture exists for.
_ISY_MINUS_2_SYMMETRY = """\
! Nsym   Cen  Laue Ireps N_Bas
     2     1      1    -2     4
! Real(0)-Imaginary(1) indicator for Ci
  0  0  0  0
!
SYMM X, Y, Z
BASR     2     0     0     0     2     0     0    -2     0    -2     0     0
BASI     0     0     0     0     0     0     0     0     0     0     0     0
BASR     2     0     0     0     2     0     0    -2     0    -2     0     0
BASI     0     0     0     0     0     0     0     0     0     0     0     0
SYMM -Y+1/2, X+1/2, Z+1/2
BASR     2     0     0     0    -2     0     0    -2     0     2     0     0
BASI     0     0     0     0     0     0     0     0     0     0     0     0
BASR     0     0     0     0     0     0     0     0     0     0     0     0
BASI     0     0     0     0     0     0     0     0     0     0     0     0
!
"""

#: corpus file 1:168-175 — two Cr sublattices whose C2 coefficients carry
#: `11.00` and `-11.00`: one refined parameter, opposite signs, the
#: antiferromagnetic constraint. Note also the `.00000` spelling with no leading
#: zero, which is how that file writes every coordinate.
_ISY_MINUS_2_ATOMS = """\
1CR  MCR3  1   0    .00000  .00000  .31111 .21111 1.00000   0.000   0.800   0.000
                    0.00    0.00    0.00    0.00    0.00    0.00   11.00    0.00
   0.050   0.000   0.000   0.000   0.000   0.000   .00000
    0.00    0.00    0.00    0.00    0.00    0.00    0.00
2CR  MCR3  2   0    .00000  .00000  .68889 .21111 1.00000   0.000  -0.800   0.000
                    0.00    0.00    0.00    0.00    0.00    0.00  -11.00    0.00
   0.050   0.000   0.000   0.000   0.000   0.000   .00000
    0.00    0.00    0.00    0.00    0.00    0.00    0.00"""

#: corpus file 2:176-177.
_RANGE = """\
!  2Th1/TOF1    2Th2/TOF2  Pattern # 1
       9.000     157.000       1
"""


def _pcr(directory: Path, name: str, *phases: str, job: int = 1,
         nph: int | None = None, trailing: str = _RANGE) -> Path:
    """Write a fixture ``.pcr``. One writer, so the encoding is named once."""
    body = _HEADER.format(job=job, nph=len(phases) if nph is None else nph)
    text = body + "\n".join(phases) + "\n" + trailing
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def _magnetic_isy1(**kw) -> str:
    """The ``Isy = -1`` magnetic phase of ``corpus file 2``."""
    return _phase(**{"name": "Trirutile", "nat": 1, "jbt": 1, "isy": -1,
                     "sg": "P -1", "symmetry": _ISY_MINUS_1_SYMMETRY,
                     "atoms": _ISY_MINUS_1_ATOM, "labelled": 3,
                     "r_bragg": "9.46", **kw})


def _magnetic_isy2(**kw) -> str:
    """The ``Isy = -2`` magnetic phase of ``corpus file 1``."""
    return _phase(**{"name": "Magnetic Phase", "nat": 2, "jbt": 1, "isy": -2,
                     "sg": "P -1", "symmetry": _ISY_MINUS_2_SYMMETRY,
                     "atoms": _ISY_MINUS_2_ATOMS, "labelled": 1,
                     "r_bragg": "1.00", **kw})


# ------------------------------------------------------------ the one grammar


@pytest.mark.parametrize("codeword, number, multiplier, provenance", [
    # Every row is a codeword copied out of a real file at the named line.
    (601.0, 60, 1.0, "corpus file 2:77 — the zero shift"),
    (71.00000, 7, 1.0, "corpus file 2:99 — a phase scale"),
    (51.00000, 5, 1.0, "corpus file 2:105 — the tetragonal a = b"),
    (61.00000, 6, 1.0, "corpus file 2:105 — the tetragonal c"),
    (11.00, 1, 1.0, "corpus file 2:160 — an ordered moment"),
    (-11.00, 1, -1.0, "corpus file 1:173 — the *other* sublattice"),
    (611.00, 61, 1.0, "corpus file 2:175 — an asymmetry term"),
    (121.00, 12, 1.0, "corpus file 5:101 — a TOF Dtt2 shift"),
    (651.000, 65, 1.0, "corpus file 3:102 — the stale-count case"),
])
def test_a_codeword_carries_the_parameter_and_the_sign(
        codeword, number, multiplier, provenance):
    """``10 x parameter + multiplier``, signed — two facts in one number.

    The sign is not decoration: ``11.00`` and ``-11.00`` on the two Cr
    sublattices of ``corpus file 1`` are *one* refined moment entered with
    opposite signs, which is the antiferromagnetic constraint. A reader that
    recorded only "this was refined" would return two independent moments and
    lose the physics the file was written to express.
    """
    code = decode_codeword(codeword)
    assert code is not None, provenance
    assert (code.number, code.multiplier) == (number, multiplier)
    assert code.codeword == codeword          # verbatim, so the decode is checkable


def test_a_zero_codeword_is_fixed_not_parameter_zero():
    """``0.00`` is FullProf's spelling of *held*, and it is written for every
    parameter — which is why the tri-state's third state below is narrower than
    a TOPAS ``.inp``'s."""
    assert decode_codeword(0.0) is None


@pytest.mark.parametrize("codeword", [0.5, 1.0, -9.9])
def test_a_codeword_under_ten_is_refused_rather_than_read_as_fixed(codeword):
    """A codeword decoding to parameter 0 is a number no FullProf run writes —
    a truncated ``601.0`` reading as ``6`` is how one arises. Reading it as
    "fixed" would free-or-fix the wrong parameter with nothing raised."""
    with pytest.raises(FullProfPcrError, match="parameter number 0"):
        decode_codeword(codeword)


def test_the_refine_flag_is_a_tri_state(tmp_path):
    """Refined / fixed / *the codeword column is absent* — asserted as three
    states, not as two.

    FullProf writes the codeword slot for every refinable value, so unlike a
    TOPAS ``.inp`` "the file said nothing" is unreachable on an intact line.
    ``None`` therefore means the column is **not there** — a ragged or truncated
    line — and is never a stand-in for ``False``, because a lost tri-state reads
    as "held", which is a confident wrong protocol.
    """
    # corpus file 2:104-105: a and c refined (51/61), the angles held.
    # The codeword line here is cut short after three fields on purpose.
    pcr = _pcr(tmp_path, "tri.pcr",
               _phase(cell_codes="   51.00000   51.00000   61.00000"))
    cell = read_fullprof_pcr(pcr).phases[0].cell
    assert cell["a"].vary is True                 # codeword 51.00000
    assert cell["alpha"].vary is None             # the column is not there
    pcr = _pcr(tmp_path, "tri2.pcr", _phase())
    cell = read_fullprof_pcr(pcr).phases[0].cell
    assert cell["alpha"].vary is False            # codeword 0.00000, i.e. held


def test_a_shared_codeword_is_the_symmetry_tie(tmp_path):
    """``51.00000 51.00000 61.00000`` on a/b/c is how a ``.pcr`` writes
    a = b: one parameter number on two columns.

    Quoted from ``corpus file 2``:105. This is the fact a reader that
    stored only a bool would drop, and it is checkable against rietx's own
    derived tie — ``phases.0.cell.b`` is symmetry-tied to ``a`` for P 4₂/mnm, so
    the file and the package agree without either being told.
    """
    pcr = _pcr(tmp_path, "tie.pcr", _phase())
    cell = read_fullprof_pcr(pcr).phases[0].cell
    assert cell["a"].code.number == cell["b"].code.number == 5
    assert cell["c"].code.number == 6
    assert cell["a"].code.multiplier == 1.0


# -------------------------------------------------------------- normalisation


@pytest.mark.parametrize("written, expected, provenance", [
    ("CR", "Cr", "corpus file 2:88"),
    ("W", "W", "corpus file 2:90"),
    ("O", "O", "corpus file 2:92"),
    ("Co", "Co", "corpus file 4:72 — already IUCr order, left alone"),
    ("AL", "Al", "corpus file 5:191"),
    ("Y", "Y", "corpus file 5:187"),
    # A magnetic form-factor label is a table name, not an element: rietx has
    # no counterpart, so it is returned verbatim rather than mangled into `Mc`.
    ("MCR3", "MCR3", "corpus file 2:159"),
    ("MCO3", "MCO3", "corpus file 4:112"),
    # Charge, in either order, out in IUCr order — the same output convention
    # `projects/topas.py` uses, so the two readers hand back one spelling.
    ("CA+2", "Ca2+", "generalisation; no corpus file writes a charge"),
    ("O-2", "O2-", "generalisation"),
])
def test_species_are_normalised_to_iucr_order(written, expected, provenance):
    assert normalize_species(written) == expected, provenance


@pytest.mark.parametrize("written, expected, provenance", [
    ("P 42/m n m", "P 42/m n m", "corpus file 2:86 — already lower case"),
    ("R -3 c", "R -3 c", "corpus file 2:117"),
    ("P -1", "P -1", "corpus file 2:144"),
    # Upper case, and an origin choice gemmi resolves the *other* way from a
    # bare symbol: `F d -3 m` alone is choice 1, and the corpus's spinel is on
    # choice 2 (Co at 1/8,1/8,1/8 and 1/2,1/2,1/2).
    ("F D -3 M", "F d -3 m:2", "corpus file 4:68"),
    ("I A -3 D", "I a -3 d", "corpus file 5:184 — one origin only"),
])
def test_the_symbol_is_case_normalised_and_the_origin_chosen(
        written, expected, provenance):
    """Only the lattice letter is upper case in a Hermann-Mauguin symbol, so
    lower-casing the tail is lossless; the origin choice is not, and dropping it
    selects the *other* origin with nothing raised.

    The choice is a convention, so it is not trusted:
    :func:`~rietx.io.projects.fullprof.occupancy_factor` re-derives every site
    multiplicity under whichever setting this returns, and a wrong origin makes
    the occupancy column stop reducing — see the occupancy tests below.
    """
    assert normalize_space_group(written) == expected, provenance


@pytest.mark.parametrize("raw, kept, provenance", [
    # A `!` opens a comment *inline* as well as at column 1, which is what makes
    # the refined-parameter count readable at all.
    ("      61    !Number of refined parameters", "61",
     "corpus file 2:74"),
    ("!Nat Dis Ang Pr1 Pr2 Pr3 Jbt Irf Isy Str Furth       ATZ    Nvk Npr More",
     "", "corpus file 2:83 — a header line is a comment"),
    ("P 42/m n m               <--Space group symbol", "P 42/m n m",
     "corpus file 2:86"),
    ("Cr     CR      0.00000  0.00000  0.31111  0.21111   0.50000   0   0   0    1  #color cyan",
     "Cr     CR      0.00000  0.00000  0.31111  0.21111   0.50000   0   0   0    1",
     "corpus file 2:88"),
])
def test_a_comment_is_cut_wherever_it_opens(raw, kept, provenance):
    assert _strip(raw) == kept, provenance


# ---------------------------------------------------------- count invariants


def test_the_declared_counts_are_asserted_against_the_lines_parsed(tmp_path):
    """Nba, Nex, Nph and Nat, all four.

    A ``.pcr`` is positional and offers no keyword to resynchronise on, so a
    dropped line does not raise — it silently reinterprets everything after it.
    A dropped background point moves the interpolated background under every
    peak it spans; a dropped atom is a wrong structure factor.
    """
    pcr = _pcr(tmp_path, "counts.pcr", _phase(), _magnetic_isy1())
    model = read_fullprof_pcr(pcr)
    assert len(model.background) == model.control["nba"] == 2
    assert len(model.excluded_regions) == model.control["nex"] == 1
    assert len(model.phases) == model.control["nph"] == 2
    for phase in model.phases:
        assert len(phase.atoms) == int(phase.control["nat"])


def test_a_declared_phase_count_the_file_cannot_satisfy_is_refused(tmp_path):
    """``Nph`` says three, the file holds one — refused naming the file, not
    read as "one phase and some trailing junk"."""
    pcr = _pcr(tmp_path, "shortnph.pcr", _phase(), nph=3)
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    assert "shortnph.pcr" in str(exc.value)


def test_a_declared_atom_count_the_phase_cannot_satisfy_is_refused(tmp_path):
    """``Nat = 5`` over four site pairs walks straight into the profile block."""
    pcr = _pcr(tmp_path, "shortnat.pcr", _phase(nat=5))
    with pytest.raises(FullProfPcrError, match="shortnat.pcr"):
        read_fullprof_pcr(pcr)


@pytest.mark.parametrize("corrupt, expected", [
    ("0.35555  0.35555  0.36666  0.17777   1.0x000", "'occ'"),
    ("0.35555  0.35555  0.36666  0.1x777   1.00000", "'biso'"),
    ("0.35555  0.3x555  0.36666  0.17777   1.00000", "'y'"),
])
def test_an_unreadable_stated_site_value_is_refused_naming_the_column(
        tmp_path, corrupt, expected):
    """Finding 4: a *stated* site value that cannot be read refuses naming
    **which** column it was, not merely the line.

    A ``.pcr`` is positional, so unlike a TOPAS ``.inp`` the reader can never
    silently default the value — the token is always refused — but naming the
    line alone left a reviewer counting tokens to see whether it was ``x``, the
    occupancy or a trailing flag. The rows corrupt O2's ``occ``, ``biso`` and
    ``y`` in turn; the refusal names each, and the absent case (a short codeword
    column, tri-state ``None``) is the pair tested separately above.
    """
    atoms = _PHASE_SITES.replace(
        "0.35555  0.35555  0.36666  0.17777   1.00000", corrupt, 1)
    pcr = _pcr(tmp_path, "badval.pcr", _phase(atoms=atoms))
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    message = str(exc.value)
    assert "badval.pcr" in message
    assert expected in message
    assert "is not a number for the" in message


def test_the_magnetic_symmetry_counts_are_asserted(tmp_path):
    """``Nsym``, ``|Ireps|`` and ``3 x N_Bas`` — the three counts that make the
    walk *past* an unmodelled block safe.

    This is the one block the reader has to skip without modelling, and it must
    land on the next phase's first line exactly. ``Isy = -1`` gives Nsym x
    (SYMM + MagMat x MSYM); ``Isy = -2`` gives Nsym x (SYMM + |Ireps| x
    (BASR, BASI)) with 3 x N_Bas numbers on each basis line — two shapes from
    two real files, which is what makes it a rule rather than one file's
    coincidence.
    """
    pcr = _pcr(tmp_path, "magsym.pcr", _phase(), _magnetic_isy1(),
               _magnetic_isy2())
    one, two = read_fullprof_pcr(pcr).magnetic_phases
    assert (one.magnetic.isy, one.magnetic.nsym, one.magnetic.magmat) == (-1, 2, 1)
    assert len(one.magnetic.operators) == 2
    assert one.magnetic.operators[0] == ("SYMM X, Y, Z", ("MSYM  u, v, w,0.000",))
    assert (two.magnetic.isy, two.magnetic.nsym, two.magnetic.ireps,
            two.magnetic.n_bas) == (-2, 2, -2, 4)
    assert two.magnetic.real_imaginary == (0, 0, 0, 0)
    assert len(two.magnetic.operators) == 2
    _, basis = two.magnetic.operators[0]
    assert len(basis) == abs(two.magnetic.ireps)     # |Ireps| BASR/BASI pairs
    for real, imaginary in basis:
        assert len(real) == len(imaginary) == 3 * two.magnetic.n_bas


def test_a_basis_line_shorter_than_three_times_n_bas_is_refused(tmp_path):
    """``N_Bas`` declares four basis vectors and the line states three
    components — the declared count and the written vectors disagree, and
    reading the short line would shift every line after it."""
    short = _ISY_MINUS_2_SYMMETRY.replace(
        "BASR     2     0     0     0     2     0     0    -2     0    -2     0     0",
        "BASR     2     0     0", 1)
    pcr = _pcr(tmp_path, "shortbasr.pcr", _phase(),
               _magnetic_isy2(symmetry=short))
    with pytest.raises(FullProfPcrError, match="3 x N_Bas"):
        read_fullprof_pcr(pcr)


def test_a_basis_line_whose_keyword_is_wrong_is_refused(tmp_path):
    """The ``BASR``/``BASI`` label is the only thing that says which of the real
    and the imaginary part this line is, so it is checked rather than skipped —
    a file with the pair the other way round would otherwise arrive silently
    transposed."""
    swapped = _ISY_MINUS_2_SYMMETRY.replace("BASR     2", "BASX     2", 1)
    pcr = _pcr(tmp_path, "badkw.pcr", _phase(), _magnetic_isy2(symmetry=swapped))
    with pytest.raises(FullProfPcrError, match="expected a BASR line"):
        read_fullprof_pcr(pcr)


# ------------------------------------------------------------------ the traps


def test_the_phase_number_comment_is_not_the_phase_index(tmp_path):
    """Trap 1: ``corpus file 1``'s **third** phase block is labelled
    ``!  Data for PHASE number:   1``.

    So phases are parsed positionally against ``Nph`` and the comment's index is
    kept beside them for provenance only. Keying on it would put a magnetic
    phase's profile parameters onto the nuclear phase of the same number.
    """
    pcr = _pcr(tmp_path, "mislabelled.pcr", _phase(labelled=1),
               _phase(name="Corundum-type", labelled=2), _magnetic_isy2(labelled=1))
    model = read_fullprof_pcr(pcr)
    assert [p.index for p in model.phases] == [1, 2, 3]
    assert [p.labelled_index for p in model.phases] == [1, 2, 1]   # the file lies
    assert model.phases[2].is_magnetic          # and position, not the comment,
    assert not model.phases[0].is_magnetic      # is what got it right


def test_the_ang_mom_column_does_not_move_with_its_name(tmp_path):
    """Trap 2: the third column of a phase's control line is headed ``Ang`` at
    ``Jbt = 0`` and ``Mom`` at ``Jbt = 1``, in the same position.

    A parser keyed on the header text breaks on exactly the phase that matters,
    so nothing here reads a header: the names are this module's own tuple zipped
    positionally. Asserted by giving the *magnetic* phase a non-zero value in
    that column — which is a soft-moment-constraint count, not an angle
    restraint, and must not be refused as one.
    """
    pcr = _pcr(tmp_path, "angmom.pcr", _phase(third_value=0),
               _magnetic_isy1(third_value=1))
    nuclear, magnetic = read_fullprof_pcr(pcr).phases
    assert nuclear.control["ang_or_mom"] == 0.0
    assert magnetic.control["ang_or_mom"] == 1.0
    # The header words in the fixture really do differ, so this is not vacuous.
    written = pcr.read_text(encoding="utf-8")
    assert "!Nat Dis Ang" in written and "!Nat Dis Mom" in written


def test_a_nuclear_phases_angle_restraints_are_refused(tmp_path):
    """The other side of trap 2: the *same* column at ``Jbt = 0`` opens an
    angle-restraint block, whose position no file here establishes."""
    pcr = _pcr(tmp_path, "angles.pcr", _phase(third_value=2))
    with pytest.raises(FullProfPcrError, match="Ang = 2"):
        read_fullprof_pcr(pcr)


def test_the_stale_lambda_slot_is_not_the_wavelength(tmp_path):
    """Trap 3: ``corpus file 2`` carries ``2.370100`` in the refinable-λ
    slot while the refinement's λ is the ``2.077100`` of the Lambda1 line.

    Its codeword is ``0.00``, so FullProf never used it — but a reader that took
    λ from the slot because it is the one *labelled* ``Lambda`` would refine
    every cell 14 % out and report a plausible Rwp.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "lambda.pcr", _phase()))
    assert model.lambda1 == pytest.approx(2.077100)
    assert model.lambda2 == pytest.approx(2.077100)
    assert model.lambda_slot.value == pytest.approx(2.370100)
    assert model.lambda_slot.vary is False       # inert, and said to be


def test_the_declared_refined_parameter_count_is_reported_not_trusted(tmp_path):
    """Trap 4: ``corpus file 3`` declares 64 refined parameters and
    carries a codeword for parameter 65.

    Both numbers are reported and neither is corrected into the other, because
    which of the two is wrong is not something the file says. The fixture
    reproduces the disagreement with the real file's own ``651.000`` codeword.
    """
    stale = _phase(cell_codes="  601.00000  601.00000  651.00000    0.00000    0.00000    0.00000")
    model = read_fullprof_pcr(_pcr(tmp_path, "stale.pcr", stale))
    assert model.refined_parameter_count == 61          # what the file declares
    assert max(model.parameter_numbers) == 65           # what it references
    assert {60, 65}.issubset(model.parameter_numbers)


# ------------------------------------ report or refuse, never drop (magnetic)


def test_a_magnetic_phase_is_read_in_full_not_dropped(tmp_path):
    """Four of the six real files have one, so dropping it silently is the
    single most damaging thing this reader could do.

    Both sub-grammars are read: the ``Isy = -1`` moment components and the
    ``Isy = -2`` basis-vector coefficients, under the same positional names
    because they are the same columns.
    """
    pcr = _pcr(tmp_path, "mag.pcr", _phase(), _magnetic_isy1(), _magnetic_isy2())
    model = read_fullprof_pcr(pcr)
    assert [p.name for p in model.nuclear_phases] == ["Trirutile"]
    assert [p.name for p in model.magnetic_phases] == ["Trirutile", "Magnetic Phase"]
    (moment,) = model.magnetic_phases[0].atoms
    assert moment.species_raw == "MCR3"
    assert moment.values["m2"].value == pytest.approx(3.000)      # Ry
    assert moment.values["m2"].vary is True                       # codeword 11.00
    assert moment.values["m1"].vary is False                      # codeword 0.00
    assert moment.values["magph"].value == pytest.approx(0.0)


def test_two_sublattices_share_one_parameter_with_opposite_signs(tmp_path):
    """``11.00`` and ``-11.00`` on the two Cr sites of
    ``corpus file 1``:169/:173.

    This is the whole argument for decoding the codeword rather than reducing it
    to a bool: the file states *one* refined moment applied with opposite sign to
    the two sublattices, and "both were refined" is a different — and wrong —
    model with two free parameters.
    """
    pcr = _pcr(tmp_path, "afm.pcr", _phase(), _magnetic_isy2())
    up, down = read_fullprof_pcr(pcr).magnetic_phases[0].atoms
    assert (up.label, down.label) == ("1CR", "2CR")
    assert up.values["m2"].code.number == down.values["m2"].code.number == 1
    assert up.values["m2"].code.multiplier == 1.0
    assert down.values["m2"].code.multiplier == -1.0
    assert up.values["m2"].value == pytest.approx(0.800)
    assert down.values["m2"].value == pytest.approx(-0.800)


def test_to_structure_refuses_a_magnetic_phase_naming_it(tmp_path):
    """rietx has no magnetic scattering model, so returning the nuclear phases
    alone would hand back a structure that looks complete while the file's
    magnetic contribution went unmentioned — the TOPAS reader's
    ``mag_space_group`` case, one format over.

    The refusal is at *build* time, not at read: refusing to read would throw
    away the nuclear phases, the wavelength and the agreement factors this
    reader got right, and make four of six real files unreadable.
    """
    pcr = _pcr(tmp_path, "refuse.pcr", _phase(), _magnetic_isy1())
    model = read_fullprof_pcr(pcr)
    with pytest.raises(FullProfPcrError) as exc:
        to_structure(model)
    message = str(exc.value)
    assert "refuse.pcr" in message
    assert "1 of 2 phases are magnetic" in message
    assert "Trirutile" in message and "Isy -1" in message
    assert "nuclear_only=True" in message       # the refusal names the way out


def test_nuclear_only_makes_the_omission_the_callers(tmp_path):
    """The third state of the "report or refuse, never drop" rule: a drop the
    *caller* declared. The magnetic phase is still on the model, so the omission
    stays inspectable rather than becoming invisible."""
    pcr = _pcr(tmp_path, "nuclearonly.pcr", _phase(), _magnetic_isy1())
    model = read_fullprof_pcr(pcr)
    structure = to_structure(model, nuclear_only=True)
    assert [p.name for p in structure.phases] == ["Trirutile"]
    assert len(model.magnetic_phases) == 1      # not lost, just not built


def test_a_file_of_nothing_but_magnetic_phases_refuses_either_way(tmp_path):
    """``nuclear_only=True`` on a file with no nuclear phase must not return an
    empty structure or a pydantic error — a reader raises naming the file."""
    pcr = _pcr(tmp_path, "allmag.pcr", _magnetic_isy1())
    model = read_fullprof_pcr(pcr)
    with pytest.raises(FullProfPcrError, match="no nuclear phase to build"):
        to_structure(model, nuclear_only=True)


@pytest.mark.parametrize("magnetic, block, expected, declared", [
    # corpus file 6:176-177 — keyed by `CR`, and that
    # file's magnetic phase (Isy -1) has exactly one atom, labelled `CR`. The
    # moment and its width stand in for the file's, at the file's own spelling.
    (_magnetic_isy1, "! Soft moment constraints:\nCR   1.000 0.01000\n",
     [("CR", 1.000, 0.01)], 1),
    # corpus file 1:189-191 — keyed by `1C`/`2C`, and that file's magnetic
    # phase (Isy -2) has two atoms, labelled `1CR` and `2CR`. One production,
    # not two: both keys are the label truncated to the field's width.
    (_magnetic_isy2, "! Soft moment constraints\n1C  1.00 0.01\n2C  1.00 0.01\n",
     [("1C", 1.00, 0.01), ("2C", 1.00, 0.01)], 1),
])
def test_soft_moment_constraints_read_in_both_spellings(
        tmp_path, magnetic, block, expected, declared):
    """Both real spellings, and the key resolved to a site by **prefix**.

    Reading the second as a *site index* also fits those two lines and would
    then read ``CR`` as a label — two productions where one explains both. The
    prefix reading is recorded, the raw key kept beside it, and the declared
    ``Mom`` is reported rather than enforced: ``corpus file 1`` declares
    ``Mom = 1`` and writes **two** constraints, and which of the two numbers is
    wrong is not something the file says.
    """
    pcr = _pcr(tmp_path, "soft.pcr", _phase(),
               magnetic(third_value=declared), trailing=block + _RANGE)
    phase = read_fullprof_pcr(pcr).phases[-1]
    got = [(c.key, c.moment, c.sigma) for c in phase.soft_moment_constraints]
    assert got == pytest.approx(expected)
    labels = [phase.atoms[c.atom_index].label if c.atom_index is not None else None
              for c in phase.soft_moment_constraints]
    assert all(label is not None for label in labels)
    assert all(label.startswith(c.key)
               for label, c in zip(labels, phase.soft_moment_constraints))
    # Reported, not corrected: the declaration and the count are both readable.
    assert int(phase.control["ang_or_mom"]) == declared
    assert len(phase.soft_moment_constraints) == len(expected)


def test_the_propagation_vectors_are_read(tmp_path):
    """``Nvk`` k-vectors, each a value line and a codeword line, after the
    phase's Pref/Asy block.

    Quoted from ``corpus file 4``:129-131, which is the **only** file that
    evidences the position — and whose phase happens to be the last, so the
    position rests on one observation and the reader's docstring says so. Note
    the trailing words: FullProf writes ``Propagation Vector  1`` after the
    numbers with no comment marker, so the line is read as a leading numeric run.
    """
    block = ("! Propagation vectors: \n"
             "   0.5000000   0.0000000   0.5000000          Propagation Vector  1\n"
             "    0.000000    0.000000    0.000000")
    pcr = _pcr(tmp_path, "kvec.pcr", _phase(),
               _magnetic_isy1(nvk=1) + "\n" + block)
    (k, codes), = read_fullprof_pcr(pcr).phases[-1].propagation_vectors
    assert k == pytest.approx((0.5, 0.0, 0.5))
    assert [c.vary for c in codes] == [False, False, False]


# --------------------------------------------------------- refused, by name


def test_a_tof_job_is_refused_naming_the_job_and_why(tmp_path):
    """``Job = -1``: the abscissa is microseconds and the whole profile block is
    Sig-2/Sig-1/Sig-0 and alpha0/beta0/alpha1 in place of Caglioti U/V/W.

    rietx models constant-wavelength diffraction only, so this is refused where
    it is declared rather than read into a model whose numbers mean something
    else. (``corpus file 5`` is the real one; it is additionally
    NPATT 6 and is refused a line earlier.)
    """
    pcr = _pcr(tmp_path, "tof.pcr", _phase(), job=-1)
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    assert "tof.pcr" in str(exc.value)
    assert "Job = -1" in str(exc.value)
    assert "time-of-flight" in str(exc.value)


def test_a_multi_pattern_file_is_refused_naming_the_pattern_count(tmp_path):
    """``corpus file 5``:3 — ``NPATT 6``, six GEM detector banks.

    A different layout throughout: per-pattern control lines (which shed ``Nph``,
    it moving to a line of its own — the ``!Job Npr Nba Nex`` header variant),
    per-pattern backgrounds, excluded regions and profile blocks, one shared set
    of atoms. Six patterns is a *joint* refinement over six banks, and which
    bank's resolution function a single ``Instrument`` should carry is a question
    the file does not answer. Refused before any of it is parsed.
    """
    path = tmp_path / "npatt.pcr"
    path.write_text(
        "COMM  a six-bank joint refinement\n"
        "! Current global Chi2 (Bragg contrib.) =      11.28\n"
        "NPATT      6       1 1 1 1 1 1 <- Flags for patterns (1:refined, 0: excluded)\n"
        "W_PAT   0.167 0.167 0.167 0.167 0.167 0.167\n"
        "!Nph Dum Ias Nre Cry Opt Aut\n   1   1   1   0   0   0   1\n"
        "!Job Npr Nba Nex Nsc Nor Iwg Ilo Res Ste Uni Cor Anm\n"
        "  -1  13   0   2   0   1   0   0   5   0   1   0   0\n", encoding="utf-8")
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(path)
    assert "npatt.pcr" in str(exc.value)
    assert "NPATT 6" in str(exc.value)
    assert "6 patterns" in str(exc.value)


@pytest.mark.parametrize("nba, why", [
    # corpus file 5 has Nba 0 and writes six polynomial coefficients
    # per pattern — but only in the multi-pattern layout, so where the
    # coefficient line sits in a *single*-pattern file is unevidenced.
    (0, "a polynomial background"),
    (1, "one interpolated point"),
    (-3, "a background model with no description here"),
])
def test_a_background_this_reader_cannot_place_is_refused(tmp_path, nba, why):
    pcr = _pcr(tmp_path, "bkg.pcr", _phase())
    text = pcr.read_text(encoding="utf-8").replace("   1   7   1   2   1",
                                   f"   1   7   1   {nba}   1")
    pcr.write_text(text, encoding="utf-8")
    with pytest.raises(FullProfPcrError, match=f"Nba = {nba}"):
        read_fullprof_pcr(pcr), why


@pytest.mark.parametrize("field, position", [
    # The control line's 19 fields, by position:
    # Job Npr Nph Nba Nex Nsc Nor Dum Iwg Ilo Ias Res Ste Nre Cry Uni Cor Opt Aut
    ("Nsc", 5), ("Nor", 6), ("Dum", 7), ("Res", 11), ("Ste", 12), ("Nre", 13),
    ("Cry", 14), ("Uni", 15), ("Cor", 16), ("Opt", 17),
])
def test_a_layout_changing_control_flag_is_refused_by_name(
        tmp_path, field, position):
    """Every control-line flag whose non-zero meaning adds lines this reader has
    no file to place — or, for ``Uni``, changes what the abscissa *is*.

    Ignoring such a flag is not the safe option: a flag that adds a line
    desynchronises the whole positional walk, and ``Uni`` non-zero would read a
    non-2θ abscissa as 2θ, which `io/CLAUDE.md`'s "the axis is never trusted"
    forbids outright. ``Iwg``, ``Ilo``, ``Ias``, ``Npr`` and ``Aut`` are
    deliberately *not* in this list — they change weighting, the profile function
    or FullProf's own parameter numbering, and move no line.
    ``corpus file 4`` has ``Aut 1`` and must still read.
    """
    pcr = _pcr(tmp_path, "flag.pcr", _phase())
    lines = pcr.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.startswith("   1   7   1   2   1"):
            fields = line.split()
            fields[position] = "3"
            lines[i] = "   " + "   ".join(fields)
            break
    pcr.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    assert f"{field} = 3" in str(exc.value)
    assert "flag.pcr" in str(exc.value)


def test_a_control_line_of_the_wrong_width_is_refused(tmp_path):
    """An eighteen-field (pre-``Aut``) control line would shift every field
    after whichever one is missing, and nothing in the corpus says which."""
    pcr = _pcr(tmp_path, "narrow.pcr", _phase())
    text = pcr.read_text(encoding="utf-8").replace(
        "   1   7   1   2   1   0   0   0   0   0   0   0   0   0   0   0   0   0   0",
        "   1   7   1   2   1   0   0   0   0   0   0   0   0   0   0   0   0   0")
    pcr.write_text(text, encoding="utf-8")
    with pytest.raises(FullProfPcrError, match="expected 19 fields"):
        read_fullprof_pcr(pcr)


@pytest.mark.parametrize("jbt", [2, 10, -3])
def test_an_unknown_jbt_is_refused_naming_it(tmp_path, jbt):
    """Only ``Jbt`` 0 (nuclear) and ±1 (magnetic) are read. The others select
    Le Bail intensity extraction, a combined nuclear+magnetic phase or a
    form-factor phase, each of which changes the *atom block's* own layout.
    ``Jbt = -1`` left this list with WP-1328: the manual states its atom block
    is Jbt = 1's with the moment as (M, phi, theta), same positions
    (``test_projects_fullprof_magnetic``)."""
    pcr = _pcr(tmp_path, "jbt.pcr", _phase(jbt=jbt))
    with pytest.raises(FullProfPcrError, match=f"Jbt = {jbt}"):
        read_fullprof_pcr(pcr)


def test_a_nuclear_phase_with_explicit_symmetry_is_refused(tmp_path):
    """``Isy != 0`` at ``Jbt = 0`` supplies the operators instead of deriving
    them from the symbol — a block no file here states the shape of."""
    pcr = _pcr(tmp_path, "isy.pcr", _phase(isy=1))
    with pytest.raises(FullProfPcrError, match="Isy = 1"):
        read_fullprof_pcr(pcr)


def test_a_magnetic_phase_with_an_unknown_isy_is_refused(tmp_path):
    """``Isy`` selects the whole magnetic sub-grammar, so an unrecognised value
    means the reader does not know how many lines the block occupies."""
    pcr = _pcr(tmp_path, "isy3.pcr", _phase(),
               _magnetic_isy1(isy=-3))
    with pytest.raises(FullProfPcrError, match="Isy = -3"):
        read_fullprof_pcr(pcr)


def test_a_positive_ireps_is_refused(tmp_path):
    """A positive ``Ireps`` names an irreducible representation from FullProf's
    own tables, which this reader has no copy of and — per ATTRIBUTION.md's
    fence, FullProf being closed — may not reproduce."""
    tabulated = _ISY_MINUS_2_SYMMETRY.replace("    -2     4", "     2     4", 1)
    pcr = _pcr(tmp_path, "ireps.pcr", _phase(),
               _magnetic_isy2(symmetry=tabulated))
    with pytest.raises(FullProfPcrError, match="Ireps = 2"):
        read_fullprof_pcr(pcr)


@pytest.mark.parametrize("field, value", [
    ("Dis", 2), ("Str", 1), ("Furth", 3), ("More", 1),
])
def test_a_phase_flag_that_adds_unevidenced_lines_is_refused(
        tmp_path, field, value):
    """Distance restraints, a strain-model block, further parameters, additional
    per-phase lines. Every one is zero in every corpus file, so where its block
    sits is a guess — and a wrong guess desynchronises the rest of the file."""
    pcr = _pcr(tmp_path, "phaseflag.pcr",
               _phase(**{{"Dis": "dis", "Str": "strn", "Furth": "furth",
                          "More": "more"}[field]: value}))
    with pytest.raises(FullProfPcrError, match=f"{field} = {value}"):
        read_fullprof_pcr(pcr)


def test_a_phase_reading_its_reflections_from_a_file_is_refused(tmp_path):
    """``Irf`` 1 or 2 reads the hkl list from a companion file, so the model this
    reader would return is not the model that was refined. ``Irf`` 0 and -1 are
    both in the corpus and both read."""
    pcr = _pcr(tmp_path, "irf.pcr", _phase(irf=2))
    with pytest.raises(FullProfPcrError, match="Irf = 2"):
        read_fullprof_pcr(pcr)


def test_an_unknown_n_t_is_refused_naming_the_atom(tmp_path):
    """``N_t`` decides how many lines a site occupies — 0 adds none, 2 adds an
    anisotropic β line and its codewords (``corpus file 5``:187-190).
    Anything else and the reader does not know where the next atom starts."""
    odd = _PHASE_SITES.replace("   0   0   0    1  #color cyan",
                                "   0   0   5    1  #color cyan", 1)
    pcr = _pcr(tmp_path, "nt.pcr", _phase(atoms=odd))
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(pcr)
    assert "N_t = 5" in str(exc.value) and "'Cr'" in str(exc.value)


def test_a_missing_file_raises_naming_it(tmp_path):
    with pytest.raises(FullProfPcrError, match="absent.pcr"):
        read_fullprof_pcr(tmp_path / "absent.pcr")


def test_a_file_that_does_not_open_with_comm_is_refused(tmp_path):
    """A ``.pcr`` opens with ``COMM``. Anything else is either not a FullProf
    control file or has had its header edited away, and reading on would
    interpret whatever line happened to be first as the control line."""
    path = tmp_path / "notpcr.pcr"
    path.write_text("data_something\n_cell_length_a 4.58\n", encoding="utf-8")
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(path)
    assert "notpcr.pcr" in str(exc.value) and "COMM" in str(exc.value)


@pytest.mark.parametrize("codec", ["utf-8", "utf-8-sig", "utf-16"])
def test_a_byte_order_mark_is_decoded_not_read_as_utf8(tmp_path, codec):
    """`io.formats.base.decode` is the seam `head()` already answers this with,
    shared rather than duplicated — the same choice ``projects/topas.py`` made.
    A UTF-16 export read as UTF-8 gives a first line that is not ``COMM`` and
    would be diagnosed as "not a FullProf file", a confident wrong diagnosis of
    a *decode* failure."""
    source = _pcr(tmp_path, "src.pcr", _phase()).read_text(encoding="utf-8")
    path = tmp_path / f"enc-{codec}.pcr"
    path.write_bytes(source.encode(codec))
    model = read_fullprof_pcr(path)
    assert model.title == "60 K"
    assert model.chi2 == pytest.approx(5.144)
    assert model.phases[0].cell["a"].value == pytest.approx(5.000000)


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_a_utf16_file_with_no_mark_is_refused_naming_the_file(tmp_path, codec):
    """`io/CLAUDE.md`'s `xy` row: ASCII-range UTF-16LE is valid UTF-8 with
    interleaved NULs and no byte-order mark says which of LE and BE it is, so
    guessing is a repair a reader cannot say it made."""
    source = _pcr(tmp_path, "src2.pcr", _phase()).read_text(encoding="utf-8")
    path = tmp_path / f"{codec}.pcr"
    path.write_bytes(source.encode(codec))
    with pytest.raises(FullProfPcrError) as exc:
        read_fullprof_pcr(path)
    assert f"{codec}.pcr" in str(exc.value)


def test_a_trailing_line_that_is_neither_production_is_refused(tmp_path):
    """After the last phase come soft moment constraints and the fitted 2θ
    range, told apart by whether the line opens with a number. Something that is
    neither is refused rather than absorbed into whichever it resembles."""
    pcr = _pcr(tmp_path, "junk.pcr", _phase(),
               trailing="SOMETHING ELSE\n" + _RANGE)
    with pytest.raises(FullProfPcrError, match="junk.pcr"):
        read_fullprof_pcr(pcr)


# ------------------------------------------------- to_structure


def test_to_structure_builds_and_carries_the_refine_flags(tmp_path):
    """``Biso`` is FullProf's B and rietx's ``biso`` is also B — no 8π².

    The refine flags are the payload: a control file says which parameters were
    free and which were held, and that is the part a person cannot reconstruct
    from a CIF plus a pattern. Here the cell's a and c were refined (codewords
    51/61) and every coordinate and displacement parameter held (0.00) — which
    is what the ``corpus file 2`` refinement actually did.
    """
    pcr = _pcr(tmp_path, "build.pcr", _phase())
    (phase,) = to_structure(read_fullprof_pcr(pcr)).phases
    assert phase.name == "Trirutile"
    assert phase.space_group == "P 42/m n m"
    assert phase.cell.a.value == pytest.approx(5.000000)
    assert phase.cell.c.value == pytest.approx(9.000000)
    assert phase.cell.a.vary is True and phase.cell.c.vary is True
    assert phase.cell.alpha.vary is False
    assert [a.label for a in phase.atoms] == ["Cr", "W", "O1", "O2"]
    assert [a.species for a in phase.atoms] == ["Cr", "W", "O", "O"]
    assert phase.atoms[3].z.value == pytest.approx(0.36666)
    assert phase.atoms[0].biso.value == pytest.approx(0.21111)
    assert phase.atoms[0].biso.vary is False
    assert phase.scale.value == pytest.approx(5.0000)
    assert phase.scale.vary is True                    # codeword 71.00000


def test_to_structure_reports_a_species_rewrite_through_diagnostics(
        tmp_path):
    """The one repair that reaches the ``Structure`` is the species spelling.

    ``read_fullprof_pcr`` reports it *structurally* — ``species_raw`` (``CR``)
    sits beside ``species`` (``Cr``) on the atom — but the ``Structure`` carries
    only the one spelling, so the raw token is dropped at the build. io/CLAUDE.md
    (a reader repairs only where it can say it did) is honoured by the same
    channel ``structure_from_cif`` uses: pass ``diagnostics=`` a list and the
    rewrite is recorded, one ``FULLPROF_SPECIES_NORMALISED`` per distinct token,
    with the affected atom path — and a clean spelling records nothing, which is
    why W/O₁/O₂ leave no diagnostic though they too pass through the normaliser.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "diag.pcr", _phase()))
    diagnostics = []
    structure = to_structure(model, diagnostics=diagnostics)
    assert [d.code for d in diagnostics] == ["FULLPROF_SPECIES_NORMALISED"]
    (recorded,) = diagnostics
    assert recorded.level == "info"
    assert recorded.where == ["phases.0.atoms.0.species"]
    assert "'CR'" in recorded.message and "'Cr'" in recorded.message
    assert structure.phases[0].atoms[0].species == "Cr"
    # No list is the same build, and it is silent — the repair is opt-in to see,
    # never suppressed for correctness.
    assert to_structure(model).phases[0].atoms[0].species == "Cr"


def test_a_refined_coordinate_reaches_the_structure_as_refined(tmp_path):
    """``corpus file 3``:88-95 refines Cr's z, O1's x/y and O2's x/y/z
    (codewords 551, 561, 571, 581) and holds W's — which is what makes this a
    tri-state test rather than a value test."""
    refined = (
        "Cr     CR      0.00000  0.00000  0.33449  0.08537   0.50000   0   0   0    1\n"
        "                  0.00     0.00   551.00   591.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.22222   0.25000   0   0   0    1\n"
        "                  0.00     0.00     0.00     0.00      0.00\n"
        "O1     O       0.29771  0.29771  0.00000  0.24444   0.50000   0   0   0    1\n"
        "                561.00   561.00     0.00     0.00      0.00\n"
        "O2     O       0.30498  0.30498  0.33853  0.23070   1.00000   0   0   0    1\n"
        "                571.00   571.00   581.00   621.00      0.00")
    pcr = _pcr(tmp_path, "flags.pcr", _phase(atoms=refined))
    cr, w, o1, o2 = to_structure(read_fullprof_pcr(pcr)).phases[0].atoms
    assert (cr.z.vary, cr.biso.vary) == (True, True)
    assert (w.z.vary, w.biso.vary) == (False, False)
    assert (o1.x.vary, o1.y.vary, o1.z.vary) == (True, True, False)
    assert (o2.x.vary, o2.z.vary, o2.biso.vary) == (True, True, True)


def test_the_built_structure_compiles_a_parameter_table(tmp_path):
    """Not just "pydantic accepted it": the structure has to reach a
    :class:`~rietx.params.vector.ParameterTable`, which is where every
    crystallography refusal lives (species, cell ties, site-symmetry DOFs).

    This is the "compile every structure returned" half of the TOPAS reader's
    review, and it is what checks that the ``.pcr``'s own codeword tie and
    rietx's *derived* symmetry tie agree: ``a`` and ``c`` come back free and
    ``b`` does not, because ``b`` is tied to ``a`` for P 4₂/mnm — the file said
    the same thing with ``51.00000`` twice, and neither was told the other.
    """
    import rietx as rx
    from rietx.params.vector import ParameterTable

    model = read_fullprof_pcr(_pcr(tmp_path, "table.pcr", _phase()))
    structure = to_structure(model)
    table = ParameterTable(
        structure, rx.Instrument.constant_wavelength_neutron(model.lambda1))
    free = {p for p in table.free_paths if p.startswith("phases")}
    assert free == {"phases.0.cell.a", "phases.0.cell.c", "phases.0.scale"}


def test_the_occupancy_column_reduces_to_a_common_factor(tmp_path):
    """FullProf's ``Occ`` is multiplicity-scaled and its absolute normalisation
    is degenerate with the phase scale, so what is recoverable is the *ratio*
    between sites.

    Measured on the real files: ``Occ x M_general / M_site`` is **2.0** for every
    site of two corpus files' phases and **1.0** for two others. Two factors,
    same convention — which is the evidence that the factor is arbitrary and
    that constancy is the only thing a reader may conclude from it.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "occ.pcr", _phase()))
    assert occupancy_factor(model.phases[0]) == pytest.approx(2.0, rel=1e-4)
    # Fully occupied, so every rietx occ is 1.0 — the arbitrary factor cancels
    # and none of it leaks into the structure factor.
    atoms = to_structure(model).phases[0].atoms
    assert [a.occ.value for a in atoms] == pytest.approx([1.0] * 4)


def test_an_occupancy_that_does_not_reduce_is_refused_naming_the_ratios(tmp_path):
    """A partially occupied site's chemical occupancy is **not in the file** —
    it is inseparable from the arbitrary common factor — so it is refused.

    Handing FullProf's ``Occ`` straight into rietx's ``occ`` would be a silently
    wrong structure factor, which is the failure class this module exists to
    avoid. The same check is what verifies the origin choice
    :func:`normalize_space_group` picks: a wrong origin gives wrong
    multiplicities, the ratios stop agreeing, and the phase is refused rather
    than returned.
    """
    partial = _PHASE_SITES.replace("0.31111  0.21111   0.50000",
                                    "0.31111  0.21111   0.35000", 1)
    model = read_fullprof_pcr(_pcr(tmp_path, "partial.pcr",
                                   _phase(atoms=partial)))
    with pytest.raises(FullProfPcrError) as exc:
        to_structure(model)
    message = str(exc.value)
    assert "partial.pcr" in message
    assert "does not reduce" in message
    assert "Cr=1.4000" in message and "W=2.0000" in message


def test_a_phase_with_no_sites_is_refused_rather_than_dropped(tmp_path):
    """``Nat = 0`` is legal in a ``.pcr`` — a phase whose reflections come from a
    companion file, or one being set up — and it has no structure factor.

    Refused rather than skipped, because ``model.phases`` would go on carrying
    its R_Bragg: the TOPAS reader's "report or refuse, never drop" case, where
    the QPA numbers looked complete with a phase missing from the ``Structure``.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "empty.pcr",
                                   _phase(nat=0, atoms="")))
    assert model.phases[0].atoms == []
    with pytest.raises(FullProfPcrError, match="Nat = 0"):
        to_structure(model)


def test_a_negative_biso_is_read_with_its_bound_widened(tmp_path):
    """``corpus file 4``:70 refined O1 to Biso = −0.67266 Å², a real FullProf
    outcome — the column absorbs absorption and normalisation error.

    FullProf stores it and so does every other code, so the reader keeps the
    file's number, widens the floor to hold it and says so (PR #663). Moving
    it to zero would change every high-Q intensity.
    """
    negative = _PHASE_SITES.replace("0.31111  0.21111", "0.31111 -0.55555", 1)
    model = read_fullprof_pcr(_pcr(tmp_path, "negb.pcr",
                                   _phase(atoms=negative)))
    diagnostics = []
    biso = to_structure(model, diagnostics=diagnostics).phases[0].atoms[0].biso
    assert (biso.value, biso.min) == (pytest.approx(-0.55555), pytest.approx(-0.55555))
    widened = [d for d in diagnostics if d.code == "BISO_BOUND_WIDENED"]
    assert [d.where for d in widened] == [["phases.0.atoms.0.biso"]]
    assert "negb.pcr" in widened[0].message


def test_an_anisotropic_beta_block_is_read_and_refused(tmp_path):
    """``N_t = 2`` adds a β line and its codewords
    (``corpus file 5``:187-190), which is read — so the line accounting
    stays exact — and refused at build.

    Converting FullProf's β_ij to rietx's U^ij needs a convention no file here
    settles: whether the stored off-diagonal already carries the exponent's
    factor of 2. A wrong factor is a silently wrong Debye-Waller factor at high
    Q, so the numbers are reported and the phase is not built.
    """
    aniso = (
        "Y    Y       0.12500  0.00000  0.25000  0.00000   0.25000   0   0   2    0\n"
        "                0.00     0.00     0.00     0.00      0.00\n"
        "    0.00024  0.00048  0.00048  0.00000  0.00000   0.00016\n"
        "     411.00   421.00   421.00     0.00     0.00    431.00")
    model = read_fullprof_pcr(_pcr(tmp_path, "aniso.pcr",
                                   _phase(nat=1, sg="I A -3 D", atoms=aniso)))
    atom = model.phases[0].atoms[0]
    assert atom.n_t == 2
    assert atom.betas["beta11"].value == pytest.approx(0.00024)
    assert atom.betas["beta23"].vary is True             # codeword 431.00
    assert atom.betas["beta12"].vary is False
    with pytest.raises(FullProfPcrError) as exc:
        to_structure(model)
    assert "aniso.pcr" in str(exc.value) and "beta" in str(exc.value)


def test_the_converged_agreement_factors_are_recovered(tmp_path):
    """The reason the format is worth reading: it carries a *validated* answer.

    FullProf rewrites the χ² and per-phase R_Bragg comments on every cycle, so
    they are the converged numbers and not a seed. The values are
    ``corpus file 2``'s own: χ² 5.144, R_Bragg 1.79 / 41.28 / 9.46 — and
    the 41.28 is worth keeping visible, because a reader that reported only χ²
    would make that phase look fitted.
    """
    pcr = _pcr(tmp_path, "fom.pcr", _phase(labelled=1, r_bragg="1.79"),
               _phase(name="Corundum-type", nat=2, labelled=2, r_bragg="41.28",
                      sg="R -3 c",
                      atoms="Cr     CR      0.00000  0.00000  0.29899  0.21111   0.66667   0   0   0    1\n"
                            "                  0.00     0.00     0.00     0.00      0.00\n"
                            "O1     O       0.27011  0.00000  0.25000  0.25592   1.00000   0   0   0    1\n"
                            "                  0.00     0.00     0.00     0.00      0.00",
                      cell="   4.954182   4.954182  13.421314  90.000000  90.000000 120.000000",
                      cell_codes="    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000",
                      scale=" 0.13355E-01", scale_code="  0.00000"),
               _magnetic_isy1(labelled=3, r_bragg="9.46"))
    model = read_fullprof_pcr(pcr)
    assert model.chi2 == pytest.approx(5.144)
    assert [p.r_bragg for p in model.phases] == pytest.approx([1.79, 41.28, 9.46])
    # `0.13355E-01` — Fortran exponent notation, on a real scale line.
    assert model.phases[1].profile["scale"].value == pytest.approx(0.013355)
    assert model.phases[1].cell["gamma"].value == pytest.approx(120.0)


def test_the_data_file_reference_is_reported_not_chased(tmp_path):
    """A header comment names a data file that is not the one beside it on
    disk, and in a second corpus file the ``PCR-file:`` name is another
    refinement's.

    So the reference is recorded and never resolved: a reader that went looking
    would either fail on a file that is not missing or find the wrong one, and
    inventing a filename is not a repair it could say it made.
    """
    pcr = _pcr(tmp_path, "ref.pcr", _phase())
    model = read_fullprof_pcr(pcr)
    assert model.data_file == "sample.dat"
    assert model.pcr_name == "another"
    assert not (tmp_path / "sample.dat").exists()   # and nothing went looking


def test_the_excluded_regions_and_fitted_range_are_read(tmp_path):
    """Protocol, not data: root CLAUDE.md's rule is that excluded regions live in
    the document because they are in neither the pattern file nor the model
    state. A ``.pcr`` is where a FullProf refinement records them, so mirroring
    its protocol means reading both the excluded list and the range that was
    actually fitted (``corpus file 2``:70-71 and :177)."""
    model = read_fullprof_pcr(_pcr(tmp_path, "excl.pcr", _phase()))
    assert model.excluded_regions == [(0.0, 9.0)]
    assert model.fitted_range == (9.0, 157.0, 1.0)


def test_the_background_points_carry_their_codewords_inline(tmp_path):
    """Where the codeword sits is not uniform, and both spellings are real: the
    atom, profile and cell blocks put it on the *following* line, the background
    points and the zero-shift line carry it as the next column."""
    model = read_fullprof_pcr(_pcr(tmp_path, "bkgin.pcr", _phase()))
    assert [pos for pos, _ in model.background] == pytest.approx([12.9, 16.4])
    assert [v.value for _, v in model.background] == pytest.approx(
        [952.8345, 977.2739])
    assert [v.code.number for _, v in model.background] == [9, 10]
    assert model.zero_shift["zero"].value == pytest.approx(-0.03994)
    assert model.zero_shift["zero"].code.number == 60
    assert model.zero_shift["sycos"].vary is False


# ---------------------------------------------------------- the robustness pin


def test_a_truncated_pcr_never_escapes_as_anything_but_a_fullprof_error(tmp_path):
    """`io/CLAUDE.md`'s refusal rule, pinned: a reader raises
    :class:`FullProfPcrError` naming the file, never its parser's exception.

    A positional format makes this the *likeliest* place to lose the rule: a cut
    through a codeword line, a basis-vector line or an atom's trailing integers
    is exactly where a bare ``ValueError`` or an ``IndexError`` gets out, and a
    ragged cut through a number leaves a token like ``0.3`` that parses fine and
    a count that does not. Bounded to ~200 offsets on purpose — the same sweep at
    every byte offset also passes, and it is not a test anyone should wait for.
    """
    raw = _pcr(tmp_path, "whole.pcr", _phase(), _magnetic_isy1(),
               _magnetic_isy2()).read_bytes()
    target = tmp_path / "cut.pcr"
    offsets = sorted({round(i * len(raw) / 199) for i in range(200)})
    for n in offsets:
        target.write_bytes(raw[:n])
        try:
            model = read_fullprof_pcr(target)
            to_structure(model, nuclear_only=True)
        except FullProfPcrError:
            pass
        except Exception as exc:            # noqa: BLE001 — the point of the test
            raise AssertionError(
                f"truncation at {n} of {len(raw)} bytes escaped as "
                f"{type(exc).__name__}: {exc}") from exc


# ----------------------------------------------- the review round: six findings
#
# One section per finding of the PR #111 review, each pinning a divergence
# between what this module's own docstring claims and what its code did. The
# fixtures reuse the quoted lines above; where a finding needs a shape no corpus
# file has, the comment says so rather than implying a real file was seen.


def _rewrite_trailing_selector(text: str, header: str, value: str) -> str:
    """Rewrite the trailing model selector on the data line after ``header``.

    Edits a *quoted* line rather than inventing one: the Strain-Model and
    Size-Model selectors are the last token of ``corpus file 2``:98 and
    :101, and only that token is replaced.
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if header in line:
            tokens = lines[i + 1].split()
            tokens[-1] = value
            lines[i + 1] = "  " + "  ".join(tokens)
            return "\n".join(lines)
    raise AssertionError(f"no {header!r} line in the fixture")


# Finding 1 — the tri-state must not collapse into False.
#
# `corpus file 2`:88-89 with its codeword line cut from five columns to
# three. FullProf always writes the slot, so this shape is a *damaged* file, not
# one that says "held" — which is the whole distinction `Value.vary is None`
# exists to keep, and the module docstring's "never collapses an absent column
# into False".
_RAGGED_CODEWORD_SITES = """\
Cr     CR      0.00000  0.00000  0.31111  0.21111   0.50000   0   0   0    1
                  0.00     0.00     0.00
W      W       0.00000  0.00000  0.00000  0.22222   0.25000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O1     O       0.33333  0.33333  0.00000  0.24444   0.50000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O2     O       0.35555  0.35555  0.36666  0.17777   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00"""


def test_an_absent_codeword_column_is_refused_not_read_as_held(tmp_path):
    """A ragged codeword line is refused at build, never defaulted to vary=False.

    The reader's own tri-state says ``None`` means "the codeword column is not
    there at all". ``to_structure`` cannot know the protocol for such a value,
    and skipping the ``vary`` kwarg let ``rx.Parameter``'s schema default supply
    ``False`` — making a parameter the file said nothing about indistinguishable
    from one it genuinely fixed. That is WP-1076's collapse one file over.
    """
    pcr = _pcr(tmp_path, "ragged.pcr", _phase(atoms=_RAGGED_CODEWORD_SITES))
    model = read_fullprof_pcr(pcr)
    # The *reader* still reports the absence faithfully — it is only the build
    # that cannot proceed on it.
    assert model.phases[0].atoms[0].values["biso"].vary is None
    assert model.phases[0].atoms[1].values["biso"].vary is False
    with pytest.raises(FullProfPcrError) as excinfo:
        to_structure(model)
    message = str(excinfo.value)
    assert "'Cr'" in message and "Biso" in message
    assert "ragged or truncated" in message
    assert "vary=False" in message


def test_an_absent_cell_codeword_column_is_refused_naming_the_column(tmp_path):
    """The same refusal on the cell line, which names *which* of the six."""
    pcr = _pcr(tmp_path, "ragged_cell.pcr",
               _phase(cell_codes="   51.00000   51.00000   61.00000"))
    with pytest.raises(FullProfPcrError, match=r"cell's alpha"):
        to_structure(read_fullprof_pcr(pcr))


# Finding 2 — a schema refusal must be converted at the same boundary.


def test_a_schema_refusal_on_an_atom_is_converted_naming_the_file(tmp_path, monkeypatch):
    """``rx.Cell`` and the atoms are built *inside* the conversion ``try``.

    They were built above it, so a pydantic ``ValidationError`` escaped raw —
    naming a field but not the file — contradicting the adjacent comment "every
    schema refusal is converted at this boundary" and reaching any caller that
    catches only the documented error type.

    ``biso`` was the reachable case, a Biso above the 25 Å² bound, until the
    readers widened the bound to hold the file's value
    (:func:`rietx.schemas.structure.biso_bounds`).  The old bound is put back
    here, so the boundary is still exercised by a refusal ``rx.Parameter``
    raises itself.  A *negative* Biso does not exercise this — it has its own
    explicit refusal further up.
    """
    import rietx.io.projects.fullprof as fullprof

    monkeypatch.setattr(fullprof, "biso_bounds", lambda value: {"min": 0.0, "max": 25.0})
    sites = _PHASE_SITES.replace("0.21111", "31.00000")
    pcr = _pcr(tmp_path, "hot.pcr", _phase(atoms=sites))
    with pytest.raises(FullProfPcrError) as excinfo:
        to_structure(read_fullprof_pcr(pcr))
    assert "hot.pcr" in str(excinfo.value)


def test_a_biso_above_the_starting_bound_reads(tmp_path):
    """A published Biso of 31 Å² reads, with its bound widened to hold it."""
    sites = _PHASE_SITES.replace("0.21111", "31.00000")
    pcr = _pcr(tmp_path, "hot.pcr", _phase(atoms=sites))
    biso = to_structure(read_fullprof_pcr(pcr)).phases[0].atoms[0].biso
    assert (biso.value, biso.max) == (pytest.approx(31.0), pytest.approx(31.0))


# Finding 3 — a tie rietx cannot express is refused, not silently loosened.
#
# Built, not quoted: **no corpus file ties two nuclear atoms**. All five readable
# real files tie only one site's own coordinates (`corpus file 4`'s O1 x=y=z on
# parameter 41; `corpus file 3`'s O1 and O2 x=y on 56 and 57), and rietx
# reproduces every one of those through its site-symmetry DOFs — verified against
# the real files, which is why they must *not* refuse. The codeword `81.00` below
# is quoted from corpus file 2:108 (an Asy1 codeword); putting it on two
# atoms' Biso is this test's construction.
_SHARED_BISO_SITES = """\
Cr     CR      0.00000  0.00000  0.31111  0.21111   0.50000   0   0   0    1
                  0.00     0.00     0.00    81.00      0.00
W      W       0.00000  0.00000  0.00000  0.21111   0.25000   0   0   0    1
                  0.00     0.00     0.00    81.00      0.00
O1     O       0.33333  0.33333  0.00000  0.24444   0.50000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O2     O       0.35555  0.35555  0.36666  0.17777   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00"""


def test_a_recoverable_cross_atom_tie_reports_rather_than_refusing(tmp_path):
    """A shared Biso across two sites is dropped, reported, and restorable.

    Two sites sharing a Biso codeword is one FullProf parameter, not two, so the
    built ``Structure`` does carry more free parameters than the fit. But that
    is a **stated, recoverable loss** rather than a reading we would have to
    choose between, and root ``CLAUDE.md``'s rule is to report those and refuse
    only the ambiguous ones. ``biso`` is a direct parameter path, so the
    restoring call is unambiguous — and this test proves the message's promise
    by making the call, rather than asserting the sentence exists.
    """
    pcr = _pcr(tmp_path, "tied.pcr", _phase(atoms=_SHARED_BISO_SITES))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert carried == []
    assert dropped == ["parameter 8: Cr.biso(x+1), W.biso(x+1)"]
    assert atom_tie_recoverability(model.phases[0]) == {
        "parameter 8: Cr.biso(x+1), W.biso(x+1)": True}

    # No refusal, and no flag needed to get past one.
    diagnostics: list = []
    structure = to_structure(model, diagnostics=diagnostics)
    assert len(structure.phases[0].atoms) == 4
    reported = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(reported) == 1
    assert reported[0].level == "warning"
    assert "Cr.biso" in reported[0].message and "W.biso" in reported[0].message
    assert reported[0].where == ["phases.0"]
    # It does not claim the caller declared anything — that prefix belongs to
    # the arm that still refuses.
    assert "drop_parameter_ties=True:" not in reported[0].message

    # The remedy the message names actually works on the structure handed back.
    refinement = rx.Refinement(
        structure, rx.Instrument(source=NeutronSource(wavelength=1.5406)))
    assert refinement.tie_equal(
        ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]) == [
            "phases.0.atoms.1.biso"]


#: A coordinate codeword shared by two sites that each have **exactly one** DOF,
#: and for both of them that DOF *is* z — so the correspondence between the two
#: paths is forced rather than picked, which is the `True` branch of
#: `atom_tie_recoverability` no other fixture reaches.  `W` is moved off
#: (0, 0, 0) — where it has no freedom at all, which is what the refusing
#: fixture below relies on — to (0, 0, 0.1), a 1-DOF position; its `Occ` moves
#: 0.25 -> 0.50 with it, because the site multiplicity doubles and
#: `occupancy_factor` requires every site's `Occ x M_general/M_site` to agree.
_SHARED_Z_SINGLE_DOF_SITES = """\
Cr     CR      0.00000  0.00000  0.31111  0.21111   0.50000   0   0   0    1
                  0.00     0.00    81.00     0.00      0.00
W      W       0.00000  0.00000  0.10000  0.22222   0.50000   0   0   0    1
                  0.00     0.00    81.00     0.00      0.00
O1     O       0.33333  0.33333  0.00000  0.24444   0.50000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O2     O       0.35555  0.35555  0.36666  0.17777   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00"""


def test_a_recoverable_coordinate_tie_restores_on_the_dof_path(tmp_path):
    """The other recoverable arm, and the spelling its message must name.

    Round five found that the restoring call this arm promises is not writable
    as a reader would naturally write it: the group description says ``Cr.z,
    W.z``, but ``Refinement.tie_equal`` **refuses** ``phases.0.atoms.1.z``
    because a coordinate column already follows its own ``dof`` by site
    symmetry, and symmetry outranks a user tie.  Only the ``dof.k`` spelling
    works.  No fixture reached this branch before — the one test that *makes*
    the call made it on ``biso``, where the column path is the parameter path —
    so the gap survived three rounds of review.

    This test asserts both halves on the same structure: that the branch
    returns ``True``, and that the call named in the diagnostic is the one that
    succeeds while the obvious one raises.  It also removes an ambiguity in the
    DOF-0 fixture below, which cannot tell a computed ``0`` from a swallowed
    exception because ``dof_count``'s ``except Exception: return None`` also
    yields ``False`` — this is the one case that must come back ``True``, so a
    signature change in ``coordinate_basis``/``stabilizer_rotations`` fails
    here rather than going quiet.
    """
    pcr = _pcr(tmp_path, "tiedz.pcr", _phase(atoms=_SHARED_Z_SINGLE_DOF_SITES))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert carried == []
    assert dropped == ["parameter 8: Cr.z(x+1), W.z(x+1)"]
    assert atom_tie_recoverability(model.phases[0]) == {
        "parameter 8: Cr.z(x+1), W.z(x+1)": True}

    # Reports rather than refuses, and needs no flag to get past a refusal.
    diagnostics: list = []
    structure = to_structure(model, diagnostics=diagnostics)
    reported = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(reported) == 1
    assert reported[0].level == "warning"
    assert reported[0].where == ["phases.0"]
    assert "drop_parameter_ties=True:" not in reported[0].message
    # The message must name the DOF spelling, because the column one raises.
    assert "dof.k" in reported[0].message

    instrument = rx.Instrument(source=NeutronSource(wavelength=1.5406))
    # The path a reader would copy out of the group description is refused...
    with pytest.raises(ValueError, match="symmetry outranks a user tie"):
        rx.Refinement(structure.model_copy(deep=True),
                      instrument.model_copy(deep=True)).tie_equal(
            ["phases.0.atoms.0.z", "phases.0.atoms.1.z"])
    # ...and the one the message names works.
    assert rx.Refinement(
        structure.model_copy(deep=True), instrument.model_copy(deep=True)
    ).tie_equal(["phases.0.atoms.0.dof.0",
                 "phases.0.atoms.1.dof.0"]) == ["phases.0.atoms.1.dof.0"]


def test_an_ambiguous_cross_atom_tie_still_refuses(tmp_path):
    """Tying two sites' *coordinates* is the case that has to refuse.

    Coordinates refine through site-symmetry directions (``dof.k``), and two
    different sites' ``dof`` bases are not the same direction — so restoring the
    tie would mean choosing which index on each site stands for it. Here both
    sites sit at DOF-0 special positions, so there is no path to tie at all.
    That is a reading we would have to pick, not a loss we can state, so it
    refuses and names the escape.
    """
    sites = _SHARED_BISO_SITES.replace(
        "                  0.00     0.00     0.00    81.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.21111   0.25000   0   0   0    1\n"
        "                  0.00     0.00     0.00    81.00      0.00",
        "                 81.00     0.00     0.00     0.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.21111   0.25000   0   0   0    1\n"
        "                 81.00     0.00     0.00     0.00      0.00")
    assert sites != _SHARED_BISO_SITES, "the codeword lines were not rewritten"
    pcr = _pcr(tmp_path, "tiedxy.pcr", _phase(atoms=sites))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert dropped == ["parameter 8: Cr.x(x+1), W.x(x+1)"]
    assert atom_tie_recoverability(model.phases[0]) == {
        "parameter 8: Cr.x(x+1), W.x(x+1)": False}
    with pytest.raises(FullProfPcrError) as excinfo:
        to_structure(model)
    message = str(excinfo.value)
    assert "Cr.x" in message and "W.x" in message
    assert "tie_equal" in message
    assert "drop_parameter_ties=True" in message


def test_dropping_an_ambiguous_tie_is_the_callers_declared_choice(tmp_path):
    """``drop_parameter_ties=True`` builds the refusing arm, and says so."""
    sites = _SHARED_BISO_SITES.replace(
        "                  0.00     0.00     0.00    81.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.21111   0.25000   0   0   0    1\n"
        "                  0.00     0.00     0.00    81.00      0.00",
        "                 81.00     0.00     0.00     0.00      0.00\n"
        "W      W       0.00000  0.00000  0.00000  0.21111   0.25000   0   0   0    1\n"
        "                 81.00     0.00     0.00     0.00      0.00")
    pcr = _pcr(tmp_path, "tiedxy.pcr", _phase(atoms=sites))
    diagnostics: list = []
    structure = to_structure(read_fullprof_pcr(pcr), drop_parameter_ties=True,
                             diagnostics=diagnostics)
    assert len(structure.phases[0].atoms) == 4
    dropped = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(dropped) == 1
    assert dropped[0].message.startswith("drop_parameter_ties=True:")
    assert "Cr.x" in dropped[0].message and "W.x" in dropped[0].message
    assert dropped[0].where == ["phases.0"]


def test_the_six_real_files_contain_no_cross_atom_tie(tmp_path):
    """Why the recoverability rule is written from principle, not from corpus.

    Every shared-number group in the archive's six ``.pcr`` files is a
    *single-atom* coordinate tie, which is carried. So the corpus reaches
    neither arm of the recoverable/ambiguous split, and a rule inferred from it
    would have been an accident — the same argument that moved the cell ties
    onto ``cell_constraints``. Recorded here as the fixture-level statement of
    that fact: a phase built from single-atom ties alone has an empty
    recoverability map, because nothing was dropped.
    """
    pcr = _pcr(tmp_path, "single.pcr", _phase(atoms=_PHASE_SITES.replace(
        "O1     O       0.33333  0.33333  0.00000  0.24444   0.50000   0   0   0    1  #color cyan\n"
        "                  0.00     0.00     0.00     0.00      0.00",
        "O1     O       0.33333  0.33333  0.00000  0.24444   0.50000   0   0   0    1  #color cyan\n"
        "                561.00   561.00     0.00     0.00      0.00")))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert dropped == []
    assert carried == ["parameter 56: O1.x(x+1), O1.y(x+1)"]
    assert atom_tie_recoverability(model.phases[0]) == {
        "parameter 56: O1.x(x+1), O1.y(x+1)": False}, (
        "a carried group's recoverability is never consulted, but it must not "
        "claim to be restorable — the map answers only 'if this were dropped'")


def test_a_sites_own_coordinate_tie_is_carried_by_symmetry_not_refused(tmp_path):
    """The corpus's real ties must **not** refuse — rietx already reproduces them.

    ``corpus file 3`` ties O1's x to its y with parameter 56, on
    ``P 42/m n m``'s 4f site. ``ParameterTable._collect_atom_coords`` gives that
    site one ``dof.0`` and writes x and y as affine rows onto it, so the
    constraint is already one free parameter. Refusing it would be a false alarm
    on a real file, which is why the check re-derives the site's DOF count
    instead of refusing every shared codeword.
    """
    sites = _PHASE_SITES.replace(
        "O1     O       0.33333  0.33333  0.00000  0.24444   0.50000   0   0   0    1  #color cyan\n"
        "                  0.00     0.00     0.00     0.00      0.00",
        "O1     O       0.33333  0.33333  0.00000  0.24444   0.50000   0   0   0    1  #color cyan\n"
        "                561.00   561.00     0.00     0.00      0.00")
    assert "561.00" in sites, "the O1 codeword line was not rewritten"
    pcr = _pcr(tmp_path, "wyckoff.pcr", _phase(atoms=sites))
    model = read_fullprof_pcr(pcr)
    carried, dropped = nuclear_parameter_ties(model.phases[0])
    assert dropped == []
    assert carried == ["parameter 56: O1.x(x+1), O1.y(x+1)"]
    # and it builds without the caller having to declare anything
    assert len(to_structure(model).phases[0].atoms) == 4


# Round-three finding — a *cell* codeword tie is the one tie the atom analysis
# above does not reach. Whether rietx reproduces it turns on the space group,
# not on a site's DOFs, so the same `51 51 61` codewords are carried under a
# tetragonal symbol and dropped under an orthorhombic or triclinic one. The
# corpus has only the tetragonal (corpus files 1-3 and 6, param 5) and cubic
# (`corpus file 4`, param 40) cases, both carried, so the dropped case is driven
# synthetically the way the reviewer drove it.


def test_a_tetragonal_cell_tie_is_carried_by_symmetry_not_reported(tmp_path):
    """`51 51 61` under `P 42/m n m` is `a = b`, which the setting ties itself.

    This is the corpus's own case (`corpus file 2`:105) and it must stay
    silent: rietx's metric already holds `b = a` under a tetragonal setting, so
    the built cell has exactly the two free lengths the file refined and there is
    nothing dropped. The default fixture carries these codewords, so this pins
    that the new cell analysis does not raise a false alarm on the real file.
    """
    model = read_fullprof_pcr(_pcr(tmp_path, "tetra.pcr", _phase()))
    carried, dropped = cell_parameter_ties(model.phases[0])
    assert carried == ["parameter 5: a(x+1), b(x+1)"]
    assert dropped == []
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    assert [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"] == []


@pytest.mark.parametrize("sg", ["P m m m", "P 1"])
def test_a_cell_tie_symmetry_does_not_hold_is_reported_not_dropped(tmp_path, sg):
    """The same `a = b` codewords under a symbol that leaves `a` and `b` free.

    Orthorhombic and triclinic do not tie the two edges, so `51 51 61` builds a
    cell with three free lengths where FullProf refined two — the function's own
    definition of a dropped tie, reached by the one path the atom analysis never
    consulted. It is *reported* through `FULLPROF_TIE_DROPPED` (the sibling
    reader's `TOPAS_CELL_COUPLING_DROPPED` shape) rather than refused: the cell
    is built either way, so no `drop_parameter_ties=True` is needed to see it.

    A one-site phase, as the reviewer drove it: the occupancy-ratio check is
    trivially self-consistent there, so what is under test is the cell tie and
    not the multiplicities.
    """
    site = ("Cr     CR      0.00000  0.00000  0.31111  0.21111   0.50000"
            "   0   0   0    1\n"
            "                  0.00     0.00     0.00     0.00      0.00")
    model = read_fullprof_pcr(
        _pcr(tmp_path, "loose.pcr", _phase(sg=sg, nat=1, atoms=site)))
    carried, dropped = cell_parameter_ties(model.phases[0])
    assert carried == []
    assert dropped == ["parameter 5: a(x+1), b(x+1)"]
    diagnostics: list = []
    # No flag passed, and it still builds — this reports, it does not refuse.
    structure = to_structure(model, diagnostics=diagnostics)
    assert len(structure.phases[0].atoms) == 1
    tie = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(tie) == 1
    assert tie[0].level == "warning"
    assert "a(x+1), b(x+1)" in tie[0].message
    assert "drop_parameter_ties=True" not in tie[0].message
    assert tie[0].where == ["phases.0.cell"]


def test_a_scaled_cell_relation_is_dropped_even_under_a_symbol_that_ties(
        tmp_path):
    """`b = 2a` is a multiplier, and symmetry only ever *equates* two edges.

    `51.00000` on `a` and `52.00000` on `b` share parameter 5 but with
    multipliers 1 and 2, so the file states `b = 2a`, not `b = a`. Even under
    `P 42/m n m`, whose symmetry ties `b = a`, rietx reproduces the equality and
    not the scaled relation, so the file's actual tie is dropped. The check must
    read the multiplier, not just the shared number — otherwise it would wave
    this through as the tetragonal `a = b` it is not.
    """
    scaled = "   51.00000   52.00000   61.00000    0.00000    0.00000    0.00000"
    model = read_fullprof_pcr(
        _pcr(tmp_path, "scaled.pcr", _phase(sg="P 42/m n m", cell_codes=scaled)))
    carried, dropped = cell_parameter_ties(model.phases[0])
    assert carried == []
    assert dropped == ["parameter 5: a(x+1), b(x+2)"]
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    tie = [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"]
    assert len(tie) == 1
    assert "a(x+1), b(x+2)" in tie[0].message


def test_a_cubic_cell_tie_is_carried_including_the_edge_named_only_transitively(
        tmp_path):
    """`a = b = c` (parameter 40) under a cubic setting, the corpus's other case.

    `corpus file 4` ties all three lengths to one parameter on `F d -3 m:2`.
    The cubic constraint table names `b -> a` and `c -> a` but not `c -> b`, so
    the check must follow ties to their root to see that `c` shares `a`'s root.
    All three land carried, and nothing is reported.
    """
    cubic = "  401.00000  401.00000  401.00000    0.00000    0.00000    0.00000"
    sites = ("Co1    CO      0.12500  0.12500  0.12500  0.35000   0.12500"
             "   0   0   0    1\n"
             "                  0.00     0.00     0.00     0.00      0.00")
    cell = "   8.068200   8.068200   8.068200  90.000000  90.000000  90.000000"
    model = read_fullprof_pcr(_pcr(tmp_path, "cubic.pcr",
                                   _phase(nat=1, sg="F D -3 M", atoms=sites,
                                          cell=cell, cell_codes=cubic)))
    carried, dropped = cell_parameter_ties(model.phases[0])
    assert carried == ["parameter 40: a(x+1), b(x+1), c(x+1)"]
    assert dropped == []
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    assert [d for d in diagnostics if d.code == "FULLPROF_TIE_DROPPED"] == []


# Finding 4 — the R_Bragg count is asserted, not truncated into agreement.


def test_more_r_bragg_comments_than_phases_is_refused_not_truncated(tmp_path):
    """``strict=False`` here would attach an agreement factor to the wrong phase.

    The comments are matched by *file order* — their own phase number is trap 1
    and cannot re-key them — so an unequal count is a refusal, exactly as the
    ``Nph``/parsed-phase count two lines above already is.
    """
    stray = ("!  Data for PHASE number:   3  ==> Current R_Bragg for "
             "Pattern#  1:     5.00\n")
    pcr = _pcr(tmp_path, "extra.pcr", _phase(), trailing=stray + _RANGE)
    with pytest.raises(FullProfPcrError) as excinfo:
        read_fullprof_pcr(pcr)
    message = str(excinfo.value)
    assert "2" in message and "1 phases" in message


def test_a_pcr_with_no_r_bragg_comments_still_reads(tmp_path):
    """Zero comments is not a mismatch — a never-run .pcr carries none."""
    pcr = _pcr(tmp_path, "unrun.pcr", _phase())
    text = "\n".join(line for line in pcr.read_text(encoding="utf-8").split("\n")
                     if "R_Bragg" not in line)
    pcr.write_text(text, encoding="utf-8")
    model = read_fullprof_pcr(pcr)
    assert model.phases[0].r_bragg is None


# Finding 5 — integer fields go through an is_integer() guard, never bare int().


def test_a_non_integer_phase_control_field_is_refused_not_truncated(tmp_path):
    """``int(3.5) == 3`` would read a three-atom phase from a four-atom one.

    The line as a whole cannot go through ``_Cursor.ints``: ``Pr1 Pr2 Pr3`` are
    ``0.0 0.0 1.0`` and ``ATZ`` is ``963.500`` on this very line
    (corpus file 2:84) and ``154213.406`` in corpus file 4:66, so
    requiring the whole line to be integral would refuse every real file. The
    eleven counts and selectors get the guard field by field instead.
    """
    pcr = _pcr(tmp_path, "fractional.pcr", _phase(nat="3.5"))
    with pytest.raises(FullProfPcrError) as excinfo:
        read_fullprof_pcr(pcr)
    message = str(excinfo.value)
    assert "Nat = 3.5" in message
    assert "desynchronises" in message


def test_a_real_phase_control_line_keeps_its_float_atz(tmp_path):
    """The guard must not reject ATZ, which is a genuine float in every file."""
    model = read_fullprof_pcr(_pcr(tmp_path, "atz.pcr", _phase()))
    assert model.phases[0].control["atz"] == 963.500
    assert model.phases[0].control["pr3"] == 1.0


@pytest.mark.parametrize("header, what", [
    ("Strain-Model", "strain"),
    ("Size-Model", "size"),
])
def test_a_non_integer_model_selector_is_refused(tmp_path, header, what):
    """A model selector names a discrete broadening model, so ``1.5`` is not a 1.

    Truncating it would select a *different* model without saying so — the one
    place left in this module that cast a float through a bare ``int()``.
    """
    phase = _rewrite_trailing_selector(_phase(), header, "1.5")
    pcr = _pcr(tmp_path, f"{what}.pcr", phase)
    with pytest.raises(FullProfPcrError, match=r"model selector"):
        read_fullprof_pcr(pcr)


def test_an_integer_model_selector_still_reads(tmp_path):
    """The guard admits the integers the real files write."""
    phase = _rewrite_trailing_selector(_phase(), "Size-Model", "1")
    model = read_fullprof_pcr(_pcr(tmp_path, "size1.pcr", phase))
    assert model.phases[0].size_model == 1
    assert model.phases[0].strain_model == 0


# Finding 6 — an R lattice on rhombohedral axes.
#
# Synthetic, and it has to be: **every R phase in the corpus is on hexagonal
# axes**. The hexagonal cell below is synthetic, and the rhombohedral one is
# that same lattice transformed to rhombohedral axes —
# a_rh = sqrt(a^2/3 + c^2/9) = 5.206833 and
# sin(alpha/2) = 3 / (2*sqrt(3 + (c/a)^2)) => alpha = 57.388870 — so the pair
# describes one lattice in two settings, which is what the test needs.
# This closes a gap; it is not a wrong answer any file here produced.
_R_PHASE_RHOMBOHEDRAL_CELL = (
    "   5.206833   5.206833   5.206833  57.388870  57.388870  57.388870")
_R_PHASE_HEXAGONAL_CELL = (
    "   5.000000   5.000000  13.000000  90.000000  90.000000 120.000000")


@pytest.mark.parametrize("cell, expected, why", [
    ({"a": 5.206833, "b": 5.206833, "c": 5.206833,
      "alpha": 57.38887, "beta": 57.38887, "gamma": 57.38887},
     "R -3 c:R", "a = b = c with alpha = beta = gamma is rhombohedral axes"),
    ({"a": 5.0, "b": 5.0, "c": 13.0,
      "alpha": 90.0, "beta": 90.0, "gamma": 120.0},
     "R -3 c", "the corpus's own R phase is hexagonal and must stay bare"),
])
def test_the_r_setting_is_picked_from_the_cell(cell, expected, why):
    """Root CLAUDE.md's invariant: ``read_small_structure`` picks R from the cell.

    gemmi resolves a bare ``R -3 c`` to the **hexagonal** setting (36
    operations); the rhombohedral one has 12. That factor of three is the
    general multiplicity :func:`occupancy_factor` divides by, so reading a
    rhombohedral cell under ``:H`` is a wrong multiplicity on every site.
    """
    assert normalize_space_group("R -3 c", cell) == expected, why


def test_without_a_cell_the_bare_r_symbol_is_unchanged():
    """No cell, no claim: the R case cannot be decided and is not guessed at."""
    assert normalize_space_group("R -3 c") == "R -3 c"


def test_a_rhombohedral_cell_selects_the_r_setting_end_to_end(tmp_path):
    """The cell line sits *after* the atoms, so the symbol is re-derived there."""
    pcr = _pcr(tmp_path, "rhombo.pcr",
               _phase(sg="R -3 c", cell=_R_PHASE_RHOMBOHEDRAL_CELL,
                      cell_codes=_PHASE_CELL_CODES))
    phase = read_fullprof_pcr(pcr).phases[0]
    assert phase.space_group_raw == "R -3 c"
    assert phase.space_group == "R -3 c:R"


def test_a_hexagonal_r_cell_is_left_on_the_default_setting(tmp_path):
    """The corpus's real R phase, pinned: it must keep reading as before."""
    pcr = _pcr(tmp_path, "hex.pcr",
               _phase(sg="R -3 c", cell=_R_PHASE_HEXAGONAL_CELL,
                      cell_codes=_PHASE_CELL_CODES))
    assert read_fullprof_pcr(pcr).phases[0].space_group == "R -3 c"


# The two lower-confidence items the review raised, both surfaced rather than
# left silent.


def test_the_origin_choice_repair_is_reported_as_a_diagnostic(tmp_path):
    """FullProf writes no origin suffix, so choosing one is a repair — and a
    repair on a value that reaches the ``Structure`` is reported the way the
    species rewrite is, on the same channel.

    ``F D -3 M`` is quoted from ``corpus file 4``:68.
    """
    # A one-site cubic phase: the spinel 8a site alone, so the symbol resolves and
    # the occupancy ratio is trivially self-consistent.
    sites = ("Co1    CO      0.12500  0.12500  0.12500  0.35000   0.12500"
             "   0   0   0    1\n"
             "                  0.00     0.00     0.00     0.00      0.00")
    cell = "   8.068200   8.068200   8.068200  90.000000  90.000000  90.000000"
    pcr = _pcr(tmp_path, "spinel.pcr",
               _phase(nat=1, sg="F D -3 M", atoms=sites, cell=cell,
                      cell_codes=_PHASE_CELL_CODES))
    model = read_fullprof_pcr(pcr)
    assert model.phases[0].space_group == "F d -3 m:2"
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    origin = [d for d in diagnostics if d.code == "FULLPROF_ORIGIN_CHOICE"]
    assert len(origin) == 1
    assert "'F D -3 M'" in origin[0].message
    assert "'F d -3 m:2'" in origin[0].message
    assert origin[0].where == ["phases.0.space_group"]


def test_a_case_only_repair_is_not_reported_as_an_origin_choice(tmp_path):
    """Lower-casing a HM symbol's tail is lossless, so it is not a convention
    the caller has to see — only the *setting* suffix is."""
    pcr = _pcr(tmp_path, "case.pcr", _phase(sg="P 42/M N M"))
    model = read_fullprof_pcr(pcr)
    assert model.phases[0].space_group == "P 42/m n m"
    diagnostics: list = []
    to_structure(model, diagnostics=diagnostics)
    assert [d for d in diagnostics if d.code == "FULLPROF_ORIGIN_CHOICE"] == []


def test_a_single_site_phase_says_its_occupancy_check_did_not_discriminate(
        tmp_path):
    """The occupancy-ratio test is structurally blind for a one-site phase.

    One ratio always agrees with itself, so the test passes for *every* setting
    and the licence it grants the origin choice is vacuous exactly there. That
    cannot be repaired by a better test — FullProf's Occ carries one arbitrary
    common factor per phase, so one site is one equation in two unknowns — so it
    is reported instead of being left silent.
    """
    sites = ("Co1    CO      0.12500  0.12500  0.12500  0.35000   0.12500"
             "   0   0   0    1\n"
             "                  0.00     0.00     0.00     0.00      0.00")
    cell = "   8.068200   8.068200   8.068200  90.000000  90.000000  90.000000"
    pcr = _pcr(tmp_path, "one_site.pcr",
               _phase(nat=1, sg="F D -3 M", atoms=sites, cell=cell,
                      cell_codes=_PHASE_CELL_CODES))
    diagnostics: list = []
    to_structure(read_fullprof_pcr(pcr), diagnostics=diagnostics)
    blind = [d for d in diagnostics if d.code == "FULLPROF_OCCUPANCY_UNCHECKED"]
    assert len(blind) == 1
    assert blind[0].level == "warning"
    assert "single site" in blind[0].message
    assert blind[0].where == ["phases.0.atoms.0.occ"]


def test_a_multi_site_phase_makes_no_such_claim(tmp_path):
    """Four sites do discriminate, so nothing is reported."""
    diagnostics: list = []
    to_structure(read_fullprof_pcr(_pcr(tmp_path, "four.pcr", _phase())),
                 diagnostics=diagnostics)
    assert [d for d in diagnostics
            if d.code == "FULLPROF_OCCUPANCY_UNCHECKED"] == []


# --------------------------------------------------- the writer (WP-1118, #148)
#
# `from_structure` is the inverse of `to_structure`, and its acceptance is a
# round trip through the reader this module already carries. No committed
# fixture is needed and none is added: every `Structure` below is built by
# hand, the same way the synthetic `.pcr` fixtures above are.


def _assert_parameter_equal(a: rx.Parameter, b: rx.Parameter):
    assert a.value == b.value and a.vary == b.vary


def test_write_fullprof_pcr_round_trips_a_multi_phase_structure(tmp_path):
    """Cell, atoms and scale come back exactly, every `vary` intact, across a
    monoclinic two-site phase and a cubic one-site phase in the same file."""
    cell = rx.Cell(a=rx.Parameter(value=8.123, vary=True),
                   b=rx.Parameter(value=5.234, vary=False),
                   c=rx.Parameter(value=9.345, vary=True),
                   alpha=rx.Parameter(value=90.0, vary=False),
                   beta=rx.Parameter(value=105.41, vary=True),
                   gamma=rx.Parameter(value=90.0, vary=False))
    fe = rx.Atom(label="Fe1", species="Fe3+",
                 x=rx.Parameter(value=-0.123, vary=True),
                 y=rx.Parameter(value=0.25, vary=False),
                 z=rx.Parameter(value=0.04512345678, vary=True),
                 occ=rx.Parameter(value=1.0, vary=False),
                 biso=rx.Parameter(value=0.9123456789, vary=True,
                                   min=0.0, max=25.0, unit="A^2"))
    o = rx.Atom(label="O1", species="O2-",
                x=rx.Parameter(value=0.31, vary=True),
                y=rx.Parameter(value=0.11, vary=True),
                z=rx.Parameter(value=0.41, vary=False),
                occ=rx.Parameter(value=1.0, vary=False),
                biso=rx.Parameter(value=0.5, vary=False,
                                  min=0.0, max=25.0, unit="A^2"))
    monoclinic = rx.Phase(name="FeO phase", space_group="P21/c", cell=cell,
                          atoms=[fe, o],
                          scale=rx.Parameter(value=1.5e-5, vary=True, min=0.0))
    cubic = rx.Phase(
        name="Al", space_group="Fm-3m", cell=rx.Cell.cubic(4.0495, vary=True),
        atoms=[rx.Atom(label="Al1", species="Al",
                       x=rx.Parameter(value=0.0), y=rx.Parameter(value=0.0),
                       z=rx.Parameter(value=0.0),
                       biso=rx.Parameter(value=0.55, vary=True,
                                         min=0.0, max=25.0, unit="A^2"))],
        scale=rx.Parameter(value=0.02, vary=True, min=0.0))
    structure = rx.Structure(phases=[monoclinic, cubic])

    out = tmp_path / "round_trip.pcr"
    rx.write_fullprof_pcr(structure, out)
    back = to_structure(read_fullprof_pcr(out))

    assert len(back.phases) == 2
    for orig, built in zip(structure.phases, back.phases):
        assert built.name == orig.name
        assert (get_spacegroup(built.space_group).xhm()
               == get_spacegroup(orig.space_group).xhm())
        for key in ("a", "b", "c", "alpha", "beta", "gamma"):
            _assert_parameter_equal(getattr(orig.cell, key), getattr(built.cell, key))
        _assert_parameter_equal(orig.scale, built.scale)
        assert len(built.atoms) == len(orig.atoms)
        for oa, ba in zip(orig.atoms, built.atoms):
            assert ba.label == oa.label
            assert ba.species == oa.species
            for key in ("x", "y", "z", "biso"):
                _assert_parameter_equal(getattr(oa, key), getattr(ba, key))
            # Occ is the one field `to_structure` never carries — every atom
            # comes back fully occupied regardless of what the file states.
            assert ba.occ.value == 1.0


@pytest.mark.parametrize("symbol", ["R-3c:H", "R-3c:R"])
def test_write_fullprof_pcr_round_trips_both_r_lattice_axis_choices(tmp_path, symbol):
    """`.pcr` writes no axis suffix at all, so the setting must come back
    from the cell metric alone — hexagonal axes for a=b≠c,γ=120°, rhombohedral
    for a=b=c with equal angles — exactly as `normalize_space_group` picks it
    on the way in."""
    if symbol.endswith(":H"):
        cell = rx.Cell(a=rx.Parameter(value=4.9542), b=rx.Parameter(value=4.9542),
                       c=rx.Parameter(value=13.4213), alpha=rx.Parameter(value=90.0),
                       beta=rx.Parameter(value=90.0), gamma=rx.Parameter(value=120.0))
    else:
        cell = rx.Cell(a=rx.Parameter(value=5.5), b=rx.Parameter(value=5.5),
                       c=rx.Parameter(value=5.5), alpha=rx.Parameter(value=55.0),
                       beta=rx.Parameter(value=55.0), gamma=rx.Parameter(value=55.0))
    atom = rx.Atom(label="Cr1", species="Cr3+", x=rx.Parameter(value=0.35),
                   y=rx.Parameter(value=0.35), z=rx.Parameter(value=0.35))
    structure = rx.Structure(phases=[rx.Phase(name="Corundum-type", space_group=symbol,
                                              cell=cell, atoms=[atom])])
    out = tmp_path / "r.pcr"
    write_fullprof_pcr(structure, out)
    back = to_structure(read_fullprof_pcr(out))
    assert (get_spacegroup(back.phases[0].space_group).xhm()
           == get_spacegroup(symbol).xhm())


def test_write_fullprof_pcr_refuses_an_unreachable_origin_choice(tmp_path):
    """`Fd-3m:1` cannot be spelled in a `.pcr`: the format writes no origin
    suffix, and a bare symbol always reads back as choice 2 (root CLAUDE.md's
    own convention), so writing one here would silently launder the phase
    into the other origin — refused instead, naming both settings."""
    structure = rx.Structure(phases=[rx.Phase(
        name="spinel", space_group="Fd-3m:1", cell=rx.Cell.cubic(8.0806),
        atoms=[rx.Atom(label="Mg1", species="Mg", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))])])
    with pytest.raises(ValueError, match="cannot be written"):
        from_structure(structure)


def test_write_fullprof_pcr_refuses_an_anisotropic_site(tmp_path):
    """FullProf's beta_ij convention is exactly what `to_structure` itself
    refuses to assume on the way in, so the writer refuses the same way
    rather than inventing a convention on the way out."""
    atom = rx.Atom(label="Na1", species="Na1+", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                   aniso=rx.AnisoU(u11=rx.Parameter(value=0.01),
                                   u22=rx.Parameter(value=0.01),
                                   u33=rx.Parameter(value=0.01)))
    structure = rx.Structure(phases=[rx.Phase(
        name="NaCl", space_group="Fm-3m", cell=rx.Cell.cubic(5.62), atoms=[atom])])
    with pytest.raises(ValueError, match="anisotropic"):
        from_structure(structure)


def test_write_fullprof_pcr_refuses_a_label_or_species_with_whitespace(tmp_path):
    """A `.pcr` atom line is whitespace-tokenized, so an embedded space would
    desynchronise every column after it."""
    atom = rx.Atom(label="Al 1", species="Al", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))
    structure = rx.Structure(phases=[rx.Phase(
        name="Al", space_group="Fm-3m", cell=rx.Cell.cubic(4.0495), atoms=[atom])])
    with pytest.raises(ValueError, match="whitespace"):
        from_structure(structure)


def test_write_fullprof_pcr_writes_a_negative_biso_that_reads_back(tmp_path):
    """FullProf stores a negative Biso and the reader now keeps one, so the
    writer writes it rather than refusing (PR #663)."""
    atom = rx.Atom(label="Al1", species="Al", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                   biso=rx.Parameter(value=-0.1, min=-1.0, max=25.0))
    structure = rx.Structure(phases=[rx.Phase(
        name="Al", space_group="Fm-3m", cell=rx.Cell.cubic(4.0495), atoms=[atom])])
    out = tmp_path / "negb.pcr"
    out.write_text(from_structure(structure), encoding="utf-8")
    back = to_structure(read_fullprof_pcr(out)).phases[0].atoms[0].biso
    assert back.value == pytest.approx(-0.1)


def test_write_fullprof_pcr_refuses_a_blank_phase_name():
    """The phase-name line is comment-stripped like every other line in a
    `.pcr`, so a blank name leaves nothing on it: `_strip` drops the line
    from the positional walk entirely rather than reading it as an empty
    name, desynchronising every line after it."""
    atom = rx.Atom(label="Al1", species="Al", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))
    structure = rx.Structure(phases=[rx.Phase(
        name="   ", space_group="Fm-3m", cell=rx.Cell.cubic(4.0495), atoms=[atom])])
    with pytest.raises(ValueError, match="blank"):
        from_structure(structure)


def test_write_fullprof_pcr_refuses_a_comment_marker_in_an_atom_label():
    """The same `!`/`#`/`<--` markers refused in a phase name also cut a
    `.pcr` atom line, since `_strip` applies to every data line alike."""
    atom = rx.Atom(label="Fe#1", species="Fe3+", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))
    structure = rx.Structure(phases=[rx.Phase(
        name="FeO", space_group="Fm-3m", cell=rx.Cell.cubic(4.0495), atoms=[atom])])
    with pytest.raises(ValueError, match="comment marker"):
        from_structure(structure)


def test_write_fullprof_pcr_is_reachable_at_the_top_level():
    assert rx.write_fullprof_pcr is write_fullprof_pcr


def test_write_fullprof_pcr_refuses_a_non_finite_value():
    """The sibling of the TOPAS and GSAS rows: `repr` spells it `inf`, no real
    program parses that, and the failure would otherwise land in someone
    else's (WP-1118)."""
    structure = rx.Structure(phases=[rx.Phase(
        name="Al", space_group="Fm-3m",
        cell=rx.Cell.cubic(4.0495, vary=True),
        atoms=[rx.Atom(label="Al1", species="Al", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))])])
    structure.phases[0].cell.a.max = float("inf")
    structure.phases[0].cell.a.value = float("inf")
    with pytest.raises(ValueError, match="does not parse"):
        from_structure(structure)


def test_write_fullprof_pcr_refuses_a_line_break_in_a_phase_name():
    """The phase-name line is one step of a positional walk, so a break splits
    it in two and every line after it is read under the wrong name — the same
    desynchronisation the blank-name refusal above prevents."""
    atom = rx.Atom(label="Al1", species="Al", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))
    structure = rx.Structure(phases=[rx.Phase(
        name="apa\ntite", space_group="Fm-3m", cell=rx.Cell.cubic(4.0495),
        atoms=[atom])])
    with pytest.raises(ValueError, match="line break"):
        from_structure(structure)


# ------------------------------------ what FullProf needs to run it (#557, #558)
#
# A round trip through this module's own reader cannot see either issue: the
# reader needs neither the widths nor FullProf's species keys to build a
# Structure. FullProf.2k 8.20, run as a black box on the writer's output, is
# the oracle (issue #557's and #558's reproductions); these tests pin the lines
# that run showed FullProf needs.

def _site(label, species, xyz=(0.0, 0.0, 0.0)):
    return rx.Atom(label=label, species=species, x=rx.Parameter(value=xyz[0]),
                   y=rx.Parameter(value=xyz[1]), z=rx.Parameter(value=xyz[2]),
                   biso=rx.Parameter(value=0.5, min=0.0, max=25.0, unit="A^2"))


def _cubic(*species, **phase_fields):
    atoms = [_site(f"A{i}", sp, (0.5 * i, 0.5 * i, 0.5 * i))
             for i, sp in enumerate(species)]
    return rx.Structure(phases=[rx.Phase(
        name="syn", space_group="Pm-3m", cell=rx.Cell.cubic(4.0), atoms=atoms,
        **phase_fields)])


def _widths(**values):
    from rietx.schemas.instrument import ProfileTCHZ
    return ProfileTCHZ(**{k: rx.Parameter(value=v, min=-1.0, max=8.0)
                          for k, v in values.items()})


def _xray(*wavelengths, profile=None, **source):
    from rietx.schemas.instrument import EmissionLine, Geometry, Source
    lines = [EmissionLine(wavelength=wavelengths[0])] + [
        EmissionLine(wavelength=w, weight=rx.Parameter(value=0.46, min=0.0, max=1.0))
        for w in wavelengths[1:]]
    return rx.Instrument(
        source=Source(lines=lines, **source),
        geometry=Geometry(kind="bragg_brentano", goniometer_radius_mm=217.5),
        **({"profile": profile} if profile is not None else {}))


def _lines(text):
    return text.splitlines()


def _width_line(text):
    """LINE 27: the first line after the scale-codeword line of phase 1."""
    lines = _lines(text)
    scale = next(i for i, line in enumerate(lines) if line.endswith(" 0")
                 and i > 12 and len(line.split()) == 7)
    return [float(v) for v in lines[scale + 2].split()[:6]]


def test_a_written_pcr_never_has_zero_widths():
    """#557: U = V = W = 0 with no resolution file is a FullProf hard stop
    ("Zero half-width parameters for phase 1 and NO resolution-file
    provided!"), so the file this writer wrote before an instrument could be
    passed must still carry widths — a default ProfileTCHZ()'s — and select
    the TCH pseudo-Voigt they belong to (Npr = 7, control line and phase)."""
    from rietx.schemas.instrument import ProfileTCHZ
    text = from_structure(_cubic("Mn"))
    u, v, w, x, y, gausiz = _width_line(text)
    default = ProfileTCHZ()
    assert (u, v, w) == (default.u.value, default.v.value, default.w.value)
    assert w > 0.0
    assert (x, y) == (default.y.value, default.x.value)
    assert _lines(text)[1].split()[1] == "7"
    assert _lines(text)[_lines(text).index("syn") + 1].split()[13] == "7"


def test_the_widths_are_the_instruments_plus_the_phases_under_fullprofs_letters():
    """FullProf Npr = 7 (manual eqs 3.24-3.25): H_G^2 = U tan^2 + V tan + W +
    IG/cos^2 and H_L = X tan + Y/cos — so FullProf's X is rietx's strain
    ``y`` and its Y rietx's size ``x``, and each phase carries its own sample
    terms. Checked by evaluating FullProf's own formulas on the written
    numbers against rietx's width laws, at three angles."""
    import math

    from rietx.model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
    sample = dict(gauss_size=0.002, lor_size=0.01, gauss_strain=0.01,
                  lor_strain=0.02)
    structure = _cubic("Mn", **{k: rx.Parameter(value=v, min=0.0)
                                for k, v in sample.items()})
    inst = _xray(1.5405929, profile=_widths(u=0.02, v=-0.01, w=0.005, x=0.01,
                                            y=0.03))
    u, v, w, x, y, ig = _width_line(from_structure(structure, instrument=inst))
    assert (u, v, w, x, y, ig) == pytest.approx(
        (0.03, -0.01, 0.005, 0.05, 0.02, 0.002), abs=1e-15)
    p = inst.profile
    for theta in (10.0, 35.0, 70.0):
        t, c = math.tan(math.radians(theta)), math.cos(math.radians(theta))
        h_g = math.sqrt(u * t * t + v * t + w + ig / (c * c))
        h_l = x * t + y / c
        assert h_g == pytest.approx(gaussian_fwhm(
            theta, p.u.value, p.v.value, p.w.value, sample["gauss_size"],
            sample["gauss_strain"]), rel=1e-12)
        assert h_l == pytest.approx(lorentzian_fwhm(
            theta, p.x.value + sample["lor_size"],
            p.y.value + sample["lor_strain"]), rel=1e-12)


@pytest.mark.parametrize("instrument, expected", [
    (None, ("0", 1.5405929, 1.5444274, 0.5)),
    ("ka1", ("0", 1.5405929, 1.5405929, 0.0)),
    ("doublet", ("0", 1.5405929, 1.5444274, 0.46)),
    ("neutron", ("1", 2.41, 2.41, 0.0)),
])
def test_the_radiation_is_the_instruments(instrument, expected):
    """LINE 4's Job and LINE 8's Lambda1/Lambda2/Ratio: one X-ray line writes
    Lambda2 = Lambda1 and Ratio 0 ("=lambda1 for monochromatic beam"), two write
    the second line's relative weight, a CW neutron source is Job = 1."""
    inst = {None: None, "ka1": _xray(1.5405929),
            "doublet": _xray(1.5405929, 1.5444274),
            "neutron": rx.Instrument.constant_wavelength_neutron(2.41)}[instrument]
    lines = _lines(from_structure(_cubic("Mn"), instrument=inst))
    job = lines[1].split()[0]
    lam1, lam2, ratio = (float(v) for v in lines[3].split()[:3])
    assert (job, lam1, lam2, ratio) == expected


@pytest.mark.parametrize("change, match", [
    ("voigt", "no exact Voigt"),
    ("microstrain", "Stephens"),
    ("axial", "axial divergence"),
    ("harmonics", "harmonics"),
    ("three_lines", "3 emission lines"),
])
def test_what_would_change_the_profile_fullprof_computes_is_refused(change, match):
    """Each of these is a profile term the file has no slot for (or none this
    writer maps), so writing without it would state narrower, symmetric or
    single-line peaks where rietx computes others."""
    structure, inst = _cubic("Mn"), _xray(1.5405929)
    if change == "voigt":
        inst.profile.shape = "voigt"
    elif change == "microstrain":
        structure.phases[0].microstrain = rx.StephensStrain()
    elif change == "axial":
        inst.geometry.axial_sl.value = 0.02
    elif change == "harmonics":
        inst = rx.Instrument.constant_wavelength_neutron(2.41, harmonics=True)
    else:
        inst = _xray(1.5405929, 1.5444274, 1.39222)
    with pytest.raises(ValueError, match=match):
        from_structure(structure, instrument=inst)


def test_a_time_of_flight_or_foreign_instrument_is_refused_by_type():
    with pytest.raises(TypeError, match="constant-wavelength"):
        from_structure(_cubic("Mn"), instrument=object())


@pytest.mark.parametrize("species, xray, neutron", [
    # measured, FullProf.2k 8.20 (#558): the IUCr order stops an X-ray run
    # ("Scattering coefficients NOT FOUND for * Zr4+ *"), the sign-first key
    # runs; a neutron run keys b on the element and stops on `O-2`.
    ("Zr4+", "ZR+4", "ZR"),
    ("O2-", "O-2", "O"),
    ("Cu1+", "CU+1", "CU"),
    ("Mn", "MN", "MN"),
])
def test_a_species_is_written_in_fullprofs_key_for_the_radiation(species, xray,
                                                                 neutron):
    from rietx.io.projects.fullprof import fullprof_species
    assert fullprof_species(species, neutron=False) == (xray, None)
    assert fullprof_species(species, neutron=True) == (neutron, None)
    assert normalize_species(xray) == species


@pytest.mark.parametrize("species, nam, b_fm", [
    ("7Li", "LI7", -2.22),
    ("7Li1+", "LI7", -2.22),
    ("D", "H2", 6.671),
    ("2H", "H2", 6.671),
    ("60Ni", "NI60", 2.8),
])
def test_an_isotope_goes_to_fullprof_as_a_line12_user_b(species, nam, b_fm):
    """#558: FullProf keys b on the element, so a bare `LI7` runs at natural
    abundance (b = -1.90 fm) with no message. The isotope is written only with
    its LINE-12 b, which FullProf uses (measured -0.222 x 10^-12 cm)."""
    from rietx.io.projects.fullprof import fullprof_species
    assert fullprof_species(species, neutron=True) == (nam, pytest.approx(b_fm))
    text = from_structure(_cubic(species, "O"),
                          instrument=rx.Instrument.constant_wavelength_neutron(1.5406))
    lines = _lines(text)
    assert lines[1].split()[5] == "1"                   # Nsc
    assert lines[7].split() == [nam, repr(round(b_fm / 10, 8)), "0.0", "0"]
    assert lines[8] == "0"                              # then LINE 13, Maxs
    assert any(line.startswith(f"A0 {nam} ") for line in lines)


@pytest.mark.parametrize("species, neutron, match", [
    ("7Li", False, "X-ray .pcr cannot state one"),
    ("D", False, "X-ray .pcr cannot state one"),
    ("157Gd", True, "A4"),
])
def test_a_species_fullprof_cannot_state_is_refused_by_name(species, neutron, match):
    """An isotope on an X-ray file (no isotope label; LINE 12 there is
    anomalous dispersion), and an isotope whose NAM exceeds four characters
    (`GD157` stops FullProf's parse, measured). The refusal names the phase
    and the atom."""
    inst = rx.Instrument.constant_wavelength_neutron(1.5406) if neutron else None
    with pytest.raises(ValueError, match=match) as exc:
        from_structure(_cubic(species), instrument=inst)
    assert "phase 'syn': atom 'A0'" in str(exc.value)


def test_an_isotope_round_trips_through_line12(tmp_path):
    """The reader takes a LINE-12 b back as the isotope it is the Sears b of,
    and says so; and the structure is otherwise the one written."""
    structure = _cubic("7Li1+", "O2-")
    out = tmp_path / "iso.pcr"
    write_fullprof_pcr(structure, out,
                       instrument=rx.Instrument.constant_wavelength_neutron(1.5406))
    model = read_fullprof_pcr(out)
    assert model.user_scatterers == {"LI7": (pytest.approx(-2.22), "7Li")}
    diagnostics = []
    back = to_structure(model, diagnostics=diagnostics)
    assert [a.species for a in back.phases[0].atoms] == ["7Li", "O"]
    said = [d.message for d in diagnostics if d.code == "FULLPROF_SPECIES_NORMALISED"]
    assert any("'LI7'" in m and "Sears b" in m for m in said)


def _with_line12(tmp_path, line, job="1"):
    text = from_structure(_cubic("7Li", "O"),
                          instrument=rx.Instrument.constant_wavelength_neutron(1.5406))
    lines = _lines(text)
    lines[7] = line
    fields = lines[1].split()
    fields[0] = job
    lines[1] = " ".join(fields)
    path = tmp_path / "line12.pcr"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("line, job, match", [
    ("LI7 -0.19 0.0 0", "1", "neither"),            # natural Li's b under an isotope name
    ("DEU 0.6671 0.0 0", "1", "neither"),           # a user name rietx cannot map
    ("LI7 -0.222 0.0 1", "1", "ITY = 1"),           # a magnetic form factor
    ("LI7 -0.222 0.0 0", "0", "only 'NAM DFP DFPP 2'"),  # X-ray: f'/f'' plus a coefficient line
])
def test_a_line12_rietx_has_no_species_for_is_refused_at_read(tmp_path, line, job,
                                                               match):
    with pytest.raises(FullProfPcrError, match=match):
        read_fullprof_pcr(_with_line12(tmp_path, line, job))


# -- #568 review: every value written is guarded, and what is dropped is dropped
#    only at its identity --------------------------------------------------------


def _set(obj, dotted, value):
    *head, last = dotted.split(".")
    for part in head:
        obj = obj[int(part)] if part.isdigit() else getattr(obj, part)
    setattr(obj, last, value)


def _make_infinite(param, bad):
    """A Parameter's own bounds refuse ±inf until they are opened (as the
    cell test above does), and NaN never validates, so ±inf is what reaches
    the writer."""
    param.min, param.max = float("-inf"), float("inf")
    param.value = bad


@pytest.mark.parametrize("path, field", [
    ("source.lines.0.wavelength", "instrument.source.lines.0.wavelength"),
    ("source.lines.1.wavelength", "instrument.source.lines.1.wavelength"),
    ("source.lines.1.weight", "instrument.source.lines.1.weight"),
    ("profile.u", "instrument.profile.u"),
    ("profile.w", "instrument.profile.w"),
    ("profile.x", "instrument.profile.x"),
    ("profile.y", "instrument.profile.y"),
])
@pytest.mark.parametrize("bad", [float("inf"), float("-inf")])
def test_a_non_finite_instrument_value_is_refused_naming_the_field(path, field, bad):
    inst = _xray(1.5405929, 1.5444274)
    from_structure(_cubic("Mn"), instrument=inst)       # the control writes
    obj = inst
    for part in path.split("."):
        obj = obj[int(part)] if part.isdigit() else getattr(obj, part)
    _make_infinite(obj, bad)
    with pytest.raises(ValueError, match=re.escape(field) + ".*FullProf does not parse"):
        from_structure(_cubic("Mn"), instrument=inst)


@pytest.mark.parametrize("term", ["gauss_strain", "gauss_size", "lor_strain", "lor_size"])
def test_a_non_finite_phase_broadening_is_refused_naming_it(term):
    st = _cubic("Mn")
    _make_infinite(getattr(st.phases[0], term), float("inf"))
    with pytest.raises(ValueError, match=f"phase 'syn' {term} is inf"):
        from_structure(st, instrument=_xray(1.5405929))


def test_a_doublet_weight_fullprof_cannot_state_is_refused():
    """A first line of weight 0 has no ratio (it raised a bare
    ZeroDivisionError); a negative second weight would write a negative Ratio,
    FullProf's flag for a second U, V, W block."""
    inst = _xray(1.5405929, 1.5444274)
    inst.source.lines[0].weight.value = 0.0
    with pytest.raises(ValueError, match=r"lines\.0\.weight is 0\.0"):
        from_structure(_cubic("Mn"), instrument=inst)
    inst = _xray(1.5405929, 1.5444274)
    inst.source.lines[1].weight.min = -1.0                # the field's bound is 0
    inst.source.lines[1].weight.value = -0.2
    with pytest.raises(ValueError, match=r"lines\.1\.weight is -0\.2.*negative LINE 8 Ratio"):
        from_structure(_cubic("Mn"), instrument=inst)
    inst.source.lines[1].weight.value = 0.0               # no second line's worth: fine
    assert _lines(from_structure(_cubic("Mn"), instrument=inst))[3].split()[2] == "0.0"


def test_a_partly_occupied_site_is_refused():
    """Occ is written as m/M, the full site, so occ = 0.5 would go out whole."""
    st = _cubic("Y", "Mn")
    st.phases[0].atoms[0].occ.value = 0.5
    with pytest.raises(ValueError, match="atom 'A0' has occ = 0.5"):
        from_structure(st)
    st.phases[0].atoms[0].occ.value = 1.0
    from_structure(st)


@pytest.mark.parametrize("path, value, match", [
    ("zero_shift.value", 0.01, "instrument.zero_shift is 0.01"),
    ("geometry.sample_displacement.value", 0.02, "sample_displacement is 0.02"),
    ("geometry.sample_transparency.value", 0.01, "sample_transparency is 0.01"),
    ("geometry.capillary_offset_along_beam.value", 0.1, "capillary_offset_along_beam"),
    ("geometry.capillary_offset_across_beam.value", 0.1, "capillary_offset_across_beam"),
    ("geometry.mu_t", 0.4, "mu_t or thickness_mm is declared"),
    ("geometry.thickness_mm", 0.2, "mu_t or thickness_mm is declared"),
    ("geometry.kind", "flat_plate_transmission", "flat_plate_transmission"),
    ("source.polarization.value", 0.99, "polarization is 0.99"),
])
def test_an_instrument_term_away_from_its_identity_is_refused(path, value, match):
    """The file states none of these, so a non-identity value would compute
    a different model; at the identity (the control) it is dropped."""
    inst = _xray(1.5405929)
    from_structure(_cubic("Mn"), instrument=inst)
    _set(inst, path, value)
    with pytest.raises(ValueError, match=match):
        from_structure(_cubic("Mn"), instrument=inst)


def test_capillary_absorption_surface_roughness_and_extra_components_are_refused():
    from rietx.schemas.instrument import HumpComponent, RoughnessSuortti
    inst = _xray(1.5405929)
    inst.geometry.kind = "debye_scherrer"
    from_structure(_cubic("Mn"), instrument=inst)          # mu_r None, no radius: off
    inst.geometry.mu_r = 0.0
    from_structure(_cubic("Mn"), instrument=inst)          # 0 is off exactly
    inst.geometry.mu_r = 0.8
    with pytest.raises(ValueError, match="mu_r is 0.8"):
        from_structure(_cubic("Mn"), instrument=inst)
    inst.geometry.mu_r, inst.geometry.capillary_radius_mm = None, 0.35
    with pytest.raises(ValueError, match="estimates a mu_r"):
        from_structure(_cubic("Mn"), instrument=inst)
    inst = _xray(1.5405929)
    inst.geometry.surface_roughness = RoughnessSuortti()
    with pytest.raises(ValueError, match="surface_roughness is a 'suortti' model"):
        from_structure(_cubic("Mn"), instrument=inst)
    inst = _xray(1.5405929)
    inst.extra_components = [HumpComponent(position=rx.Parameter(value=20.0),
                                           height=rx.Parameter(value=5.0),
                                           fwhm=rx.Parameter(value=8.0))]
    with pytest.raises(ValueError, match="extra_components holds 1"):
        from_structure(_cubic("Mn"), instrument=inst)


def test_preferred_orientation_and_extinction_away_from_identity_are_refused():
    st = _cubic("Mn")
    st.phases[0].preferred_orientation = rx.PreferredOrientation(
        axis=(0, 0, 1), r=rx.Parameter(value=1.0))
    from_structure(st)                                      # r = 1 is no texture
    st.phases[0].preferred_orientation.r.value = 0.8
    with pytest.raises(ValueError, match=r"March-Dollase .*r = 0\.8"):
        from_structure(st)
    st = _cubic("Mn")
    st.phases[0].extinction.value = 500.0
    with pytest.raises(ValueError, match="extinction = 500.0"):
        from_structure(st)


def _line12(text):
    lines = _lines(text)
    nsc = int(lines[1].split()[5])
    start = lines.index("155.0 10.0 0.0") + 1
    return [line.split() for line in lines[start:start + nsc]]


def test_an_xray_file_states_rietx_s_own_anomalous_dispersion(tmp_path):
    """FullProf applies its own f'/f'' to a file without LINE 12 (measured,
    8.20: Fe at 1.85 Å is −2.095/0.566 there, Cromer-Liberman −2.548/0.521),
    so every X-ray Typ gets an ITY = 2 line with rietx's values, lower-case
    NAM; the reader reads them past. A pair that reader would refuse is
    refused at write (round 3)."""
    from rietx.crystallography.dispersion import dispersion
    from rietx.schemas.instrument import Dispersion
    st = _cubic("Zr4+", "O2-", "Zr4+")
    text = from_structure(st, instrument=_xray(1.85, dispersion=Dispersion()))
    want = [["zr+4", *map(repr, dispersion("Zr", 1.85)), "2"],
            ["o-2", *map(repr, dispersion("O", 1.85)), "2"]]
    assert _line12(text) == want
    # a pair the reader would refuse is refused at write, naming the atom and why
    with pytest.raises(ValueError, match=r"atom .*f' = 0\.0.*could not be read back"):
        from_structure(st, instrument=_xray(1.85, dispersion=None))
    with pytest.raises(ValueError, match=r"f' = -7\.5.*could not be read back"):
        from_structure(st, instrument=_xray(1.85, dispersion=Dispersion(
            overrides={"Zr": (-7.5, 1.25)})))
    # an override inside the reader's tolerance is rietx's value, so it is what is written
    f1, f2 = dispersion("Zr", 1.85)
    near = from_structure(st, instrument=_xray(1.85, dispersion=Dispersion(
        overrides={"Zr": (f1 + 0.005, f2)})))
    assert _line12(near)[0] == ["zr+4", repr(f1 + 0.005), repr(f2), "2"]
    p_near = tmp_path / "near.pcr"
    p_near.write_text(near, encoding="utf-8")
    to_structure(read_fullprof_pcr(p_near))
    # no instrument: Cu Kα1's, the line the default doublet is resolved at
    assert _line12(from_structure(_cubic("Fe")))[0] == [
        "fe", *map(repr, dispersion("Fe", 1.5405929)), "2"]
    path = tmp_path / "anomalous.pcr"
    path.write_text(text, encoding="utf-8")
    back = to_structure(read_fullprof_pcr(path))
    assert [a.species for a in back.phases[0].atoms] == ["Zr4+", "O2-", "Zr4+"]


def test_a_structure_only_export_names_the_way_out_of_an_edge_element():
    """#568 round 2, item 1: with no instrument the dispersion is resolved at
    the placeholder Cu K\u03b1 lines, which refuse Eu and Ho (an edge between
    them); the message must say the caller never chose them and name the way
    out, which is an instrument whose wavelength has a value for it."""
    for el in ("Eu", "Ho"):
        with pytest.raises(ValueError, match=r"No instrument was given.*instrument="):
            from_structure(_cubic(el))
        # positive arm: the named way out writes
        text = from_structure(_cubic(el), instrument=_xray(0.7093))
        assert _line12(text)[0][0] == el.lower()
    # an element without an edge there is unchanged
    assert from_structure(_cubic("Fe"))


def _xray_pcr(tmp_path, *, edit=None):
    from rietx.schemas.instrument import Dispersion
    text = from_structure(_cubic("Fe"), instrument=_xray(1.85, dispersion=Dispersion()))
    if edit is not None:
        lines = text.splitlines()
        i = next(k for k, line in enumerate(lines) if line.startswith("fe "))
        lines[i] = edit
        text = "\n".join(lines) + "\n"
    path = tmp_path / "xray.pcr"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_reader_reads_a_files_own_dispersion_and_refuses_a_different_one(tmp_path):
    """#568 round 2, item 2: a stated f'/f'' was checked for shape and dropped,
    so the fit ran on Cromer-Liberman values whatever the file said (FullProf's
    Fe at 1.85 \u00c5 is -2.095/0.566 against -2.548/0.521: 9.7 % in R)."""
    from rietx.crystallography.dispersion import dispersion
    # positive arm: a file the writer produced reads back, and the pair is kept
    model = read_fullprof_pcr(_xray_pcr(tmp_path))
    assert model.dispersion["Fe"] == pytest.approx(dispersion("Fe", 1.85))
    to_structure(model)
    # within the stated tolerance (a three-decimal rounding of rietx's pair)
    f1, f2 = dispersion("Fe", 1.85)
    read_fullprof_pcr(_xray_pcr(tmp_path, edit=f"fe {f1:.3f} {f2:.3f} 2"))
    # FullProf's own pair for Fe at 1.85 \u00c5 differs by 0.45 e: refused, by name
    with pytest.raises(FullProfPcrError, match=r"f' = -2\.095.*Fe.*Dispersion\.overrides"):
        read_fullprof_pcr(_xray_pcr(tmp_path, edit="fe -2.095 0.566 2"))
    # zeros state f = f0, which a Structure cannot carry (the writer refuses them too)
    with pytest.raises(FullProfPcrError, match=r"f' = 0\.0"):
        read_fullprof_pcr(_xray_pcr(tmp_path, edit="fe 0.0 0.0 2"))


def test_a_neutron_file_writes_a_digitless_ion_as_its_element():
    """Follow-up 7: a neutron file keys b on the element, and rietx and
    FullProf both give Cu+ Cu's b."""
    text = from_structure(_cubic("Cu+"),
                          instrument=rx.Instrument.constant_wavelength_neutron(1.5406))
    assert any(line.startswith("A0 CU ") for line in _lines(text))


@pytest.mark.parametrize("species, xray, neutron", [
    # WP-1527: the atom rietx computes, in the measured keys above. A
    # digitless ion is the tabulated one; an untabulated ion is neutral.
    ("Cu+", "CU+1", "CU"),
    ("Na+", "NA+1", "NA"),
    ("Fe+", "FE", "FE"),
])
def test_a_digitless_ion_is_written_as_the_atom_rietx_computes(species, xray,
                                                               neutron):
    from rietx.crystallography.scattering import written_species
    from rietx.io.projects.fullprof import fullprof_species
    assert fullprof_species(species, neutron=False) == (xray, None)
    assert fullprof_species(species, neutron=True) == (neutron, None)
    assert normalize_species(xray) == written_species(species)[0]


@pytest.mark.parametrize("instrument, named", [
    (None, True),
    (rx.Instrument.constant_wavelength_neutron(1.5406), False),
])
def test_a_written_ion_reads_back_and_a_substitution_is_named(tmp_path,
                                                              instrument, named):
    """The maintainer's rule (WP-1527, 2026-10-03): `Cu+` round-trips as the
    ion on an X-ray file, and `Fe+`, which rietx computes as neutral Fe, is
    written so and named. A neutron file writes the element for every ion
    and substitutes nothing, so it names nothing."""
    diagnostics: list = []
    out = tmp_path / "ions.pcr"
    write_fullprof_pcr(_cubic("Cu+", "Fe+"), out, instrument=instrument,
                       diagnostics=diagnostics)
    back = to_structure(read_fullprof_pcr(out))
    assert [a.species for a in back.phases[0].atoms] == (
        ["Cu1+", "Fe"] if instrument is None else ["Cu", "Fe"])
    rows = [d for d in diagnostics
            if d.code == "FULLPROF_SPECIES_WRITTEN_NEUTRAL"]
    assert [d.where for d in rows] == (
        [["phases.0.atoms.1.species"]] if named else [])
