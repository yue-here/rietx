"""Read a FullProf ``.pcr`` refinement control file into a rietx model.

Format: FullProf Suite (Rodríguez-Carvajal) ``.pcr`` control files. FullProf is
closed source; **this reader is written from the file layout alone plus the
published format description**, as ``ATTRIBUTION.md``'s fence requires — no
FullProf code was read, no source file was consulted, and every layout fact
below is quoted in a comment from a real file at a real line so that the
evidence for it is checkable. The corpus is the maintainer's own unpublished
research data, so the files are cited as **corpus file 1** to **6** and the map
from number to file is not public; the maintainer holds it in the private
repository ``yue-here/rietx-corpus-map``. Where a real file is the *only*
evidence for a block's position, that is said, and where there is no evidence at all the construct is **refused
by name** rather than parsed on a guess.

Why the format is worth reading: a ``.pcr`` carries the whole solved model — the
phases, the sites, the cell, the instrument resolution function and, in the
header comments FullProf rewrites on every cycle, the converged χ² and per-phase
R_Bragg. That makes it the cheapest possible source of a *validated* refinement
to test against, exactly as a TOPAS ``.inp`` is (the sibling ``projects/topas.py``
reader, where it has landed — PR #98).

Scope — what this reader claims
-------------------------------

**Handled completely: the single-pattern, constant-wavelength, nuclear case**
(``Job`` 0 or 1, one diffraction pattern, ``Jbt = 0`` phases). For those, every
value and every refinement codeword is read, the counts the file declares are
asserted against the lines actually parsed, and :func:`to_structure` builds a
:class:`~rietx.schemas.Structure`.

**Read but not modelled: magnetic phases** (``Jbt = 1``, both ``Isy = -1`` and
``Isy = -2`` sub-grammars). rietx *does* have a magnetic model since WP-1327 —
a moment on a site of a nuclear phase, under a magnetic space group given as an
operator list — and a ``Jbt = 1`` phase still does not fit it, for the two
reasons :data:`MAGNETIC_PHASE_REFUSAL` states: it is a **pure magnetic** phase
with its own scale and no nuclear half (FullProf's spelling of a TOPAS
``mag_only``), and its symmetry is a magnetic *representation* whose matrices
need not be the Shubnikov axial action. So a
magnetic phase cannot become a :class:`~rietx.schemas.Phase`. It is neither
dropped nor allowed to make the file unreadable: :func:`read_fullprof_pcr`
returns it in full on :attr:`FullProfModel.phases`, and
:func:`to_structure` **refuses**, naming every magnetic phase it would have
had to omit. See the design note below — four of the six real files this
reader was written against have a magnetic phase, so silently returning their
nuclear half is the single most damaging thing it could do.

**Refused by name, at read:** neutron time-of-flight (``Job = -1``), the
multi-pattern ``NPATT`` layout (a different grammar throughout, not merely a
different control-line header), a polynomial or Fourier background, single-
crystal/integrated-intensity jobs (``Cry``), restraint blocks, and every
control-line flag whose non-zero meaning would add lines this reader has no
file to establish the position of. Each refusal names the file, the field and
the value.

The three design decisions, and why
-----------------------------------

1. **A magnetic phase is carried, and the refusal is at build time.** Root
   CLAUDE.md's rule is *report or refuse, never drop*, and the choice here is
   between refusing the whole file at read and refusing only the build. Refusing
   at read throws away facts the reader read correctly — the nuclear phases, the
   wavelength, the agreement factors — because of a phase nobody asked it to
   build; and it would make 4 of the 6 real files simply unreadable, which is a
   reader nobody can use on the archive it was written for. Refusing at
   :func:`to_structure` puts the refusal exactly where the impossible thing is
   asked for, and :attr:`FullProfModel.magnetic_phases` is how the model
   *says* what it read. A caller who genuinely wants the nuclear subset passes
   ``nuclear_only=True``: the omission is then a caller's declared choice, named
   in the refusal message it replaces, rather than a reader's silence.

2. **TOF is refused at read, and so is every multi-bank file.** ``Job = -1``
   changes the meaning of the abscissa (TOF in µs, not degrees 2θ) and of the
   whole profile block (Sig-2/Sig-1/Sig-0, Gam-2/Gam-1/Gam-0, α₀/β₀/α₁ in place
   of Caglioti U/V/W and the asymmetry terms), and rietx has neither. The one
   real TOF file here is additionally ``NPATT 6``: **six patterns**, six
   independent control lines, six background blocks and six copies of every
   phase's profile block, sharing one set of atoms. That is a joint refinement
   over six detector banks — rietx's ``multi.py`` shape, not ``sequential.py``'s
   — and reading it would mean deciding *which* bank's resolution function to
   return, which is a question the file does not answer. Refused at the first
   line that says so (``NPATT``), before any of it is parsed.

3. **FullProf's ``Occ`` column is not rietx's ``occ``, and the difference is
   verified rather than assumed.** FullProf writes an occupancy already scaled
   by the site multiplicity over the general multiplicity, and the *absolute*
   normalisation of that column is degenerate with the phase scale factor —
   doubling every ``Occ`` and halving ``Scale`` is the same pattern. So the
   quantity a file states is a set of site occupancies *up to one arbitrary
   common factor*, and the corpus proves the factor is not conventional: two
   corpus files carry a factor of 2 where two others carry 1. What is recoverable is the *ratio* between sites, so
   :func:`to_structure` divides each ``Occ`` by its site multiplicity, and
   **requires the result to be the same for every atom in the phase** — which
   is the statement "this phase is fully occupied", the only case where the
   arbitrary factor cancels. A phase where it is not constant is **refused**,
   naming the ratios, because a partially occupied site's chemical occupancy is
   not in the file. Handing the column straight through would be a silently
   wrong structure factor, which is the failure class this whole module exists
   to avoid.

Four traps, all verified against the real files
-----------------------------------------------

1. **The ``!  Data for PHASE number: N`` comments lie.** In
   ``corpus file 1`` the *third* phase block is labelled ``PHASE number:
   1``. Phases are therefore parsed **positionally against ``Nph``** and the
   comment's index is recorded as :attr:`FullProfPhase.labelled_index` for
   provenance only. The parsed count is asserted against ``Nph``.

2. **Field names change with ``Jbt``.** The third column of a phase's control
   line is headed ``Ang`` when ``Jbt = 0`` and ``Mom`` when ``Jbt = 1``, in the
   same position — so a parser keyed on the header comment breaks on exactly
   the phase that matters. Nothing here reads a header comment: every block is
   located by walking the *data* lines in order, comments are dropped before the
   walk begins, and the column names are this module's own tables
   (:data:`_CELL_COLUMNS` and friends) zipped positionally.

3. **A stale λ sits in the refinable-λ slot.** ``corpus file 2`` has
   ``2.370100`` in the ``Zero Code SyCos Code SySin Code Lambda Code`` line
   while the refinement's real wavelength is the ``2.077100`` of the
   ``Lambda1 Lambda2`` line. Its codeword is ``0.00``, so it is inert and
   FullProf never used it. It is read into :attr:`FullProfModel.lambda_slot`,
   which is documented as *not* the wavelength; :attr:`FullProfModel.lambda1`
   is.

4. **The file's own refined-parameter count can be stale.**
   ``corpus file 3`` declares 64 refined parameters and carries a
   codeword for parameter 65. Both numbers are reported —
   :attr:`FullProfModel.refined_parameter_count` is the declaration and
   :attr:`FullProfModel.parameter_numbers` the set actually referenced — and
   neither is silently corrected into the other, because which of the two is
   wrong is not something the file says.

One grammar for a refined value
-------------------------------

Every refinable scalar in a ``.pcr`` is a number paired with a **codeword**,
and the codeword carries two facts at once: ``10 × parameter_number +
multiplier``, signed. So it says *which* free parameter drives the value and
with what sign — which is how a ``.pcr`` writes a tie. ``corpus file 1``'s
two Cr sublattices carry ``11.00`` and ``-11.00`` on the same basis-vector
coefficient: one parameter, opposite signs, i.e. the antiferromagnetic
constraint, and a reader that recorded only "refined" would lose the physics.
:class:`Code` is that decoding and :class:`Value` is the pair.

``0.00`` means fixed, and unlike a TOPAS ``.inp`` the slot is *always written* —
so the tri-state's third state is not "the file said nothing about this
parameter" but "the codeword column is not there at all", which happens only on
a ragged or truncated line. :attr:`Value.vary` is ``None`` exactly then, and
never collapses an absent column into ``False``.

Where the codeword sits is **not** uniform, and both spellings are real: the
atom, profile, cell and asymmetry blocks put it on the *following* line, while
the background points, the zero-shift line and the absorption line carry it
**inline** as the next column. Nothing here assumes one.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ...schemas.common import Diagnostic, Parameter
from ..formats.base import decode

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ...schemas import Structure

# --------------------------------------------------------------------- errors


#: Why a ``Jbt = 1`` phase is refused, once, so the read-time report and the
#: build-time refusal cannot drift apart (WP-1328).
#:
#: **The reason changed and the old one had gone stale**, which is the failure
#: worth naming here: until WP-1327 the sentence was "rietx has no magnetic
#: scattering model", and that is now false — rietx has one. What it does not
#: have is a shape for *this* construct, and the two are different refusals with
#: different remedies. A ``Jbt = 1`` phase is a **pure magnetic** phase, which
#: is FullProf's spelling of what a TOPAS ``.inp`` writes as ``mag_only``
#: (:mod:`.coverage` refuses that keyword for the same argument): only the
#: magnetic atoms are listed (``Nat 1`` in the corpus's ``Isy = -1`` file), the
#: species is a magnetic form-factor table name rather than an element
#: (``MCR3``), the symbol line is the placeholder ``P -1`` rather than a space
#: group, and the phase carries its **own** ``Scale``. WP-1327's model is a
#: moment on a site of a *nuclear* phase sharing one scale, so there is nothing
#: here for the file's own decomposition to land in.
#:
#: The symmetry is the second half, and it is the harder one. FullProf states a
#: magnetic phase's symmetry as a **magnetic representation** — ``SYMM`` with
#: one or more magnetic matrices ``MSYM`` *and a phase*, or basis vectors of an
#: irrep (``BASR``/``BASI``) — and those matrices are not required to be the
#: Shubnikov axial action ε·det(R)·R that WP-1327's operator list stores. The
#: corpus's own ``Isy = -1`` pair is the evidence for the caution rather than
#: against it: ``SYMM Y, X, -Z+1`` with ``MSYM -u,-v,w`` gives a moment matrix
#: of diag(−1,−1,1) where ε·det(R)·R for that rotation is the off-diagonal
#: (v, u, −w), so the two cannot both be read as a Shubnikov operator, and
#: **which reading is right is not something any file on this tree settles**.
#: So the conversion is refused rather than guessed, per ``io/CLAUDE.md``'s rule
#: for a construct with no evidence: a wrong ε is a fit under the wrong magnetic
#: group, reported with a confident esd.
MAGNETIC_PHASE_REFUSAL = (
    "A Jbt = 1 phase is a *pure magnetic* phase — no nuclear structure factor, "
    "its own Scale, only the magnetic atoms listed, and a magnetic "
    "form-factor label in the species column — and rietx's magnetic model is a "
    "moment on a site of a nuclear phase sharing one scale (WP-1327), so the "
    "file's own decomposition has nowhere to land. Its symmetry is a magnetic "
    "*representation* besides (SYMM with magnetic matrices and a phase under "
    "Isy = -1, basis vectors of an irrep under Isy = -2), and those matrices "
    "need not be the Shubnikov axial action eps*det(R)*R that a magnetic space "
    "group's operator list is, so converting them would be a guess about the "
    "physics rather than a reading of the file. What would make this readable: "
    "the phase restated as a nuclear phase carrying moments — which is what a "
    "magCIF states, and `rietx.Structure.from_cif` reads one (WP-1328) — or a "
    "file that settles FullProf's MSYM convention against a known magnetic "
    "space group.")


class FullProfPcrError(ValueError):
    """Raised naming the file and the offending line, never a bare parse miss.

    `io/CLAUDE.md`'s refusal rule: a reader raises naming the file, never its
    parser's exception. A ``.pcr`` is a positional format, so an unexpected
    field count desynchronises everything after it — which is why this is
    raised on the *first* line that does not fit rather than carried forward.
    """


# ------------------------------------------------------- the column-name tables
#
# These names are **this module's**, not the file's. A `.pcr` states its columns
# in a `!` comment line whose text changes with `Jbt` (trap 2), so reading them
# is how a parser comes to mis-key exactly the magnetic phase. Every block below
# is therefore a fixed tuple zipped positionally onto the numbers of one line,
# and the header comment is dropped before the walk starts.
#
# Each tuple was read off a real file, named in the comment above it.

#: ``!Job Npr Nph Nba Nex Nsc Nor Dum Iwg Ilo Ias Res Ste Nre Cry Uni Cor Opt Aut``
#: — corpus file 2:4, values on :5. Nineteen fields; the count is
#: asserted, because an eighteen-field (pre-``Aut``) form would shift every
#: field after it and nothing in the corpus establishes which one is missing.
_CONTROL_FIELDS = (
    "job", "npr", "nph", "nba", "nex", "nsc", "nor", "dum", "iwg", "ilo",
    "ias", "res", "ste", "nre", "cry", "uni", "cor", "opt", "aut")

#: The control-line flags whose only observed value is 0 and whose non-zero
#: meaning either adds lines this reader has no file to place, or changes what
#: the abscissa *is*. Refused by name rather than ignored: ignoring a flag that
#: adds a line desynchronises the whole positional walk, and ignoring ``Uni``
#: would read a non-2θ abscissa as 2θ, which `io/CLAUDE.md`'s "the axis is never
#: trusted" forbids outright.
#:
#: ``Iwg``, ``Ilo``, ``Ias``, ``Npr`` and ``Aut`` are deliberately *not* here:
#: they change weighting, the profile function or FullProf's own parameter
#: numbering, none of which moves a line. ``corpus file 4`` has ``Aut 1``.
_MUST_BE_ZERO = {
    "nsc": "extra scattering-factor lines follow it",
    "nor": "its meaning is not established by any file here",
    "dum": "its meaning is not established by any file here",
    "res": "a resolution-function filename line follows it",
    "ste": "its meaning is not established by any file here",
    "nre": "restraint blocks follow it and their position is unevidenced",
    "cry": "it selects a single-crystal or integrated-intensity job, which is "
           "not a powder profile refinement",
    "uni": "it changes what the abscissa is, and reading a non-2θ axis as 2θ "
           "is the one repair a reader may never make",
    "cor": "its meaning is not established by any file here",
    "opt": "its meaning is not established by any file here",
}

#: ``!Ipr Ppl Ioc Mat Pcr Ls1 Ls2 Ls3 NLI Prf Ins Rpa Sym Hkl Fou Sho Ana`` —
#: corpus file 2:7, values on :8. Output-control switches only; recorded
#: for provenance and never acted on, because none of them moves a line.
_OUTPUT_FIELDS = (
    "ipr", "ppl", "ioc", "mat", "pcr", "ls1", "ls2", "ls3", "nli", "prf",
    "ins", "rpa", "sym", "hkl", "fou", "sho", "ana")

#: ``! Lambda1  Lambda2    Ratio    Bkpos    Wdt    Cthm     muR   AsyLim
#: Rpolarz  2nd-muR -> Patt# 1`` — corpus file 2:10, values on :11.
_PATTERN_FIELDS = (
    "lambda1", "lambda2", "ratio", "bkpos", "wdt", "cthm", "mur", "asylim",
    "rpolarz", "mur2")

#: ``!NCY  Eps  R_at  R_an  R_pr  R_gl     Thmin       Step       Thmax    PSD
#: Sent0`` — corpus file 2:13, values on :14.
_CYCLE_FIELDS = (
    "ncy", "eps", "r_at", "r_an", "r_pr", "r_gl", "thmin", "step", "thmax",
    "psd", "sent0")

#: ``!Nat Dis Ang Pr1 Pr2 Pr3 Jbt Irf Isy Str Furth       ATZ    Nvk Npr More``
#: — corpus file 2:83, values on :84; and the *same* fifteen positions
#: under the ``Mom`` spelling on :141/:142, which is trap 2. ``ang_or_mom`` is
#: deliberately one field: it is one column, and which of the two names it
#: carries is a function of ``Jbt``, not of the file's prose.
_PHASE_FIELDS = (
    "nat", "dis", "ang_or_mom", "pr1", "pr2", "pr3", "jbt", "irf", "isy",
    "str", "furth", "atz", "nvk", "npr", "more")

#: Which of :data:`_PHASE_FIELDS` are counts and selectors rather than
#: quantities. The line as a whole **cannot** go through :meth:`_Cursor.ints`
#: the way the top-level control lines do, and that is a fact about the format
#: rather than an oversight: ``Pr1 Pr2 Pr3`` are ``0.0 0.0 1.0`` and ``ATZ`` is
#: ``963.500`` in corpus file 2:84 and ``154213.406`` in
#: corpus file 4:66, so requiring the whole line to be integral would refuse
#: every real file. The eleven fields below are the ones whose value is a count
#: (``Nat``, ``Nvk``), a flag (``Dis``, ``Str``, ``Furth``, ``More``) or a
#: grammar selector (``Jbt``, ``Irf``, ``Isy``, ``Npr``, and ``Ang``/``Mom``),
#: and each is read through ``int()`` somewhere below. They get
#: :meth:`_Cursor.ints`'s ``.is_integer()`` guard field by field, because
#: truncating ``Jbt 1.5`` to nuclear — or ``Nat 3.5`` to three atoms — reads a
#: different file from the one on disk and desynchronises the positional walk.
_PHASE_INTEGER_FIELDS = (
    "nat", "dis", "ang_or_mom", "jbt", "irf", "isy", "str", "furth", "nvk",
    "npr", "more")

#: ``!  Zero    Code    SyCos    Code   SySin    Code  Lambda     Code MORE``
#: — corpus file 2:76, values on :77. The value/codeword pairs are
#: **inline** here, not on a following line. ``lambda_slot`` is trap 3: a stale
#: number with an inert codeword, and never the wavelength.
_ZERO_FIELDS = ("zero", "sycos", "sysin", "lambda_slot")

#: ``!  Scale        Shape1      Bov      Str1      Str2      Str3
#: Strain-Model`` — corpus file 2:97, values on :98, codewords on :99.
#: Six values plus a trailing integer model selector that has no codeword.
_SCALE_COLUMNS = ("scale", "shape1", "bov", "str1", "str2", "str3")

#: ``!       U         V          W           X          Y        GauSiz
#: LorSiz Size-Model`` — corpus file 2:100/:101/:102. Seven values plus
#: a trailing integer model selector. U/V/W are Caglioti in deg²(2θ); X/Y are
#: the Lorentzian pair, and note the root CLAUDE.md convention warning — GSAS
#: and FullProf swap the X/Y labels, so these are carried under FullProf's own
#: spelling and translated nowhere in this module.
_WIDTH_COLUMNS = ("u", "v", "w", "x", "y", "gausiz", "lorsiz")

#: ``!     a          b         c        alpha      beta       gamma`` —
#: corpus file 2:103/:104/:105. The codeword line is where a `.pcr`
#: writes a symmetry tie: ``51.00000 51.00000 61.00000`` ties a and b to
#: parameter 5 and c to parameter 6, which is the tetragonal constraint.
_CELL_COLUMNS = ("a", "b", "c", "alpha", "beta", "gamma")

#: ``!  Pref1    Pref2      Asy1     Asy2     Asy3     Asy4      S_L      D_L``
#: — corpus file 2:106/:107/:108. Eight values, eight codewords, no
#: trailing model selector.
_ASYM_COLUMNS = ("pref1", "pref2", "asy1", "asy2", "asy3", "asy4", "s_l", "d_l")

#: ``!Atom   Typ       X        Y        Z     Biso       Occ     In Fin N_t
#: Spc /Codes`` — corpus file 2:87, atom on :88, codewords on :89. The
#: label and the type consume the first two tokens; ``In``/``Fin``/``N_t``/
#: ``Spc`` are trailing integers with no codewords.
_ATOM_COLUMNS = ("x", "y", "z", "biso", "occ")

#: ``!Atom   Typ  Mag Vek    X      Y      Z       Biso    Occ      Rx  Ry  Rz``
#: then ``!     Ix     Iy     Iz    beta11  beta22  beta33    MagPh`` —
#: corpus file 2:157-162 (``Isy = -1``, real/imaginary moment
#: components) and corpus file 1:166-171 (``Isy = -2``, where the same
#: two columns are basis-vector coefficients ``C1..C3`` and ``C4..C9``). Same
#: positions, different physical meaning, so the names are neutral: a magnetic
#: atom occupies **four** lines — values, codewords, continuation, codewords.
_MAGNETIC_COLUMNS = ("x", "y", "z", "biso", "occ", "m1", "m2", "m3")
_MAGNETIC_CONTINUATION = ("m4", "m5", "m6", "m7", "m8", "m9", "magph")

#: What a nuclear phase's ``N_t`` adds to each atom. ``0`` is the isotropic
#: form every single-pattern file here uses; ``2`` adds an anisotropic β line
#: and its codeword line, evidenced by corpus file 5:187-190. Any
#: other value is refused, because how many lines it occupies is then a guess
#: and a wrong guess desynchronises the rest of the file.
_N_T_EXTRA_LINES = {0: 0, 2: 2}

#: FullProf writes ``beta11 beta22 beta33 beta12 beta13 beta23`` in this order
#: (corpus file 5:186). Read, and refused at :func:`to_structure` —
#: the β → U^ij conversion needs a convention (whether the stored off-diagonal
#: already carries the factor 2 of the exponent) that no file here settles, and
#: a wrong factor is a silently wrong Debye-Waller factor at high Q.
_BETA_COLUMNS = ("beta11", "beta22", "beta33", "beta12", "beta13", "beta23")


# ------------------------------------------------------------ codeword grammar


@dataclass(frozen=True)
class Code:
    """A FullProf refinement codeword, decoded.

    The encoding is ``10 × number + multiplier``, signed, so one number carries
    both *which* free parameter drives this value and the linear coefficient
    (usually ±1) with which it does. That is how a ``.pcr`` writes a tie: the
    two Cr sublattices of ``corpus file 1`` carry ``11.00`` and ``-11.00``
    on the same basis-vector coefficient — one parameter, opposite sign, the
    antiferromagnetic constraint — and the tetragonal cell of
    ``corpus file 2`` carries ``51.00000`` on both ``a`` and ``b``.

    A reader that recorded only "refined" would lose all of that, which is the
    same class of loss as the TOPAS reader's collapsed tri-state.
    """

    number: int
    multiplier: float
    #: The codeword exactly as the file wrote it, so a consumer can check the
    #: decoding rather than trust it.
    codeword: float


def decode_codeword(codeword: float) -> Code | None:
    """``601.0`` → parameter 60, multiplier +1; ``-11.00`` → parameter 1, −1.

    ``0.0`` is FullProf's spelling of *fixed* and returns None — the absence of
    a driving parameter, not parameter zero.

    A non-zero codeword that decodes to parameter **0** raises: that is a number
    no FullProf run writes — a truncated ``601.0`` reading as ``6`` is how one
    arises — and returning None for it would report a refined parameter as held,
    which is exactly the distinction a consumer of this function is making.
    """
    if codeword == 0.0:
        return None
    magnitude = abs(codeword)
    number = int(magnitude // 10)
    if number == 0:
        raise FullProfPcrError(
            f"codeword {codeword!r} decodes to parameter number 0, which no "
            f"FullProf refinement writes — the encoding is 10*number+multiplier")
    multiplier = round(magnitude - 10.0 * number, 6)
    return Code(number=number, multiplier=math.copysign(multiplier, codeword),
                codeword=codeword)


@dataclass(frozen=True)
class Value:
    """One scalar as the file states it, with its codeword.

    :attr:`vary` is a tri-state and the third state is narrower than a TOPAS
    ``.inp``'s. FullProf *always* writes the codeword slot, so "the file said
    nothing" is not reachable for a value whose line is intact; ``None`` means
    the codeword **column is absent** — a ragged or truncated line — and is
    never a stand-in for ``False``. Collapsing the two is how a reader comes to
    report a refined parameter as held.
    """

    value: float
    #: The codeword verbatim, or None where the codeword column is not there.
    codeword: float | None = None

    @property
    def vary(self) -> bool | None:
        """Was this value free in the refinement the file records?"""
        return None if self.codeword is None else self.codeword != 0.0

    @property
    def code(self) -> Code | None:
        """The decoded codeword: which parameter drives this, and with what sign."""
        return None if not self.codeword else decode_codeword(self.codeword)


# ------------------------------------------------------------------ the model


@dataclass
class FullProfAtom:
    """One site of a nuclear phase, or of a magnetic one.

    ``values`` is keyed by :data:`_ATOM_COLUMNS` for a nuclear site and by
    :data:`_MAGNETIC_COLUMNS` + :data:`_MAGNETIC_CONTINUATION` for a magnetic
    one — the *positions* named, never the header comment's words.
    """

    label: str
    #: The scattering-species token as the file wrote it (``CR``, ``MCR3``).
    species_raw: str
    #: The same token in IUCr spelling where it names an element (``Cr``); a
    #: magnetic form-factor label (``MCR3``) is left verbatim, since it names a
    #: table rietx has no counterpart for.
    species: str
    values: dict = field(default_factory=dict)
    #: ``In Fin N_t Spc`` — trailing integers with no codewords.
    flags: tuple = ()
    #: The anisotropic β block, where ``N_t = 2`` states one. Keyed by
    #: :data:`_BETA_COLUMNS`.
    betas: dict = field(default_factory=dict)

    @property
    def n_t(self) -> int:
        """FullProf's displacement-model selector for this site."""
        return int(self.flags[2]) if len(self.flags) > 2 else 0


@dataclass
class MagneticSymmetry:
    """A magnetic phase's symmetry sub-block, in whichever spelling it uses.

    ``Isy`` switches the whole grammar and both branches are in the corpus:

    * ``Isy = -1`` — ``Nsym Cen Laue MagMat`` then ``Nsym`` × (``SYMM``,
      ``MagMat`` × ``MSYM``); the atoms then carry real moment components
      ``Rx Ry Rz`` and imaginary ``Ix Iy Iz``
      (``corpus file 2``:145-162).
    * ``Isy = -2`` — ``Nsym Cen Laue Ireps N_Bas``, a real/imaginary indicator
      line of ``N_Bas`` values, then ``Nsym`` × (``SYMM``, ``|Ireps|`` ×
      (``BASR``, ``BASI``)) with ``3 × N_Bas`` numbers per basis line; the
      atoms then carry basis-vector coefficients ``C1..C9``
      (``corpus file 3``:145-161, ``corpus file 1``:145-164,
      ``corpus file 4``:98-108).

    Every count above is asserted, which is what makes the walk past an
    unmodelled block safe: this reader has to land on the next phase's first
    line exactly, and there is no keyword it could resynchronise on.
    """

    isy: int
    nsym: int
    cen: int
    laue: int
    #: ``MagMat`` under ``Isy = -1``; None under ``Isy = -2``.
    magmat: int | None = None
    #: ``Ireps`` and ``N_Bas`` under ``Isy = -2``; None under ``Isy = -1``.
    ireps: int | None = None
    n_bas: int | None = None
    #: The ``N_Bas`` real(0)/imaginary(1) indicators, ``Isy = -2`` only.
    real_imaginary: tuple = ()
    #: One entry per ``SYMM``: the operator text and the lines that follow it,
    #: verbatim. Verbatim because nothing here models them — carrying a parsed
    #: form would be a claim about a magnetic symmetry algebra this package does
    #: not have.
    operators: list = field(default_factory=list)


@dataclass
class SoftMomentConstraint:
    """One soft moment restraint: a target moment and its σ, keyed to a site.

    Both spellings in the corpus are the *same* production — an atom label
    truncated to the field's width — which is why this resolves the key by
    **prefix** against the phase's labels rather than switching on a shape:

    * ``CR   1.000 0.01000`` (``corpus file 6``:177),
      whose phase's one atom is labelled ``CR``;
    * ``1C  1.00 0.01`` / ``2C  1.00 0.01`` (``corpus file 1``:190-191),
      whose phase's two atoms are labelled ``1CR`` and ``2CR``. The moment and
      its σ stand in for the corpus numbers; the **spelling** of each — how many
      digits, in how many columns — is the file's own, and it is the spelling
      this production turns on.

    Reading the second as a *site index* also fits those two lines, and would
    then read ``CR`` as a label — two productions where one explains both. The
    prefix reading is recorded, the raw key is kept beside it, and an
    unresolvable key is reported as such rather than guessed at.
    """

    key: str
    moment: float
    sigma: float
    #: Index into the phase's ``atoms`` where the key resolves to exactly one
    #: label by prefix; None where it resolves to none or to several.
    atom_index: int | None = None


@dataclass
class FullProfPhase:
    """One phase block, nuclear or magnetic.

    ``index`` is **positional** — its ordinal among the ``Nph`` blocks — and
    ``labelled_index`` is what the ``!  Data for PHASE number: N`` comment
    claimed. They disagree in a real file (``corpus file 1``'s third block
    says 1), which is why nothing keys on the comment.
    """

    index: int
    name: str
    control: dict = field(default_factory=dict)
    space_group: str = ""
    #: The symbol exactly as written, before case normalisation.
    space_group_raw: str = ""
    atoms: list = field(default_factory=list)
    magnetic: MagneticSymmetry | None = None
    #: :data:`_SCALE_COLUMNS` ∪ :data:`_WIDTH_COLUMNS` ∪ :data:`_ASYM_COLUMNS`.
    profile: dict = field(default_factory=dict)
    #: :data:`_CELL_COLUMNS`.
    cell: dict = field(default_factory=dict)
    strain_model: int | None = None
    size_model: int | None = None
    #: ``Nvk`` propagation vectors, each a ``(k, codewords)`` pair.
    propagation_vectors: list = field(default_factory=list)
    soft_moment_constraints: list = field(default_factory=list)
    labelled_index: int | None = None
    r_bragg: float | None = None

    @property
    def jbt(self) -> int:
        return int(self.control["jbt"])

    @property
    def is_magnetic(self) -> bool:
        """``Jbt = 1``. A pure magnetic phase has no shape in rietx's magnetic
        model (:data:`MAGNETIC_PHASE_REFUSAL`), so this phase can be reported
        but not built — see the module docstring's decision 1."""
        return self.jbt == 1

    @property
    def isy(self) -> int:
        return int(self.control["isy"])

    @property
    def nvk(self) -> int:
        """How many propagation vectors this phase declares."""
        return int(self.control["nvk"])


@dataclass
class FullProfModel:
    """What a ``.pcr`` states.

    Deliberately not a :class:`~rietx.schemas.Structure`: the caller decides
    which phases to keep, and this object's whole job is to be able to *say*
    what it read — including the parts rietx cannot model, which is the only
    alternative to dropping them.
    """

    #: The file this was read from, so every refusal downstream can name it.
    path: str | None = None
    #: The ``COMM`` title line.
    title: str | None = None
    #: ``! Current global Chi2 (Bragg contrib.) =`` — FullProf rewrites this
    #: comment every cycle, so it is the converged value, and it is the reason
    #: the format is worth reading at all.
    chi2: float | None = None
    #: The data file the header comment names. **Reported, never chased**: the
    #: reference is routinely stale, naming a pattern that is not the one
    #: beside the file on disk. Resolving it would be a reader inventing a
    #: filename.
    data_file: str | None = None
    #: The ``PCR-file:`` name from the same comment, which is likewise often
    #: another refinement's (``corpus file 1`` says ``corpus file 3``).
    pcr_name: str | None = None
    control: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    pattern: dict = field(default_factory=dict)
    cycles: dict = field(default_factory=dict)
    #: ``(2θ position, Value)`` per interpolated background point. The codeword
    #: is **inline** as the third column here, not on a following line.
    background: list = field(default_factory=list)
    #: ``(low, high)`` per excluded region, in file order.
    excluded_regions: list = field(default_factory=list)
    #: The count the file declares. Compare with :attr:`parameter_numbers`
    #: rather than trusting either: they disagree in a real file (trap 4).
    refined_parameter_count: int | None = None
    #: Zero shift, cos/sin sample displacement, and trap 3's stale λ slot.
    zero_shift: dict = field(default_factory=dict)
    phases: list = field(default_factory=list)
    #: ``(2θ_low, 2θ_high, pattern)`` — the range actually fitted, from the
    #: trailing ``!  2Th1/TOF1  2Th2/TOF2  Pattern #`` block.
    fitted_range: tuple | None = None

    @property
    def job(self) -> int:
        """0 = X-ray CW, 1 = neutron CW. −1 (neutron TOF) is refused at read."""
        return int(self.control["job"])

    @property
    def lambda1(self) -> float | None:
        """The refinement's wavelength — **not** :attr:`lambda_slot` (trap 3)."""
        return self.pattern.get("lambda1")

    @property
    def lambda2(self) -> float | None:
        return self.pattern.get("lambda2")

    @property
    def lambda_slot(self) -> Value | None:
        """The refinable-λ slot of the zero-shift line.

        Trap 3: ``corpus file 2`` has ``2.370100`` here against a real λ
        of 2.077100, with codeword ``0.00`` so FullProf never used it. Read for
        provenance; :attr:`lambda1` is the wavelength.
        """
        return self.zero_shift.get("lambda_slot")

    @property
    def nuclear_phases(self) -> list:
        return [ph for ph in self.phases if not ph.is_magnetic]

    @property
    def magnetic_phases(self) -> list:
        """The phases rietx has no model for. Reported, never dropped."""
        return [ph for ph in self.phases if ph.is_magnetic]

    @property
    def parameter_numbers(self) -> frozenset:
        """Every parameter number any codeword in the file references."""
        numbers: set[int] = set()

        def gather(values) -> None:
            for value in values:
                code = value.code
                if code is not None:
                    numbers.add(code.number)

        gather(self.zero_shift.values())
        gather(v for _, v in self.background)
        for ph in self.phases:
            gather(ph.profile.values())
            gather(ph.cell.values())
            for atom in ph.atoms:
                gather(atom.values.values())
                gather(atom.betas.values())
            for _, codes in ph.propagation_vectors:
                gather(codes)
        return frozenset(numbers)


# --------------------------------------------------------------- normalisation


def normalize_species(token: str) -> str:
    """``CR`` → ``Cr``, ``CA+2`` → ``Ca2+``; a magnetic label is left alone.

    FullProf writes the scattering-species token in whatever case the author
    typed — ``CR``, ``AL``, ``Co``, ``W`` all appear in the corpus — and rietx's
    species are element symbols in IUCr spelling. Title-casing a one- or
    two-letter element token is unambiguous, and the charge is reordered
    digit-first to the IUCr house convention — the same spelling the sibling
    ``projects/topas.py`` reader hands back where it has landed (PR #98), so a
    species reads identically whichever project file it came from.

    A token that does not look like an element with an optional charge —
    ``MCR3``, a magnetic form-factor table name — is returned **verbatim**.
    It is not an element, so inventing ``Mc`` + charge from it would be a
    species that means nothing, and the phase carrying it is refused
    at :func:`to_structure` anyway.
    """
    stripped = re.sub(r"[^A-Za-z0-9+-]", "", token)
    if m := re.fullmatch(r"([A-Za-z]{1,2})([+-])(\d*)", stripped):
        element, sign, magnitude = m.groups()
        return f"{element.capitalize()}{magnitude or ''}{sign}"
    if m := re.fullmatch(r"([A-Za-z]{1,2})(\d*)([+-])", stripped):
        element, magnitude, sign = m.groups()
        return f"{element.capitalize()}{magnitude}{sign}"
    if re.fullmatch(r"[A-Za-z]{1,2}", stripped):
        return stripped.capitalize()
    return token.strip()


#: How far a cell may stray from ``a = b = c``/``α = β = γ`` and still be called
#: rhombohedral axes. Generous on purpose: the discrimination it has to make is
#: against the *hexagonal* setting of the same R symbol, whose metric is
#: ``α = β = 90°, γ = 120°`` — thirty degrees away, not a rounding.
_RHOMBOHEDRAL_LENGTH_RTOL = 1e-3
_RHOMBOHEDRAL_ANGLE_ATOL = 1e-2


def _is_rhombohedral_metric(cell: dict) -> bool:
    """``a = b = c`` with ``α = β = γ`` — an R lattice on rhombohedral axes.

    The hexagonal setting of the same symbol has ``a = b ≠ c`` and
    ``α = β = 90°, γ = 120°``, so requiring all three angles equal is what tells
    the two apart; every R phase in the corpus is hexagonal, carrying two
    equal edges and a third that differs, with γ = 120°.
    """
    try:
        a, b, c = (float(cell[k]) for k in ("a", "b", "c"))
        alpha, beta, gamma = (float(cell[k]) for k in ("alpha", "beta", "gamma"))
    except (KeyError, TypeError, ValueError):
        return False
    if a <= 0.0:
        return False
    lengths_equal = (abs(b - a) <= _RHOMBOHEDRAL_LENGTH_RTOL * a
                     and abs(c - a) <= _RHOMBOHEDRAL_LENGTH_RTOL * a)
    angles_equal = (abs(beta - alpha) <= _RHOMBOHEDRAL_ANGLE_ATOL
                    and abs(gamma - alpha) <= _RHOMBOHEDRAL_ANGLE_ATOL)
    return lengths_equal and angles_equal


def normalize_space_group(symbol: str, cell: dict | None = None) -> str:
    """``F D -3 M`` → ``F d -3 m:2``; ``P 42/m n m`` unchanged.

    Three repairs, and each is a *report* rather than a contradiction:

    **Case.** FullProf carries the Hermann-Mauguin symbol in whatever case the
    author typed: ``F D -3 M`` (``corpus file 4``:68) and ``I A -3 D``
    (``corpus file 5``:184) against ``P 42/m n m`` and ``R -3 c`` in
    the same corpus. Only the lattice letter is upper case in a HM symbol —
    everything after it is drawn from ``m a b c d n`` plus digits, ``/`` and
    ``-`` — so lower-casing the tail is lossless.

    **Origin choice.** FullProf writes no origin suffix at all, which is the
    TOPAS ``Pn-3mZ`` trap in a worse form: gemmi resolves a bare ``F d -3 m`` to
    origin choice **1**, and the corpus's spinel is on choice 2 (the A cation at
    ⅛⅛⅛ and ½½½, O at x,x,x — the standard spinel description). Choice 2 is
    therefore
    preferred wherever the bare symbol lands on choice 1.

    **Rhombohedral axes.** An R-lattice symbol is likewise written bare, and
    gemmi resolves a bare ``R -3 c`` to the **hexagonal** setting (``:H``, 36
    operations). Its rhombohedral setting (``:R``) has 12. That factor of three
    is the general multiplicity :func:`occupancy_factor` divides by, so reading
    a rhombohedral-axes cell under ``:H`` is a wrong multiplicity on every site
    — root CLAUDE.md's own invariant ("an R lattice on **rhombohedral** axes
    needs a = b = c with α = β = γ free... ``read_small_structure`` picks the R
    setting from the cell", the trap that served 79 of gemmi's 564 settings
    wrong under a correct free-parameter count). So the setting is picked **from
    the cell**, the same way, and ``cell`` is why this function takes one.

    ``cell`` is a mapping of :data:`_CELL_COLUMNS` to floats. Without it the R
    case cannot be decided and the bare symbol is returned unchanged, which is
    the hexagonal setting — so :func:`_read_phase` calls this a second time once
    the phase's cell line has been read, the cell block sitting *after* the
    atoms in a ``.pcr``.

    Every corpus R phase is hexagonal — two equal edges, a third that differs,
    γ = 120° — so this case closes a gap rather than fixing a measured wrong
    answer, and it is stated as a gap.

    The case and origin preferences are *conventions*, so they are not left to
    be trusted: :func:`to_structure` re-derives every site's multiplicity under
    whichever setting this returns and refuses the phase unless the occupancy
    column reduces consistently (module docstring, decision 3). A wrong origin
    gives wrong multiplicities and is refused, not returned.
    """
    text = " ".join(symbol.split())
    if not text:
        return text
    normalised = text[0].upper() + text[1:].lower()
    try:
        import gemmi
    except ImportError:  # pragma: no cover - gemmi is a hard dependency
        return normalised
    try:
        sg = gemmi.SpaceGroup(normalised)
    except Exception:
        return normalised
    # An R symbol and an origin-choice symbol are disjoint cases: gemmi reports
    # `ext` "H"/"R" for the former and "1"/"2" for the latter, never both.
    if sg.ext == "H" and cell is not None and _is_rhombohedral_metric(cell):
        try:
            gemmi.SpaceGroup(f"{normalised}:R")
        except Exception:
            return normalised
        return f"{normalised}:R"
    if sg.ext == "1":
        try:
            gemmi.SpaceGroup(f"{normalised}:2")
        except Exception:
            return normalised
        return f"{normalised}:2"
    return normalised


# ---------------------------------------------------------------- the line walk


def _strip(raw: str) -> str:
    """One line with its comments removed.

    Three markers, all real and all needed:

    * ``!`` opens a comment, and does so **inline** as well as at column 1 —
      ``61    !Number of refined parameters`` is a data line with a comment on
      it (``corpus file 2``:74), so cutting at ``!`` is what makes the
      count readable *and* what makes the header lines disappear.
    * ``<--`` annotates the space-group line
      (``P 42/m n m               <--Space group symbol``).
    * ``#`` annotates an atom line (``#color cyan`` on every site of one
      corpus file's phases).

    A line that is empty after the cut is a comment line and never reaches the
    walk. The risk this accepts is a phase *name* containing one of the three
    markers, which no file here does; the alternative — position-only comment
    detection — would lose the refined-parameter count.
    """
    for marker in ("!", "#", "<--"):
        index = raw.find(marker)
        if index >= 0:
            raw = raw[:index]
    return raw.strip()


@dataclass(frozen=True)
class _Line:
    number: int
    text: str


class _Cursor:
    """A walk over the file's **data** lines, in order.

    Positional by construction, which is the answer to trap 2: the column names
    live in this module's tables and the file's ``!`` header comments are gone
    before the first ``take``. Every exhaustion and every field-count surprise
    raises :class:`FullProfPcrError` naming the file and the line, because a
    ``.pcr`` has no keyword a reader could resynchronise on — one wrong field
    count silently reinterprets everything after it.
    """

    def __init__(self, path: Path, lines: list) -> None:
        self.path = path
        self.lines = lines
        self.at = 0

    def _fail(self, what: str, detail: str, line: _Line | None = None) -> FullProfPcrError:
        where = f" line {line.number}" if line is not None else ""
        return FullProfPcrError(f"{self.path}:{where} {what}: {detail}")

    @property
    def exhausted(self) -> bool:
        return self.at >= len(self.lines)

    def peek(self) -> _Line | None:
        return None if self.exhausted else self.lines[self.at]

    def take(self, what: str) -> _Line:
        if self.exhausted:
            raise FullProfPcrError(
                f"{self.path}: the file ends where {what} was expected — "
                f"{len(self.lines)} data lines read. A .pcr is positional, so a "
                f"truncated file cannot be partially interpreted.")
        line = self.lines[self.at]
        self.at += 1
        return line

    def remaining(self) -> list:
        rest = self.lines[self.at:]
        self.at = len(self.lines)
        return rest

    def floats(self, what: str, *, at_least: int, skip: int = 0,
               leading: bool = False) -> tuple[_Line, list]:
        """The numbers of the next data line, and the line itself.

        ``skip`` drops leading non-numeric tokens (an atom's label and species).
        ``leading`` parses only the leading numeric *run* and stops at the first
        token that is not a number, which one block genuinely needs: FullProf
        writes ``0.0000000 0.0000000 0.0000000          Propagation Vector  1``
        (``corpus file 4``:130), where the trailing words carry no comment
        marker for :func:`_strip` to cut at.
        """
        line = self.take(what)
        tokens = line.text.split()[skip:]
        numbers: list[float] = []
        for token in tokens:
            try:
                numbers.append(float(token))
            except ValueError as exc:
                if leading:
                    break
                raise self._fail(
                    what, f"{token!r} is not a number in {line.text!r}", line) from exc
        if len(numbers) < at_least:
            raise self._fail(
                what, f"expected at least {at_least} numbers, found "
                      f"{len(numbers)} in {line.text!r}", line)
        return line, numbers

    def ints(self, what: str, *, expect: int) -> tuple[_Line, list]:
        """Exactly ``expect`` integers.

        Exact rather than "at least": these are the control lines, where an
        extra or a missing field shifts the meaning of every field after it, so
        a count surprise is refused instead of being read off the front.
        """
        # `at_least=0`, so a *narrow* line is reported by the exact-count
        # message below rather than by the generic one: the actionable fact is
        # which form the reader expects, not that it wanted more numbers.
        line, numbers = self.floats(what, at_least=0)
        if len(numbers) != expect:
            raise self._fail(
                what, f"expected {expect} fields, found {len(numbers)} in "
                      f"{line.text!r} — only the {expect}-field form is "
                      f"evidenced by any file this reader was written against",
                line)
        out = []
        for value in numbers:
            if not float(value).is_integer():
                raise self._fail(what, f"{value!r} is not an integer in "
                                       f"{line.text!r}", line)
            out.append(int(value))
        return line, out


def _row(names: tuple, values: list, codewords: list | None) -> dict:
    """Zip a value line and its codeword line onto positional names.

    A codeword column the line does not reach is ``None``, which
    :attr:`Value.vary` reports as "the column is absent" rather than as
    "held" — the tri-state kept honest at the one place it could collapse.
    """
    out: dict[str, Value] = {}
    for i, name in enumerate(names):
        if i >= len(values):
            break
        codeword = None
        if codewords is not None and i < len(codewords):
            codeword = codewords[i]
        out[name] = Value(value=values[i], codeword=codeword)
    return out


def _block(cur: _Cursor, names: tuple, what: str, *, trailing: int = 0
           ) -> tuple[dict, int | None]:
    """A value line, its codeword line, and an optional trailing model selector.

    ``trailing`` is the integer model code that ends the scale and width lines
    (``Strain-Model``, ``Size-Model``) and carries **no** codeword, which is why
    it is taken off the value line rather than being a column.

    That selector is an **integer** and is checked as one. The line as a whole
    cannot go through :meth:`_Cursor.ints` — every column before the selector is
    a genuine float — so the ``.is_integer()`` guard that :meth:`_Cursor.ints`
    applies to a control line is applied here to the one field that needs it.
    Casting through a bare ``int()`` would read a corrupted ``1.5`` as model 1,
    which selects a *different* strain or size broadening model without saying
    so; a model selector is a discrete choice and a truncated one is a wrong
    answer, not a rounded one.
    """
    line, values = cur.floats(what, at_least=len(names) + trailing)
    _, codewords = cur.floats(f"{what} codewords", at_least=1)
    model = None
    if trailing and len(values) > len(names):
        selector = values[len(names)]
        if not float(selector).is_integer():
            raise cur._fail(
                what, f"the trailing model selector is {selector!r}, and it "
                      f"names a discrete strain/size broadening model — a "
                      f"non-integer cannot be truncated into one",
                line)
        model = int(selector)
    return _row(names, values, codewords), model


# ------------------------------------------------------------------- the reader


#: ``! Current global Chi2 (Bragg contrib.) =      5.144`` — the converged χ²,
#: rewritten by FullProf on every cycle, so it is the answer and not a seed.
_CHI2 = re.compile(r"Current\s+global\s+Chi2[^=]*=\s*([-+0-9.eE]+)")

#: ``! Files => DAT-file: sample.dat,  PCR-file: another``
_FILES = re.compile(r"DAT-file:\s*([^,]+?)\s*,\s*PCR-file:\s*(\S+)")

#: ``!  Data for PHASE number:   1  ==> Current R_Bragg for Pattern#  1: 1.79``
#: The phase number here is trap 1 and is recorded for provenance only.
_PHASE_COMMENT = re.compile(
    r"Data\s+for\s+PHASE\s+number:\s*(\d+).*?R_Bragg[^:]*:\s*([-+0-9.eE]+)")


def read_fullprof_pcr(path: str | Path) -> FullProfModel:
    """Parse a ``.pcr``. Raises :class:`FullProfPcrError` naming file and line.

    Handles the single-pattern constant-wavelength layout completely and refuses
    everything else by name — see the module docstring for the exact boundary.
    """
    path = Path(path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise FullProfPcrError(f"{path}: cannot read: {exc}") from exc
    # `base.decode` is the seam `head()` already goes through, shared rather
    # than duplicated — the same reasoning the sibling `projects/topas.py`
    # reader uses where it has landed.
    raw, codec, _bom = decode(raw_bytes)
    if "\x00" in raw:
        # `io/CLAUDE.md`'s `xy` row: ASCII-range UTF-16 is valid UTF-8 with
        # interleaved NULs, so a surviving NUL means no byte-order mark said
        # which of LE and BE this is, and guessing is a repair a reader cannot
        # say it made.
        raise FullProfPcrError(
            f"{path}: not text this reader can decode — NUL bytes survive a "
            f"{codec} decode, which is what an ASCII-range UTF-16 export with "
            f"no byte-order mark looks like. Re-save it as UTF-8.")

    raw_lines = raw.split("\n")
    model = FullProfModel(path=str(path))

    # The comments are read *first* and separately, for provenance only: the
    # agreement factors and the file references live nowhere else, and the phase
    # index one of them states is trap 1. Nothing structural comes from here.
    r_braggs: list[tuple[int, float]] = []
    for text in raw_lines:
        if m := _CHI2.search(text):
            model.chi2 = float(m.group(1))
        if m := _FILES.search(text):
            model.data_file, model.pcr_name = m.group(1), m.group(2)
        if m := _PHASE_COMMENT.search(text):
            r_braggs.append((int(m.group(1)), float(m.group(2))))

    data = [_Line(number=i + 1, text=stripped)
            for i, stripped in ((i, _strip(text)) for i, text in enumerate(raw_lines))
            if stripped]
    cur = _Cursor(path, data)

    first = cur.take("the COMM title line")
    if not first.text.upper().startswith("COMM"):
        raise FullProfPcrError(
            f"{path}: line {first.number} is {first.text!r}, and a .pcr opens "
            f"with a COMM title line — this is not a FullProf control file, or "
            f"its header was edited away")
    model.title = first.text[4:].strip() or None

    # The multi-pattern layout announces itself on the line after COMM, and it
    # is a different grammar from here down: per-pattern control lines that shed
    # `Nph` (it moves to a line of its own), per-pattern background and excluded
    # regions, and one copy of every phase's whole profile block per pattern.
    # Refused before any of it is parsed — see the module docstring's decision 2.
    if (nxt := cur.peek()) is not None and nxt.text.upper().startswith("NPATT"):
        count = nxt.text.split()[1] if len(nxt.text.split()) > 1 else "?"
        raise FullProfPcrError(
            f"{path}: line {nxt.number} declares NPATT {count} — a joint "
            f"refinement over {count} patterns. That is a different layout "
            f"throughout (per-pattern control lines, backgrounds, excluded "
            f"regions and profile blocks, one set of atoms), and choosing which "
            f"bank's resolution function to return is a question the file does "
            f"not answer. Single-pattern .pcr files only.")

    _, control = cur.ints("the Job/Npr/Nph control line",
                          expect=len(_CONTROL_FIELDS))
    model.control = dict(zip(_CONTROL_FIELDS, control, strict=True))

    job = model.control["job"]
    if job not in (0, 1):
        kind = {-1: "neutron time-of-flight", -2: "energy-dispersive X-ray",
                2: "energy-dispersive X-ray", 3: "neutron time-of-flight"}
        named = kind.get(job, "a job this reader does not know")
        raise FullProfPcrError(
            f"{path}: Job = {job} ({named}). rietx models "
            f"constant-wavelength diffraction only: a TOF pattern's abscissa is "
            f"microseconds, and its whole profile block is Sig-2/Sig-1/Sig-0 and "
            f"alpha0/beta0/alpha1 in place of Caglioti U/V/W. Job 0 (X-ray) and "
            f"Job 1 (neutron CW) are read.")
    for name, why in _MUST_BE_ZERO.items():
        if model.control[name] != 0:
            raise FullProfPcrError(
                f"{path}: control-line field {name.capitalize()} = "
                f"{model.control[name]}, and this reader only handles 0, because "
                f"{why}. No file it was written against states a non-zero value, "
                f"so reading on would be a guess at the layout.")
    # A negative count is not "none of them": `range(-1)` is empty, so an
    # excluded-region block declared negative would leave its lines to be
    # reinterpreted by whatever reads next. Refused rather than clamped.
    if model.control["nex"] < 0:
        raise FullProfPcrError(
            f"{path}: Nex = {model.control['nex']} — an excluded-region count "
            f"cannot be negative")
    if model.control["nph"] < 1:
        raise FullProfPcrError(
            f"{path}: Nph = {model.control['nph']} — a .pcr with no phase states "
            f"no model to read")
    nba = model.control["nba"]
    if nba < 2:
        raise FullProfPcrError(
            f"{path}: Nba = {nba}. Only an interpolated background of two or "
            f"more points is evidenced here (51 and 32 points, in two real "
            f"files); Nba 0 or 1 selects a polynomial or a debye/"
            f"Fourier background whose coefficient line's *position* in the "
            f"single-pattern layout no file establishes, and a negative Nba "
            f"selects a background model this reader does not know.")

    _, output = cur.ints("the Ipr/Ppl output-control line",
                         expect=len(_OUTPUT_FIELDS))
    model.output = dict(zip(_OUTPUT_FIELDS, output, strict=True))

    _, pattern = cur.floats("the Lambda1/Lambda2 line",
                            at_least=len(_PATTERN_FIELDS))
    model.pattern = dict(zip(_PATTERN_FIELDS, pattern[:len(_PATTERN_FIELDS)],
                             strict=True))
    _, cycles = cur.floats("the NCY/Eps/Thmin line", at_least=len(_CYCLE_FIELDS))
    model.cycles = dict(zip(_CYCLE_FIELDS, cycles[:len(_CYCLE_FIELDS)],
                            strict=True))

    # The background points carry their codeword *inline* as the third column,
    # unlike the atom and profile blocks. Read as `Nba` lines exactly, and the
    # count is the invariant rather than something the loop is trusted for: a
    # dropped point moves the interpolated background under every peak it spans.
    for i in range(nba):
        _, numbers = cur.floats(f"background point {i + 1} of {nba}", at_least=2)
        codeword = numbers[2] if len(numbers) > 2 else None
        model.background.append(
            (numbers[0], Value(value=numbers[1], codeword=codeword)))
    if len(model.background) != nba:  # pragma: no cover - the loop is exact
        raise FullProfPcrError(
            f"{path}: parsed {len(model.background)} background points from a "
            f"declared Nba = {nba}")

    for i in range(model.control["nex"]):
        _, numbers = cur.floats(
            f"excluded region {i + 1} of {model.control['nex']}", at_least=2)
        model.excluded_regions.append((numbers[0], numbers[1]))

    count_line, counts = cur.floats("the refined-parameter count", at_least=1)
    if not float(counts[0]).is_integer():
        raise FullProfPcrError(
            f"{path}: line {count_line.number}: refined-parameter count "
            f"{counts[0]!r} is not an integer")
    model.refined_parameter_count = int(counts[0])

    # Value and codeword interleaved on one line: zero, SyCos, SySin, Lambda.
    zero_line, zero = cur.floats("the Zero/SyCos/SySin/Lambda line", at_least=8)
    model.zero_shift = {
        name: Value(value=zero[2 * i], codeword=zero[2 * i + 1])
        for i, name in enumerate(_ZERO_FIELDS)}
    if len(zero) > 8 and zero[8] != 0:
        raise FullProfPcrError(
            f"{path}: line {zero_line.number}: MORE = {zero[8]!r} on the "
            f"zero-shift line, which adds instrument lines whose position no "
            f"file here establishes")

    for index in range(1, model.control["nph"] + 1):
        model.phases.append(_read_phase(cur, path, index))
    if len(model.phases) != model.control["nph"]:  # pragma: no cover
        raise FullProfPcrError(
            f"{path}: parsed {len(model.phases)} phases from a declared "
            f"Nph = {model.control['nph']}")

    # Trap 1, recorded rather than trusted: the R_Bragg comments are attached in
    # *file order*, and the index each one claims is kept beside it so a consumer
    # can see the disagreement instead of inheriting it.
    #
    # The count is asserted before the zip, the way the `Nph`/parsed-phase count
    # above is. `strict=False` here would *truncate* on a mismatch, which is the
    # one failure this attachment cannot afford: the comments are matched by file
    # order, so a file carrying four comments for three phases would attach the
    # first three — silently giving phase 3 the R_Bragg of some other phase. An
    # agreement factor reported against the wrong phase is worse than none, and
    # the whole point of "recorded rather than trusted" is that the disagreement
    # is *visible*. Zero comments is not a mismatch: a `.pcr` that has never been
    # run through FullProf carries no `R_Bragg` at all, and there is then nothing
    # to misattribute.
    if r_braggs:
        if len(r_braggs) != len(model.phases):
            raise FullProfPcrError(
                f"{path}: {len(r_braggs)} '! Data for PHASE number: N ... "
                f"R_Bragg' comments for {len(model.phases)} phases. They are "
                f"attached by file order, so an unequal count would report an "
                f"agreement factor against the wrong phase. The comment's own "
                f"phase number is trap 1 and cannot be used to re-key them — the "
                f"third block of one real file is labelled "
                f"'PHASE number: 1'.")
        for phase, (labelled, r_bragg) in zip(model.phases, r_braggs,
                                              strict=True):
            phase.labelled_index, phase.r_bragg = labelled, r_bragg

    _read_trailing(cur, path, model)
    # Decode every codeword now rather than lazily. A garbled one — a truncated
    # `601.0` reading as `6` — decodes to parameter 0, which is not a number any
    # FullProf run writes; refusing it here means the refusal names the *file*,
    # which `io/CLAUDE.md` requires, instead of surfacing from whatever consumer
    # first touched `Value.code`.
    try:
        model.parameter_numbers  # noqa: B018 - the decode is the point
    except FullProfPcrError as exc:
        raise FullProfPcrError(f"{path}: {exc}") from exc
    return model


def _read_phase(cur: _Cursor, path: Path, index: int) -> FullProfPhase:
    """One phase block, walked positionally.

    The order is the file's and every count is asserted: name, control line,
    space group, the magnetic symmetry sub-block where ``Isy < 0``, ``Nat``
    atoms, four profile blocks, then ``Nvk`` propagation vectors. There is no
    keyword to resynchronise on, so a surprise anywhere here is a refusal.
    """
    name_line = cur.take(f"the name of phase {index}")
    phase = FullProfPhase(index=index, name=name_line.text)

    control_line, control = cur.floats(
        f"phase {index} ({phase.name}) control line", at_least=len(_PHASE_FIELDS))
    phase.control = dict(zip(_PHASE_FIELDS, control[:len(_PHASE_FIELDS)],
                             strict=True))
    where = f"{path}: phase {index} ({phase.name!r})"
    # Every field below that is read through `int()` is checked to *be* one
    # first — the guard `_Cursor.ints` gives a control line, applied field by
    # field because `ATZ` and `Pr1..Pr3` on this same line are genuine floats.
    for name in _PHASE_INTEGER_FIELDS:
        if not float(phase.control[name]).is_integer():
            raise FullProfPcrError(
                f"{where}: line {control_line.number}: the phase control line "
                f"states {name.capitalize()} = {phase.control[name]!r}, and it "
                f"is a count or a grammar selector rather than a quantity. "
                f"Truncating it would read a different phase block from the one "
                f"written — and a .pcr is positional, so that desynchronises "
                f"every line after this one.")

    jbt = phase.jbt
    if jbt not in (0, 1):
        raise FullProfPcrError(
            f"{where}: Jbt = {jbt}. Only Jbt 0 (nuclear) and Jbt 1 (magnetic) "
            f"are evidenced here; the others select Le Bail intensity "
            f"extraction, a combined nuclear+magnetic phase or a form-factor "
            f"phase, each of which changes the atom block's own layout. In "
            f"particular the **Fourier-component** magnetic forms — a phase "
            f"whose moments are stated as amplitudes per propagation vector "
            f"rather than as one moment per site — are outside rietx's "
            f"magnetic model whatever their Jbt: WP-1327 carries a single "
            f"commensurate moment per site, and a (3+d)-dimensional "
            f"modulation has no shape here (the same fence "
            f"`rietx.Structure.from_cif` states by name for a magCIF's "
            f"_atom_site_moment_Fourier loop). Which Jbt selects which of "
            f"those layouts is **not** something this reader claims to know: "
            f"no file it was written against states one, and guessing would "
            f"desynchronise every line after this — a .pcr is positional.")
    # `Ang` when Jbt = 0, `Mom` when Jbt = 1 — one column, two header words
    # (trap 2). A nuclear phase's non-zero `Ang` opens an angle-restraint block
    # whose position nothing here establishes; a magnetic phase's `Mom` is the
    # declared soft-moment-constraint count and adds no line to *this* block.
    ang_or_mom = int(phase.control["ang_or_mom"])
    for name, why in (
            ("dis", "distance-restraint lines follow it"),
            ("str", "a strain-model block follows it"),
            ("furth", "further-parameter lines follow it"),
            ("more", "additional per-phase lines follow it")):
        if int(phase.control[name]) != 0:
            raise FullProfPcrError(
                f"{where}: {name.capitalize()} = {int(phase.control[name])} and "
                f"{why}, at a position no file this reader was written against "
                f"establishes")
    if jbt == 0 and ang_or_mom != 0:
        raise FullProfPcrError(
            f"{where}: Ang = {ang_or_mom} and angle-restraint lines follow it, "
            f"at a position no file here establishes")
    if int(phase.control["irf"]) not in (0, -1):
        raise FullProfPcrError(
            f"{where}: Irf = {int(phase.control['irf'])}, which reads the "
            f"reflection list from a companion file rather than generating it "
            f"from the atoms — so the model this reader would return is not the "
            f"model that was refined")

    sg_line = cur.take(f"phase {index} space-group symbol")
    phase.space_group_raw = sg_line.text
    phase.space_group = normalize_space_group(sg_line.text)

    isy = phase.isy
    if jbt == 1 and isy not in (-1, -2):
        raise FullProfPcrError(
            f"{where}: a magnetic phase (Jbt 1) with Isy = {isy}. The magnetic "
            f"sub-grammar is selected by Isy and only -1 (SYMM/MSYM pairs) and "
            f"-2 (SYMM/BASR/BASI triples) are evidenced here")
    if jbt == 0 and isy != 0:
        raise FullProfPcrError(
            f"{where}: a nuclear phase (Jbt 0) with Isy = {isy}, which supplies "
            f"the symmetry operators explicitly instead of deriving them from "
            f"the space-group symbol — a block no file here states the shape of")
    if isy != 0:
        phase.magnetic = _read_magnetic_symmetry(cur, where, isy)

    nat = int(phase.control["nat"])
    if nat < 0 or phase.nvk < 0:
        # `range(-1)` is empty, so a negative count reads as "none" and leaves
        # the block's lines to be reinterpreted by whatever comes next.
        raise FullProfPcrError(
            f"{where}: Nat = {nat}, Nvk = {phase.nvk} — neither count can be "
            f"negative")
    for i in range(nat):
        phase.atoms.append(
            _read_magnetic_atom(cur, where, i + 1, nat) if jbt == 1
            else _read_nuclear_atom(cur, where, i + 1, nat))
    # A dropped site is a silently wrong structure factor, so the count is an
    # invariant rather than something the walk is trusted to get right — the
    # TOPAS reader's rule, and it costs nothing to restate here.
    if len(phase.atoms) != nat:  # pragma: no cover - the loop is exact
        raise FullProfPcrError(
            f"{where}: parsed {len(phase.atoms)} atoms from a declared Nat = {nat}")

    scale, phase.strain_model = _block(
        cur, _SCALE_COLUMNS, f"phase {index} scale/shape line", trailing=1)
    width, phase.size_model = _block(
        cur, _WIDTH_COLUMNS, f"phase {index} U/V/W width line", trailing=1)
    phase.cell, _ = _block(cur, _CELL_COLUMNS, f"phase {index} cell line")
    # The cell line sits *after* the atoms, so the space-group symbol above was
    # normalised without it and an R symbol landed on gemmi's default hexagonal
    # setting. Re-derive it now that the metric is known: a rhombohedral-axes
    # cell selects `:R`, whose general multiplicity is a third of `:H`'s. Case
    # and origin choice are unaffected — the R branch is disjoint from them.
    phase.space_group = normalize_space_group(
        phase.space_group_raw, {k: v.value for k, v in phase.cell.items()})
    asym, _ = _block(cur, _ASYM_COLUMNS, f"phase {index} Pref/Asy line")
    phase.profile = {**scale, **width, **asym}

    # Nvk propagation vectors, one value line and one codeword line each,
    # positioned after the Pref/Asy block. Evidenced by exactly one file
    # (`corpus file 4`:129-131, Nvk = 1) whose phase happens to be the last,
    # so the *position* rests on one observation and is said to.
    for i in range(phase.nvk):
        _, k = cur.floats(f"phase {index} propagation vector {i + 1}",
                          at_least=3, leading=True)
        _, codes = cur.floats(
            f"phase {index} propagation vector {i + 1} codewords", at_least=3,
            leading=True)
        phase.propagation_vectors.append(
            (tuple(k[:3]), tuple(Value(value=k[j], codeword=codes[j])
                                 for j in range(3))))
    return phase


def _labelled(cur: _Cursor, keyword: str, what: str, where: str) -> str:
    """A ``SYMM``/``MSYM`` line, verbatim, with its label checked.

    Verbatim because nothing here models a magnetic symmetry operator: carrying
    a parsed form would be a claim about an algebra this package does not have.
    The label is still checked, because it is the only thing that says the walk
    is still where it thinks it is — a `.pcr` has no other landmark.
    """
    line = cur.take(what)
    if not line.text.upper().startswith(keyword):
        raise FullProfPcrError(
            f"{where}: line {line.number}: expected a {keyword} line, found "
            f"{line.text!r}")
    return line.text


def _keyworded(cur: _Cursor, keyword: str, what: str, where: str,
               count: int) -> list:
    """A ``BASR``/``BASI`` line: the keyword, then exactly ``count`` numbers.

    The keyword is **checked**, not skipped. It is the one place a ``.pcr``
    labels a line, and the label is what says whether the numbers are the real
    or the imaginary part of the basis vector; reading past it on trust would
    let a file with the pair in the other order arrive silently transposed.
    """
    line = cur.take(what)
    tokens = line.text.split()
    if not tokens or tokens[0].upper() != keyword:
        raise FullProfPcrError(
            f"{where}: line {line.number}: expected a {keyword} line, found "
            f"{line.text!r}")
    numbers: list[float] = []
    for token in tokens[1:]:
        try:
            numbers.append(float(token))
        except ValueError as exc:
            raise FullProfPcrError(
                f"{where}: line {line.number}: {token!r} is not a number in "
                f"{line.text!r}") from exc
    if len(numbers) < count:
        # 3 * N_Bas is the invariant: three components per basis vector, so a
        # short line means the declared N_Bas and the written vectors disagree.
        raise FullProfPcrError(
            f"{where}: line {line.number}: {keyword} states {len(numbers)} "
            f"numbers where 3 x N_Bas = {count} are declared")
    return numbers[:count]


def _read_magnetic_symmetry(cur: _Cursor, where: str, isy: int) -> MagneticSymmetry:
    """The ``Isy < 0`` sub-block, in whichever of the two spellings it uses.

    Every count is asserted because this is the one block the reader has to walk
    *past* without modelling: it must land on the next phase's first line
    exactly, and a `.pcr` offers nothing to resynchronise on. The two shapes and
    their evidence are in :class:`MagneticSymmetry`'s docstring.
    """
    if isy == -1:
        _, header = cur.ints("the Nsym/Cen/Laue/MagMat line", expect=4)
        nsym, cen, laue, magmat = header
        block = MagneticSymmetry(isy=isy, nsym=nsym, cen=cen, laue=laue,
                                 magmat=magmat)
        for i in range(nsym):
            symm = _labelled(cur, "SYMM", f"SYMM {i + 1} of {nsym}", where)
            msyms = [_labelled(cur, "MSYM", f"MSYM {j + 1} of SYMM {i + 1}", where)
                     for j in range(max(magmat, 1))]
            block.operators.append((symm, tuple(msyms)))
        return block

    _, header = cur.ints("the Nsym/Cen/Laue/Ireps/N_Bas line", expect=5)
    nsym, cen, laue, ireps, n_bas = header
    if ireps >= 0:
        raise FullProfPcrError(
            f"{where}: Ireps = {ireps}. Only a negative Ireps — basis vectors "
            f"given explicitly — is evidenced here; a positive one names an "
            f"irreducible representation from FullProf's own tables, which this "
            f"reader has no copy of and may not reproduce.")
    block = MagneticSymmetry(isy=isy, nsym=nsym, cen=cen, laue=laue,
                             ireps=ireps, n_bas=n_bas)
    # The indicator line carries one flag per basis vector: `0 0 0 0` for
    # N_Bas = 4 (corpus file 3:148), a single `0` for N_Bas = 1
    # (corpus file 4:101). The count is what pins the reading.
    _, indicators = cur.ints("the Real(0)/Imaginary(1) indicator line",
                             expect=n_bas)
    block.real_imaginary = tuple(indicators)
    # Each BASR/BASI line holds 3 * N_Bas numbers — three components per basis
    # vector — and there are |Ireps| pairs per SYMM. Both counts are asserted:
    # `corpus file 1` has Nsym 3, Ireps -2, N_Bas 4 (3 x 5 = 15 lines,
    # 12 numbers each) and `corpus file 4` has Nsym 2, Ireps -1, N_Bas 1
    # (2 x 3 = 6 lines, 3 numbers each), which is what makes the rule a rule
    # rather than one file's coincidence.
    for i in range(nsym):
        symm = _labelled(cur, "SYMM", f"SYMM {i + 1} of {nsym}", where)
        basis: list = []
        for j in range(abs(ireps)):
            real = _keyworded(cur, "BASR", f"BASR {j + 1} of SYMM {i + 1}",
                              where, 3 * n_bas)
            imaginary = _keyworded(cur, "BASI", f"BASI {j + 1} of SYMM {i + 1}",
                                   where, 3 * n_bas)
            basis.append((tuple(real), tuple(imaginary)))
        block.operators.append((symm, tuple(basis)))
    return block


def _atom_floats(tokens: list, value_names: tuple, where: str,
                 line: _Line) -> list:
    """Parse an atom line's numeric tokens, naming the column a bad one sits in.

    Finding 4, the TOPAS reader's rigor: a *stated* site value that cannot be
    read is refused naming **which** column it was, not merely that some token on
    the line is not a number. A positional format cannot silently default a value
    the way a TOPAS ``.inp`` fell back on ``c["a"]`` — the token is always
    refused — so what naming the column buys is a reviewer being able to see
    whether it was ``x``, the ``occ`` or a trailing flag, rather than counting
    tokens by hand. Positions past the named columns are the trailing integer
    flags (``In Fin N_t Spc``), named generically.
    """
    numbers: list[float] = []
    for j, token in enumerate(tokens):
        try:
            numbers.append(float(token))
        except ValueError as exc:
            col = (f"{value_names[j]!r}" if j < len(value_names)
                   else f"trailing integer {j - len(value_names) + 1}")
            raise FullProfPcrError(
                f"{where}: line {line.number}: {token!r} is not a number for the "
                f"{col} column in {line.text!r} — a stated site value that "
                f"cannot be read is refused, never defaulted") from exc
    return numbers


def _read_nuclear_atom(cur: _Cursor, where: str, i: int, nat: int) -> FullProfAtom:
    """One nuclear site: a value line, a codeword line, and ``N_t``'s extras."""
    line = cur.take(f"atom {i} of {nat}")
    tokens = line.text.split()
    if len(tokens) < 2 + len(_ATOM_COLUMNS):
        raise FullProfPcrError(
            f"{where}: line {line.number}: an atom line needs a label, a "
            f"species and {len(_ATOM_COLUMNS)} numbers; found {len(tokens)} "
            f"tokens in {line.text!r}")
    numbers = _atom_floats(tokens[2:], _ATOM_COLUMNS, where, line)
    _, codewords = cur.floats(f"atom {i} codewords", at_least=1)
    atom = FullProfAtom(
        label=tokens[0], species_raw=tokens[1],
        species=normalize_species(tokens[1]),
        values=_row(_ATOM_COLUMNS, numbers, codewords),
        flags=tuple(numbers[len(_ATOM_COLUMNS):]))
    extra = _N_T_EXTRA_LINES.get(atom.n_t)
    if extra is None:
        raise FullProfPcrError(
            f"{where}: atom {atom.label!r} declares N_t = {atom.n_t}, and how "
            f"many lines that adds to the site is not established by any file "
            f"this reader was written against. Guessing it would desynchronise "
            f"every line after this one (N_t 0 and 2 are read).")
    if extra:
        _, betas = cur.floats(f"atom {i} anisotropic betas",
                              at_least=len(_BETA_COLUMNS))
        _, beta_codes = cur.floats(f"atom {i} beta codewords", at_least=1)
        atom.betas = _row(_BETA_COLUMNS, betas, beta_codes)
    return atom


def _read_magnetic_atom(cur: _Cursor, where: str, i: int, nat: int) -> FullProfAtom:
    """One magnetic site: **four** lines, values and codewords twice over.

    The moment columns are ``Rx Ry Rz`` / ``Ix Iy Iz`` under ``Isy = -1`` and
    basis-vector coefficients ``C1..C9`` under ``Isy = -2`` — the same
    positions, so they are read under the neutral names of
    :data:`_MAGNETIC_COLUMNS`. Nothing here models them; the point of reading
    them is that :attr:`FullProfModel.magnetic_phases` can *say* what it read,
    which is the alternative to dropping the phase.
    """
    line = cur.take(f"magnetic atom {i} of {nat}")
    tokens = line.text.split()
    # label, species, Mag, Vek, then the eight columns. `Mag` and `Vek` are
    # integer selectors (which magnetic form factor, which propagation vector)
    # and carry no codeword, so they sit with the label rather than in the row.
    if len(tokens) < 4 + len(_MAGNETIC_COLUMNS):
        raise FullProfPcrError(
            f"{where}: line {line.number}: a magnetic atom line needs a label, "
            f"a species, Mag, Vek and {len(_MAGNETIC_COLUMNS)} numbers; found "
            f"{len(tokens)} tokens in {line.text!r}")
    numbers = _atom_floats(tokens[2:], ("Mag", "Vek") + _MAGNETIC_COLUMNS,
                           where, line)
    _, codewords = cur.floats(f"magnetic atom {i} codewords", at_least=1)
    _, continuation = cur.floats(f"magnetic atom {i} continuation",
                                 at_least=len(_MAGNETIC_CONTINUATION))
    _, continuation_codes = cur.floats(
        f"magnetic atom {i} continuation codewords", at_least=1)
    values = _row(_MAGNETIC_COLUMNS, numbers[2:], codewords)
    values.update(_row(_MAGNETIC_CONTINUATION, continuation, continuation_codes))
    return FullProfAtom(label=tokens[0], species_raw=tokens[1],
                        species=normalize_species(tokens[1]), values=values,
                        flags=tuple(numbers[:2]))


def _read_trailing(cur: _Cursor, path: Path, model: FullProfModel) -> None:
    """The lines after the last phase: soft moment constraints and the 2θ range.

    Two productions share this region and they are told apart by whether the
    line **opens with a number**, which is a structural difference rather than a
    sniff: the fitted-range line is three numbers
    (``9.000 157.000 1``, ``corpus file 2``:177) and a soft moment
    constraint opens with a site key that is not one (``CR``, ``1C``).

    The constraints are attached to the last phase, which is where every real
    file puts them; a *non-final* phase declaring ``Mom > 0`` is refused above,
    because nothing here establishes where its block would sit. The declared
    ``Mom`` and the number of lines found are both recorded and neither is
    corrected into the other — they disagree in ``corpus file 1``, which
    declares ``Mom = 1`` and writes two constraints.
    """
    last = model.phases[-1]
    ranges: list[tuple] = []
    for line in cur.remaining():
        tokens = line.text.split()
        try:
            float(tokens[0])
        except ValueError:
            if len(tokens) < 3:
                raise FullProfPcrError(
                    f"{path}: line {line.number}: {line.text!r} follows the "
                    f"last phase and is neither a fitted-range line (three "
                    f"numbers) nor a soft moment constraint (a site key, a "
                    f"moment and a sigma)") from None
            try:
                moment, sigma = float(tokens[1]), float(tokens[2])
            except ValueError as exc:
                raise FullProfPcrError(
                    f"{path}: line {line.number}: {line.text!r} looks like a "
                    f"soft moment constraint but its moment/sigma do not "
                    f"parse") from exc
            # One production, not two: both real spellings are an atom label
            # truncated to the field's width, so the key is resolved by prefix
            # and an unresolvable one is *reported* as unresolved rather than
            # guessed at. See SoftMomentConstraint's docstring.
            matches = [j for j, atom in enumerate(last.atoms)
                       if atom.label.startswith(tokens[0])]
            last.soft_moment_constraints.append(SoftMomentConstraint(
                key=tokens[0], moment=moment, sigma=sigma,
                atom_index=matches[0] if len(matches) == 1 else None))
            continue
        numbers = []
        for token in tokens:
            try:
                numbers.append(float(token))
            except ValueError:
                break
        if len(numbers) < 2:
            raise FullProfPcrError(
                f"{path}: line {line.number}: {line.text!r} follows the last "
                f"phase and states fewer than two numbers, so it is neither a "
                f"fitted 2theta range nor anything else this reader knows")
        ranges.append(tuple(numbers[:3]))
    if len(ranges) > 1:
        raise FullProfPcrError(
            f"{path}: {len(ranges)} fitted-range lines follow the last phase, "
            f"and a single-pattern .pcr states one")
    model.fitted_range = ranges[0] if ranges else None


# --------------------------------------------------- to_structure


#: How far the per-site occupancy ratios may spread and still be called
#: constant. The corpus states ``Occ`` to five decimals — ``0.16667`` for 1/6 —
#: so the ratios carry ~2e-5 of rounding; the origin-choice error this gate
#: exists to catch is a **factor of two**. Anything between is a real partial
#: occupancy, and a real partial occupancy is refused rather than rounded off.
_OCCUPANCY_RTOL = 5e-3


def occupancy_factor(phase: FullProfPhase, where: str | None = None) -> float:
    """The common factor FullProf's ``Occ`` column carries, or a refusal.

    FullProf's ``Occ`` is the chemical occupancy times the site multiplicity
    over the general multiplicity, and the *absolute* normalisation of the
    column is degenerate with the phase scale — doubling every ``Occ`` and
    halving ``Scale`` is the same pattern, which is why the corpus carries a
    factor of 2 on two of its files and 1 on two others.

    So ``Occ_i × M_general / M_i`` is the site occupancy up to one unknown
    common factor. Where it is the *same* for every site the phase is fully
    occupied, the factor cancels, and every rietx ``occ`` is 1.0 — which is the
    only case a chemical occupancy is recoverable in. Where it is not, the
    factor and the partial occupancies are not separable and the phase is
    refused, naming the ratios: handing the column through would be a silently
    wrong structure factor.

    Returns the common factor, for the record.
    """
    import gemmi
    import numpy as np

    from ...crystallography.symmetry import expand_positions

    where = where or f"phase {phase.index} ({phase.name!r})"
    try:
        sg = gemmi.SpaceGroup(phase.space_group)
    except Exception as exc:
        raise FullProfPcrError(
            f"{where}: space group {phase.space_group_raw!r} (read as "
            f"{phase.space_group!r}) is not one gemmi resolves: {exc}") from exc
    if not phase.atoms:
        raise FullProfPcrError(
            f"{where}: the phase states Nat = 0, so it has no sites to build a "
            f"structure factor from — and dropping it would leave its R_Bragg "
            f"reporting for a phase the Structure lacks")
    general = len(list(sg.operations()))
    ratios: list[float] = []
    for atom in phase.atoms:
        xyz = np.array([atom.values[k].value for k in ("x", "y", "z")], float)
        multiplicity = len(expand_positions(sg, xyz))
        ratios.append(atom.values["occ"].value * general / multiplicity)
    reference = max(ratios, key=abs)
    if reference == 0.0 or any(
            abs(r - reference) > _OCCUPANCY_RTOL * abs(reference) for r in ratios):
        stated = ", ".join(f"{a.label}={r:.4f}"
                           for a, r in zip(phase.atoms, ratios, strict=True))
        raise FullProfPcrError(
            f"{where}: FullProf's Occ column does not reduce to one chemical "
            f"occupancy. Occ x M_general/M_site is [{stated}] under "
            f"{phase.space_group!r}, and those must agree for the arbitrary "
            f"common factor to cancel — FullProf's Occ normalisation is "
            f"degenerate with the phase scale, so a partial occupancy is not "
            f"separable from it. Unequal ratios mean either a genuinely "
            f"partially occupied phase, whose chemical occupancies are not in "
            f"the file, or the wrong origin choice for this symbol. Read "
            f"`phase.atoms[i].values['occ']` for what the file does state.")
    return reference


#: The atom columns :func:`to_structure` puts on a :class:`~rietx.schemas.Atom`
#: and whose codeword can therefore state a tie that has somewhere to go. The
#: magnetic moment columns are deliberately absent: their phase is refused
#: whole, so a tie among them is reported by that refusal, not this one.
_TIED_ATOM_COLUMNS = ("x", "y", "z", "biso", "occ")


def nuclear_parameter_ties(phase: FullProfPhase, where: str | None = None
                           ) -> tuple[list[str], list[str]]:
    """Which of a nuclear phase's codeword ties rietx reproduces, and which not.

    A ``.pcr`` writes a tie by giving two values the **same parameter number**
    in their codewords (``Code.number``), signed by ``Code.multiplier``. rietx
    reproduces some of those by construction and cannot express others on a
    :class:`~rietx.schemas.Structure` at all, and the difference decides whether
    a built structure has the same number of free parameters as the fit it came
    from. Returns ``(carried, dropped)``, each a list of human-readable group
    descriptions.

    **Carried** — a group whose members are all *coordinates of one atom*.
    ``ParameterTable._collect_atom_coords`` gives each site one ``dof.k`` per
    site-symmetry-allowed direction and writes x, y, z as affine rows onto them,
    so ``x = y = z`` on a cubic ``32e`` site is already one free parameter and
    re-declaring it would be redundant. This is *checked*, not assumed: the
    site's DOF count is re-derived here and the group is only called carried
    where rietx's freedom is no larger than FullProf's. Both real cases in the
    corpus land here — ``corpus file 4``'s O1 ties x, y and z to parameter 41
    on ``F d -3 m:2``'s 32e site (one DOF), and ``corpus file 3`` ties
    O1's and O2's x to their y (parameters 56 and 57) on ``P 42/m n m``'s 4f
    (one DOF each). The phase's **cell** ties are the same kind of shared-number
    tie, but whether rietx reproduces one turns on the space group rather than on
    a site's DOFs, so they are analysed by :func:`cell_parameter_ties` against
    ``crystallography.symmetry.cell_constraints`` — the one authority on which
    edges a setting holds equal — not here. The corpus's ``a = b`` (parameter 5,
    tetragonal) and ``a = b = c`` (parameter 40, cubic) land carried there
    because their symmetry ties the edges; the same codewords under an
    orthorhombic or triclinic symbol do not, and are reported dropped.

    **Dropped** — anything else, and the two that matter are a group spanning
    **two atoms** (a shared ``Biso`` across sites) and a group involving a
    non-coordinate column. Neither is derivable from symmetry, so nothing on the
    built ``Structure`` would hold them together and the refinement would carry
    strictly more free parameters than FullProf's did.

    Being dropped does not decide whether :func:`to_structure` refuses. That
    turns on whether the caller can put the tie back in one unambiguous call,
    which :func:`atom_tie_recoverability` answers per group: a recoverable drop
    reports, an ambiguous one refuses.
    """
    import gemmi

    from ...crystallography.wyckoff import coordinate_basis, stabilizer_rotations

    where = where or f"phase {phase.index} ({phase.name!r})"
    groups: dict[int, list[tuple[int, str, str, float]]] = {}
    for atom_index, atom in enumerate(phase.atoms):
        for column in _TIED_ATOM_COLUMNS:
            value = atom.values.get(column)
            if value is None:
                continue
            code = value.code
            if code is None:
                continue
            groups.setdefault(code.number, []).append(
                (atom_index, atom.label, column, code.multiplier))

    try:
        sg = gemmi.SpaceGroup(phase.space_group)
    except Exception:  # the symbol is refused with a better message elsewhere
        sg = None

    def dof_count(atom_index: int) -> int | None:
        """How many free coordinates rietx will give this site, or None."""
        if sg is None:
            return None
        atom = phase.atoms[atom_index]
        try:
            xyz = [atom.values[k].value for k in ("x", "y", "z")]
            return len(coordinate_basis(stabilizer_rotations(sg, xyz)))
        except Exception:
            return None

    carried: list[str] = []
    dropped: list[str] = []
    for number in sorted(groups):
        members = groups[number]
        if len(members) < 2:
            continue
        described = ", ".join(
            f"{label}.{column}(x{multiplier:+g})"
            for _, label, column, multiplier in members)
        text = f"parameter {number}: {described}"
        atom_indices = {m[0] for m in members}
        columns = {m[2] for m in members}
        if len(atom_indices) == 1 and columns <= {"x", "y", "z"}:
            # One site's coordinates. rietx's site-symmetry DOFs already unify
            # them — but only where its DOF count is no larger than the number
            # of distinct parameters FullProf spent on this site's coordinates.
            atom_index = next(iter(atom_indices))
            atom = phase.atoms[atom_index]
            fullprof_free = {
                value.code.number
                for k in ("x", "y", "z")
                if (value := atom.values.get(k)) is not None
                and value.code is not None}
            n_dof = dof_count(atom_index)
            if n_dof is not None and n_dof <= len(fullprof_free):
                carried.append(text)
                continue
        dropped.append(text)
    return carried, dropped


def atom_tie_recoverability(phase: FullProfPhase) -> dict[str, bool]:
    """For each tie :func:`nuclear_parameter_ties` drops, can the caller restore it?

    Keyed by the same ``parameter N: ...`` description that function returns, so
    the two compose. The value answers the only question that decides whether
    dropping a tie is a *stated, recoverable loss* or a reading the reader would
    have to choose between — the distinction ``io/CLAUDE.md`` draws between
    reporting and refusing.

    ``True`` where the constraint can be re-declared on the ``Refinement`` with
    one unambiguous call, measured rather than assumed:

    * a group in ``biso`` or ``occ`` alone — those are direct parameter paths
      (``phases.i.atoms.j.biso``), and ``Refinement.tie_equal`` accepts a
      cross-atom pair of them.
    * a group in **one** coordinate column where every site involved has
      **exactly one** DOF — the site's only freedom is ``dof.0``, so the
      correspondence between the two paths is forced rather than picked. Note
      the call must be written on the ``dof.k`` paths, not the ``.x``/``.y``/
      ``.z`` columns the group description names: a coordinate column already
      follows its own dof by site symmetry, and ``tie_equal`` refuses to
      outrank that. The three user-facing strings say so.

    ``False`` where writing the call would mean choosing:

    * a group spanning **different** columns (``A.x`` to ``B.y``, and equally
      ``A.x`` to ``A.y`` on one atom — the branch is ``len(columns) != 1``):
      coordinates refine through site-symmetry directions, and two ``dof``
      bases are not the same direction, so which index stands for the tied
      direction is a decision the file does not make.
    * a coordinate group touching a site whose DOF count is not 1 — with two or
      more DOFs the index correspondence is again a choice, and with none there
      is no path to tie.

    The corpus reaches none of these: its three shared-number groups are all
    *single-atom* coordinate ties, which :func:`nuclear_parameter_ties` carries.
    So this function's job is to keep a case the corpus cannot reach from being
    decided by accident — the same argument that moved the cell ties onto
    ``cell_constraints`` rather than onto corpus faith.
    """
    import gemmi

    from ...crystallography.wyckoff import coordinate_basis, stabilizer_rotations

    groups: dict[int, list[tuple[int, str, str, float]]] = {}
    for atom_index, atom in enumerate(phase.atoms):
        for column in _TIED_ATOM_COLUMNS:
            value = atom.values.get(column)
            if value is None or value.code is None:
                continue
            groups.setdefault(value.code.number, []).append(
                (atom_index, atom.label, column, value.code.multiplier))

    try:
        sg = gemmi.SpaceGroup(phase.space_group)
    except Exception:
        sg = None

    def dof_count(atom_index: int) -> int | None:
        if sg is None:
            return None
        atom = phase.atoms[atom_index]
        try:
            xyz = [atom.values[k].value for k in ("x", "y", "z")]
            return len(coordinate_basis(stabilizer_rotations(sg, xyz)))
        except Exception:
            return None

    out: dict[str, bool] = {}
    for number in sorted(groups):
        members = groups[number]
        if len(members) < 2:
            continue
        described = ", ".join(
            f"{label}.{column}(x{multiplier:+g})"
            for _, label, column, multiplier in members)
        text = f"parameter {number}: {described}"
        columns = {m[2] for m in members}
        if len(columns) != 1:
            out[text] = False
            continue
        (column,) = columns
        if column in ("biso", "occ"):
            out[text] = True
            continue
        out[text] = all(
            dof_count(index) == 1 for index in {m[0] for m in members})
    return out


#: Two decoded multipliers count as the same coefficient within this tolerance.
#: They come off the same ``round(magnitude - 10*number, 6)`` path, so equality
#: is exact for a well-formed codeword; the tolerance guards the float compare.
_CELL_TIE_MULTIPLIER_TOL = 1e-6


def _symmetry_reproduces(space_group: str, target: str, source: str) -> bool:
    """Would this phase's own symmetry tie cell edge ``target`` to ``source``?

    A ``.pcr`` ties two cell parameters the same way it ties two coordinates —
    one shared ``Code.number`` — but rietx carries such a tie on a
    :class:`~rietx.schemas.Structure` only where the space group's own metric
    already holds the edges equal, which
    ``crystallography.symmetry.cell_constraints`` is the authority on. ``b = a``
    is rietx's own constraint under a tetragonal or cubic setting, so the built
    cell states exactly what the file did and there is nothing to report; under
    an orthorhombic or triclinic one it is not, and the built ``b`` refines away
    from an ``a`` the file tied it to — a free parameter FullProf did not spend.

    Ties are followed to their **root**, because a cubic constraint table names
    ``b -> a`` and ``c -> a`` but not ``c -> b``, yet a codeword shared by ``b``
    and ``c`` is one parameter and both root to ``a``. An angle pair is also
    reproduced where symmetry fixes *both* at the same value — they then move
    together by not moving at all, which is what the file said.

    This is the same discriminator ``io/projects/topas.py`` makes for
    ``TOPAS_CELL_COUPLING_DROPPED``, one reader over, so the two agree on the same
    defect. A symbol this package cannot resolve returns ``False``, i.e.
    **report**: not being able to show the model carries the tie is not the same
    as showing it does.
    """
    try:
        import gemmi

        from ...crystallography.symmetry import cell_constraints
        cons = cell_constraints(gemmi.SpaceGroup(space_group))
    except Exception:
        return False

    def root(key: str) -> str:
        seen: set[str] = set()
        while key in cons.ties and key not in seen:
            seen.add(key)
            key = cons.ties[key]
        return key

    if target in cons.ties and root(target) == root(source):
        return True
    fixed = cons.fixed_angles
    return target in fixed and source in fixed and fixed[target] == fixed[source]


def cell_parameter_ties(phase: FullProfPhase, where: str | None = None
                        ) -> tuple[list[str], list[str]]:
    """Which of a nuclear phase's **cell** codeword ties rietx reproduces.

    The cell analogue of :func:`nuclear_parameter_ties`. FullProf ties two cell
    parameters by giving them one ``Code.number``, signed by ``Code.multiplier``:
    ``51.00000`` on both ``a`` and ``b`` ties ``a = b``, while ``52.00000`` on
    ``b`` against ``51.00000`` on ``a`` ties ``b = 2a`` — a scaled relation, not
    an equality. Whether rietx reproduces such a tie is decided entirely by the
    space group, through :func:`_symmetry_reproduces`, and *not* by any site's
    DOFs. Returns ``(carried, dropped)``, each a list of human-readable group
    descriptions.

    **Carried** — a group whose members share one multiplier (so the tie is an
    *equality*) and whose edges ``cell_constraints`` already holds equal: ``a =
    b`` on a tetragonal cell, ``a = b = c`` on a cubic one. rietx's own metric
    carries these, so re-declaring them is redundant and the built cell has the
    free parameters the file refined.

    **Dropped** — anything the setting does not already hold: ``a = b`` under an
    orthorhombic or triclinic symbol (symmetry leaves both free — the reviewer's
    round-three case), or any scaled relation such as ``b = 2a`` (symmetry only
    *equates* edges, so it never expresses a multiplier), which stays dropped
    even under a symbol that ties the edges. A dropped cell tie means the built
    ``Cell`` carries one more free length or angle than the refinement did.
    """
    where = where or f"phase {phase.index} ({phase.name!r})"
    groups: dict[int, list[tuple[str, float]]] = {}
    for key in _CELL_COLUMNS:
        value = phase.cell.get(key)
        if value is None:
            continue
        code = value.code
        if code is None:
            continue
        groups.setdefault(code.number, []).append((key, code.multiplier))

    carried: list[str] = []
    dropped: list[str] = []
    for number in sorted(groups):
        members = groups[number]
        if len(members) < 2:
            continue
        described = ", ".join(
            f"{key}(x{multiplier:+g})" for key, multiplier in members)
        text = f"parameter {number}: {described}"
        ref_key, ref_multiplier = members[0]
        equality_reproduced = all(
            abs(multiplier - ref_multiplier) < _CELL_TIE_MULTIPLIER_TOL
            and _symmetry_reproduces(phase.space_group, key, ref_key)
            for key, multiplier in members[1:])
        (carried if equality_reproduced else dropped).append(text)
    return carried, dropped


def to_structure(model: FullProfModel, *, nuclear_only: bool = False,
                                drop_parameter_ties: bool = False,
                                diagnostics: list[Diagnostic] | None = None):
    """Build a :class:`~rietx.schemas.Structure` from a parsed ``.pcr``.

    ``Biso`` is FullProf's B and rietx's ``biso`` is also B — no 8π²
    conversion. The cell, the coordinates, the displacement parameters and the
    scale all carry the file's own refine flags, decoded from the codewords.

    The one repair this reader makes on a value it hands to the ``Structure`` is
    the species spelling: :func:`normalize_species` reads FullProf's ``CR`` as
    ``Cr`` and ``CA+2`` as ``Ca2+``, because rietx's species are IUCr-spelled
    element symbols. :func:`read_fullprof_pcr` reports that repair *structurally*
    — ``species_raw`` sits beside ``species`` on every
    :class:`FullProfAtom`, so the model is checkable against the file — but a
    :class:`~rietx.schemas.Structure` carries only the one spelling, so the raw
    token is dropped here. Pass ``diagnostics=`` a list to record it: each
    distinct rewrite appends one ``FULLPROF_SPECIES_NORMALISED`` diagnostic
    naming the substitution, with ``where`` carrying every affected atom path —
    the same channel and code shape as ``crystallography.cif.structure_from_cif``
    (``CIF_SPECIES_NORMALISED``). A file that needs no rewrite appends nothing.

    Three more repairs are reported the same way where ``diagnostics=`` is
    passed: ``FULLPROF_ORIGIN_CHOICE`` where :func:`normalize_space_group` added
    an origin or axes suffix the file did not write (``F D -3 M`` →
    ``F d -3 m:2``), ``FULLPROF_OCCUPANCY_UNCHECKED`` where the occupancy-ratio
    test that licenses that choice had no discriminating power, and
    ``FULLPROF_TIE_DROPPED`` where a **cell** codeword tie the space group does
    not reproduce is lost (see :func:`cell_parameter_ties`). The cell case only
    *reports* — the cell is built either way — matching what the TOPAS reader
    does for the same defect (``TOPAS_CELL_COUPLING_DROPPED``); it does not refuse
    and is not gated on ``drop_parameter_ties``, which the *atom*-tie refusal
    below is.

    Six refusals, each naming what it would otherwise have dropped:

    * **A magnetic phase.** A ``Jbt = 1`` phase has no shape in rietx's
      magnetic model (:data:`MAGNETIC_PHASE_REFUSAL`), so returning the nuclear
      phases alone would hand back a structure that looks complete
      while the file's magnetic contribution — and its R_Bragg — went
      unmentioned. ``nuclear_only=True`` is how a caller *declares* it wants the
      nuclear subset; the omission is then the caller's, and named in the
      message this refusal replaces.
    * **A negative ``Biso``.** An oxygen site in ``corpus file 4`` refined to a
      negative value, which is a real FullProf outcome (the column absorbs
      absorption and normalisation error). rietx bounds ``biso`` at zero, and
      clamping a negative Biso to 0 changes every high-Q intensity — a
      *contradiction*, not the kind of small deviation root CLAUDE.md licenses
      a reader to repair silently.
    * **An anisotropic β block.** The β → U^ij conversion needs a convention no
      file here settles (whether the stored off-diagonal already carries the
      exponent's factor of 2), and a wrong factor is a silently wrong
      Debye-Waller factor.
    * **An occupancy column that does not reduce** — see
      :func:`occupancy_factor`.
    * **A value whose codeword column is absent.** ``Value.vary is None`` means
      the codeword was not on the line at all — a ragged or truncated line — so
      the file does not say whether FullProf refined that value. Skipping the
      ``vary`` kwarg would let ``rx.Parameter``'s schema default supply
      ``False``, making a parameter the file said nothing about
      indistinguishable from one it genuinely fixed. That is the collapse this
      module's own docstring forbids ("never collapses an absent column into
      ``False``"), so it is refused instead of invented.
    * **A codeword tie whose restoring call cannot be written unambiguously** —
      see :func:`nuclear_parameter_ties` for which ties are dropped and
      :func:`atom_tie_recoverability` for which of those refuse. The rule is
      root ``CLAUDE.md``'s: **report a stated, recoverable loss; refuse a
      reading we would have to choose.** Dropping a tie is not a contradiction,
      so it refuses only where putting it back would mean picking one
      correspondence over another — a group spanning *different* columns on
      different atoms, or a coordinate group touching a site whose DOF count is
      not 1, since ``dof.k`` indices on two different sites are not the same
      direction. Where the call *is* unambiguous — a shared ``Biso`` or ``Occ``
      across sites, or one coordinate column across single-DOF sites — the tie
      is dropped, **reported** as ``FULLPROF_TIE_DROPPED``, and the message names
      the ``Refinement.tie_equal`` / ``Refinement.tie`` call that recovers it.
      ``drop_parameter_ties=True`` remains how a caller declares it accepts the
      looser model where the tie *does* refuse. **Cell** ties always report, for
      the same reason — see :func:`cell_parameter_ties`.

    ``Scale`` is carried through **verbatim** as a starting value and a refine
    flag, and is *not* comparable with a rietx scale: FullProf's folds ``ATZ``,
    the occupancy normalisation above and its own profile normalisation into one
    number.
    """
    import rietx as rx

    magnetic = model.magnetic_phases
    if magnetic and not nuclear_only:
        named = ", ".join(f"{ph.index}:{ph.name!r} (Jbt {ph.jbt}, Isy {ph.isy}, "
                          f"{len(ph.atoms)} sites)" for ph in magnetic)
        raise FullProfPcrError(
            f"{model.path or '<model>'}: {len(magnetic)} of {len(model.phases)} "
            f"phases are magnetic: {named}. {MAGNETIC_PHASE_REFUSAL} Returning "
            f"only the nuclear phases would hand back a structure that looks "
            f"complete while those phases' contribution went unmentioned. Read "
            f"`model.magnetic_phases` for what the file states about them, or "
            f"pass nuclear_only=True to declare that the nuclear subset is "
            f"what you want.")

    phases = []
    # Keyed by the raw file token, so ``CR`` on two sites is one diagnostic
    # carrying both atom paths — the shape ``structure_from_cif`` uses. The
    # index is the phase's position in the *built* Structure, not the file's
    # ``Nph`` ordinal, because that is what a ``where`` path has to resolve
    # against on the object handed back.
    rewrites: dict[str, tuple[str, list[str]]] = {}
    #: (phase path, group description) per tie the caller declared it would drop.
    dropped_ties: list[tuple[str, str]] = []
    #: (phase path, group description) per *atom* codeword tie that is dropped but
    #: which the caller can re-declare in one unambiguous call. Reported
    #: unconditionally rather than refused, for the same reason the cell arm below
    #: is: the loss is stated and recoverable, so it is not a reading we would have
    #: to choose. ``atom_tie_recoverability`` decides which arm a group lands in.
    recoverable_ties: list[tuple[str, str]] = []
    #: (cell path, group description) per *cell* codeword tie the space group does
    #: not reproduce. Reported unconditionally — never a refusal — because the
    #: cell is built either way and the loss is the same whether or not a caller
    #: passed a list; this matches ``TOPAS_CELL_COUPLING_DROPPED`` one reader over.
    dropped_cell_ties: list[tuple[str, str]] = []
    #: Origin/axes suffixes this reader added that the file did not write.
    origin_choices: list[tuple[str, str, str]] = []
    #: Phases whose occupancy-ratio cross-check could not discriminate.
    unchecked_occupancy: list[tuple[str, str]] = []
    for structure_index, ph in enumerate(model.nuclear_phases):
        where = f"{model.path or '<model>'}: phase {ph.index} ({ph.name!r})"
        missing = [k for k in _CELL_COLUMNS if k not in ph.cell]
        if missing:
            raise FullProfPcrError(
                f"{where}: the cell line states no {', '.join(missing)}, so this "
                f"phase cannot be built — and dropping it would leave its "
                f"R_Bragg reporting for a phase the Structure lacks")
        for atom in ph.atoms:
            if atom.betas:
                raise FullProfPcrError(
                    f"{where}: atom {atom.label!r} carries an anisotropic beta "
                    f"block (N_t = {atom.n_t}). Converting FullProf's beta_ij "
                    f"to rietx's U^ij needs a convention no file here settles — "
                    f"whether the stored off-diagonal already carries the "
                    f"exponent's factor of 2 — and a wrong factor is a silently "
                    f"wrong Debye-Waller factor at high Q. Read "
                    f"`atom.betas` for what the file states.")
            biso = atom.values["biso"].value
            if biso < 0.0:
                raise FullProfPcrError(
                    f"{where}: atom {atom.label!r} has Biso = {biso}, and rietx "
                    f"bounds biso at zero. A negative B is a real FullProf "
                    f"outcome — the column absorbs absorption and normalisation "
                    f"error — but clamping it to zero changes every high-Q "
                    f"intensity, so it is a contradiction rather than a "
                    f"deviation a reader may repair. Read "
                    f"`atom.values['biso'].value` for the file's own number.")
        # The occupancy check is also what verifies `normalize_space_group`'s
        # origin choice: a wrong origin gives wrong multiplicities, so the
        # ratios stop agreeing and the phase is refused rather than returned.
        occupancy_factor(ph, where)
        # ...but only where it has more than one ratio to compare. With a single
        # site the test compares one number with itself and passes for *every*
        # setting, so the licence it grants the origin choice above is vacuous
        # exactly there. That cannot be repaired by a better test — FullProf's
        # Occ carries one arbitrary common factor per phase, so one site is one
        # equation in two unknowns — so it is reported rather than fixed.
        if len(ph.atoms) == 1:
            unchecked_occupancy.append(
                (f"phases.{structure_index}", ph.space_group))
        # Only the *setting* suffix is reported, not the case repair beside it:
        # lower-casing the tail of a HM symbol is lossless (everything after the
        # lattice letter is drawn from `m a b c d n` plus digits, `/` and `-`),
        # whereas choosing an origin or an axes setting the file never wrote is
        # this reader supplying a convention, which is what a caller has to be
        # able to see.
        if ":" in ph.space_group and ":" not in ph.space_group_raw:
            origin_choices.append((f"phases.{structure_index}",
                                   ph.space_group_raw.strip(), ph.space_group))

        # A codeword tie is refused before anything is built only where its
        # restoring call would be a choice rather than a statement; the rest
        # report. `atom_tie_recoverability` draws that line.
        carried, dropped = nuclear_parameter_ties(ph, where)
        # A dropped tie the caller can re-declare in one unambiguous call is a
        # stated, recoverable loss, so it reports; one that would make us choose
        # between two readings of the file refuses. `io/CLAUDE.md`'s rule.
        recoverable = atom_tie_recoverability(ph)
        restorable = [g for g in dropped if recoverable.get(g, False)]
        dropped = [g for g in dropped if not recoverable.get(g, False)]
        for group in restorable:
            recoverable_ties.append((f"phases.{structure_index}", group))
        if dropped and not drop_parameter_ties:
            also_carried = (f" It does reproduce {'; '.join(carried)}."
                            if carried else "")
            raise FullProfPcrError(
                f"{where}: the file ties parameters that a Structure cannot "
                f"carry — {'; '.join(dropped)}. A .pcr writes a tie by giving "
                f"two values one parameter number and a signed multiplier, and "
                f"rietx reproduces such a tie on a Structure only where its own "
                f"site symmetry already does.{also_carried} Building anyway "
                f"would hand back a model with strictly more free parameters "
                f"than the refinement this file records, with nothing raised. "
                f"The tie can be re-declared one layer up, on the Refinement: "
                f"`ref.tie_equal(['phases.{structure_index}.atoms.I.biso', "
                f"'phases.{structure_index}.atoms.J.biso'])` for a +1 group in "
                f"Biso or Occ, or the same call on the DOF paths "
                f"(`phases.{structure_index}.atoms.I.dof.k`) for one in a "
                f"coordinate column — a coordinate column already follows its "
                f"own dof by site symmetry, so tie_equal refuses `.x` and takes "
                f"`.dof.k`. `ref.tie(path, source, scale=multiplier)` for a "
                f"signed one. "
                f"Pass drop_parameter_ties=True to declare instead that the "
                f"looser model is what you want.")
        for group in dropped:
            dropped_ties.append((f"phases.{structure_index}", group))

        # The cell's ties are the one tie the atom analysis above does not reach.
        # rietx's own metric carries them where the space group holds the edges
        # equal (the corpus's tetragonal a = b, cubic a = b = c) and drops them
        # where it does not (a = b under an orthorhombic or triclinic symbol, or
        # a scaled b = 2a symmetry never expresses). Unlike a cross-atom group
        # this only *reports*: the cell is built the same either way, so refusing
        # would gate a build on a diagnostic that the sibling reader emits without
        # one. See `cell_parameter_ties` and `_symmetry_reproduces`.
        _, cell_dropped = cell_parameter_ties(ph, where)
        for group in cell_dropped:
            dropped_cell_ties.append((f"phases.{structure_index}.cell", group))

        def _p(value: Value, what: str, **kw):
            """One rietx Parameter carrying the file's own refine flag.

            The tri-state is **not** collapsed here. ``vary is None`` means the
            codeword column was absent from the line, so the file states no
            protocol for this value; letting the schema default supply ``False``
            would report it as definitively fixed. Refused instead — a ragged
            line is a malformed file, and this reader's whole claim is that it
            never turns an absence into a confident answer.
            """
            if (free := value.vary) is None:
                raise FullProfPcrError(
                    f"{where}: {what} states the value {value.value!r} with no "
                    f"codeword column beside it — the line is ragged or "
                    f"truncated, so the file does not say whether FullProf "
                    f"refined this value. FullProf always writes the codeword "
                    f"slot, so an absent column is a damaged line rather than a "
                    f"held parameter, and reading it as vary=False would make it "
                    f"indistinguishable from one the file genuinely fixed.")
            return rx.Parameter(value=value.value, vary=free, **kw)

        # `rx.Cell` and the atoms are built *inside* the try with the phase: a
        # pydantic refusal on a degenerate cell length or an out-of-bound
        # coordinate is a schema refusal like any other, and the comment below
        # claims every one of them is converted here. Built above the try they
        # escaped as a raw ValidationError naming a field but not the file.
        scale = ph.profile.get("scale")
        try:
            cell = rx.Cell(**{
                name: _p(ph.cell[key], f"the cell's {key}")
                for name, key in zip(("a", "b", "c", "alpha", "beta", "gamma"),
                                     _CELL_COLUMNS, strict=True)})
            atoms = [
                rx.Atom(label=atom.label, species=atom.species,
                        x=_p(atom.values["x"], f"atom {atom.label!r}'s x"),
                        y=_p(atom.values["y"], f"atom {atom.label!r}'s y"),
                        z=_p(atom.values["z"], f"atom {atom.label!r}'s z"),
                        # Fully occupied, verified above; the file's own Occ is a
                        # multiplicity-scaled quantity and stays on the model.
                        occ=rx.Parameter(value=1.0, min=0.0, max=1.5),
                        biso=_p(atom.values["biso"],
                                f"atom {atom.label!r}'s Biso",
                                min=0.0, max=25.0))
                for atom in ph.atoms]
            phases.append(rx.Phase(
                name=ph.name, space_group=ph.space_group, cell=cell, atoms=atoms,
                scale=(rx.Parameter(value=1e-4, min=0.0, transform="softplus")
                       if scale is None else
                       _p(scale, "the phase scale", min=0.0,
                          transform="softplus"))))
        except FullProfPcrError:
            raise
        except Exception as exc:
            # Every schema refusal is converted at this boundary: a reader raises
            # naming the file, and pydantic's report names a field.
            raise FullProfPcrError(f"{where}: {exc}") from exc
        # Every atom above is past the beta/biso/occupancy refusals and on the
        # Structure — collect its species rewrite now that its path is real.
        for atom_index, atom in enumerate(ph.atoms):
            if atom.species != atom.species_raw:
                rewrites.setdefault(atom.species_raw, (atom.species, []))[1].append(
                    f"phases.{structure_index}.atoms.{atom_index}.species")
    if not phases:
        raise FullProfPcrError(
            f"{model.path or '<model>'}: no nuclear phase to build. The file "
            f"states {len(model.phases)} phase(s), all magnetic — read "
            f"`model.magnetic_phases` for what it does say about them.")
    if diagnostics is not None:
        named = model.path or "<model>"
        # `nuclear_only=True` makes the omission the *caller's* declared choice,
        # which is not the same as the omission being invisible (WP-1328): the
        # channel still says which phases went, what each stated, and its
        # R_Bragg, so a caller who asked for the nuclear subset can still see
        # the size of what they asked to drop.
        for ph in model.magnetic_phases:
            moment_columns = sorted(
                {k for atom in ph.atoms for k in ("m1", "m2", "m3")
                 if atom.values.get(k)})
            diagnostics.append(Diagnostic(
                level="warning", code="FULLPROF_MAGNETIC_PHASE_OMITTED",
                where=[f"phases.{ph.index}"],
                value=ph.r_bragg,
                message=(f"{named}: phase {ph.index} ({ph.name!r}) is magnetic "
                         f"(Jbt {ph.jbt}, Isy {ph.isy}, {len(ph.atoms)} site"
                         f"{'' if len(ph.atoms) == 1 else 's'}, "
                         f"{len(ph.propagation_vectors)} propagation vector"
                         f"{'' if len(ph.propagation_vectors) == 1 else 's'}, "
                         f"non-zero moment columns "
                         f"{', '.join(moment_columns) or 'none'}"
                         + (f", R_Bragg {ph.r_bragg}" if ph.r_bragg is not None
                            else "")
                         + ") and nuclear_only=True omitted it"),
                suggestion=MAGNETIC_PHASE_REFUSAL))
        for raw, (canonical, wheres) in rewrites.items():
            diagnostics.append(Diagnostic(
                level="info", code="FULLPROF_SPECIES_NORMALISED",
                message=(f"species {raw!r} in {named} read as "
                         f"{canonical!r} — FullProf writes the scattering token in "
                         f"the author's case; normalised to IUCr spelling"),
                where=wheres))
        # The origin/axes choice is a *repair* on a value that reaches the
        # Structure, exactly as the species spelling is, so it is reported on
        # the same channel: FullProf writes no suffix at all, and which setting
        # a bare symbol means is a convention this reader supplied.
        for path, raw, resolved in origin_choices:
            diagnostics.append(Diagnostic(
                level="info", code="FULLPROF_ORIGIN_CHOICE",
                message=(f"space group {raw!r} in {named} read as {resolved!r} "
                         f"— FullProf writes no origin-choice or axes suffix, so "
                         f"the setting was chosen here (origin choice 2 where the "
                         f"bare symbol resolves to 1; rhombohedral axes where the "
                         f"cell says so) and licensed by the occupancy-ratio "
                         f"check, which a wrong setting fails"),
                where=[f"{path}.space_group"]))
        for path, sg in unchecked_occupancy:
            diagnostics.append(Diagnostic(
                level="warning", code="FULLPROF_OCCUPANCY_UNCHECKED",
                message=(f"the occupancy-ratio check on {path} of {named} "
                         f"compared a single site with itself, so it passed for "
                         f"{sg!r} without discriminating — with one site there "
                         f"is one equation and two unknowns (the chemical "
                         f"occupancy and FullProf's arbitrary per-phase Occ "
                         f"factor), so it cannot license this phase's setting "
                         f"the way it does a multi-site one"),
                where=[f"{path}.atoms.0.occ"]))
        for path, group in dropped_ties:
            diagnostics.append(Diagnostic(
                level="warning", code="FULLPROF_TIE_DROPPED",
                message=(f"drop_parameter_ties=True: the codeword tie {group} in "
                         f"{named} is not carried onto the Structure, which "
                         f"therefore has more free parameters than the "
                         f"refinement the file records. Re-declare it with "
                         f"Refinement.tie_equal/tie to recover the constraint"),
                where=[path]))
        # The cell arm of the same code: a cell codeword tie the space group does
        # not reproduce. No `drop_parameter_ties=True` prefix — this is not gated
        # on the flag (the cell builds either way), so the sentence is the loss
        # itself, the same one `TOPAS_CELL_COUPLING_DROPPED` carries.
        # The recoverable atom arm: dropped, reported, and restorable in one call.
        for path, group in recoverable_ties:
            diagnostics.append(Diagnostic(
                level="warning", code="FULLPROF_TIE_DROPPED",
                message=(f"the codeword tie {group} in {named} is not carried "
                         f"onto the Structure, which therefore has more free "
                         f"parameters than the refinement the file records. It "
                         f"is dropped rather than refused because it can be "
                         f"re-declared in one unambiguous call: "
                         f"Refinement.tie_equal on the two parameter paths — "
                         f"the column paths (phases.i.atoms.j.biso, .occ) for a "
                         f"Biso or Occ group, but the DOF paths "
                         f"(phases.i.atoms.j.dof.k) for a coordinate group, "
                         f"because a coordinate column already follows its own "
                         f"dof by site symmetry and tie_equal refuses to "
                         f"outrank that — or Refinement.tie(path, source, "
                         f"scale=multiplier) for a signed group"),
                where=[path]))
        for path, group in dropped_cell_ties:
            diagnostics.append(Diagnostic(
                level="warning", code="FULLPROF_TIE_DROPPED",
                message=(f"the cell codeword tie {group} in {named} is not "
                         f"carried onto the Structure: the space group does not "
                         f"tie these cell parameters, so the built cell has more "
                         f"free parameters than the refinement the file records. "
                         f"Re-declare it with Refinement.tie_equal/tie to recover "
                         f"the constraint"),
                where=[path]))
    try:
        return rx.Structure(phases=phases)
    except Exception as exc:
        raise FullProfPcrError(f"{model.path or '<model>'}: {exc}") from exc


# ------------------------------------------------------------------- the writer


def _bare_symbol(xhm: str) -> str:
    return xhm.split(":", 1)[0].strip()


def from_structure(structure: Structure) -> str:
    """Serialise ``structure`` as a FullProf ``.pcr`` — the inverse of
    :func:`to_structure`.

    Carries exactly what :func:`to_structure` reads back: per phase, the
    space group, the six cell edges, and every atom's coordinates, Biso and
    ``vary``. Nothing else — the instrument resolution function, the fitted
    2θ range and every control/output switch on the file are FullProf
    protocol :func:`to_structure` never reads into a ``Structure``, so this
    writer invents safe, inert values for them (a two-point flat background,
    Cu Kα1/Kα2 on the pattern line, one cycle) purely so the file is
    *complete* — a ``.pcr`` is positional with no keyword to resynchronise
    on, so every line :func:`read_fullprof_pcr` expects must exist even
    where a ``Structure`` carries nothing for it.

    Every free parameter gets its **own** codeword number
    (``10 * n + 1``, `n` counting up from 1), never a shared tie: a
    Structure carries no record of which parameters were tied in the
    refinement that produced it, and :func:`to_structure` only ever *reports*
    a dropped tie rather than needing one reconstructed, so a tie-free
    encoding loses nothing a caller could tell apart from one that tried and
    got the grouping wrong.

    FullProf's ``Occ`` column is discarded by :func:`to_structure` — every
    atom always comes back fully occupied — so this writer computes it from
    each site's own multiplicity (``Occ = M_site / M_general``, the *only*
    value that makes every ratio equal to 1 and so passes
    :func:`occupancy_factor`'s consistency check) rather than carrying the
    source ``Structure``'s (nonexistent) chemical occupancy.

    Eight refusals, each naming what FullProf's grammar cannot state, or
    what this same module's own reader would refuse on the way back in. A
    blank phase name: the name line is comment-stripped like every other
    line, so a name that strips to nothing leaves the line blank and the
    reader's own blank-line filter drops it from the positional walk
    entirely, desynchronising everything after it rather than raising. A
    phase name, or an atom's label or species, carrying one of FullProf's
    comment markers (``!``/``#``/``<--``): the reader cuts a line at the
    first one it meets, so the rest of that line, codeword and all, would
    silently vanish. An anisotropic site: FullProf's β_ij convention is
    exactly what :func:`to_structure` itself refuses to assume on the way
    in, so writing one would assume the convention this reader declines to
    read back. A space group whose resolved setting a bare symbol cannot
    reach: FullProf writes no origin or axis suffix at all, so
    :func:`normalize_space_group` always *prefers* origin choice 2 over a
    bare symbol landing on choice 1, and the rhombohedral axes only where
    the cell metric already says so — there is no way to spell "no, choice
    1" in this format. The check is not a heuristic: it calls
    :func:`normalize_space_group` on the candidate bare symbol and this
    phase's own cell, the same call :func:`read_fullprof_pcr` will make, and
    refuses unless that reproduces ``get_spacegroup(phase.space_group).xhm()``
    exactly. An atom's label or species carrying whitespace: a ``.pcr`` atom
    line is whitespace-tokenized, so an embedded space would desynchronise
    every column after it. A negative ``biso``: :func:`to_structure`
    refuses one on the way in (§ above), so writing one here would only fail
    later, at the read, with the file already on disk. And a **non-finite**
    value, which ``repr`` spells ``inf``/``nan`` and FullProf does not parse —
    surfaced by the review pass on this writer's own branch and answered for
    all three foreign-format writers at once (WP-1118).
    """
    import numpy as np

    from ..._about import DIST_NAME
    from ...crystallography.symmetry import (
        expand_positions,
        get_spacegroup,
        refuse_operation_list,
    )
    from ...schemas.instrument import _KA_DOUBLETS

    for phase in structure.phases:
        # A non-finite value is refused before anything else, for all three
        # foreign-format writers at once (WP-1118). `Parameter` does not forbid
        # one and a converged fit cannot reach one, but `repr` spells it
        # `inf`/`nan` and FullProf parses neither — so the file would be
        # written and fail in someone else's program instead of here.
        for param in (phase.cell.a, phase.cell.b, phase.cell.c,
                      phase.cell.alpha, phase.cell.beta, phase.cell.gamma,
                      phase.scale,
                      *(p for atom in phase.atoms
                        for p in (atom.x, atom.y, atom.z, atom.biso))):
            if not math.isfinite(param.value):
                raise ValueError(
                    f"phase {phase.name!r} carries a value of "
                    f"{param.value!r}, which `repr` spells "
                    f"'{param.value}' and FullProf does not parse — refused "
                    f"here rather than written into a file that fails in "
                    f"another program")
        if not phase.name.strip():
            raise ValueError(
                f"phase name {phase.name!r} cannot be written to a FullProf "
                f".pcr: the phase-name line is comment-stripped like every "
                f"other line, so a blank name leaves nothing on it and the "
                f"line is dropped from the positional walk entirely — "
                f"desynchronising every line after it rather than raising")
        if "\n" in phase.name or "\r" in phase.name:
            raise ValueError(
                f"phase name {phase.name!r} cannot be written to a FullProf "
                f".pcr: it carries a line break, and the phase-name line is "
                f"one line of a positional walk — the remainder becomes a "
                f"line of its own and every line after it is read under the "
                f"wrong name, the same desynchronisation a blank name causes "
                f"above")
        for marker in ("!", "#", "<--"):
            if marker in phase.name:
                raise ValueError(
                    f"phase name {phase.name!r} cannot be written to a "
                    f"FullProf .pcr: it contains {marker!r}, which the reader "
                    f"takes as a comment marker and cuts the line there")
        for atom in phase.atoms:
            for marker in ("!", "#", "<--"):
                if marker in atom.label or marker in atom.species:
                    raise ValueError(
                        f"phase {phase.name!r}: atom label {atom.label!r} / "
                        f"species {atom.species!r} contains {marker!r}, which "
                        f"a .pcr atom line takes as a comment marker and cuts "
                        f"the line there — the same reason the phase name is "
                        f"refused this marker above")
            if atom.aniso is not None:
                raise ValueError(
                    f"phase {phase.name!r}: atom {atom.label!r} carries an "
                    f"anisotropic displacement tensor. FullProf's beta_ij "
                    f"convention (whether the stored off-diagonal already "
                    f"carries the exponent's factor of 2) is not settled by "
                    f"any file to_structure was written against, so writing "
                    f"one would assume a convention this reader refuses to "
                    f"read back — the same refusal to_structure makes on the "
                    f"way in.")
            if any(ch.isspace() for ch in atom.label) or any(
                    ch.isspace() for ch in atom.species):
                raise ValueError(
                    f"phase {phase.name!r}: atom label {atom.label!r} / "
                    f"species {atom.species!r} contains whitespace, which a "
                    f".pcr atom line cannot carry — the line is "
                    f"whitespace-tokenized and a space inside either field "
                    f"desynchronises every column after it")
            if atom.biso.value < 0.0:
                raise ValueError(
                    f"phase {phase.name!r}: atom {atom.label!r} has Biso = "
                    f"{atom.biso.value}, and read_fullprof_pcr's own "
                    f"to_structure refuses a negative Biso on the way back "
                    f"in (it bounds biso at zero) — writing this file would "
                    f"only fail later, at the read, rather than here where "
                    f"the value is still in hand")

    counter = [0]

    def _code() -> float:
        counter[0] += 1
        return 10.0 * counter[0] + 1.0

    def _free_or_held(param: Parameter) -> float:
        return _code() if param.vary else 0.0

    body: list[str] = []
    # The zero-shift line: value/codeword interleaved, four pairs. Nothing a
    # Structure carries maps onto it, so every value is inert and every
    # codeword held — `lambda_slot`'s own docstring calls it "a stale number
    # with an inert codeword, never the wavelength".
    body.append("0.0 0.0 0.0 0.0 0.0 0.0 1.0 0.0")

    for phase in structure.phases:
        refuse_operation_list(phase, "a FullProf `.pcr`")
        sg = get_spacegroup(phase.space_group)
        resolved = sg.xhm()
        bare = _bare_symbol(resolved)
        cell_dict = {"a": phase.cell.a.value, "b": phase.cell.b.value,
                    "c": phase.cell.c.value, "alpha": phase.cell.alpha.value,
                    "beta": phase.cell.beta.value, "gamma": phase.cell.gamma.value}
        check = normalize_space_group(bare, cell_dict)
        # Compared as *settings*, not as text: a hexagonal-axes R symbol reads
        # back with no suffix at all (`get_spacegroup`'s default for a bare
        # `R -3 c` already is `:H`), so the literal strings disagree while the
        # group is the same one.
        if get_spacegroup(check).xhm() != resolved:
            raise ValueError(
                f"phase {phase.name!r}: space group {resolved!r} cannot be "
                f"written to a FullProf .pcr — the format has no suffix for "
                f"an origin or axis choice, and the bare symbol {bare!r} "
                f"would read back as {check!r} instead. FullProf can only "
                f"state a setting its own case/origin/rhombohedral-axes "
                f"convention already prefers.")

        general = len(list(sg.operations()))
        body.append(phase.name)
        phase_control = dict(nat=len(phase.atoms), dis=0, ang_or_mom=0,
                             pr1=0.0, pr2=0.0, pr3=1.0, jbt=0, irf=0, isy=0,
                             str=0, furth=0, atz=0.0, nvk=0, npr=0, more=0)
        body.append(" ".join(repr(phase_control[k]) for k in _PHASE_FIELDS))
        body.append(bare)

        for atom in phase.atoms:
            xyz = np.array([atom.x.value, atom.y.value, atom.z.value], float)
            multiplicity = len(expand_positions(sg, xyz))
            occ = multiplicity / general
            body.append(f"{atom.label} {atom.species} {atom.x.value!r} "
                       f"{atom.y.value!r} {atom.z.value!r} {atom.biso.value!r} "
                       f"{occ!r}")
            # Occ carries no vary state on our side (to_structure discards the
            # column entire), so its own codeword is held.
            body.append(" ".join(repr(_free_or_held(p)) for p in
                                 (atom.x, atom.y, atom.z, atom.biso)) + " 0.0")

        # Scale/shape line: `scale` is the phase's own, everything else is a
        # profile term no Structure carries, so it is inert and held.
        body.append(f"{phase.scale.value!r} 0.0 0.0 0.0 0.0 0.0 0")
        body.append(f"{_free_or_held(phase.scale)!r} 0.0 0.0 0.0 0.0 0.0")
        # Width line (U/V/W/X/Y/GauSiz/LorSiz): instrument profile, inert.
        body.append("0.0 0.0 0.0 0.0 0.0 0.0 0.0 0")
        body.append("0.0 0.0 0.0 0.0 0.0 0.0 0.0")
        # Cell line: the six edges, each its own codeword, no trailing selector.
        cell_params = (phase.cell.a, phase.cell.b, phase.cell.c,
                       phase.cell.alpha, phase.cell.beta, phase.cell.gamma)
        body.append(" ".join(repr(p.value) for p in cell_params))
        body.append(" ".join(repr(_free_or_held(p)) for p in cell_params))
        # Pref/Asy line: preferred orientation and asymmetry, inert.
        body.append("0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0")
        body.append("0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0")

    lines: list[str] = [f"COMM Written by {DIST_NAME}.io.projects.fullprof.write_fullprof_pcr"]
    control = dict(job=0, npr=0, nph=len(structure.phases), nba=2, nex=0,
                   nsc=0, nor=0, dum=0, iwg=0, ilo=0, ias=0, res=0, ste=0,
                   nre=0, cry=0, uni=0, cor=0, opt=0, aut=0)
    lines.append(" ".join(str(control[k]) for k in _CONTROL_FIELDS))
    lines.append(" ".join("0" for _ in _OUTPUT_FIELDS))
    # Cu Kα1/Kα2 from the package's own canonical anode table — never a
    # second, independently-sourced pair — even though `to_structure` never
    # reads this line back into a `Structure` at all (a `Structure` carries
    # no `Instrument`, so this whole line is an inert placeholder for the
    # reader's positional walk regardless of which anode it names).
    ka1, ka2 = _KA_DOUBLETS["CuKa"]
    pattern = dict(lambda1=ka1, lambda2=ka2, ratio=0.5, bkpos=40.0,
                   wdt=8.0, cthm=1.0, mur=0.0, asylim=50.0, rpolarz=0.0,
                   mur2=0.0)
    lines.append(" ".join(repr(pattern[k]) for k in _PATTERN_FIELDS))
    cycles = dict(ncy=1, eps=0.01, r_at=1.0, r_an=1.0, r_pr=1.0, r_gl=1.0,
                 thmin=5.0, step=0.02, thmax=100.0, psd=0.0, sent0=0.0)
    lines.append(" ".join(repr(cycles[k]) for k in _CYCLE_FIELDS))
    # Nba = 2, a flat two-point background — the minimum this reader accepts.
    lines.append("5.0 10.0 0.0")
    lines.append("155.0 10.0 0.0")
    # Nex = 0, so no excluded-region lines follow the background — then the
    # refined-parameter count `_read_phase`'s caller reads next
    # (`cur.floats("the refined-parameter count", ...)`), which is a
    # required line regardless of Nex and is `counter[0]`, the number of
    # codewords this writer actually handed out.
    lines.append(str(counter[0]))
    lines.extend(body)
    return "\n".join(lines) + "\n"


def write_fullprof_pcr(structure: Structure, path: str | Path) -> None:
    """Write ``structure`` to ``path`` as a FullProf ``.pcr``. See
    :func:`from_structure` for exactly what carries and what does not."""
    Path(path).write_text(from_structure(structure), encoding="utf-8")
