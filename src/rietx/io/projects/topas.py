"""Read a TOPAS ``.inp`` refinement input into a rietx model.

Format: Bruker TOPAS (Academic/v4-v7) input files. TOPAS itself is closed
source; this reader is written from the *file syntax* only, as
``ATTRIBUTION.md``'s fence requires — no TOPAS code or macro library is used,
and the emission-profile macros (``CuKa5`` and friends) are deliberately **not**
expanded here: only the anode is reported, and the caller supplies the
wavelengths from :data:`rietx.schemas.instrument._RADIATIONS`.

Why this belongs in the package: a ``.inp`` carries the whole solved model —
phases, sites, cell, instrument geometry, and the converged ``r_wp`` — so it is
the cheapest possible source of a *validated* refinement to test against. The
alternative is hunting CIFs that may not match what was actually fitted.

**The format, as this reader understands it.** Five rounds of this reader were
written from archive files, which finds the bugs one lab's dialect happens to
contain and does not terminate. The archive is the maintainer's own unpublished
research data, so its files are cited as **archive file 1** onwards and the map
from number to file is not public; the maintainer holds it in the private
repository ``yue-here/rietx-corpus-map``. The model below is derived from TOPAS
Academic's own *Technical Reference* instead, and the archive is used to
corroborate and to prioritise. Where the two disagreed, the reference won and the code moved.

1. **A lexer, then a pre-processor, then a grammar — in that order** (§1.2, §19).
   A line comment is ``'`` to end of line; a block comment is ``/* … */`` **and
   nests**. The pre-processor then decides what text there even is: ``macro``
   definitions, ``#include``/``#ingest``/``#external_INP``,
   ``#define``/``#undef``, the ``#if``/``#ifdef``/``#ifndef``/``#elseif``/
   ``#else``/``#endif`` family, ``#delete_macros``, ``#list``, and the ``#m_*``
   directives invoked on macro expansion. This reader evaluates ``macro``
   excision, the ``#ifdef``/``#ifndef`` family and ``#prm``/``#if``/``#elseif``
   over hash parameters (§19.1.2, WP-1433); the rest is refused by name,
   because a directive it does not evaluate means the text in hand is not the
   text TOPAS parsed. See :func:`refuse_unevaluable_directives`.
2. **Everything is a token; nothing is a line.** The format is
   whitespace-insensitive, so a keyword, a value or a directive is wherever it is
   written. Every line anchor this reader ever had was typography mistaken for
   syntax, and each cost real files — the cell scan (a whole cell on one line),
   the site split (two sites on one line), and the conditional resolver
   (``#else #ifdef X``, 283 files). :func:`_masked` is the one mechanism that
   makes a token scan safe.
3. **The scope is four levels**, and §5.1's tree is the authority for it::

       Ttop → xdd → {str | dummy_str | hkl_Is | xo_Is | d_Is} → site → occ

   with ``xdd``, the phase kinds, ``site`` and ``occ`` all arrays. So a phase is
   a fact about one **pattern**, a ``beq`` is a fact about one ``occ``, and
   ``r_wp`` exists at both the top and the dataset level. A block runs to "the
   next keyword of the same type" (§5.1), which is what :data:`_BLOCK` slices —
   and ``for``/``load``/``move_to`` suspend that. ``for xdds``/``for strs`` are
   expanded into the blocks they reach (:func:`expand_for_loops`); the rest
   refuse (:func:`refuse_moved_attachment`).
4. **One value grammar, and a name is a flag** (§1.2, §2.1-2.3). ``#`` is a
   number, ``$`` a string, ``N`` a name, ``E`` "an equation (i.e. ``= a+b;``) or
   constant (i.e. ``1.245``) or a parameter name with a value (i.e. ``lp
   5.4013``) that can be refined", ``!E`` the same but not refinable. Crucially:
   "*a parameter is flagged for refinement by giving it a name*" — so ``beq b1
   0.5`` is **refined**, ``!b1`` holds it, ``@`` refines it anonymously, and a
   bare number is a constant. :func:`_read_tail` is the one place that knows all
   of this and :func:`_flag` the one place that decides the refine state.
5. **What the reference does not settle.** It gives the notation and the tree; it
   does not give a lexical grammar for a *value* as it is actually written. The
   write-back backtick, the ``= expr;: value`` evaluated tail, the
   ``_esd``/``_LIMIT_*`` suffixes, the ``A1``/``A2``/``A3`` coordinate macros and
   the ``ADPs { … }`` six-slot ordering are archive-derived and recorded as such
   in ``tests/data/README.md``. The authority that would settle them is a TOPAS
   ``.OUT`` writer specification, which is not published.

Four properties of these files cause silent, not loud, failures, and each is
handled explicitly below. All four were found by refining real archives, not by
reading the syntax:

1. **Dead text outnumbers live text.** ``/* … */`` blocks and ``'`` line
   comments routinely disable several instrument blocks per file. Reading a
   wavelength without stripping them picks up whichever block was commented out.
   A ``'`` inside a ``"…"`` string is *not* a comment, though: cutting there
   turned ``xdd "C:\\data\\o'brien.xy"`` into ``C:\\data\\o`` and a phase called
   ``d'Alembert`` into ``d``, a silently mislabelled phase.
2. **``#ifdef`` gates real content.** A phase inside a disabled branch is not in
   the model. Nesting is shallow but real.
3. **A coordinate is not always a literal.** Special positions are conventionally
   written as equations (``x = 1/3;``), and refinable values carry a *name*
   before the number (``y ph1_o_y 0.24625```). A parser that demands a bare
   number silently drops the first and mis-reads the second — dropping two heavy
   atoms out of seven cost a 98 wt% phase-fraction error with a *better* Rwp,
   which is why :func:`read_topas_inp` counts sites and raises.
4. **The refine flags are the payload, not the numbers** (WP-1118). A control
   file says which parameters were free and which were held, and that is the
   part a person cannot reconstruct from a CIF plus a pattern — it is also what
   decides whether a cross-code comparison means anything. ``!`` is held, ``@``
   is refined, and a trailing backtick means TOPAS wrote the value back after
   refining it; the *absence* of that backtick is the inference WP-1110's agent
   round named as the hardest single thing about transcribing an ``.inp`` by
   hand. :func:`refined` is that reading, and it is a tri-state: a file that
   says nothing is not a file that said "held".
5. **Symbols use TOPAS spellings.** Space-group origin choices are letter
   suffixes (``Pn-3mZ``), and ionic charge is written sign-first (``Cu+1``).
   Both are translated; the origin one matters because dropping the suffix
   silently selects the *other* origin.

**A silent default or a clamp is the same bug as a wrong parse.** Four places
answered where they should have refused, and each returned a number no file
states: a *stated* cell key that could not be read fell back on ``c["a"]`` or
90° (so a monoclinic phase arrived orthorhombic — see
:func:`read_topas_inp`'s cell loop); a ``str`` chunk that ran into the next
block took the neighbour's cell, scale and weight_percent (:data:`_BLOCK`); a
schema refusal raised above the boundary that converts it; and a negative
``beq`` was moved to zero (:func:`to_structure`). ``STR(...)`` was the same
class one level up — answered with "this file has no phases" — and is now
read from what §19.3.12 says it does (:func:`expand_str_macros`); the calls
that reference does not describe are refused by name.

**A cell edge coupled to another is read through the scope, not guessed.** The
spelling the archive uses for a tetragonal or cubic phase written without a cell
macro is ``b = Get(a);`` — 4 files, the PbPdO2/PdO fits — and it is the one
place a cell edge may name another edge: §2.5 documents ``Get(xx)`` as the value
of ``xx``, found locally and then outward, and says why the built-in exists,
which is that a bare name in an equation reaches a *parameter* (§2.3-2.4) and a
cell keyword is not one. So the coupling is resolved against the keys already
read for the same phase (:func:`_resolve`'s ``getters``), and a name in no scope
at all still refuses. What that buys is measured: those 4 files went from
refusing outright to reading every phase, cBN at a = b = c = 3.615 Å and PdO at
a = b = 3.042, c = 5.337. The coupled edge carries **no** refine flag of its own
— it states an equation, so it is a dependent parameter, and only the edge it
names is refined.

What resolution copies is the **value**; the tie does not travel with it, and
that is a repair, so it is reported. Whether it costs anything turns on the
space group, which is why ``TOPAS_CELL_COUPLING_DROPPED`` asks it: where the
phase's symmetry ties the pair anyway the built model states what the file
stated and the code stays silent — all 11 couplings across those 4 files are
tetragonal or cubic and raise none. Where it does not, one edge refines and the
other is held at the value it was handed, which is a third thing neither the
file nor rietx meant, and the reader may make that trade only because it can
say here that it made it (:func:`_symmetry_reproduces`).

Reading a *reference* is not reading a statement, which is why the cell scan has
two views of the mask: ``b = Get(a);`` states ``b`` and merely mentions ``a``, so
the text that **locates** a key hides the referenced name while the text that
**resolves** its value keeps it. Conflating them reports a phase as stating an
edge nobody wrote — and on ``ga = Get(al);`` it refuses a whole file over a
missing ``al``.

**One grammar, read once, and it carries the flag with the value.** Every scalar
in a ``.inp`` — a coordinate, a cell edge, a scale, an occupancy, a lattice
macro's argument — is the same four spellings of one production, so
:func:`_read_tail` is the only place that knows them and every caller goes
through it. Five ad-hoc spellings of it disagreed on real files before WP-1118;
a *sixth*, the cell loop's own regex, then disagreed with the unified one about
the ``= expr;: value`` tail and cost **320 phases in 15 archive files**. The
flag travels with the value for the same reason: a second regex re-reading the
line for the flag alone lost it wherever the two grammars disagreed, and a lost
tri-state reads as "held", which is a confident wrong protocol.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ...crystallography.symmetry import (
    OperatorGroup,
    get_spacegroup,
    refuse_operation_list,
    setting_diagnostics,
)
from ...schemas.common import Diagnostic, Parameter
from ...schemas.structure import biso_bounds, biso_widening_diagnostic
from ..formats.base import decode
from . import coverage as _coverage

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ...schemas import Structure

#: What a phase scope keyword this reader does not build into the model costs a
#: caller, decided per construct in :mod:`.coverage` rather than at each call
#: site. Compiled here because the *scan* is this module's — it owns the mask
#: that makes a token scan safe — while what a stance means is the registry's.
#: Longest first, so ``\b`` never truncates ``occ_merge_radius`` to
#: ``occ_merge`` or ``min_r`` to ``min``.
_COVERED = re.compile(
    r"\b(?:" + "|".join(sorted((re.escape(k) for k in _coverage.SCANNED),
                               key=len, reverse=True)) + r")\b")

#: The library macros :mod:`.coverage` gives a stance, matched as an
#: **invocation** — the name, then ``(`` — on the text with only its quoted
#: strings blanked (:func:`_unquoted`). Not on THE mask: that blanks every
#: ``name(...)`` call, name included, which is why a registry of keywords alone
#: never met a ``TCHZ_Peak_Type(...)`` and the import said nothing (#649). The
#: ``(`` is what keeps a parameter that happens to share a short form (a
#: ``prm SD``, an equation reading ``CS``) from reading as the macro; every
#: macro listed takes arguments. Longest first, as above.
_MACRO_CALL = re.compile(
    r"\b(" + "|".join(sorted((re.escape(m) for m in _coverage.MACROS),
                              key=len, reverse=True)) + r")\s*\(")


#: A call, ``name(``, anywhere in the text. Not preceded by ``.`` or a word
#: character, so the tail of a longer name is not a call.
_ANY_CALL = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*\(")

#: The names a call may carry without the reader owing the caller a word: the
#: equation functions, and the calls this reader reads by name elsewhere. The
#: registry's macros, the file's own ``macro`` definitions and the dataset,
#: cell and emission macros are added at the scan (:func:`_unread_calls`).
_EQUATION_FUNCTIONS = frozenset({
    "Abs", "Sin", "Cos", "Tan", "Asin", "Acos", "Atan", "Atan2", "Sinh", "Cosh",
    "Tanh", "Exp", "Ln", "Log", "Sqrt", "Mod", "Min", "Max", "If", "Get", "Val",
    "Sign", "Floor", "Ceil", "Int", "Log10", "Pow", "Rand", "Rad", "Deg",
    "Radius", "STR", "TOF_XYE", "TOF_GSAS"})

#: ``Out…`` and ``Create_…`` macros write files and states about the run, not
#: the model (the registry's IGNORED stance, by name), so their calls are not
#: unread in the sense that matters.
_RUN_LEVEL_CALL = re.compile(r"(?:Out|Create)_\w*")


def _unread_calls(unquoted: str, stripped: str) -> tuple[str, ...]:
    """The names ``unquoted`` calls that nothing here defines or reads (#651).

    TOPAS stops on an undefined macro ("unknown or misplaced keyword"), so a
    file reaching this reader either defines the name in an include the reader
    does not have or has a typo, and the structure built from it is the same
    in both cases: missing whatever the call states.
    """
    known = (_EQUATION_FUNCTIONS | _coverage.MACROS | set(_CELL_MACROS)
             | set(_DATASET_MACROS)
             | set(re.findall(r"\bmacro\s+(\w+)", stripped)))
    return tuple(sorted({
        m.group(1) for m in _ANY_CALL.finditer(unquoted)
        if m.group(1) not in known
        and m.group(1).rstrip("_") not in known
        and not re.fullmatch(r"(?:Cu|Co|Cr|Fe|Mo|Ag)Ka\d?", m.group(1))
        and not _RUN_LEVEL_CALL.fullmatch(m.group(1))}))


def _unquoted(text: str) -> str:
    """``text`` with its ``"…"`` strings blanked, offset-for-offset, so a macro
    name inside a path or a phase name is not an invocation."""
    return re.sub(r'"[^"\n]*"', lambda m: _blank(m.group()), text)

#: TOPAS origin/axis suffixes → the Hermann-Mauguin extension gemmi wants.
#: ``Z`` is *Zentrum*, the centrosymmetric origin (choice 2); ``S`` is the
#: site-symmetry origin (choice 1). Dropping the letter is not harmless: for
#: #224 a bare ``Pn-3m`` resolves to choice **1**, so a Cu2O described on
#: choice 2 (Cu at 0,0,0; O at ¼,¼,¼) would be given the wrong origin's
#: symmetry with nothing raised.
_SG_SUFFIX: dict[str, str] = {"Z": ":2", "S": ":1", "R": ":R", "H": ":H"}

_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"

#: One background coefficient as a file writes it: an optional ``@``, the
#: number, the write-back backtick, and the ``_esd``/``_LIMIT_*`` annotation a
#: refinement with errors attaches to it (``40`_0.2``,
#: ``1e-6`_2e-7_LIMIT_MIN_1e-6``). The annotation is *inside* the slot because
#: it is a number too: counting every number in the list would double the
#: answer, and leaving it out of the repeated group ended the list at its first
#: coefficient, so every written-back file reported one term (#652). The
#: annotation is the one `_ADP_ANNOTATION` skips between ADP slots.
#: The refine marker is ``@`` (refined) or ``!`` (held), and it **stays** for the
#: numbers after it until the other one appears, so ``bkg ! c0 c1`` holds the
#: whole list (#652).
_BKG_SLOT = rf"\s*(?P<flag>[@!])?\s*{_NUM}`?(?:_[^\s;{{}}]*)?"

#: A TOPAS parameter name. Leading character is deliberately **not** ``\w``:
#: ``\w`` matches a digit, so ``(?:\w+\s+)?`` in front of a value silently eats
#: the integer part of a *nameless* one — ``weight_percent 97.9`` came back
#: 0.9, and ``Cubic_(4.15689)`` came back 0.15689, a wrong number with nothing
#: raised, which is the whole failure class this reader exists to avoid.
_NAME = r"[A-Za-z_]\w*"

#: Refinement flags, in every spelling the archive actually contains: ``@``
#: (refine), ``!`` (fix), and either followed by a comma — ``@, 0.0013`` is
#: how TOPAS writes a refined value it did not name, and appears on 100+ files
#: here. Flags may sit before the name, after it, or both.
_FLAG = r"(?:[@!]\s*,?\s*)"


class TopasInpError(ValueError):
    """Raised naming the file and the offending line, never a bare regex miss."""


@dataclass
class TopasSite:
    label: str
    species: str
    x: float
    y: float
    z: float
    occupancy: float = 1.0
    #: TOPAS's B, exactly as the file states it — ``None`` where the site line
    #: gives no ``beq`` (WP-1118). :class:`TopasModel` is "what a ``.inp``
    #: states", and a seeded 0.5 a caller cannot tell from a stated 0.5 is the
    #: silent-default class this reader exists to avoid; the 0.5 seed a builder
    #: needs is applied in :func:`to_structure`, not stored here. ``occ``'s 1.0
    #: default stays — it is the *format's* own default, measured on three
    #: files, not a value this reader invents.
    beq: float | None = None
    #: The anisotropic displacement tensor exactly as the file states it, keyed
    #: ``"u11"``…``"u23"`` (WP-1118). TOPAS's ``u_ij`` are U^ij in Å² — the CIF
    #: ``_atom_site_aniso_U_ij`` convention rietx's :class:`~rietx.AnisoU` holds,
    #: so no 8π² conversion. ``None`` where the site states no tensor. Like
    #: ``beq``, this is *what the file states*: the isotropic 0.5 seed a
    #: tensor-free site needs and the :class:`~rietx.AnisoU` a tensor-bearing one
    #: needs are both :func:`to_structure`'s, behind its ``aniso=`` opt-in.
    adps: dict | None = None
    #: The site's magnetic moment exactly as the file states it, keyed
    #: ``"mlx"``/``"mly"``/``"mlz"`` and ``"mg"`` for the Landé factor
    #: (WP-1328). ``None`` where the site states no moment; a *key* is absent
    #: where that component is not stated, which is not the same as zero — the
    #: same tri-state ``beq`` and ``adps`` keep, and for the same reason.
    #:
    #: **The basis is fractional**: m = mlx·**a** + mly·**b** + mlz·**c**, the
    #: edges in Å, so the crystal-axis μ_B that
    #: :class:`~rietx.schemas.structure.Moment` stores (magCIF's
    #: ``_atom_site_moment.crystalaxis_*``, unit vectors along a, b, c) is
    #: ``(mlx·|a|, mly·|b|, mlz·|c|)`` — a per-axis scale on every cell, never a
    #: rotation. Stored here as the file writes it; :func:`to_structure`
    #: converts. The evidence is the TOPAS Technical Reference § 13 "Magnetic
    #: Structure Refinement": Fmagc = L·Fmag with m = {mlx, mly, mlz} and L the
    #: Cartesian lattice matrix, which is m_Cartesian = L·m, and its two macros
    #: ``MM_CrystalAxis_Display`` (mxc = mlx·a, myc = mly·b, mzc = mlz·c) and
    #: ``MM_CrystalAxis_Refine`` (mlx = mxc/a). The Durham LaMnO₃ magnetic
    #: tutorial prints both sides, ``mlx mly mlz`` beside
    #: ``MM_CrystalAxis_Display``, and its display values are those three
    #: products to the printed digits. One sentence in the same reference
    #: points elsewhere —
    #: the ``mlx`` keyword entry calls them "Cartesian components" — and its
    #: own formula and both macros contradict it, so it is not followed. It is
    #: also **measured** (2026-09-25, TOPAS-64 v6): one Mn²⁺ site in BNS 1.1 on
    #: a 5.2 / 6.9 / 8.4 Å, β = 115° cell with ``mlx 0.4 mly -0.3 mlz 0.3``.
    #: TOPAS's magnetic intensity ratios over 54 strong equal-d pairs
    #: (h k l)/(h −k l), which cancel form factor, Lorentz factor and scale,
    #: match this reading to four digits on every pair, and its absolute
    #: magnetic intensity gives |m| = 3.2452 μ_B, this reading's value. The
    #: crystal-axis and Cartesian readings miss the median pair by factors of
    #: 1.58 and 1.80. A moment along b alone, where all three readings
    #: coincide, matches under all three, which is the control that the
    #: comparison can separate them. The same holds on the orthogonal cell.
    #: TOPAS's table for the three-axis moment is vendored
    #: (``tests/data/topas_moment_basis_A_mono3_mag_hkl.txt``) and the pair
    #: check re-runs against it in ``tests/test_magcif.py``.
    #: Until WP-1328's review this reader took the crystal-axis reading
    #: (``mlx`` as μ_B along a unit vector), which made an imported moment too
    #: small by roughly the edge length and, wherever the edges differ and the
    #: moment has two or more components, point elsewhere.
    moment: dict | None = None
    #: Which of this site's parameters the file records as having been free.
    #: Keyed by field name (``"x"``, ``"beq"``, ``"u11"``…, …); a key is absent
    #: where the file said nothing, which is not the same as "held" — see
    #: :func:`refined`.
    vary: dict = field(default_factory=dict)


@dataclass
class TopasPhase:
    name: str
    #: The nuclear ``space_group`` as written (origin suffix normalised), or
    #: ``""`` where the ``str`` states only ``mag_space_group`` — TOPAS's own
    #: magnetic examples do — and :func:`to_structure` derives the nuclear
    #: group from the magnetic one (``TOPAS_MAGNETIC_GROUP_READ``).
    space_group: str
    cell: dict = field(default_factory=dict)
    cell_limits: dict = field(default_factory=dict)
    sites: list = field(default_factory=list)
    scale: float | None = None
    weight_percent: float | None = None
    #: The phase-level half of the same protocol, keyed as the cell dict is
    #: (``"a"``, ``"be"``, …) plus ``"scale"``.
    vary: dict = field(default_factory=dict)
    #: Which dataset this phase belongs to — the index of the ``xdd``-family
    #: block it sits inside, or ``None`` where the file opens no explicit one.
    #: The grammar makes ``str`` a **child** of ``xdd`` and ``xdd`` an array, so
    #: a phase is a fact about one pattern and not about the file.
    dataset: int | None = None
    #: ``mag_space_group`` exactly as written (WP-1328): a BNS number
    #: (``62.448``, ``1.1`` — how the Durham LaMnO₃ tutorial and ISODISTORT's
    #: TOPAS export write it), an OG number (three integers), or a Shubnikov
    #: **symbol**. :func:`to_structure` takes a number as the phase's magnetic
    #: group (:func:`magnetic_group_number`); a symbol is metadata only,
    #: because no dependency here parses one, and the group then has to come
    #: from ``to_structure(magnetic_symmetry=...)``.
    mag_space_group: str | None = None


@dataclass
class SkippedBlock:
    """A ``str`` block this reader saw but could not read as a phase — it stated
    no ``phase_name`` or no ``space_group``, so naming it would be the
    neighbour's-name bleed :data:`_BLOCK` fixes. Recorded rather than passed
    over in silence (WP-1118), and recording *what it lacked and what it did
    carry*, so :func:`to_structure` can tell a block that plainly states a cell
    or a site — a phase in all but its name, whose loss unbalances the weight
    fractions — from an empty one."""

    lacked: str                       # "phase_name", "space_group", or both
    n_sites: int
    cell: dict = field(default_factory=dict)
    scale: float | None = None
    weight_percent: float | None = None

    def __str__(self) -> str:
        carried = []
        if self.cell:
            carried.append("a cell (" + ", ".join(sorted(self.cell)) + ")")
        if self.scale is not None:
            carried.append(f"scale {self.scale}")
        if self.weight_percent is not None:
            carried.append(f"weight_percent {self.weight_percent}")
        tail = f", carrying {', '.join(carried)}" if carried else ""
        return (f"a `str` block stating {self.n_sites} site line"
                f"{'' if self.n_sites == 1 else 's'} but no {self.lacked}{tail}")


def _skipped_remedy(blocks) -> str:
    """The one line each skipped block is missing, as the sentence a refusal ends on.

    A block is skipped for lacking a ``phase_name``, a ``space_group``, or both,
    and nothing else: a ``mag_space_group`` stands in for the ``space_group``
    (how TOPAS's magnetic examples write a phase), so a magnetic ``str`` with no
    ``phase_name`` is one ``phase_name`` line from reading. Saying *that* is the
    difference between a refusal a caller can act on and one that only reports
    — "no phase carries a cell" about a file carrying one sent a caller looking
    for a missing cell.
    """
    lacked = {w for sb in blocks for w in sb.lacked.split(" or ")}
    want = [line for word, line in (("phase_name", 'a `phase_name "…"` line'),
                                    ("space_group", 'a `space_group "…"` line'))
            if word in lacked]
    return ("a `str` block is read as a phase once it states a `phase_name` and "
            "a `space_group` (or a `mag_space_group`), so add "
            + " and ".join(want) + (" to it" if len(blocks) == 1 else " to each"))


@dataclass
class TopasModel:
    """What a ``.inp`` states. Deliberately not a :class:`Structure` yet — the
    caller decides which phases to keep and how to seed what the file omits."""

    phases: list = field(default_factory=list)
    #: The file this was read from, so :func:`to_structure` can name it in a
    #: refusal — a reader raises naming the file, never its parser's exception,
    #: and pydantic's report names a field rather than a file.
    path: str | None = None
    anode: str | None = None          # "CuKa" from a CuKa5(...) macro
    emission_macro: str | None = None  # "CuKa5" verbatim, for provenance
    #: The profile's **reference** wavelength — the ``lo`` of the ``lo_ref``
    #: line, else of the line with the largest ``la`` (the reference's own rule
    #: for what ``Lam`` takes), and ``None`` where the file states no
    #: ``la``/``lo`` profile at all. Not the first line written.
    wavelength: float | None = None
    #: Every emission line the file states, in file order — the grammar makes
    #: ``la``/``lo`` an array, and a doublet is two of them.
    emission_lines: list = field(default_factory=list)
    goniometer_radius_mm: float | None = None
    #: ``"debye_scherrer"`` only where the file **states** a capillary construct
    #: (:data:`_CAPILLARY`), ``None`` where every dataset is time of flight, and
    #: otherwise ``"bragg_brentano"`` — which is this reader's **default**, not
    #: something the file said: a ``neutron_data`` file or one carrying only a
    #: ``Radius(…)`` arrives as ``"bragg_brentano"`` whatever its experiment
    #: was. So choose the :class:`~rietx.schemas.instrument.Instrument`
    #: preset from the radiation and the experiment you know, and read this
    #: field only as "a capillary was declared, or not".
    geometry: str | None = None
    #: The run's own converged ``r_wp``/``gof`` — the one stated at top level,
    #: above every block opener. ``None`` where the file states none there or
    #: states several, because ``Tr_wp`` hangs off ``Txdd`` as well and picking
    #: one dataset's number as the file's is the confident wrong singleton this
    #: reader exists to avoid. Every value stated is on ``r_wp_all``/``gof_all``.
    r_wp: float | None = None
    gof: float | None = None
    r_wp_all: list = field(default_factory=list)
    gof_all: list = field(default_factory=list)
    #: How many ``xdd``-family blocks the file opens. Zero is normal — a macro
    #: may supply the dataset — and anything above one means the phases below
    #: belong to different patterns.
    n_datasets: int = 0
    data_files: list = field(default_factory=list)
    #: How many coefficients the ``bkg`` list states, refined or held.
    background_terms: int | None = None
    #: Whether any of them is refined (``@``). ``False`` is a held list
    #: (``bkg ! c0 c1``), ``None`` is a file stating no ``bkg`` list.
    background_refined: bool | None = None
    #: One :class:`SkippedBlock` per ``str`` block that states no ``phase_name``
    #: or no ``space_group``, saying what it lacked and what it did carry (its
    #: cell, scale and weight_percent). Such a
    #: block cannot be read as a phase and is not one this reader may name —
    #: taking the name from the next block is exactly the bleed :data:`_BLOCK`
    #: fixes. But *silence* about it is the other half of that bug, because the
    #: zero-phase refusal then reports "a Pawley or indexing-only .inp is legal
    #: and has none" about a file carrying a cell and two sites. So it is
    #: recorded, and :func:`to_structure` quotes it instead.
    skipped_blocks: list = field(default_factory=list)
    #: What the phases state that this import does **not** carry
    #: (:mod:`.coverage`). A ``.inp`` states more than a structure, and before
    #: this the difference was invisible: a construct nobody had written a
    #: branch for was dropped exactly as silently as one that does not matter.
    #: It is on the model rather than only on the ``diagnostics`` channel for
    #: the reason ``skipped_blocks`` is — a fact about the answer should not
    #: depend on the caller having asked for messages. ``coverage.partial`` is
    #: the yes/no; ``coverage.reported`` and ``.refused`` are the story.
    coverage: _coverage.Coverage = field(default_factory=_coverage.Coverage)
    #: The datasets that are **time of flight**, each with the constructs that
    #: say so — ``{1: ("TOF_XYE", "TOF_x_axis_calibration")}`` — keyed like
    #: :attr:`TopasPhase.dataset`, ``None`` where the file opens no dataset.
    #: rietx models constant-wavelength diffraction only (time of flight is
    #: issue #193), so such a dataset's phases are refused by
    #: :func:`to_structure`; on the model for the reason ``coverage`` is, and
    #: empty for a file with none.
    time_of_flight: dict = field(default_factory=dict)


def strip_comments(text: str) -> str:
    """Remove ``/* */`` blocks and ``'`` line comments (rule 1).

    A ``'`` inside a ``"…"`` string is a character, not a comment opener: TOPAS
    quotes file paths and phase names, and both may hold an apostrophe. Cutting
    at the first ``'`` regardless read ``xdd "C:\\data\\o'brien.xy"`` as the
    data file ``C:\\data\\o`` and named a phase ``d`` — a truncated path is a
    loud failure later, but a truncated ``phase_name`` is a silently
    mislabelled phase, which is the class this reader exists to avoid. Nothing
    in the 606-file archive carries one, so this is latent rather than measured.

    A block comment **nests** — "a block comment is delimited by ``/*`` and
    ``*/`` and may be nested" (Technical Reference §1.2). A boolean ``in_block``
    therefore ended the outer comment at the *inner* ``*/`` and read the rest of
    it as live input; the counter is what the sentence asks for. Nothing in the
    606-file archive nests one, so this is the specification closing a hole the
    files never opened — which is the only way this particular hole could ever
    be closed, since a nested comment that reads as code raises nothing.

    The block and line comments are stripped in **one pass**, not block-first,
    because the two interact: the ``'/*`` idiom comments out the block-comment
    *delimiter itself*, so the phase between a ``'/*`` and a ``'*/`` is **live**
    (real, measured — an archive file uses it to hold three refinements in one
    input and enable one of them). Stripping ``/* */`` first with
    a regex read the ``/*`` in ``'/*`` as opening a block and deleted that live
    phase. So a ``/*`` or ``*/`` preceded on its line by an unquoted ``'`` is
    itself comment text and opens/closes nothing: the ``'`` line comment is
    seen first, char by char, and the delimiter never reached.
    """
    out_lines: list[str] = []
    depth = 0
    for line in text.split("\n"):
        result: list[str] = []
        i, n, quoted = 0, len(line), False
        while i < n:
            if depth:
                # Inside a block comment nothing is code, so `\'` opens no line
                # comment here and only the two delimiters matter — and both do,
                # because the reference says a block comment "may be nested".
                opened = line.find("/*", i)
                closed = line.find("*/", i)
                if closed == -1 and opened == -1:
                    i = n
                elif opened != -1 and (closed == -1 or opened < closed):
                    depth += 1
                    i = opened + 2
                else:
                    depth -= 1
                    i = closed + 2
                continue
            ch = line[i]
            if ch == '"':
                quoted = not quoted
                result.append(ch)
                i += 1
            elif quoted:
                result.append(ch)
                i += 1
            elif ch == "'":
                break  # line comment: the rest of the line is dead
            elif line.startswith("/*", i):
                depth += 1
                i += 2
            else:
                result.append(ch)
                i += 1
        out_lines.append("".join(result))
    return "\n".join(out_lines)


#: A conditional directive, **as a token**. TOPAS is whitespace-insensitive, so
#: a directive is wherever it is written and not only at the start of a line:
#: `#else #ifdef individual_contributions_` on one line occurs in **283 of the
#: 606 archive files**, `#define gsas_convolution #ifdef gsas_convolution` in
#: 13, and one file gates a site's `beq` with an `#ifdef` *inside the site line*.
#: The alternation is ordered so `#ifdef`/`#ifndef` win over `#if` and `#elseif`
#: over `#else`; the symbol is captured only for the two that take one, so a
#: `#else` never swallows the directive that follows it. `#prm` is here because
#: a hash parameter is declared *in sequence* with the conditionals that read it
#: — one declared inside a dead branch was never declared (WP-1433).
_DIRECTIVE = re.compile(
    r"#(?:(?P<cond>ifdef|ifndef)\s+(?P<sym>\S+)"
    r"|prm\s+(?P<prm>[A-Za-z_]\w*)\s*="
    r"|(?P<kw>elseif|else|endif|if)\b)")

#: A `#define`d symbol, read with the **same** charset the `#ifdef` above uses.
#: `\w+` on one side and a bare token on the other is how `#define ABO3-x_fit`
#: comes to define `ABO3` while `#ifdef ABO3-x_fit` asks for something else:
#: two spellings of one name, disagreeing in silence (5 archive files).
_DEFINE = re.compile(r"#define\s+(\S+)")


# ----------------------------------------------- `#prm` and `#if` (WP-1433)
#
# Technical Reference §19.1.2, "Pre-processor equations and `#prm`, `#if`,
# `#elseif`, `#out`", is the whole specification. A `#prm` is a *hash
# parameter*, evaluated at the pre-processor stage and "totally separate to
# parameters defined using `prm`" — unknown to the kernel — so this namespace is
# its own and `symbol_table` is never consulted: mixing the two would read a
# kernel parameter's value into a pre-processor condition. `#if E;` …
# `[#elseif E;]` … `#endif` selects text by the value of `E`, and the
# reference's worked example is `And(space_group_number >= 75,
# space_group_number <= 142)`, so comparisons, `And` and arithmetic over `#prm`s
# reach every case the archive and the workshop files write. Not a TOPAS
# equation engine (WP-1433 § Non-goals): a function other than `And` is refused
# by name, and so are the two the reference itself shows have no answer a
# reader can give — `Rand` (its own example is `#prm ran = Constant(Rand(0,1));
# #if ran < 0.5;`) and a string-valued condition.

#: `Run_Number` is the one name a condition reads that no `#prm` declares: the
#: index of the current `num_runs` iteration, 0 on the first (§ `num_runs`;
#: the reference's own idiom is `#if (Run_Number) … #else … #endif` to tell the
#: first run from the rest). A file with no `num_runs` has one run, so it is 0.
_RUN_NUMBER = "Run_Number"

_HASH_TOKEN = re.compile(r"""
    (?P<ws>[ \t\r]+)
  | (?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)
  | (?P<out>\#out\b)
  | (?P<name>[A-Za-z_]\w*)
  | (?P<str>"[^"\n]*")
  | (?P<op>==|!=|<=|>=|<|>|[-+*/^(),;])
""", re.X)


def _juxtaposed(tok: str) -> _Undecidable:
    """The refusal for a value straight after a complete equation. Table 3-1:
    "Multiply is optional, x*y = x y", so `#if n 2 > 3;` is `n*2 > 3`, and
    ending the condition at `n` decided it from its prefix (#587 review,
    round 2). A *name* there still ends the condition — the reference's own
    inline `#if (Run_Number) type out.txt` — so only a number, a `(` or an
    `#out` is refused."""
    return _Undecidable(
        f"a value ({tok!r}) follows it with no operator between, and Table 3-1 "
        f"makes that an implied multiply (`x y` = `x*y`), which this reader "
        f"does not evaluate")


def _starts_a_value(kind: str | None, tok: str) -> bool:
    return kind in ("num", "out") or tok == "("


def _unknown(char: str) -> _Undecidable:
    """The refusal for a character no hash equation here contains. Without it
    the equation was decided from the part before it: `#if n^2 > 5;` from `n`,
    `#prm n = 2 % 3;` as 2 (#587 review)."""
    return _Undecidable(
        f"it reaches {char!r}, which is not an operator this reader evaluates "
        f"(numbers, + - * / ^, the six comparisons, `And` and parentheses), "
        f"so deciding it from the text before {char!r} would be a guess")


#: The reference's own example of a condition with no answer (§19.1.2).
_RAND = ("it reaches `Rand`, so the branch is chosen by a random draw at load "
         "time and no reader can say which one TOPAS took")


class _Undecidable(Exception):
    """A pre-processor equation this reader will not decide, and why — in the
    words the refusal quotes."""


@dataclass(frozen=True)
class _HashValue:
    """One evaluated hash equation. ``error`` is set instead of ``value`` when
    it could not be decided — kept rather than raised, because a `#prm` nothing
    tests costs nothing; only a condition that reaches it refuses."""

    value: float | None = None
    run_dependent: bool = False
    error: str | None = None


def _hash_tokens(text: str, start: int, stop: int | None = None):
    """``(kind, text, offset)`` from ``start`` until a newline, a ``;`` (which
    is yielded), or ``stop``. A character no hash equation contains ends the
    tokens as one ``("bad", char, offset)`` token, so the parser refuses it if
    it reaches it (:func:`_unknown`) and not otherwise — the reference's
    inline `#if (Run_Number) type out.txt` ends at `)`, before the `.`."""
    pos, stop = start, len(text) if stop is None else stop
    while pos < stop:
        m = _HASH_TOKEN.match(text, pos, stop)
        if not m:
            if text[pos] != "\n":
                yield "bad", text[pos], pos
            return
        pos = m.end()
        if m.lastgroup != "ws":
            yield m.lastgroup, m.group(), m.start()
            if m.group() == ";":
                return


class _HashParser:
    """Recursive descent over one hash equation, stopping at the first token
    that cannot continue it — so ``#if (Run_Number) type out.txt`` ends the
    condition at ``)``, which is how the reference's own example writes it."""

    def __init__(self, tokens, params: dict[str, _HashValue]):
        self.toks = list(tokens)
        self.i = 0
        self.params = params
        self.run_dependent = False

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, "", -1)

    def take(self, want: str | None = None):
        kind, tok, off = self.peek()
        if kind == "bad":
            raise _unknown(tok)
        if kind is None or (want is not None and tok != want):
            raise _Undecidable(f"expected {want or 'a value'}, found "
                               f"{tok or 'the end of the line'!r}")
        self.i += 1
        return kind, tok, off

    def end(self) -> int:
        """Offset just past the last token consumed."""
        if not self.i:
            return -1
        _, tok, off = self.toks[self.i - 1]
        return off + len(tok)

    def expression(self) -> float:
        left = self.additive()
        _, tok, _ = self.peek()
        if tok in ("==", "!=", "<", ">", "<=", ">="):
            self.take()
            right = self.additive()
            left = float({"==": left == right, "!=": left != right,
                          "<": left < right, ">": left > right,
                          "<=": left <= right, ">=": left >= right}[tok])
        return left

    def additive(self) -> float:
        value = self.multiplicative()
        while self.peek()[1] in ("+", "-"):
            _, op, _ = self.take()
            right = self.multiplicative()
            value = value + right if op == "+" else value - right
        return value

    def multiplicative(self) -> float:
        value, _ = self.power()
        while self.peek()[1] in ("*", "/"):
            _, op, _ = self.take()
            right, raised = self.power()
            if raised:
                raise _Undecidable(
                    f"it writes `^` to the right of `{op}`, and Table 3-1 "
                    f"states `x^y*z = (x^y)*z` and `x^y/z = (x^y)/z` but not "
                    f"which of `(x{op}y)^z` and `x{op}(y^z)` `x{op}y^z` is")
            if op == "/" and right == 0:
                raise _Undecidable("it divides by zero")
            value = value * right if op == "*" else value / right
        return value

    def power(self) -> tuple[float, bool]:
        """``x^y`` as Table 3-1 (Equation Operators and Functions) states it:
        "Calculates x to the power of y", binding left — `x^y^z = (x^y)^z`,
        `x^y*z = (x^y)*z`, `x^y/z = (x^y)/z`. Only what those three forms
        settle is decided: a signed base (`-x^y`) and a `^` right of `*` or
        `/` are refused, since the table orders neither. Whether a `^` was
        read is returned for :meth:`multiplicative`'s check."""
        signed = self.peek()[1] in ("-", "+")
        value = self.unary()
        raised = False
        while self.peek()[1] == "^":
            if signed:
                raise _Undecidable(
                    "it raises a signed value to a power, and Table 3-1 does "
                    "not state whether `-x^y` is `(-x)^y` or `-(x^y)`")
            self.take()
            exponent = self.unary()
            if value == 0 and exponent < 0:
                raise _Undecidable("it divides by zero")
            if value < 0 and exponent != int(exponent):
                raise _Undecidable(
                    "it raises a negative number to a non-integer power")
            try:
                value = math.pow(value, exponent)
            except OverflowError:
                raise _Undecidable("its power overflows") from None
            raised = True
        return value, raised

    def unary(self) -> float:
        if self.peek()[1] in ("-", "+"):
            _, op, _ = self.take()
            value = self.unary()
            return -value if op == "-" else value
        return self.primary()

    def primary(self) -> float:
        kind, tok, _ = self.take()
        if kind == "num":
            return float(tok)
        if kind == "str":
            raise _Undecidable(
                f"it compares the string {tok}, and a string condition is not "
                f"evaluated here — only numbers over `#prm`s")
        if tok == "(":
            value = self.expression()
            self.take(")")
            return value
        if kind == "out":
            kind, tok, _ = self.take()
            if kind != "name":
                raise _Undecidable(f"`#out` names no hash parameter ({tok!r})")
            return self.lookup(tok)
        if kind == "name":
            if self.peek()[1] == "(":
                return self.call(tok)
            return self.lookup(tok)
        raise _Undecidable(f"{tok!r} cannot start a value")

    def call(self, name: str) -> float:
        if name == "Rand":
            raise _Undecidable(_RAND)
        if name != "And":
            depth, j = 0, self.i          # `Constant(Rand(0,1))`: name Rand
            while j < len(self.toks):
                tok = self.toks[j][1]
                depth += (tok == "(") - (tok == ")")
                if tok == "Rand" and self.toks[j][0] == "name":
                    return self.call("Rand")
                if depth <= 0 and j > self.i:
                    break
                j += 1
            raise _Undecidable(
                f"it calls `{name}`, and this reader evaluates `And`, the "
                f"comparisons and arithmetic over `#prm`s — not TOPAS's "
                f"function library")
        self.take("(")
        values = [self.expression()]
        while self.peek()[1] == ",":
            self.take()
            values.append(self.expression())
        self.take(")")
        return float(all(values))

    def lookup(self, name: str) -> float:
        if name in self.params:
            hv = self.params[name]
            if hv.error:
                raise _Undecidable(f"`{name}` is a `#prm` that {hv.error}")
            self.run_dependent |= hv.run_dependent
            return hv.value
        if name == _RUN_NUMBER:
            self.run_dependent = True
            return 0.0
        raise _Undecidable(
            f"`{name}` is no `#prm` declared above it in live text — a kernel "
            f"`prm` is not a hash parameter, and the reference keeps the two "
            f"namespaces apart")


def _precheck(tokens) -> None:
    """Name `Rand` before anything else does: `Constant(Rand(0,1))` is the
    reference's own spelling, and refusing it as "calls `Constant`" would name
    the wrapper rather than the reason."""
    for kind, tok, _ in tokens:
        if kind == "name" and tok == "Rand":
            raise _Undecidable(_RAND)


def _hash_condition(text: str, start: int,
                    params: dict[str, _HashValue]) -> tuple[bool, bool, int]:
    """Evaluate the condition of an ``#if``/``#elseif`` whose keyword ends at
    ``start``: ``(live, read Run_Number, offset past the condition)``. A
    trailing ``;`` is the reference's form and is consumed with it."""
    parser = _HashParser(_hash_tokens(text, start), params)
    value = parser.expression()
    stop = parser.end()
    kind, tok, _ = parser.peek()
    if tok == ";":
        parser.take()
        stop = parser.end()
    elif kind == "bad":
        raise _unknown(tok)
    elif _starts_a_value(kind, tok):
        raise _juxtaposed(tok)
    elif kind == "op":
        raise _Undecidable(f"this reader cannot evaluate past {tok!r}")
    return value != 0, parser.run_dependent, stop


def _hash_definition(text: str, start: int,
                     params: dict[str, _HashValue]) -> tuple[_HashValue, int]:
    """Evaluate a ``#prm name = E;`` whose ``=`` ends at ``start``: the value
    (or the reason it has none) and the offset past its ``;``. Evaluated where
    it is written — the pre-processor reads in order — and an undecidable one
    is kept as its reason, not raised, until a condition reaches it."""
    semi = text.find(";", start)
    if semi == -1:                        # never blank the rest of the file
        stop = text.find("\n", start)
        return _HashValue(error="has no closing `;`"), (
            len(text) if stop == -1 else stop)
    stop = semi + 1
    tokens = list(_hash_tokens(text.replace("\n", " "), start, semi))
    parser = _HashParser(tokens, params)
    try:
        _precheck(tokens)
        if bad := [tok for kind, tok, _ in tokens if kind == "bad"]:
            raise _unknown(bad[0])
        if any(kind == "str" for kind, _, _ in tokens):
            raise _Undecidable("is a string, and a string condition is not "
                               "evaluated here — only numbers")
        value = parser.expression()
        if _starts_a_value(*parser.peek()[:2]):
            raise _juxtaposed(parser.peek()[1])
        if parser.i != len(tokens):
            raise _Undecidable(
                f"this reader cannot evaluate past {parser.peek()[1]!r}")
    except _Undecidable as exc:
        reason = str(exc)
        return _HashValue(error=reason if reason.startswith("is ")
                          else f"could not be evaluated: {reason}"), stop
    return _HashValue(value=value, run_dependent=parser.run_dependent), stop


@dataclass
class _Conditionals:
    """What resolving the conditionals found beyond the text itself."""

    text: str
    #: Whether a live/dead decision read `Run_Number` (directly or through a
    #: `#prm`), so the text is the first run's (:data:`_RUN_NUMBER`).
    run_dependent: bool = False
    #: The `#prm`s live at the end of the file, for `num_runs = #out n;`.
    params: dict[str, _HashValue] = field(default_factory=dict)


_NUM_RUNS = re.compile(r"\bnum_runs\b\s*=?")


def _num_runs(active: str, params: dict[str, _HashValue]) -> float | None:
    """The run count ``num_runs`` states — 1 where it is absent, ``None`` where
    its equation (``num_runs = #out pattern_count;``) is not one this reader
    decides."""
    m = _NUM_RUNS.search(active)
    if not m:
        return 1.0
    try:
        parser = _HashParser(_hash_tokens(active, m.end()), params)
        value = parser.expression()
    except _Undecidable:
        return None
    if parser.peek()[0] == "bad":         # `num_runs = 2^3 % 2`: not 8
        return None
    return None if parser.run_dependent else value


def resolve_ifdefs(text: str, path: str | Path = "<text>") -> str:
    """Blank the conditional branches that are not live (rule 2).

    ``#ifdef``/``#ifndef`` test a ``#define``; symbols are collected first
    because TOPAS permits a ``#define`` after its own use; the stack keeps
    nesting honest. ``#if``/``#elseif`` test a hash equation over the ``#prm``s
    declared above them in live text (WP-1433, see :func:`_resolve_conditionals`).

    **Token-oriented, not line-oriented** — the same correction the cell scan
    and the site split already made, for the same reason: the format is
    whitespace-insensitive, so a line anchor is an assumption about typography
    rather than a fact about the format. A line-anchored resolver saw the
    `#else` in `#else #ifdef X` and not the `#ifdef`, so the nested frame was
    never pushed and its `#endif` then popped the **enclosing** one — the dead
    branch and everything after it came back live. That is 283 of the 606
    archive files, and no count moves when it happens.

    Dead text is **blanked rather than deleted** (:func:`_blank`), so a line
    number in a later refusal still names the line the file has.
    """
    return _resolve_conditionals(text, path).text


def _resolve_conditionals(text: str, path: str | Path) -> _Conditionals:
    """:func:`resolve_ifdefs`, with what a caller reporting on it needs.

    One mechanism for both families, as WP-1433 asks: an ``#if`` frame is the
    same ``[keeping_here, branch_already_taken]`` an ``#ifdef`` frame is, and
    only how ``keeping_here`` is decided differs. A condition is evaluated only
    where every enclosing frame is live — a dead branch is text TOPAS never
    pre-processed, so its ``#if`` can be anything — and a directive inside a
    ``macro`` body is left alone, since the body is excised whole
    (:func:`_excise_macro_defs`) and its ``#if`` tests the macro's arguments,
    which only an expansion binds. The directive and its condition are blanked,
    and so is a live ``#prm`` declaration: the kernel never sees one, so leaving
    it in reads ``#prm n = 4;`` as the kernel ``prm n`` (:func:`symbol_table`).
    """
    defined = set(_DEFINE.findall(text))
    in_macro = _excise_macro_defs(text)
    params: dict[str, _HashValue] = {}
    run_dependent = False
    out: list[str] = []
    stack: list[list[bool]] = []          # [keeping_here, branch_already_taken]
    position = 0

    def refuse(at: int, directive: str, reason: str) -> TopasInpError:
        line = text.count("\n", 0, at) + 1
        snippet = text[at:].split("\n", 1)[0]
        return TopasInpError(
            f"{path}:{line}: `{directive}` in {snippet.strip()[:60]!r} is not "
            f"decided here: {reason}. Which branch TOPAS read is unknown, and "
            f"reading on would report a model mixing both.")

    for m in _DIRECTIVE.finditer(text):
        if m.start() < position:
            continue                      # inside a condition already consumed
        live_here = all(frame[0] for frame in stack)
        chunk = text[position:m.start()]
        out.append(chunk if live_here else _blank(chunk))
        position = m.end()
        opaque = in_macro[m.start()] != text[m.start()]
        if m["prm"]:
            if live_here and not opaque:
                value, position = _hash_definition(text, m.end(), params)
                params[m["prm"]] = value
                out.append(_blank(text[m.start():position]))
            else:
                out.append(m.group() if live_here else _blank(m.group()))
            continue
        if m["kw"] in ("if", "elseif") and not opaque:
            decide = live_here if m["kw"] == "if" else (
                all(frame[0] for frame in stack[:-1]) and bool(stack)
                and not stack[-1][1])
            live = False
            if decide:
                try:
                    live, by_run, position = _hash_condition(text, m.end(), params)
                except _Undecidable as exc:
                    raise refuse(m.start(), f"#{m['kw']}", str(exc)) from None
                run_dependent |= by_run
            out.append(_blank(text[m.start():position]))
            if m["kw"] == "if":
                stack.append([live, live])
            elif stack:
                stack[-1] = [live, stack[-1][1] or live]
            continue
        out.append(_blank(m.group()))
        if m["kw"] in ("if", "elseif"):   # inside a macro body: excised later
            if m["kw"] == "if":
                stack.append([True, True])
        elif m["cond"]:
            live = (m["sym"] in defined) != (m["cond"] == "ifndef")
            stack.append([live, live])
        elif m["kw"] == "else":
            if stack:
                stack[-1] = [not stack[-1][1], True]
        elif m["kw"] == "endif":
            if stack:
                stack.pop()
    tail = text[position:]
    out.append(tail if all(frame[0] for frame in stack) else _blank(tail))
    return _Conditionals("".join(out), run_dependent, params)


#: Every pre-processor directive the reference names, by what it does to the
#: text (Technical Reference §19, which lists them verbatim). The reader
#: evaluates exactly one family and must say so about the rest, because a
#: directive it does not evaluate means **the text it is holding is not the text
#: TOPAS parsed** — the ``/* */`` problem one level up.
#:
#: * *evaluated here* — ``macro`` (excised whole by :func:`_excise_macro_defs`),
#:   ``#define`` and the ``#ifdef``/``#ifndef``/``#else``/``#endif`` family
#:   (:func:`resolve_ifdefs`), and ``#prm``/``#if``/``#elseif`` over hash
#:   parameters (WP-1433, :func:`_resolve_conditionals`).
#: * *brings in text that is not in this file* — ``#include``, ``#ingest``,
#:   ``#external_INP``. Refused: no amount of care with the bytes in hand can
#:   recover bytes that are somewhere else.
#: * *changes which definitions are live* — ``#delete_macros``, ``#undef``.
#:   Refused: the first un-defines macros, the second un-defines the symbols
#:   :func:`resolve_ifdefs` collects, and neither is honoured.
#: * *a condition this reader cannot decide* — an ``#if``/``#elseif`` reaching
#:   ``Rand``, a string, or a function other than ``And``. Refused by name where
#:   it is evaluated (:class:`_HashParser`), not here: whether a condition is
#:   decidable depends on the ``#prm``s live above it.
#: * *invoked on macro expansion* — the ``#m_*`` family. These live only inside
#:   a macro body, so :func:`_excise_macro_defs` removes them; one surviving in
#:   the excised text means the body was not balanced, and is refused.
_INCLUDE_DIRECTIVES = ("#include", "#ingest", "#external_INP")
_UNDEFINING_DIRECTIVES = ("#delete_macros", "#undef")


def refuse_unevaluable_directives(text: str, path) -> None:
    """Refuse a file whose *active text* this reader cannot determine.

    Called on the comment-stripped, macro-excised text — before
    :func:`resolve_ifdefs`, which is the thing being checked.

    Five rounds of this reader treated ``#ifdef`` as "one more spelling to
    handle". The reference makes it a **class**: §19 lists the whole
    pre-processor, and the reader evaluates one family of it. So the rule is
    stated once over the class rather than patched per file, and the shape that
    matters is not which directive appears but whether the text left afterwards
    is the text TOPAS read.

    ``#if``/``#elseif`` used to be refused here; WP-1433 evaluates them
    (:func:`_resolve_conditionals`), and the conditions it cannot decide refuse
    there, by name. One conditional form is still refused here because *either*
    reading of it is a guess:

    * ``#ifdef !name``, which the reference does not describe at all: it says
      ``#ifdef``/``#ifndef`` "test whether a name has (or hasn't) been
      previously ``#define``'d", and says nothing about ``!``. Read as a
      negation the branch is live; read as a plain name it never matches and the
      branch is dead. 6 archive files, and choosing between two opposite wrong
      answers is not a reader's to do.

    What is **not** refused is a conditional merely written somewhere other than
    the start of a line. That was this reader's assumption rather than the
    format's, it cost 283 files, and :func:`resolve_ifdefs` now scans tokens.
    """
    lines = text.split("\n")
    depth = 0
    for number, line in enumerate(lines, 1):
        s = line.strip()
        for directive in _INCLUDE_DIRECTIVES:
            if re.search(rf"{re.escape(directive)}\b", s):
                raise TopasInpError(
                    f"{path}:{number}: `{directive}` pulls text from another "
                    f"file at the pre-processor stage, so the model this file "
                    f"states is not in this file. Reading on would report "
                    f"whatever happens to be left. Inline it, or read the "
                    f"expanded .OUT TOPAS writes beside the refinement.")
        for directive in _UNDEFINING_DIRECTIVES:
            if re.search(rf"{re.escape(directive)}\b", s):
                raise TopasInpError(
                    f"{path}:{number}: `{directive}` un-defines names this "
                    f"reader has already collected, and it is not honoured "
                    f"here — so a `#ifdef` below it would be resolved against a "
                    f"symbol table TOPAS no longer had.")
        if m := re.search(r"#m_\w+", s):
            raise TopasInpError(
                f"{path}:{number}: `{m.group()}` is invoked on macro expansion "
                f"and should only ever sit inside a `macro ... {{ ... }}` body; "
                f"one surviving here means the body's braces are unbalanced and "
                f"the excision could not find its end.")
        for m in re.finditer(r"#ifn?def\s+(\S+)", s):
            if m.group(1).startswith("!"):
                raise TopasInpError(
                    f"{path}:{number}: `{m.group()}` — the technical reference "
                    f"says `#ifdef`/`#ifndef` \"test whether a name has (or "
                    f"hasn't) been previously #define'd\" and describes no `!` "
                    f"form, so whether this branch is live is a guess. Both "
                    f"readings are wrong in opposite directions: as a negation "
                    f"the branch is live, as a plain name it never matches and "
                    f"the branch is dead. Write `#ifndef NAME` instead.")
        for m in re.finditer(r"#if(?:n?def)?\b|#elseif\b|#endif\b", s):
            if m.group() == "#elseif":
                if not depth:
                    raise TopasInpError(
                        f"{path}:{number}: `#elseif` with no `#if` open, so "
                        f"which text it selects is this reader's guess.")
                continue
            depth += 1 if m.group().startswith("#if") else -1
            if depth < 0:
                raise TopasInpError(
                    f"{path}:{number}: `#endif` with no `#ifdef` open. An "
                    f"unbalanced conditional silently changes which of the "
                    f"*following* text is live, so it is refused rather than "
                    f"absorbed.")
    if depth:
        raise TopasInpError(
            f"{path}: {depth} `#if`/`#ifdef`/`#ifndef` here {'is' if depth == 1 else 'are'} "
            f"never closed by an `#endif`, so where the conditional text ends "
            f"is this reader's guess rather than the file's statement.")


#: Every keyword this reader takes a value from, split by the tree level it
#: belongs to, because the two levels are affected differently by a card that
#: moves (below).
_KEYWORDS_READ = ("phase_name", "space_group", "site", "occ", "beq", "scale",
                  "weight_percent", "a", "b", "c", "al", "be", "ga",
                  "x", "y", "z", "u11", "u22", "u33", "u12", "u13", "u23",
                  "adps", "r_wp", "gof", "bkg", "la", "lo")

#: The **phase and site** half of it — what a `str` block is made of. A cell
#: edge is included only where it opens a line, the same discrimination
#: :data:`_CELL_LINE_START` already makes: one-letter keywords are cell edges
#: inside a phase and ordinary words everywhere else, and a body full of
#: `Simple_Axial_Model` and `start_X` is not a phase. Matching them anywhere
#: refused 62 archive files where 36 carry a phase.
_PHASE_CONTENT = re.compile(
    r"(?m)\b(?:phase_name|space_group|site|occ|beq|scale|weight_percent"
    r"|u11|u22|u33|u12|u13|u23|adps)\b|^[ \t]*(?:al|be|ga|a|b|c)\b")

#: TOPAS's data-tree verbs (Technical Reference §2.20, §2.21, §2.23 and
#: `TMisc_keywords`). Each **moves where a card attaches**, and this reader's
#: whole block model is "a card belongs to the block it is lexically inside" —
#: which `_BLOCK` implements by slicing the text between openers.
#:
#: * ``for $object_type { … }`` — "a pre-processor loop that expands its body
#:   once for every existing instance of the given object type". So its body is
#:   *every* phase's, not the one whose slice it happens to land in.
#: * ``load $keyword { … }`` — "allows keywords of the same type to be entered
#:   once instead of repeated", so the brace body is a list of that keyword's
#:   values rather than ordinary input.
#: * ``move_to $keyword`` — walks the tree to somewhere else entirely.
_FOR_LOOP = re.compile(r"\bfor\s+\w+(?:\s+\d+\s+to\s+\d+)?\s*\{")
_LOAD = re.compile(r"\bload\s+(\w+)")
_MOVE_TO = re.compile(r"\bmove_to\b")


def _brace_body(text: str, open_brace: int) -> str:
    """The balanced ``{ … }`` body whose opening brace is at ``open_brace``."""
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1:i]
    return text[open_brace + 1:]


def refuse_moved_attachment(active: str, path) -> None:
    """Refuse a file whose cards do not attach where they are written.

    This reader's block model — ``_BLOCK`` slicing the text between openers —
    *is* the assumption that a card belongs to the block it sits inside. The
    reference's §5.1 licenses it ("the keyword ``str`` signifies that all
    information occurring between it and the next keyword of the same type
    belongs to that ``str``"), and three verbs suspend it.

    ``for`` is the one the archive uses, and it is not decoration: the
    ``archive file 27`` series and ``archive file 1`` declare a **whole phase** —
    ``phase_name``, ``space_group``, all six cell edges, every ``site`` line —
    inside ``for xdds { for strs 1 to 1 { … } }``. ``_BLOCK`` looks for ``str``
    at the start of a line and ``for strs`` is not that, so such a phase is
    invisible to the split; and where a real ``str`` exists elsewhere in the
    file, the loop body's cell and sites are swept into *it* instead. Those two
    object types are now expanded before this runs (:func:`expand_for_loops`:
    54 of the 468 archive files it was measured on went from refused to read,
    and none the other way), so what reaches this check is a loop over
    another object type — ``for site_recs { … }`` — or one left as written
    because its body states nothing the model carries.

    Only a loop whose body carries **phase or site** content refuses: a
    ``for strs { r_bragg 0 }``, a loop of ``out`` records, or a ``for xdds``
    setting ``start_X`` and an instrument macro moves nothing this reader would
    have got wrong. A cell edge counts only where it opens a line — the
    discrimination :data:`_CELL_LINE_START` already makes, since one-letter
    keywords are cell edges inside a phase and ordinary words everywhere else.

    ``load`` is likewise refused only where it loads a keyword this reader
    reads. The five spellings the archive uses — ``load out_record``,
    ``hkl_m_d_th2``, ``sh_Cij_prm``, ``xo``, ``index_th2`` — load none of them,
    which is why 276 files carry one and none is refused.
    """
    for m in _FOR_LOOP.finditer(active):
        body = _brace_body(active, m.end() - 1)
        if found := _PHASE_CONTENT.search(body):
            raise TopasInpError(
                f"{path}: `{' '.join(m.group().split())}` is a pre-processor loop — the "
                f"reference expands its body \"once for every existing instance "
                f"of the given object type\" — and its body states "
                f"`{found.group().strip()}`, which this reader reads. A value inside it "
                f"belongs to *every* phase or dataset, not to the one whose "
                f"text it happens to sit in, and a phase declared inside it is "
                f"invisible to the block split altogether. Reading on would "
                f"report one phase's worth of a statement about all of them. "
                f"Write the phases out, or read the .OUT TOPAS writes with the "
                f"loops already expanded.")
    for m in _LOAD.finditer(active):
        if m.group(1) in _KEYWORDS_READ:
            raise TopasInpError(
                f"{path}: `load {m.group(1)}` enters a list of `{m.group(1)}` "
                f"values in one brace block instead of repeating the keyword, "
                f"so this reader — which reads `{m.group(1)}` where it is "
                f"written — would see one of them and silently drop the rest.")
    if m := _MOVE_TO.search(active):
        raise TopasInpError(
            f"{path}: `move_to` walks TOPAS's internal data tree, so the cards "
            f"after it attach somewhere this reader cannot follow from the "
            f"text's own nesting.")


#: A ``for`` loop's head, with the ``N to M`` range the archive writes
#: (``for strs 1 to 1``) captured. The reference's grammar node is
#: ``[for { .. } ]`` and gives no range form; what the range selects is
#: measured, and :func:`expand_for_loops` records the measurement. The brace
#: may sit on a later line, as :data:`_FOR_LOOP` allows: TOPAS input is
#: free-format, and a head that stopped at the newline missed an outer
#: ``for xdds`` and expanded its inner ``for strs`` as if it were top-level.
#: ``rest`` stops at a ``;`` or a brace, so it never runs into a statement.
_FOR_HEAD = re.compile(
    r"\bfor\s+(?P<kind>\w+)(?:\s+(?P<lo>\d+)\s+to\s+(?P<hi>\d+))?"
    r"(?P<rest>[^{};]*?)\s*\{")

#: The macros the reference's macro index lists as stating ``xdd`` and whose
#: datasets this reader sees as openers (:data:`_DATASET_MACROS`) but whose
#: loops it still does not expand (WP-1530 counted them, and left the refusal
#: alone: no file here exercises the expansion). A ``for xdds`` loop iterates over every
#: dataset that exists, so where one of these supplies a dataset the reader
#: cannot see, the iteration count is unknown and the loop is refused rather
#: than expanded over the datasets it happens to see. ``yobs_eqn`` is the
#: keyword form of the same thing — a dataset made from an equation.
_UNSEEN_DATASETS = re.compile(
    r"\b(?:(?:RAW|XDD|XYE|XY|DAT|BRML|SST|Create_XDDs)\s*\(|yobs_eqn\b)")


def _brace_close(text: str, open_brace: int) -> int | None:
    """One past the ``}`` balancing the ``{`` at ``open_brace``, or ``None``."""
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _top_level_loops(text: str) -> list[tuple[re.Match, int]]:
    """The ``for`` loops of ``text`` that no other loop encloses, each with the
    offset one past its closing brace."""
    loops: list[tuple[re.Match, int]] = []
    reached = 0
    for m in _FOR_HEAD.finditer(text):
        if m.start() < reached:
            continue
        close = _brace_close(text, m.end() - 1)
        if close is None:
            return loops        # unbalanced: left to refuse_moved_attachment
        loops.append((m, close))
        reached = close
    return loops


def _bears_on_the_model(body: str) -> bool:
    """Does a loop body state anything this reader reads or reports?

    Phase or site content, a time-of-flight construct, or a phase-scope
    keyword :mod:`.coverage` gives a stance with an outcome. A loop stating
    none of these (``for strs { Remove_Phase(0.3, 0.5) }``, ``for xdds {
    th2_offset = … }``) changes nothing the built model carries, so it is left
    as written — and is not refused for a target TOPAS would not have found.
    """
    return bool(_PHASE_CONTENT.search(body) or _TOF_CONSTRUCT.search(body)
                or _COVERED.search(_masked(body)))


def expand_for_loops(active: str, path) -> str:
    """Expand ``for xdds { … }`` and ``for strs [N to M] { … }`` textually.

    The reference defines ``for $object_type { … }`` as "a pre-processor loop
    that expands its body once for every existing instance of the given object
    type" (Technical Reference, the ``for`` entry under ``TMisc_keywords``), and
    its own examples place the loop *after* the objects (§2.22-2.23,
    ``str … str … for strs { … }``). What "existing" means, and what the range
    form selects — which the reference does not state — was measured on TOPAS
    v6 as a black box, on two-``xdd`` synthetic files whose loop body sets a
    distinguishable peak shift (``tests/data/README.md`` § ``for`` loops):

    * a ``for xdds`` loop reaches **every dataset opened above it** and none
      below (a loop between two ``xdd``\\ s shifted the first only), and one
      with no dataset above it stops TOPAS with ``Error loading sstring_in``;
    * a ``for strs`` loop reaches the phases of the **dataset it is written
      in** — at the end of the file, the last one's, not every phase in the
      file — and inside ``for xdds`` each dataset's own in turn;
    * a "phase" there is a ``str``: an ``hkl_Is`` above it is not counted and
      not reached;
    * ``N to M`` counts phases from 1 **within that dataset**, and on
      ``for xdds`` counts datasets from 1; a range past the last instance, or
      a loop with nothing to reach, stops TOPAS too (``invalid index``).

    So the expansion is textual and positional, which is what the block model
    needs: a ``for xdds`` body's own text is inserted at the head of each
    dataset above the loop, before its first ``str``, where a dataset-level
    card belongs; a ``for strs`` body at the end of each phase it reaches; the
    loop itself is blanked. A loop whose body states nothing this reader reads
    is left as written (:func:`_bears_on_the_model`). Everything TOPAS refuses
    is refused here, and so is everything the reader cannot place — a body
    that opens a block of its own,
    a loop over another object type nested inside one of these two, and a file
    whose datasets come from a macro this reader does not open
    (:data:`_UNSEEN_DATASETS`), because then the number of datasets the loop
    iterates over is not in the text. A loop over another object type is left
    as it is, for :func:`refuse_moved_attachment` to judge. Offsets after the
    first insertion move, so this runs after every check that reports a line.
    """
    quoted = re.sub(r'"[^"\n]*"', lambda m: _blank(m.group()), active)
    # The two head scanners must agree: a head `refuse_moved_attachment` sees
    # and this expansion does not would be a loop left in place while the
    # loops around or inside it are rewritten.
    heads = {m.start() for m in _FOR_HEAD.finditer(quoted)}
    for m in _FOR_LOOP.finditer(quoted):
        if m.start() not in heads:
            raise TopasInpError(
                f"{path}: `{' '.join(m.group().rstrip('{').split())}` is a "
                f"pre-processor loop this reader's loop expansion does not "
                f"parse as one (its head runs into the text before it), so "
                f"which instances its body reaches, and where its body lands, "
                f"is not something it can place.")
    loops = [(m, close) for m, close in _top_level_loops(quoted)
             if m["kind"] in ("xdds", "strs")
             and _bears_on_the_model(quoted[m.end():close - 1])]
    if not loops:
        return active
    if hit := _UNSEEN_DATASETS.search(quoted):
        raise TopasInpError(
            f"{path}: `{' '.join(loops[0][0].group().rstrip('{').split())}` expands its "
            f"body once per dataset or phase that exists, and this file opens "
            f"a dataset through `{hit.group().rstrip('(').strip()}`, which "
            f"this reader does not expand a loop over (it counts a data-file "
            f"macro as one dataset, but a loop would need each phase placed "
            f"in its dataset) — so how many times the body is expanded, and "
            f"into which phases, is not something it can place.")
    openers = list(_BLOCK.finditer(active))
    datasets = [o for o in openers if o["kw"] in _DATASET_OPENERS]

    def head(m: re.Match) -> str:
        return " ".join(m.group().rstrip("{").split())

    def phases_of(start: int, stop: int) -> list[re.Match]:
        return [o for o in openers if o["kw"] == "str" and start < o.start() < stop]

    def phase_end(phase: re.Match, stop: int) -> int:
        later = [o.start() for o in openers if o.start() > phase.start()]
        return min([stop, *later])

    def selected(m: re.Match, phases: list[re.Match], where: str) -> list[re.Match]:
        if m["rest"].strip():
            raise TopasInpError(
                f"{path}: `{head(m)}` selects its instances with "
                f"`{m['rest'].strip()}`, which is not an `N to M` range this "
                f"reader can read — a macro, most likely, standing for one — "
                f"so which instances the body reaches is not in the text.")
        if not phases:
            raise TopasInpError(
                f"{path}: `{head(m)}` has nothing this reader can see to "
                f"reach in {where}. Either there is none, which TOPAS itself "
                f"refuses (measured: `Error loading sstring_in`), or a macro "
                f"whose body this reader does not expand states it — and "
                f"either way the text the loop would have filled is not here.")
        if m["lo"] is None:
            return phases
        lo, hi = int(m["lo"]), int(m["hi"])
        if not 1 <= lo <= hi <= len(phases):
            raise TopasInpError(
                f"{path}: `{head(m)}` asks for instances {lo} to {hi} of "
                f"{where}, which states {len(phases)} — TOPAS itself stops on "
                f"this (measured: `invalid index`).")
        return phases[lo - 1:hi]

    def checked_body(m: re.Match, body: str, qbody: str) -> None:
        if (inner := _FOR_HEAD.search(qbody)):
            raise TopasInpError(
                f"{path}: `{head(m)}` holds `{head(inner)}`, a loop this "
                f"reader does not expand inside another, so where its body "
                f"lands is not something it can place.")
        if (block := _BLOCK.search(body)):
            raise TopasInpError(
                f"{path}: `{head(m)}` opens a `{block['kw']}` block inside its "
                f"body — a new object per iteration, which this reader does "
                f"not expand.")

    inserts: list[tuple[int, int, str]] = []        # (offset, loop order, text)
    for order, (m, close) in enumerate(loops):
        body = active[m.end():close - 1]
        qbody = quoted[m.end():close - 1]
        above = [d for d in datasets if d.start() < m.start()]
        if not above:
            raise TopasInpError(
                f"{path}: `{head(m)}` is written above every dataset this "
                f"reader can see, and a loop reaches only the instances that "
                f"exist where it is written. Either the file opens none above "
                f"it, which TOPAS itself refuses (measured: `Error loading "
                f"sstring_in`), or a macro whose body this reader does not "
                f"expand opens them — and then how many there are is not in "
                f"the text in hand.")
        def span_end(d: re.Match) -> int:
            later = [o.start() for o in datasets if o.start() > d.start()]
            return min([m.start(), *later])
        if m["kind"] == "strs":
            checked_body(m, body, qbody)
            current = above[-1]
            stop = span_end(current)
            for ph in selected(m, phases_of(current.start(), stop),
                               f"the dataset `{current['kw']}` above it"):
                inserts.append((phase_end(ph, stop), order, body))
            continue
        # `for xdds`: its own text goes to each dataset's head; a nested
        # `for strs` goes to that dataset's phases.
        nested = _top_level_loops(qbody)
        own = list(body)
        for inner, inner_close in nested:
            if inner["kind"] != "strs":
                raise TopasInpError(
                    f"{path}: `{head(m)}` holds `{head(inner)}`, a loop this "
                    f"reader does not expand, so where its body lands is not "
                    f"something it can place.")
            own[inner.start():inner_close] = _blank(qbody[inner.start():inner_close])
        own_text = "".join(own)
        checked_body(m, own_text, re.sub(r'"[^"\n]*"',
                                         lambda q: _blank(q.group()), own_text))
        for d in selected(m, above, "the file above it"):
            k = datasets.index(d)
            stop = span_end(d)
            if own_text.strip():
                blocks = [o.start() for o in openers if d.start() < o.start() < stop]
                inserts.append((blocks[0] if blocks else stop, order, own_text))
            for inner, inner_close in nested:
                inner_body = body[inner.end():inner_close - 1]
                checked_body(inner, inner_body, qbody[inner.end():inner_close - 1])
                for ph in selected(inner, phases_of(d.start(), stop),
                                   f"dataset {k}"):
                    inserts.append((phase_end(ph, stop), order, inner_body))
    out = list(active)
    for m, close in loops:
        out[m.start():close] = _blank(active[m.start():close])
    text = "".join(out)
    # Insert from the end so every offset above is still the original's; at one
    # offset the earlier loop's text comes first, as TOPAS reads them in order.
    ranked = sorted(((offset, order, seq, body)
                     for seq, (offset, order, body) in enumerate(inserts)),
                    key=lambda i: i[:3], reverse=True)
    for offset, _, _, body in ranked:
        text = text[:offset] + "\n" + body + "\n" + text[offset:]
    return text


def normalize_species(species: str) -> str:
    """``Cu+1`` → ``Cu1+``, ``7Li+1`` → ``7Li1+`` (rule 4). IUCr order is digit-first.

    A leading mass number is TOPAS's isotope spelling and rietx's alike
    (``7Li``, ``60Ni``), so it is carried through unchanged.
    """
    s = re.sub(r"[^A-Za-z0-9+-]", "", species)
    if m := re.fullmatch(r"(\d*)([A-Za-z]{1,2})([+-])(\d*)", s):
        mass, element, sign, magnitude = m.groups()
        return f"{mass}{element}{magnitude or ''}{sign}"
    return s


def topas_species(species: str) -> str:
    """``Cu1+`` → ``Cu+1``: the inverse of :func:`normalize_species`, for writing.

    TOPAS reads an ion sign-first and stops on the IUCr order rietx stores:
    ``occ O2-`` ends the run with "Cannot find o2 in file isotopes.txt", for
    X-ray and neutron data alike, and ``occ O-2`` runs (issue #550; TOPAS 6,
    run as a black box). An isotope keeps its leading mass number, which is
    TOPAS's order too: ``7Li1+`` → ``7Li+1`` (``7Li1+`` stops TOPAS with
    "Cannot find 7li1 in file isotopes.txt"; ``7Li+1`` runs and gives ⁷Li's b).
    A neutral atom or isotope, or any label that is not an element plus a
    charge, is written as it is.

    The species written is the one rietx computes
    (:func:`~rietx.crystallography.scattering.written_species`, WP-1527). A
    one-charge ion without its digit is the tabulated ion, so ``Cu+`` →
    ``Cu+1``, which TOPAS reads as that ion. An ion rietx's table lacks is
    computed as the neutral atom, so ``Fe+`` → ``Fe``, and
    :func:`from_structure` reports it as ``TOPAS_SPECIES_WRITTEN_NEUTRAL``.
    """
    from ...crystallography.scattering import written_species

    return _sign_first(written_species(species)[0])


def _sign_first(species: str) -> str:
    """``Fe4+`` → ``Fe+4``, and nothing else: TOPAS's spelling of a label."""
    if m := re.fullmatch(r"(\d*)([A-Za-z]{1,2})(\d*)([+-])", species):
        mass, element, magnitude, sign = m.groups()
        return f"{mass}{element}{sign}{magnitude}"
    return species


def normalize_space_group(symbol: str) -> str:
    """``Pn-3mZ`` → ``Pn-3m:2`` (rule 4, and see :data:`_SG_SUFFIX`)."""
    s = symbol.strip()
    if s.endswith(tuple(_SG_SUFFIX)) and not s.endswith(":"):
        stem, suffix = s[:-1], s[-1]
        # only a real suffix, not the final letter of a symbol like "Fm-3m"
        if re.search(r"[a-z\-0-9/]$", stem):
            return stem + _SG_SUFFIX[suffix]
    return s


_AST_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)


def _arith(expr: str) -> float | None:
    """Evaluate the rational arithmetic TOPAS writes for a special position.

    ``ast`` rather than ``eval``: the charset gate this replaces admitted
    ``**``, so ``9**9**9`` in a malformed file was an unbounded computation
    inside a reader. Only the five operators a coordinate equation needs are
    walked, and anything else — a name, a call, a power — returns None.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    def walk(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, _AST_OPS):
            v = walk(node.operand)
            return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
        if isinstance(node, ast.BinOp) and isinstance(node.op, _AST_OPS):
            a, b = walk(node.left), walk(node.right)
            if a is None or b is None:
                return None
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            return None if b == 0 else a / b
        return None

    return walk(tree.body)


#: TOPAS's ``Get`` built-in. Its argument is a *name* — a keyword or a
#: parameter — not an expression, which is why it is matched exactly and never
#: handed to :func:`_arith` as a call. §2.5 is explicit about what it returns
#: and where it looks: the value of that name, searched for locally first and
#: then outward through the enclosing scopes. That makes ``Get`` the one
#: spelling in which a cell edge may name **another cell edge**, because a bare
#: name in an equation reaches a *parameter* (§2.3-2.4) and a cell keyword is
#: not one — which is the reason the reference gives for the built-in existing.
_GET = re.compile(rf"\bGet\s*\(\s*(?P<name>{_NAME})\s*\)")


def _resolve(expr: str, symbols: dict[str, float],
             getters: dict[str, float] | None = None,
             refs: set[str] | None = None) -> float | None:
    """An equation's value: resolve ``Get(...)``, substitute named parameters,
    then evaluate.

    ``getters`` is the **local** scope a ``Get(name)`` sees before the file's
    own symbol table — for a cell key, the keys of the same phase already read.
    A name it does not hold is left standing as a bare name, so the symbol
    substitution below gets its turn: that is §2.5's "searches for xx locally,
    if not found it searches its parent's scope", with this reader's flat symbol
    table as the parent. A name in neither scope still resolves to None and the
    caller still refuses, so widening what *can* be read has not widened what
    can be silently guessed.

    ``Get`` is resolved *before* substitution, not after: the argument is a name,
    and substituting into it first would leave ``Get(4.15)`` — a call, which
    :func:`_arith` correctly refuses to evaluate.

    Longest name first, so a name that is a prefix of another is never
    half-replaced (``Fe1_1_x`` inside ``Fe1_1_x2``).

    ``refs`` collects the **file symbols** this expression was resolved
    through, because a value copied out of a shared symbol is a coupling in
    exactly the way ``Get(a)`` is: ``a = edge; b = edge;`` under one
    ``prm edge`` is the format's other way of tying two cell edges, and the
    number arrives with the tie left behind either way. Collected here rather
    than re-matched off the expression by a caller, for the reason the flag
    travels with the value — a second reading of the same text is a second
    grammar, and the two drift.
    """
    scope = getters or {}
    expr = _GET.sub(
        lambda m: (repr(scope[m["name"]]) if m["name"] in scope else m["name"]),
        expr)
    for sym in sorted(symbols, key=len, reverse=True):
        if sym in expr:
            substituted, n = re.subn(rf"\b{re.escape(sym)}\b",
                                     repr(symbols[sym]), expr)
            if n and refs is not None:
                refs.add(sym)
            expr = substituted
    return _arith(expr)


# --------------------------------------------------------------- one grammar

#: An equation *and the value TOPAS evaluated it to*: ``= 1/4 + Fe1_1_dx;: 0.25``.
#: The ``;:`` tail is the most authoritative number in the file — it is what the
#: converged refinement actually used, so it is preferred over re-evaluating the
#: expression here, which would need every symbol the expression reaches. The
#: write-back backtick sits *after* that tail, which is where a flag regex
#: reading the line a second time could not reach it.
_TAIL_EVALUATED = re.compile(
    rf"\s*(?P<pre>{_FLAG})?(?:(?P<name>{_NAME})\s*)?(?P<post>{_FLAG})?"
    rf"=\s*[^;\n]*;\s*:\s*(?P<value>{_NUM})(?P<tick>`?)")

#: An equation with no evaluated tail — ``x = 1/3;``, ``x Zr1_x =1/2;``,
#: ``a = mlpa;``. This reader has to evaluate it itself, against
#: :func:`symbol_table`, and an unresolvable one is None and still raises.
_TAIL_EQUATION = re.compile(
    rf"\s*(?P<pre>{_FLAG})?(?:(?P<name>{_NAME})\s*)?(?P<post>{_FLAG})?"
    rf"=\s*(?P<expr>[^;\n]+);")

#: A stated number: ``[flags] [name] [flags] <number>[`]``. The trailing
#: ``_esd`` and ``_LIMIT_*`` annotations need no stripping, because ``_`` ends
#: :data:`_NUM` — ``5.17632205e-006_3.88e-006_LIMIT_MIN_1e-015`` is one match.
_TAIL_VALUE = re.compile(
    rf"\s*(?P<pre>{_FLAG})?(?:(?P<name>{_NAME})\s+(?P<post>{_FLAG})?)?"
    rf"(?P<value>{_NUM})(?P<tick>`?)")

#: A1/A2/A3 are x/y/z, written as a macro because the axis letter does not
#: appear on the line at all. The flag sits *inside* the parenthesis, which is
#: the one place the flag grammar could not follow the value grammar.
_AXIS_MACROS = {
    axis: re.compile(rf"\b{macro}\(\s*(?P<pre>{_FLAG})?(?P<name>{_NAME})\s*,\s*"
                     rf"(?P<value>{_NUM})(?P<tick>`?)")
    for axis, macro in (("x", "A1"), ("y", "A2"), ("z", "A3"))}


@dataclass(frozen=True)
class _Read:
    """One scalar exactly as the file states it.

    ``value`` is None only where an equation could not be resolved — the caller
    is the only place that knows whether that is fatal. ``vary`` is the
    tri-state :func:`refined` returns. ``name`` is the parameter's own name
    where the file gave one, which is what makes the value a *declaration*
    another equation can reference. ``rest`` is the text after the number,
    where a ``min``/``max`` window sits.

    ``expr`` is the **equation this value was computed from**, and only the
    equation form sets it: an evaluated tail carries TOPAS's own number and a
    stated value names nothing, so for those two there is no expression and it
    stays None. It is what lets a caller ask *how* a number was arrived at
    rather than only what it is — the cell scan uses it to see that ``b`` came
    from ``Get(a)``, which is a coupling and not just a 5.128. Carried on the
    read rather than re-matched off the line because the line may state several
    keys, and re-matching would attribute one key's equation to another.
    """

    value: float | None
    vary: bool | None
    name: str | None = None
    rest: str = ""
    expr: str | None = None
    #: The file symbols the equation was resolved **through**, from
    #: :func:`_resolve`. Empty for the two non-equation forms, which reference
    #: nothing. Its use is the same as ``expr``'s — asking *how* a number was
    #: arrived at — one step further out: ``expr`` says the value came from an
    #: equation, this says which declared parameters that equation reached, and
    #: those are what carry a refine flag of their own.
    refs: tuple[str, ...] = ()


def _flag(*tokens: str | None, named: str | None = None) -> bool | None:
    """The refine tri-state a set of flag tokens, a name and a write-back tick.

    ``!`` outranks everything: TOPAS writes the converged value back into a
    *held* parameter too, so a backtick beside a ``!`` is a write, not a claim
    that the parameter moved.

    **A name is itself the refine flag.** Technical Reference §2.1, *When is a
    parameter refined*, opens with the rule and gives all three spellings::

        A parameter is flagged for refinement by giving it a name.
            site Zr x 0 y 0 z 0 occ Zr+4 1 beq b1 0.5      ' b1 is refined
            site Zr x 0 y 0 z 0 occ Zr+4 1 beq !b1 0.5     ' ! holds it
            site Zr x 0 y 0 z 0 occ Zr+4 1 beq @ 0.5       ' @ refines it

    So ``beq b1 0.5`` is *not* a file that says nothing about b1 — it is a file
    that says b1 was free — and reading it as ``None`` made it arrive
    ``vary=False``. **3891 named-but-unflagged values across 89 archive files**
    were reported as unstated and built as held. That is this reader's own
    headline claim ("the refine flags are the payload, not the numbers")
    getting the payload backwards on the format's *primary* spelling, and no
    archive sweep could find it: a wrong `vary` raises nothing and changes no
    parsed number.

    ``named`` is passed only where the file states a **value** — ``[name]
    <number>`` and the ``A1(name, value)`` coordinate macro. It is deliberately
    *not* passed for the ``= expr;`` forms: §2.4 makes an equation a
    *constraint*, so a named equation is a dependent parameter rather than an
    independent refined one, and its write-back backtick already says whether
    it moved.

    A bare number with no name and no flag stays ``None`` rather than becoming
    ``False``. The reference calls it a constant, but the tri-state's caution is
    worth keeping at the one boundary where nothing was written: a caller can
    tell "the file did not flag this" from "the file held this", and
    ``rx.Parameter`` defaults it to fixed either way.
    """
    joined = "".join(t or "" for t in tokens)
    if "!" in joined:
        return False
    if "@" in joined or "`" in joined:
        return True
    return True if named else None


def _read_tail(tail: str, symbols: dict[str, float],
               getters: dict[str, float] | None = None) -> _Read | None:
    """The one grammar, applied to the text that follows a keyword.

    Three forms, all real, in decreasing order of authority: TOPAS's own
    evaluated tail (preferred, because it is what the converged refinement
    used), an equation this reader has to evaluate itself, and a stated number.
    The fourth spelling — the ``A1(…)`` coordinate macro — is not a tail at all
    and is handled by :func:`_read`. Each form yields the value *and* its flag
    off a single match, which is what stops the two grammars drifting apart.

    ``getters`` is passed through to :func:`_resolve` as the local scope a
    ``Get(...)`` in the equation form may name. It reaches only that form: the
    evaluated tail already carries TOPAS's own number, and a stated value names
    nothing.
    """
    if m := _TAIL_EVALUATED.match(tail):
        return _Read(float(m["value"]), _flag(m["pre"], m["post"], m["tick"]),
                     m["name"], tail[m.end():])
    if m := _TAIL_EQUATION.match(tail):
        refs: set[str] = set()
        value = _resolve(m["expr"].strip(), symbols, getters, refs)
        return _Read(value, _flag(m["pre"], m["post"]), m["name"],
                     tail[m.end():], expr=m["expr"].strip(),
                     refs=tuple(sorted(refs)))
    if m := _TAIL_VALUE.match(tail):
        return _Read(float(m["value"]),
                     _flag(m["pre"], m["post"], m["tick"], named=m["name"]),
                     m["name"], tail[m.end():])
    return None


#: Every keyword the grammar allows *inside* a ``site``, and therefore every
#: token that can follow ``occ`` and bound its text. That boundary is what makes
#: an *absent* occupancy different from one whose value is the next keyword's:
#: ``occ Sr+2 beq 0.765`` is a full occupancy and a B of 0.765, and reading the
#: token after the species gave it occupancy 0.765.
#:
#: The list is the technical reference's own (``Tstr_details``), not a set
#: collected from files, because a name that is missing here is a *silently
#: wrong occupancy* and the archive cannot enumerate what it happens not to
#: contain. The grammar states::
#:
#:     [site $site [x E] [y E] [z E]]...
#:       [occ $atom E [beq E] [scale_occ E]]...
#:       [num_posns #] [rand_xyz !E] [inter !E #]
#:       [[adps] | [[u11 E] [u22 E] [u33 E] [u12 E] [u13 E] [u23 E]]]
#:       Tmin_max_r                       ' min_r, max_r
#:       [adps_scale E]
#:       [mlx E] [mly E] [mlz E] [mg E]
#:       [mag_only] [co #] [g !N] [q E] [s E] [track !E] [layer $layer]
#:
#: Thirteen of those were missing before this round. None of them misreads a
#: file in the 606-file archive — every site there states its occupancy — so
#: this is latent cover, closed from the specification rather than from a
#: failure. ``vcocc`` is kept though the reference's table does not name it: it
#: was already here, and a spurious terminator can only end an occupancy early,
#: never lengthen one. ``site`` itself terminates because the next site's token
#: bounds this one.
#: ``adps`` is the one child the archive spells in two cases (``ADPs``/``adps``),
#: so it carries a scoped case-insensitive flag rather than two entries — the
#: same spelling :data:`_ADPS_KW` already reads. Longest first, so ``\b`` never
#: truncates ``adps_scale`` to ``adps`` or ``min_r`` to ``min``.
_SITE_CHILDREN = ("beq", "scale_occ", "num_posns", "rand_xyz", "inter",
                  "(?i:adps_scale)", "(?i:adps)", "min_r", "max_r",
                  "mlx", "mly", "mlz", "mg", "mag_only",
                  "co", "g", "q", "s", "track", "layer",
                  "vcocc", "site", r"u\d\d")
_SITE_KEYWORDS = r"\b(?:" + "|".join(
    sorted(_SITE_CHILDREN, key=len, reverse=True)) + r")\b"

#: The six anisotropic displacement components TOPAS writes, in the order
#: :meth:`rietx.AnisoU.from_values` expects. TOPAS's ``u_ij`` are U^ij in Å² —
#: the CIF ``_atom_site_aniso_U_ij`` convention, crystal frame — the same
#: numbers rietx's :class:`~rietx.AnisoU` holds, so no 8π² conversion (a
#: NaCl u11 = 0.013 is B_eq = 8π²·0.013 = 1.026, not 0.013).
#:
#: That magnitude is *corroboration*, and it is all there is: unlike the scale
#: convention beside it, this one is **not measured against TOPAS's own
#: output**, which ``io/CLAUDE.md`` asks for first. The row in
#: ``tests/data/README.md`` says so and says what would settle it — the claim
#: names the state of its own evidence rather than reading as established.
_ADP_KEYS = ("u11", "u22", "u33", "u12", "u13", "u23")

#: The site's magnetic keywords, in the order :class:`~rietx.Moment` stores
#: them plus the Landé factor last (WP-1328).  ``mlx``/``mly``/``mlz`` are
#: fractional-basis components, converted to crystal-axis μ_B by
#: :func:`to_structure` — see :attr:`TopasSite.moment` for what that rests
#: on — and ``mg`` is the g the ⟨j₂⟩ term of a 4f form factor
#: needs (``crystallography.magnetic.form_factor.resolve_g``).
_MOMENT_KEYS = ("mlx", "mly", "mlz", "mg")

#: The three components of :data:`_MOMENT_KEYS`, without the g.
_MOMENT_COMPONENT_KEYS = _MOMENT_KEYS[:3]

#: Any anisotropic component marks a site anisotropic — with or without the
#: ``adps`` keyword, which introduces the tensor but carries no value itself.
_ADP_TOKEN = re.compile(r"\bu(?:11|22|33|12|13|23)\b")

#: The ``ADPs`` keyword, in any case the archive spells it. ``ADPs_Keep_PD``
#: does not match — the ``_`` is a word character, so ``\b`` refuses it.
_ADPS_KW = re.compile(r"\badps\b", re.I)

#: The archive's live anisotropic spelling: a six-slot positional brace block,
#: ``ADPs { u11 u22 u33 u12 u13 u23 }``, each slot any spelling of the one
#: grammar (named, flagged, equation, evaluated tail). The slot order is an
#: archive-evidenced **specification fact** (`io/CLAUDE.md`'s rule 2):
#: `archive file 2:187` names its slots ``Ho1_u11 … Ho1_u23`` in exactly that
#: order, and `archive file 3:73` names slots 1, 2, 3 and 6
#: ``u11Se``/``u22Se``/``u33Se``/``u23Se`` with the two zeros in the
#: ``u12``/``u13`` positions.
_ADPS_BRACE = re.compile(r"\badps\b\s*\{([^}]*)\}", re.I)

#: An ``_esd``/``_LIMIT_*`` annotation attached to the previous value with no
#: whitespace — ``0.01835`_0.00053`` — which sequential slot reading must skip.
#: Anchored (used with ``.match``), so a *name* after whitespace never matches.
_ADP_ANNOTATION = re.compile(r"_[^\s;{}]*")

#: A ``min``/``max`` window between slots — ``min 0.0001 max=0.1;`` — the
#: author's search box, inert on rietx's AnisoU components (the schema refines
#: tensor patterns, not boxes), so it is skipped rather than carried.
_ADP_WINDOW = re.compile(rf"\s*\b(?:min|max)\b\s*(?:=[^;\n]*;|{_NUM})")


def _read_adps_slots(inner: str, symbols: dict[str, float]) -> list[_Read] | None:
    """The six slot reads of an ``ADPs { … }`` block, in slot order, or None
    where the block does not read as exactly six values of the one grammar."""
    reads: list[_Read] = []
    text = inner
    while len(reads) < 6:
        while True:
            if m := _ADP_ANNOTATION.match(text):
                text = text[m.end():]
                continue
            if m := _ADP_WINDOW.match(text):
                text = text[m.end():]
                continue
            break
        if not text.strip():
            break
        if (read := _read_tail(text, symbols)) is None:
            return None
        reads.append(read)
        text = read.rest
    while True:
        if m := _ADP_ANNOTATION.match(text):
            text = text[m.end():]
            continue
        if m := _ADP_WINDOW.match(text):
            text = text[m.end():]
            continue
        break
    if len(reads) != 6 or text.strip():
        return None
    return reads


def _read(name: str, text: str, symbols: dict[str, float] | None = None,
          getters: dict[str, float] | None = None) -> _Read | None:
    """What ``text`` states for the keyword ``name``, value and flag together.

    Two keywords are not simply "name then value" and both are handled here
    rather than by a second grammar:

    * ``x``/``y``/``z`` may be written as the ``A1(…)``/``A2(…)``/``A3(…)``
      macro, whose flag is inside the parenthesis.
    * ``occ``'s next token is a **species**, not a parameter name. The grammar
      has one name slot and on an ``occ`` line the species consumes it, so
      ``occ Ca @ 0.6`` used to work by accident while ``occ Ca+2 @ 0.6`` and
      ``occ Ca !n 0.6`` both lost their flag — 38 real site lines, including a
      Si/Ge solid solution deliberately held at 0.8/0.2. Widening
      :data:`_NAME` to admit ``+``/``-`` is not the fix: it is load-bearing
      everywhere else, and a held-by-default occupancy cannot be told from a
      held-by-file one.

    ``getters`` is the local scope a ``Get(...)`` in this keyword's value may
    name, passed straight through to :func:`_read_tail`.
    """
    symbols = symbols or {}
    if (macro := _AXIS_MACROS.get(name)) and (m := macro.search(text)):
        return _Read(float(m["value"]),
                     _flag(m["pre"], m["tick"], named=m["name"]), m["name"],
                     text[m.end():])
    for m in re.finditer(rf"\b{re.escape(name)}\b", text):
        tail = text[m.end():]
        if name == "occ":
            if not (species := re.match(r"\s*\S+", tail)):
                continue
            tail = re.split(_SITE_KEYWORDS, tail[species.end():], maxsplit=1)[0]
        if (read := _read_tail(tail, symbols, getters)) is not None:
            return read
    return None


#: An occupancy value is bounded by the **next ``occ``** as well as by the site
#: keywords, so each ``occ`` token on a mixed site reads its own value and no
#: other's — ``occ Al+3 0.9 occ Cr+3 0.1`` is two pairs, not one value read off
#: whichever match a separate walk reached first.
_OCC_TERMINATOR = re.compile(r"\bocc\b|" + _SITE_KEYWORDS)


def _site_occupancies(text: str, symbols: dict[str, float]) -> list[tuple[str, "_Read | None"]]:
    """Every ``(species, value-read)`` the ``occ`` tokens of a site segment state,
    in file order (WP-1118, findings 2 and 3).

    A mixed site is written either as two ``site`` lines sharing a label or as
    **one** line carrying several ``occ`` tokens — ``occ Al+3 0.9 occ Cr+3 0.1``.
    The predecessor read the species off the *first* ``\\bocc\\b`` match and the
    value off a *separate* walk that returned the first tail to parse, so three
    things went wrong at once: every species after the first was dropped, and
    ``occ Al+3 occ Cr+3 0.1`` gave **Al** the 0.1 that is Cr's (species from
    match one, value from match two). Here each ``occ`` token is read **once**:
    its species is the token immediately after it, and its value travels with
    that same species, bounded by the next ``occ`` or site keyword so one pair's
    value can never be read off the next.

    The second element is ``None`` where the token states no value at all
    (``occ Al+3`` with nothing after) — the format's own 1.0 default, established
    in round two. A :class:`_Read` whose ``value`` is ``None`` is a *stated*
    value that could not be resolved (``occ Na+1 =mystery;``), which the site
    loop refuses rather than defaulting (finding 4).
    """
    out: list[tuple[str, "_Read | None"]] = []
    for m in re.finditer(r"\bocc\b", text):
        tail = text[m.end():]
        if not (species := re.match(r"\s*(\S+)", tail)):
            continue
        rest = _OCC_TERMINATOR.split(tail[species.end():], maxsplit=1)[0]
        out.append((species.group(1), _read_tail(rest, symbols)))
    return out


def _field(name: str, line: str, symbols: dict[str, float] | None = None) -> float | None:
    """One field's value, or None where the line does not state one (rule 3).

    The value half of :func:`_read`, kept as a name because most callers want
    only the number — the flag half is :func:`refined`, and both come off the
    same match rather than from two regexes over the same line.
    """
    read = _read(name, line, symbols)
    return read.value if read else None


def refined(name: str, text: str) -> bool | None:
    """Was this parameter free in the refinement the file records?

    **The refine flags are the payload, not the numbers** (WP-1118): a control
    file says which parameters were free, which were held and what was
    excluded, and that is the part a person cannot reconstruct from a CIF plus
    a pattern. It is also the part that decides whether a cross-code comparison
    means anything — DESIGN.md's v0.2 lesson, that a guessed protocol gave
    Rwp 16 % and +390 ppm on fluorapatite against 9.73 % for the mirrored one.

    Three signals, in decreasing order of authority:

    * ``!`` before the value or its name — explicitly **held**.
    * ``@`` before either — explicitly **refined**.
    * a trailing backtick — TOPAS wrote this value back after refining it, so
      it was free. Its *absence* is the inference WP-1110's agent round named
      as the hardest single thing about transcribing an ``.inp`` by hand.

    None means the file says nothing either way, which is not the same as
    "fixed" and is why this is a tri-state rather than a bool.

    Read off the **same match as the value**, through :func:`_read`, rather
    than by a second regex over the line: the value grammar was unified before
    the flag grammar was, and wherever the two disagreed — the ``A1(@xO3, …)``
    macro, a backtick after a ``;:`` tail, any ``occ`` with a species — the
    flag came back None, which ``rx.Parameter`` then defaults to
    ``vary=False``. The tri-state collapsed to "held" at the one boundary
    where the file had been explicit.
    """
    read = _read(name, text)
    return read.vary if read else None


# -------------------------------------------------------- symbol declarations

#: The keywords this reader reads a value for, and therefore the only places a
#: **name slot** can sit. ``x ph1_O1_x 0.29935`` declares ``ph1_O1_x``, which
#: ``y = ph1_O1_x;`` two tokens later references; refusing that cost 14 of the
#: 606 archive files, the tier-1 references among them. ``prm`` and
#: ``local`` are TOPAS's explicit declarations.
#:
#: The *keyword* slot is never a declaration, and that is the whole narrowing:
#: the predecessor swept every ``<name> <number>`` pair in the file, which on a
#: realistic 30-line file bound 21 symbols including ``beq``, ``bkg``, ``gof``,
#: ``min``, ``max``, ``r_wp``, ``x``, ``y``, ``z``. Nothing raises when one is
#: substituted into an equation — ``_resolve`` substitutes and ``_arith``
#: returns a plausible number — and ``setdefault`` meant a real ``prm x 0.9999``
#: lost to an earlier site's ``x 0.1111``.
_DECLARING_KEYWORDS = ("prm", "local", "a", "b", "c", "al", "be", "ga",
                       "x", "y", "z", "beq", "occ", "scale", "weight_percent")

_DECLARATION = re.compile(rf"\b(?P<kw>{'|'.join(_DECLARING_KEYWORDS)})\b")

#: A macro's *named* argument is a declaration too — ``CS_L(csl1, 210.4)`` names
#: a crystallite size an equation elsewhere may reach, and ``Cubic_(lpa …)``
#: names a lattice parameter. Comma- or space-separated, because TOPAS writes
#: both, and bounded by the separator so a nameless argument cannot be read as
#: a name.
_DECLARED_ARG = re.compile(
    rf"[(,]\s*(?:{_FLAG})?(?P<name>{_NAME})\s*[,\s]\s*(?:{_FLAG})?"
    rf"(?P<value>{_NUM})")


def symbol_table(text: str) -> dict[str, float]:
    """Every parameter the file **declares**, by name.

    Needed because a coordinate equation routinely *references another
    parameter* rather than being self-contained: ``y = ph1_O1_x;`` is how a
    tetragonal oxygen site says y is tied to x. Refusing those cost 14 of the
    606 archive files, so the reference is resolved instead — and an
    unresolvable one still returns None and still raises, because inventing a
    coordinate is the one outcome worse than refusing to read the file.

    A *declaration*, never any ``<name> <number>`` pair: see
    :data:`_DECLARING_KEYWORDS` for what that bought and what it cost.

    The values half of :func:`_symbol_reads`, kept as its own name because it is
    what every resolver takes and what the tests read.
    """
    return {name: read.value for name, read in _symbol_reads(text).items()}


def _symbol_reads(text: str) -> dict[str, _Read]:
    """:func:`symbol_table`'s single pass, keeping the whole read.

    The flag is on it because **a declared parameter carries a refine state and
    a value that copies it does not** — ``prm edge @ 5.0`` with ``a = edge;``
    refines the cell edge, and reading only the number made that file
    byte-identical to one declaring a constant. This module's own rule is that
    the flag travels *with* the value through one grammar, and re-reading the
    declaration for its flag alone would be the second grammar that rule exists
    to prevent, so the whole :class:`_Read` is kept and the callers take the
    half they need.
    """
    out: dict[str, _Read] = {}
    for m in _DECLARATION.finditer(text):
        tail = text[m.end():]
        if m["kw"] == "occ":
            # `occ La 1.` puts the *species* where the name slot is, so the old
            # sweep bound `La` to 1.0 and a `prm La` would silently have got
            # lanthanum's occupancy. Read past the species, as `_read` does.
            if not (species := re.match(r"\s*\S+", tail)):
                continue
            tail = tail[species.end():]
        read = _read_tail(tail, {})
        # `prm Fe1_1_x = 1/4 + Fe1_1_dx;: 0.25000` binds the evaluated value,
        # which is the whole reason the deeper chain never has to be walked.
        if read is not None and read.name and read.value is not None:
            out.setdefault(read.name, read)
    for m in _DECLARED_ARG.finditer(text):
        # A macro's named argument states a value and may carry a flag with it,
        # which `_DECLARED_ARG` captures as part of the same match rather than
        # by a second look at the text.
        out.setdefault(m["name"], _Read(float(m["value"]),
                                        _flag(named=m["name"]), m["name"]))
    return out


# ------------------------------------------------------------ lattice macros

@dataclass(frozen=True)
class _CellMacro:
    """What one TOPAS cell macro couples, in this reader's own idiom.

    ``slots`` holds one entry per positional argument, naming every cell key
    that argument sets; ``angles`` holds the angles the macro's crystal system
    fixes outright, which take no argument and so can never be refined. Between
    them they say the whole of what a cell macro is for — which keys move
    together, and which are not the file's to state.

    Written this way rather than as "angles plus a count" because the count is
    not enough: ``Rhombohedral`` also takes two arguments, and its second is an
    **angle**, so a table that assumed argument two was ``c`` would give a
    rhombohedral phase a 60 Å edge and three right angles with nothing raised.
    """

    slots: tuple[tuple[str, ...], ...]
    angles: dict[str, float] = field(default_factory=dict)


#: The cell macros this reader implements, each enumerated and cited
#: individually. A macro's name, its arity and which cell key each argument
#: carries are **specification facts** (`io/CLAUDE.md`'s rule 2) taken from
#: TOPAS Academic's Technical Reference; the coupling below is stated in this
#: reader's own terms and no macro body is reproduced here or anywhere else.
#: §19.3 fixes how to read the argument names the reference prints — a ``c``
#: suffix is a parameter name, ``v`` a value, ``cv`` either — so ``a_cv`` names
#: the ``a`` edge and ``al_cv`` the ``al`` angle, and the order is the
#: reference's, not a guess. How each argument then propagates is
#: crystallography rietx already owns: the reference names only the independent
#: keys, and the crystal system says which others follow.
#:
#: * ``Cubic(cv)`` — §19.3.2, and §19.1, whose prose says the single argument
#:   "defines the a, b and c lattice parameters". One edge, all three coupled,
#:   all angles 90°.
#: * ``Tetragonal(a_cv, c_cv)`` — §19.3.2. ``a`` and ``c`` stated, ``b``
#:   following ``a``, all angles 90°.
#: * ``Hexagonal(a_cv, c_cv)`` — §19.3.2. As tetragonal, with ``ga`` 120°.
#: * ``Rhombohedral(a_cv, al_cv)`` — §19.3.2. An **edge and an angle**, in that
#:   order: all three edges follow the first argument and all three angles the
#:   second. This is the one the argument-order question was about, and the
#:   reference answers it in the names themselves.
#: * ``Trigonal(a_cv, c_cv)`` — **not** in §19.3.2's list, which has only the
#:   four above. Its authority is §1.3, the reference's own worked input file,
#:   where ``Trigonal(@ 4.759, @ 12.992)`` gives the cell of a ``R-3C``
#:   corundum — a hexagonal-setting a and c, so the same shape as ``Hexagonal``.
#:   The archive corroborates it in 4 files. Kept in this table because it is
#:   evidenced twice over, and flagged here because its citation is an example
#:   rather than the list.
_CELL_MACROS: dict[str, _CellMacro] = {
    "Cubic": _CellMacro((("a", "b", "c"),),
                        {"al": 90.0, "be": 90.0, "ga": 90.0}),
    "Tetragonal": _CellMacro((("a", "b"), ("c",)),
                             {"al": 90.0, "be": 90.0, "ga": 90.0}),
    "Hexagonal": _CellMacro((("a", "b"), ("c",)),
                            {"al": 90.0, "be": 90.0, "ga": 120.0}),
    "Trigonal": _CellMacro((("a", "b"), ("c",)),
                           {"al": 90.0, "be": 90.0, "ga": 120.0}),
    "Rhombohedral": _CellMacro((("a", "b", "c"), ("al", "be", "ga"))),
}

#: The macro names a refusal message may offer, derived from
#: :data:`_CELL_MACROS` so the two cannot drift. Spelled out because the two
#: lists are **not** the same list and a message that conflated them would be
#: wrong either way round: §19.3.2 defines four (``Trigonal`` is §1.3's), while
#: this reader reads five. A refusal's job is to say what the author may write
#: *here*, so it enumerates the reader's — the citation for each stays in
#: `_CELL_MACROS`' comment and in `ATTRIBUTION.md`, which is where a claim about
#: the reference belongs.
_CELL_MACRO_LIST = (", ".join(list(_CELL_MACROS)[:-1])
                    + f" and {list(_CELL_MACROS)[-1]}")

#: Cell-shaped macro names that are **not** cell macros of this format. The
#: reference's lattice-parameter list (§19.3.2) has exactly four entries, and
#: none of these is among them: across the whole manual the three words occur
#: only as English — crystal-system labels in the indexing tables, and a
#: ``Orthorhombic_Bipyramide`` bond-length restraint, which is not a cell at
#: all. They occur in **no** archive file either, in live text or in a comment.
#:
#: So a file invoking one is invoking a macro somebody defined themselves, whose
#: body `_excise_macro_defs` has already removed and whose argument order
#: nothing establishes — and a wrong order is a wrong cell with nothing raised.
#: Refused by name, and only where the macro is the phase's *only* cell: beside
#: explicit ``a``/``b``/``c`` lines there is nothing left to get wrong. A name
#: is added to :data:`_CELL_MACROS` only with its own citation, never by
#: analogy with the ones already there.
_UNDEFINED_CELL_MACROS = ("Orthorhombic", "Monoclinic", "Triclinic")

#: What **ends** a ``str`` block. A `.inp` has no closing brace, so a phase's
#: text runs to the next block opener — and splitting on ``str`` alone made a
#: trailing ``hkl_Is``/``xo_Is`` Pawley block part of the phase above it, so
#: `_read` swept the neighbour's numbers: `archive file 4`
#: gave tungsten b = 3.814 and c = 19.299 off the Nb2O5 ``load hkl_m_d_th2 I``
#: table (a d-spacing column, read as a cell edge), and a `scale` or a
#: `weight_percent` the ``str`` block itself omits is still read off the block
#: below with nothing raised. Each opener is a **specification fact**
#: (`io/CLAUDE.md`'s rule 2) and the ones with a count are what the archive
#: states at the start of a line: ``str`` (1601), ``xdd`` (609),
#: ``xo_Is`` (277), ``hkl_Is`` (139), ``STR`` (7), ``fit_obj`` (2).
#: ``d_Is``, ``xdd_scr`` and ``xdd_sum`` occur in no file here and are listed
#: because they open a block of the same two kinds — a peak-phase and a
#: dataset — so leaving them out could only re-create the bleed. ``macro`` is
#: **not** here (WP-1118): it opens no phase and no dataset — it is a reusable
#: *definition* — so treating it as an opener truncated any ``str`` a ``macro
#: dummy { 1 }`` sat inside, dropping every site below it, and the per-phase
#: count guard was blind to it because both sides of that guard read the same
#: truncated chunk. Macro definitions are excised whole by
#: :func:`_excise_macro_defs` before the file is split, braces and body and all.
#: ``TOF_XYE`` and ``TOF_GSAS`` are the two macros here, and they open a dataset
#: (:data:`_DATASET_OPENERS` says why) — so a phase above one ends at it rather
#: than running on through the next bank's dataset-level cards.
_BLOCK_OPENERS = ("str", "hkl_Is", "xo_Is", "d_Is", "xdd_scr", "xdd_sum",
                  "xdd", "fit_obj", "STR", "TOF_XYE", "TOF_GSAS")

#: The data-file macros the reference's macro index lists as stating ``xdd``
#: and which are not in :data:`_BLOCK_OPENERS`, so that
#: ``registry._TOPAS_LINE`` does not claim a file on a bare ``XY`` or ``DAT``
#: (WP-1530). Each opens a dataset only **as a call**, hence the lookahead.
_DATASET_MACROS = ("RAW", "XDD", "XYE", "XY", "DAT", "BRML", "SST")

#: ``xdd`` must follow ``xdd_scr``/``xdd_sum`` in the alternation above, and the
#: pattern is anchored with ``[ \t]`` rather than ``\s`` because ``\s`` matches
#: the newline and would let one match span two lines.
_BLOCK = re.compile(
    rf"^[ \t]*(?P<kw>{'|'.join(_BLOCK_OPENERS)}"
    rf"|(?:{'|'.join(_DATASET_MACROS)})(?=[ \t]*\())\b", re.M)

#: The openers that start a **dataset** rather than a phase. The grammar's
#: `Txdd`/`Txdd_scr` put every phase kind — `str`, `hkl_Is`, `xo_Is`, `d_Is` —
#: *inside* one of these, so an opener from this set is where one pattern ends
#: and the next begins. ``TOF_XYE(path, calc_step)`` and ``TOF_GSAS(…)`` are
#: macros, and are here because the reference says what they open: §19.3.11
#: lists them as the time-of-flight data-file macros, and its macro index
#: lists both among the macros stating ``xdd``. Without them every bank of a
#: multi-bank time-of-flight file was the dataset above it — 44 of the 68
#: archive files carrying a `for` loop open their datasets this way. The other
#: data-file macros (:data:`_DATASET_MACROS`) open one too since WP-1530: a file
#: opening two datasets with ``RAW(a)`` and ``RAW(b)`` read as none, and
#: ``to_structure`` built both specimens' phases into one ``Structure``. A
#: phase above a single such macro is dataset 0 now, not ``None``.
_DATASET_OPENERS = ("xdd", "xdd_scr", "xdd_sum", "TOF_XYE", "TOF_GSAS",
                   *_DATASET_MACROS)

#: What says a dataset is **time of flight**. Each is the reference's: the
#: macros of §19.3.11 ("Neutron TOF" — the data-file macros, the emission
#: profile ``TOF_LAM``, the calibration ``TOF_x_axis_calibration`` that "writes
#: the pk_xo equation … converting d-spacing to x-axis space", and the three
#: profile macros), and ``pk_xo`` written in ``D_spacing`` (§5.2: "the peak
#: position for neutron time-of-flight data is typically calculated in
#: time-of-flight space, tof = t0 + t1 d + t2 d²"). ``gui_tof_*`` is not in the
#: reference and is here from the archive, which writes it beside ``pk_xo``.
#: ``neutron_data`` is not: constant-wavelength neutron data states it too.
_TOF_CONSTRUCT = re.compile(
    r"\b(?:(?P<macro>TOF_XYE|TOF_GSAS|TOF_x_axis_calibration|TOF_LAM"
    r"|TOF_Exponential|TOF_PV|TOF_CS_L|TOF_CS_G)\s*\("
    r"|(?P<gui>gui_tof_\w+)|(?P<pk>pk_xo\b[^;{}]*?\bD_spacing\b))")


def _time_of_flight(stripped: str, active: str) -> dict:
    """The datasets of ``active`` that state a time-of-flight construct, each
    with the names of the constructs (:data:`_TOF_CONSTRUCT`).

    A user macro whose body states one is a construct too, named by the macro:
    the archive's time-of-flight files write the ``pk_xo`` equation inside a
    macro of their own and invoke it once per bank, and the definition is
    excised before the text is read. A construct above every
    dataset opener is charged to **every** dataset, since this reader cannot
    say which one TOPAS gave it to and the cost of guessing low is a
    time-of-flight bank read as constant wavelength.
    """
    def names(text: str) -> list[tuple[int, str]]:
        return [(m.start(), m["macro"] or ("gui_tof_*" if m["gui"] else
                                           "pk_xo in D_spacing"))
                for m in _TOF_CONSTRUCT.finditer(text)]

    bodies = {}
    for m in _MACRO_DEF.finditer(stripped):
        name = re.match(r"macro\s*(\w*)", m.group())[1]
        if name:
            bodies[name] = _brace_body(stripped, m.end() - 1)
    tof_macros: set[str] = set()
    while True:     # a macro invoking a time-of-flight macro is one too
        grown = {n for n, b in bodies.items() if n not in tof_macros and (
            names(b) or any(re.search(rf"\b{re.escape(t)}\b", b)
                            for t in tof_macros))}
        if not grown:
            break
        tof_macros |= grown
    quoted = re.sub(r'"[^"\n]*"', lambda m: _blank(m.group()), active)
    found = names(quoted)
    for name in tof_macros:
        found += [(m.start(), name)
                  for m in re.finditer(rf"\b{re.escape(name)}\b", quoted)]
    starts = [o.start() for o in _BLOCK.finditer(active)
              if o["kw"] in _DATASET_OPENERS]
    out: dict = {}
    for at, name in found:
        before = sum(1 for s in starts if s <= at)
        for k in ([before - 1] if before else range(len(starts)) or [None]):
            out.setdefault(k, set()).add(name)
    return {k: tuple(sorted(v)) for k, v in sorted(
        out.items(), key=lambda kv: (kv[0] is not None, kv[0] or 0))}

#: TOPAS's ``STR(...)`` macro, which opens a phase. Its body is in a macro
#: library this reader does not have and may not reproduce (``ATTRIBUTION.md``'s
#: fence), so it is expanded from what the Technical Reference **says it does**
#: rather than from what it is: §19.3.12 lists ``STR(sg)`` as "signals the start
#: of structure information with a space group of sg" — a ``str`` stating
#: ``space_group sg``. The reference's own example inputs also write a second
#: argument, the phase's name (``STR(R_-3_c, "Corundum Al2 O3")``), read as
#: ``phase_name``. That is a special case and not a macro pass (WP-1433's
#: decision, :func:`expand_str_macros`): the archive's every macro-opened phase
#: is this one macro, and a general pass would need the library's bodies.
#: Before WP-1433 it was refused by name, because *saying nothing* — "a Pawley
#: or indexing-only .inp is legal and has none" — was the alternative.
_STR_MACRO = re.compile(r"^[ \t]*STR\s*\(([^)\n]*)\)", re.M)

#: A file's **own** ``STR`` macro. Its body, not the reference's description,
#: is what TOPAS expands, so the special case would read the wrong text.
_STR_DEFINED = re.compile(r"\bmacro\s+STR\s*\(")


def expand_str_macros(active: str, live: str, path) -> str:
    """Rewrite each ``STR(sg[, name])`` as the ``str`` block it opens (WP-1433).

    ``active`` is the live text; ``live`` is the same text with the macro
    definitions still in it, which is where a file's own ``macro STR`` would
    be. Live, not all the comment-stripped text: a ``macro STR`` in a branch
    the conditionals ruled out is a definition TOPAS never reads (#587). The rewrite stays on its line, so every later line number is the
    file's. Values are written **quoted**, so the ``space_group``/``phase_name``
    scans and :func:`_masked` take exactly the argument and not the rest of the
    line. Refused by name, never guessed:

    * a file defining its own ``STR`` (``_STR_DEFINED``);
    * a call with no argument or more than two, which the reference describes
      neither of;
    * a space group carrying ``#`` — ``STR(######, "#name#")`` is a template's
      slot that a script fills before TOPAS runs, not a symbol (2 archive
      files), and reading it as one would hand ``to_structure`` a group no
      table has.
    """
    calls = list(_STR_MACRO.finditer(active))
    if not calls:
        return active
    if m := _STR_DEFINED.search(live):
        line = live.count("\n", 0, m.start()) + 1
        raise TopasInpError(
            f"{path}:{line}: this file defines its own `STR` macro, and that "
            f"body — not the reference's description of TOPAS's own — is what "
            f"its {len(calls)} `STR(...)` call(s) expand to. This reader does "
            f"not expand macro bodies, so the phases are not read.")
    out: list[str] = []
    position = 0
    for m in calls:
        # Split on the commas outside quotes: a name may hold one.
        args = [a.strip() for a in
                re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', m.group(1))]
        line = active.count("\n", 0, m.start()) + 1
        if not 1 <= len(args) <= 2 or not args[0]:
            raise TopasInpError(
                f"{path}:{line}: `STR({m.group(1).strip()})` — the reference "
                f"describes `STR(sg)` and its examples `STR(sg, name)`; "
                f"{len(args)} arguments is neither, so what it opens is unknown.")
        sg, name = args[0].strip('"').strip(), (
            args[1].strip('"').strip() if len(args) == 2 else "")
        if "#" in sg:
            raise TopasInpError(
                f"{path}:{line}: `STR({m.group(1).strip()})` — {sg!r} is a "
                f"template's placeholder, filled by whatever writes this file "
                f"before TOPAS reads it, not a space group. Read the filled-in "
                f"copy.")
        indent = m.group()[:len(m.group()) - len(m.group().lstrip())]
        out.append(active[position:m.start()])
        out.append(f'{indent}str space_group "{sg}"'
                   + (f' phase_name "{name}"' if name else ""))
        position = m.end()
    out.append(active[position:])
    return "".join(out)

#: What declares a capillary (Debye-Scherrer) geometry, as the archive spells
#: it: the two ``Cylindrical_…`` correction macros and TOPAS's ``capillary_…``
#: keywords (``capillary_diameter_mm``, ``capillary_parallel_beam``,
#: ``capillary_divergent_beam``, ``capillary_u_cm_inv``), which is how the 26
#: capillary files here say it. Anchored to the start of a line because a
#: geometry is a **statement**: the predecessor matched
#: ``Cylindrical_|capillary|Debye`` case-insensitively over the whole file, so a
#: phase called ``Debye_test_material`` flipped a file carrying ``Radius(217.5)``
#: and ``LP_Factor(26.4)`` — unambiguously Bragg-Brentano — and so did a data
#: file named ``debye_run3.xy`` and a ``prm capillary_diam``. ``Debye`` itself is
#: gone: it names no TOPAS keyword and occurs in none of the 606 files.
_CAPILLARY = re.compile(r"^[ \t]*(?:capillary_\w+|Cylindrical_\w*\s*\()", re.M)


#: One emission-profile line, exactly as the file states it. The technical
#: reference's ``Tcomm_2`` grammar is ``[la E lo E [lh E] | [lg E] [lo_ref]]...``
#: — an **array**, one entry per line of the profile — and it names what each
#: slot means: ``la`` is the *area* under the line, ``lo`` its wavelength in Å,
#: ``lh``/``lg`` the Lorentzian/Gaussian half-widths in mÅ.
@dataclass(frozen=True)
class TopasEmissionLine:
    area: float | None
    wavelength: float | None
    lo_ref: bool = False


def _emission_lines(active: str, masked: str,
                    symbols: dict[str, float]) -> list:
    """Every ``la … lo …`` line of the emission profile, in file order.

    Located on THE masked text — so an ``la`` inside a quoted path or a macro's
    arguments is not one — and read off ``active`` at the same offsets, which is
    the invariant :func:`_masked` exists to provide.

    Each line's text runs to the next ``la`` token, so one line's ``lo`` can
    never be read off the next's; both values go through :func:`_read_tail`, the
    one grammar, rather than through a bare-number regex. The predecessor's
    ``\\bla\\s+NUM\\s+lo\\s+(NUM)`` demanded a literal number for ``la`` and so
    matched no profile whose lines are named or flagged — **16 of the 606
    archive files** state an emission profile and came back with no wavelength
    at all.
    """
    starts = [m.start() for m in re.finditer(r"\bla\b", masked)]
    lines = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(active)
        segment, mseg = active[start:end], masked[start:end]
        area = _read_tail(segment[len("la"):], symbols)
        wavelength = None
        if lo := re.search(r"\blo\b", mseg):
            wavelength = _read_tail(segment[lo.end():], symbols)
        lines.append(TopasEmissionLine(
            area=area.value if area else None,
            wavelength=wavelength.value if wavelength else None,
            lo_ref=bool(re.search(r"\blo_ref\b", mseg))))
    return lines


def _reference_wavelength(lines: list) -> float | None:
    """The profile's *reference* wavelength — the one TOPAS's ``Lam`` takes.

    The reference is explicit about which line that is: ``Lam`` "is taken from
    the emission profile line with the **largest ``la`` value**", and ``lo_ref``
    "marks a specific line's ``lo`` as the one to use as the reference
    wavelength instead". Neither rule is "the first one written".

    Taking ``lo[0]`` was right in the archive by accident — a CuKα doublet is
    conventionally written ``la 0.6605`` then ``la 0.3395``, so the larger area
    happens to come first — and **51 of the 606 files** state more than one
    line, none of which is obliged to be ordered that way. An accident that
    survives a test suite is the class this reader keeps finding.

    A line whose own ``lo`` could not be read contributes nothing rather than a
    guess; a profile no line of which states a wavelength is ``None``, which is
    what "the file states no explicit ``la``/``lo``" already meant.
    """
    stated = [ln for ln in lines if ln.wavelength is not None]
    if not stated:
        return None
    if marked := [ln for ln in stated if ln.lo_ref]:
        return marked[0].wavelength
    return max(stated, key=lambda ln: (ln.area if ln.area is not None
                                       else -math.inf)).wavelength


def _cell_macro(chunk: str, symbols: dict[str, float]) -> tuple[dict, dict] | None:
    """The cell and refine flags a cell macro states, or None if it states no
    complete one.

    The first macro in :data:`_CELL_MACROS` that reads completely wins, which is
    deterministic and only ever matters in a chunk holding two. A macro whose
    argument count does not match its entry does **not** read: the arity is part
    of what the reference states, and taking "the first and last argument that
    happened to parse" is how a two-argument reading of a one-argument macro
    would put an unrelated number in ``c``.

    Every key the macro couples takes the flag of the argument it came from, so
    a refined ``Cubic(@ 4.15)`` refines all three edges rather than only ``a``.
    An angle the macro's symmetry fixes takes no flag at all, because the file
    states no parameter for it — the one exception being ``Rhombohedral``, where
    the angle *is* an argument and so carries its own.
    """
    for name, macro in _CELL_MACROS.items():
        if not (m := re.search(rf"\b{name}_?\(([^)\n]*)\)", chunk)):
            continue
        args = m.group(1).split(",")
        if len(args) != len(macro.slots):
            continue
        reads = [_read_tail(arg, symbols) for arg in args]
        if any(r is None or r.value is None for r in reads):
            continue
        cell: dict[str, float] = dict(macro.angles)
        vary: dict[str, bool] = {}
        for keys, read in zip(macro.slots, reads):
            for key in keys:
                cell[key] = read.value
                if read.vary is not None:
                    vary[key] = read.vary
        # Emitted in `_CELL_KEYS` order, so a macro-stated cell iterates the
        # same way a line-stated one does whatever order the table filled it in.
        return {k: cell[k] for k in _CELL_KEYS if k in cell}, vary
    return None


# --------------------------------------------------- whitespace-insensitive scan

#: A ``macro name [(...)] { ... }`` definition head. The body is brace-balanced
#: and excised by :func:`_excise_macro_defs`, so this only has to find the open.
_MACRO_DEF = re.compile(r"\bmacro\b\s*\w*\s*(?:\([^)]*\))?\s*\{")


def _blank(text: str) -> str:
    """Replace every non-newline character with a space, so a span can be
    removed from a token scan without moving any line or shifting any offset."""
    return re.sub(r"[^\n]", " ", text)


def _excise_macro_defs(text: str) -> str:
    """Blank ``macro name [(...)] { ...balanced... }`` definitions (WP-1118).

    A macro definition is neither a phase nor a dataset, so it must not open or
    end a block — and its body's ``site`` and cell tokens must not be swept into
    whatever phase held it. Removed here, before the file is split, with a
    brace counter rather than a regex because a macro body may itself nest
    braces. An unterminated definition (a truncated file) blanks to EOF, which
    is a loud absence rather than a bad parse.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        m = _MACRO_DEF.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        depth, j = 0, m.end() - 1          # j points at the opening '{'
        while j < n:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        out.append(_blank(text[m.start():j]))
        i = j
    return "".join(out)


#: A cell key at the **start of its own line** — where the real cell edges
#: resume below a site block. It ends a ``site`` segment (see :func:`_blank_sites`):
#: a continuation like ``beq b 0.5`` starts with ``beq`` and is site text, while
#: ``b 6.0`` starts with the edge itself and is the cell. The two-letter keys
#: precede the one-letter ones so ``\b`` never truncates ``al``/``be``/``ga``.
_CELL_LINE_START = re.compile(r"(?m)^[ \t]*(?:al|be|ga|a|b|c)\b")


def _masked(text: str, *, keep_get: bool = False) -> str:
    """**The** masked text every token scan reads (WP-1118).

    The scan is token-oriented — a key wherever it sits, because TOPAS is
    whitespace-insensitive and ``a 5.4 b 6.1 c 7.2`` is a whole cell on one
    line. With the line anchor gone, the *only* safety is that every span a key
    (or a ``site`` token) must not be read from is blanked first, once, into a
    text every scan shares — the cell-key scan, the site split, and the
    file-level site count — so a span nobody blanked cannot be read by one scan
    while another is safe. The unmasked text stays for the messages, which quote
    the original line. Blanked here, offset-for-offset (:func:`_blank`):

    * a ``"…"`` string, so the ``a`` in ``space_group "P21/a"``, or the word in
      ``xdd "C:\\data\\site\\run1.xy"``, or a phase name, is not a token;
    * a macro's parenthesised arguments, so a named ``a`` in ``Cubic_(a, …)`` is
      the macro's argument and ``site`` in ``Out_X_Ycalc("site.xy")`` is not a
      site (the reason the cell scan's line anchor once existed);
    * a ``prm``/``local`` declaration to end of line, so ``prm a 0.9`` declares a
      symbol and is not an ``a`` line;
    * the ``space_group`` and ``phase_name`` **values**, over the same span the
      reader's own value-regexes consume, so an unquoted Hermann-Mauguin symbol
      ``P 1 21/c 1`` does not read ``/c 1`` as ``c = 1.0`` — legal, and the
      reader's own regex accepts it, so the mask has to know the spelling too.

    A ``site`` **segment** is not blanked here — the site split and the count
    need the ``site`` tokens to survive. :func:`_blank_sites` blanks the segments
    on top of this, for the cell scan alone.

    ``keep_get`` yields the **second** view, and the cell scan is the only caller
    that wants it: a lone name inside a ``Get(...)`` survives the argument
    blanking. The two views answer two different questions about the same line,
    which is why one text could not serve both. ``b = Get(a);`` *states* ``b``
    and merely *references* ``a``, so locating a key must not see the ``a``
    (or `ga = Get(al);` would report a phase as stating an ``al`` it never wrote)
    while resolving ``b``'s value must. Both are :func:`_blank`-built and so stay
    offset-for-offset with each other and with the text they came from.
    """
    masked = re.sub(r'"[^"\n]*"', lambda m: _blank(m.group()), text)
    # `\b` anchors the name's start so a kept `Get(a)` cannot be re-entered one
    # character in and blanked as `et(a)`.
    masked = re.sub(r"\b\w+\([^)]*\)",
                    lambda m: (m.group() if keep_get and _GET.fullmatch(m.group())
                               else _blank(m.group())), masked)
    masked = re.sub(r"\b(?:prm|local)\b[^\n]*", lambda m: _blank(m.group()),
                    masked)
    # `[ \t]+`, not `\s+`: the reader's own value-regex (`\s+`) never crosses a
    # newline on the original text, because a quote or the symbol's first letter
    # follows the space — but here the value has already been quote-blanked to
    # spaces, so `\s+` would run through the newline and blank the next line's
    # `a 5.0`. Confined to one line, this blanks exactly the span the reader reads.
    for kw in ("space_group", "phase_name"):
        masked = re.sub(rf'(\b{kw}[ \t]+"?)([^"\n]+)',
                        lambda m: m.group(1) + _blank(m.group(2)), masked)
    return masked


def _blank_sites(masked: str) -> str:
    """``masked`` with each ``site`` **segment** blanked, for the cell-key scan.

    A ``site`` declaration does not end at the newline: its fields may continue
    on the next line (``beq b 0.5`` on its own), and the ``b`` there naming the
    ``beq`` parameter is not the cell edge ``b`` (WP-1118). So the segment runs
    from a ``site`` token to the next ``site``, the chunk end, **or** the next
    line that begins with a cell edge — whichever comes first. The last of those
    is the one refinement to the reviewer's "to the next site or block end":
    where the site block sits *above* the cell lines, "block end" would blank the
    real ``a``/``b``/``c`` below it and default the cell, so the segment stops
    where the edges resume at a line start instead.
    """
    site_pos = [m.start() for m in re.finditer(r"\bsite\b", masked)]
    if not site_pos:
        return masked
    cell_pos = [m.start() for m in _CELL_LINE_START.finditer(masked)]
    chars = list(masked)
    for i, start in enumerate(site_pos):
        nxt_site = site_pos[i + 1] if i + 1 < len(site_pos) else len(masked)
        nxt_cell = next((p for p in cell_pos if p > start), len(masked))
        for j in range(start, min(nxt_site, nxt_cell)):
            if chars[j] != "\n":
                chars[j] = " "
    return "".join(chars)


def _cell_search_text(chunk: str, *, keep_get: bool = False) -> str:
    """The cell-scan view of a chunk: :func:`_masked` with the ``site`` segments
    blanked on top (:func:`_blank_sites`). Kept as a named successor so a test
    can pin what survives a chunk without a whole file per hole.

    ``keep_get`` selects :func:`_masked`'s second view — the one that keeps a
    ``Get(name)`` whole — which the cell loop reads *values* from after locating
    the key on the view that does not."""
    return _blank_sites(_masked(chunk, keep_get=keep_get))


_CELL_KEYS = ("a", "b", "c", "al", "be", "ga")

#: TOPAS's cell keys spelled the way `crystallography.symmetry` keys its ties.
#: The two vocabularies meet here and nowhere else, so a comparison against the
#: constraint table cannot quietly compare ``ga`` with ``gamma`` and conclude
#: nothing is tied.
_CELL_KEY_LONG = {"a": "a", "b": "b", "c": "c",
                  "al": "alpha", "be": "beta", "ga": "gamma"}


def _symmetry_reproduces(space_group: str, target: str, source: str) -> bool:
    """Would this phase's own symmetry tie ``target`` to ``source`` anyway?

    ``Get`` resolution copies a **value**; the constraint that produced it does
    not reach the model, so ``b = Get(a);`` builds a ``b`` that is merely
    *numerically equal* to ``a``. Whether that loses anything turns entirely on
    the space group, which is why this asks it rather than reporting every
    coupling: under ``P 4/m m m`` rietx ties ``b ← a`` itself, so the built
    model states exactly what the file did and there is nothing to report;
    under ``P 1`` it does not, and ``a`` refines away from a frozen ``b`` —
    a third thing neither the file nor rietx meant.

    Ties are followed to their **root**, because a tie table names one
    representative and not every pair: cubic ties both ``b`` and ``c`` to ``a``,
    so ``c = Get(b);`` is reproduced even though no entry says ``c → b``. An
    angle pair is also reproduced where symmetry fixes *both* to the same
    constant — they then move together by not moving at all, which is what the
    file said.

    A symbol this package cannot resolve returns False, i.e. **report**. Not
    being able to show that the model carries the coupling is not the same as
    showing that it does, and the quiet answer is the one this reader owes an
    argument for.
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

    lo_t, lo_s = _CELL_KEY_LONG[target], _CELL_KEY_LONG[source]
    if lo_t in cons.ties and root(lo_t) == root(lo_s):
        return True
    fixed = cons.fixed_angles
    return lo_t in fixed and lo_s in fixed and fixed[lo_t] == fixed[lo_s]


def _cell_reads(cell_scan: str, symbols: dict[str, float]) -> dict[str, float]:
    """Best-effort ``{key: value}`` for the cell keys an *already cell-masked*
    text states, raising nothing — for recording what a :class:`SkippedBlock`
    carried."""
    out: dict[str, float] = {}
    for key in _CELL_KEYS:
        for line in cell_scan.split("\n"):
            if re.search(rf"\b{key}\b", line):
                read = _read(key, line, symbols)
                if read is not None and read.value is not None:
                    out[key] = read.value
                    break
    return out


def read_topas_inp(path: str | Path, *,
                   diagnostics: list[Diagnostic] | None = None) -> TopasModel:
    """Parse a ``.inp``. Raises :class:`TopasInpError` naming the file and line.

    Pass ``diagnostics=`` a list to record the repairs this reader makes on a
    successful parse — the ones the model carries but a caller reading it back
    cannot tell from a stated value (the same channel
    :func:`~rietx.crystallography.cif.structure_from_cif` and
    :func:`~rietx.io.readers.read_pattern` take). Each distinct rewritten species
    (``occ La+3`` read as ``La3+``, IUCr digit-first order) appends one
    ``TOPAS_SPECIES_NORMALISED`` naming the substitution and every atom path it
    touched; each translated space-group origin suffix (``Pn-3mZ`` → ``Pn-3m:2``,
    which *selects* the origin — dropping it silently takes the other) appends
    one ``TOPAS_ORIGIN_TRANSLATED``. Each ``str`` block that stated no
    ``phase_name``/``space_group`` — recorded on ``model.skipped_blocks`` whether
    or not a list is passed, so the read never drops it in silence — also reports
    one ``TOPAS_BLOCK_SKIPPED`` naming what it lacked and what it carried. A cell
    key read through ``Get`` on another key (``b = Get(a);``) appends one
    ``TOPAS_CELL_COUPLING_DROPPED`` — but **only** where the phase's space group
    does not tie the pair itself, because where it does the built model states
    what the file stated and there is nothing to report
    (:func:`_symmetry_reproduces`). All of this happens whether or not a list is
    passed — the model is the same — so ``diagnostics`` makes it *visible*, it
    does not change what is built.

    The channel is the **report** arm of "report or refuse, never drop", not a
    way to turn a refusal into a silent drop. A stated-but-unreadable key still
    **refuses** here, and :func:`to_structure` still refuses to build a
    ``Structure`` that omits a cell-bearing skipped block while other phases build
    (the weight fractions would no longer sum) — that refusal must hold whether
    or not a caller passed a list, so it is not routed through the channel.
    """
    path = Path(path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise TopasInpError(f"{path}: cannot read: {exc}") from exc
    # `base.decode` is the seam `head()` already goes through, shared rather
    # than duplicated: a `read_text(encoding="utf-8")` on a UTF-16 export gave
    # zero phases and `to_structure` then reported "a Pawley or indexing-only
    # .inp is legal and has none" — a confident wrong diagnosis of a decode
    # failure, which is the class this reader exists to remove.
    raw, codec, _bom = decode(raw_bytes)
    # What a mark cannot name is refused, per `io/CLAUDE.md`'s `xy` row:
    # ASCII-range UTF-16 is *valid* UTF-8 with interleaved NULs, so a surviving
    # NUL means no byte-order mark said which of LE and BE this is. Guessing is
    # a repair this reader could not say it made.
    if "\x00" in raw:
        raise TopasInpError(
            f"{path}: not text this reader can decode — NUL bytes survive a "
            f"{codec} decode, which is what an ASCII-range UTF-16 export with "
            f"no byte-order mark looks like. Re-save it as UTF-8.")
    # Macro definitions are excised before anything reads the text: they open no
    # block (so they may not end a `str`), and their bodies' `site`/cell tokens
    # are not any phase's — see `_excise_macro_defs`.
    # The pre-processor runs before any of the grammar is true, so what it does
    # to the text is checked before the text is read. Macro definitions come out
    # first (their bodies legitimately hold `#m_*` directives and conditionals
    # of their own), then what is left has to be text this reader can resolve.
    stripped = strip_comments(raw)
    refuse_unevaluable_directives(_excise_macro_defs(stripped), path)
    conditionals = _resolve_conditionals(stripped, path)
    active = expand_str_macros(_excise_macro_defs(conditionals.text),
                               conditionals.text, path)
    # Where a card attaches is decided before any card is read: the block split
    # below *is* the assumption that a card belongs to the block it sits in.
    active = expand_for_loops(active, path)
    refuse_moved_attachment(active, path)
    # THE masked text, built once and sliced by every token scan below (the
    # cell-key scan, the site split, the file-level site count) — offset-for-
    # offset with `active`, so a slice of one indexes the other. The mask is the
    # invariant that keeps a token-oriented scan honest; see `_masked`.
    masked = _masked(active)
    # The cell scan's second view of the same offsets, keeping `Get(name)`
    # whole so a coupled edge's value can be resolved after the key has been
    # located on the mask that hides it (see `_masked`).
    gmasked = _masked(active, keep_get=True)
    model = TopasModel(path=str(path))
    # The declarations, whole: the values every resolver takes, and the refine
    # flag a value resolved *through* one of them has to inherit (`_symbol_reads`).
    symbol_reads = _symbol_reads(active)
    symbols = {name: read.value for name, read in symbol_reads.items()}

    # A `str` block ends at the next block opener of any kind, not at the next
    # `str`: see `_BLOCK_OPENERS` for the numbers, and `test_projects_topas.py`
    # for the neighbour's cell, scale and weight_percent this stops arriving on
    # the phase above. Read before the figures of merit, because *where* an
    # opener sits is what decides which of them is the file's own.
    openers = list(_BLOCK.finditer(active))
    model.n_datasets = sum(1 for o in openers if o["kw"] in _DATASET_OPENERS)

    # `Tr_wp` hangs off **both** `Ttop` and `Txdd`, and `xdd` is an array, so a
    # multi-dataset file states one r_wp per dataset *and* the run's own. The
    # first match is therefore not "the" r_wp: `archive file 5` states
    # 4.408 above its `xdd` and 14.188 inside it, and 81 of the 606 archive
    # files state more than one. What the grammar does settle is *which* one is
    # the file's: the one at top level, above every block opener. Where there is
    # no such statement, or more than one, the number is withheld rather than
    # picked — the converged r_wp is the reason this format is worth reading and
    # a confident wrong one is worse than none. Every value is carried either
    # way, in file order.
    top = openers[0].start() if openers else len(active)
    for key, scalar, every in (("r_wp", "r_wp", "r_wp_all"),
                               ("gof", "gof", "gof_all")):
        found = [(m.start(), float(m.group(1)))
                 for m in re.finditer(rf"\b{key}\s+({_NUM})", active)]
        setattr(model, every, [value for _, value in found])
        at_top = [value for start, value in found if start < top]
        if len(at_top) == 1:
            setattr(model, scalar, at_top[0])
        elif not at_top and len(found) == 1:
            setattr(model, scalar, found[0][1])
    if m := re.search(r"\b((?:Cu|Co|Cr|Fe|Mo|Ag)Ka\d?)\s*\(", active):
        model.emission_macro = m.group(1)
        model.anode = re.sub(r"\d$", "", m.group(1))
    model.emission_lines = _emission_lines(active, masked, symbols)
    model.wavelength = _reference_wavelength(model.emission_lines)
    if m := re.search(rf"Radius\(\s*({_NUM})", active):
        model.goniometer_radius_mm = float(m.group(1))
    model.geometry = ("debye_scherrer" if _CAPILLARY.search(active)
                      else "bragg_brentano")
    # A time-of-flight dataset has no diffractometer geometry of either kind,
    # so a file whose every dataset is one states none — `bragg_brentano` was
    # this reader's default, and on such a file it was a fact nobody wrote.
    model.time_of_flight = _time_of_flight(stripped, active)
    if model.time_of_flight and set(model.time_of_flight) >= (
            set(range(model.n_datasets)) or {None}):
        model.geometry = None
    if m := re.search(rf"bkg((?:{_BKG_SLOT})+)", active):
        refined, flags = False, []
        for slot in re.finditer(_BKG_SLOT, m.group(1)):
            refined = (slot["flag"] == "@") if slot["flag"] else refined
            flags.append(refined)
        model.background_terms = len(flags)
        model.background_refined = any(flags)
    model.data_files = [d.strip() for d in re.findall(r'xdd\s+"?([^"\n]+)', active)]

    parsed_site_tokens = 0        # site *tokens* read into phases, not atoms
    #: Which dataset the `str` blocks below currently sit in. `None` until an
    #: `xdd`-family opener is seen: the grammar makes `str` a child of `xdd`, and
    #: a dataset a macro supplies (`RAW(...)`, `TOF_XYE(...)`) is an opener too
    #: (:data:`_DATASET_OPENERS`, WP-1530). A phase above every opener stays
    #: `None`: inventing dataset 0 for a file that states none would be a fact
    #: the reader made up.
    dataset: int | None = None
    # Repairs to surface on `diagnostics` (finding 4): a distinct rewritten
    # species keyed to its raw form, carrying every atom path it touched (the
    # `structure_from_cif` shape), and each translated origin suffix keyed to
    # the phase. Collected here and emitted once at the end, so N atoms sharing
    # a rewrite are one diagnostic, not N.
    species_rewrites: dict[str, tuple[str, list[str]]] = {}
    origin_translations: list[tuple[str, str, str]] = []
    #: ``(phase, space group, key, the key it is coupled to, how the file wrote
    #: it)`` — see :func:`_symmetry_reproduces` for why the space group travels
    #: with it. The last field is there because the format has **two** ways of
    #: coupling two edges, `Get(a)` and a parameter both edges name, and a
    #: message that names the wrong one sends a reader looking for a line that
    #: is not in the file.
    cell_couplings: list[tuple[str, str, str, str, str]] = []
    #: ``keyword -> the phases that stated it``, for every phase-scope construct
    #: with a stance that produces an outcome (:data:`_COVERED`). Collected per
    #: phase rather than per file so a report can say *which* phase carries the
    #: rigid body — on a four-phase QPA file, "the file states a rigid body" is
    #: a sentence a caller cannot act on.
    covered: dict[str, set[str]] = {}
    #: ``(start, end, phase name)`` of each `str` chunk that became a phase, so
    #: a macro invocation found by the file-wide scan below says which phase
    #: stated it.
    phase_spans: list[tuple[int, int, str]] = []
    for index, opener in enumerate(openers):
        if opener["kw"] in _DATASET_OPENERS:
            dataset = 0 if dataset is None else dataset + 1
        if opener["kw"] != "str":
            continue
        end = (openers[index + 1].start() if index + 1 < len(openers)
               else len(active))
        chunk = active[opener.end():end]
        mchunk = masked[opener.end():end]      # the same span of THE masked text
        gchunk = gmasked[opener.end():end]     # and of its `keep_get` view
        name = re.search(r'phase_name\s+"?([^"\n]+)', chunk)
        sg = re.search(r'\bspace_group\s+"?([^"\n]+)', chunk)
        # A *magnetic* space group used to raise here, because rietx had no
        # magnetic model at all and a nuclear-only import would have looked
        # complete. WP-1327 gave it one, so the construct is now **read** and
        # the refusal moved to where the impossible thing is actually asked
        # for: the value is carried as written (:mod:`.coverage`'s `magnetic
        # space group` row), the site moments are read below, and
        # :func:`to_structure` takes a BNS/OG number as the group and refuses
        # a phase whose moments have no operator list to be propagated over —
        # a Shubnikov symbol, which no dependency here parses, with no
        # caller-supplied group. `\b` is what keeps the unanchored
        # `space_group` search above off this keyword — `mag_space_group`
        # offers no word boundary before `space` — and
        # `test_mag_space_group_is_not_read_as_the_nuclear_one` pins it, since
        # arriving as the *symbol* "62.448" is how this went wrong once.
        # A quoted value is the symbol inside the quotes; an unquoted one is one
        # token (`mag_space_group 62.448`), so a keyword later on the same line
        # is not read into it — the BNS number is matched on this value.
        if mag := re.search(r'\bmag_space_group\s+(?:"([^"\n]*)"|(\S+))', chunk):
            mag_space_group = (mag.group(1) if mag.group(1) is not None
                               else mag.group(2)).strip()
        else:
            mag_space_group = None
        # A `str` stating `mag_space_group` and **no** `space_group` is a phase:
        # it is how TOPAS's own magnetic examples and the Durham LaMnO3
        # tutorial write one, TOPAS generating the atoms with the magnetic
        # group's operators. Its nuclear group is `to_structure`'s to derive
        # (from the file's BNS/OG number, `_nuclear_groups`), so it is stored
        # here as "" — what the file states — and never as the number.
        if not (name and (sg or mag_space_group)):
            # Recorded rather than passed over in silence: `archive file 6`
            # has a `str` block stating a cell and two sites and no
            # `phase_name`, and it used to arrive named "CaO" with scale 1.0 —
            # both read off the `hkl_Is` block below it. Naming it is the
            # neighbour's number again; saying nothing about it is the
            # confident wrong diagnosis. It records what it lacked *and* what it
            # carried (cell/scale/weight_percent), because that is what lets
            # `to_structure` tell a phase in all but its name from an empty
            # block — and `to_structure` refuses where such a block is dropped.
            n_sites = len(re.findall(r"\bsite\b", mchunk))
            lacks = " or ".join(w for w, got in
                                (("phase_name", name),
                                 ("space_group", sg or mag_space_group))
                                if not got)
            scale_read = _read("scale", chunk, symbols)
            model.skipped_blocks.append(SkippedBlock(
                lacked=lacks, n_sites=n_sites,
                cell=_cell_reads(_blank_sites(mchunk), symbols),
                scale=scale_read.value if scale_read else None,
                weight_percent=_field("weight_percent", chunk, symbols)))
            continue
        raw_sg = sg.group(1).strip() if sg else ""
        norm_sg = normalize_space_group(sg.group(1)) if sg else ""
        phase = TopasPhase(name=name.group(1).strip(), space_group=norm_sg,
                           dataset=dataset, mag_space_group=mag_space_group)
        if norm_sg != raw_sg:
            origin_translations.append((phase.name, raw_sg, norm_sg))
        # What this phase states that the import does not carry. Scanned on THE
        # masked chunk for the same reason every other token scan is: a `rotate`
        # inside `Out_X_Ycalc("rotate.xy")` is a path, and `prm hat 0.1` names a
        # parameter rather than invoking a convolution. The stances are
        # `coverage`'s; the scan is this module's, because the mask is.
        for m in _COVERED.finditer(mchunk):
            covered.setdefault(m.group(), set()).add(phase.name)
        phase_spans.append((opener.end(), end, phase.name))
        # The cell keys are read token-wise (WP-1118): the grammar is unified per
        # keyword but the scan was still per line, and TOPAS is whitespace-
        # insensitive, so `a 5.4 b 6.1 c 7.2` on one line read only `a` and built
        # a=b=c — an orthorhombic phase arrived cubic with nothing raised, and
        # `al 90 be 90 ga 120` read only `al` so a P6/mmm built with gamma 90.
        # The line anchor existed to keep `lpa` inside `Cubic_(lpa …)` off the
        # `a` scan; that job is THE mask's now — `_blank_sites(mchunk)` is the
        # shared masked span with the `site` segments blanked on top, so the key
        # is read wherever it sits in what is left and no `beq b`/`space_group`
        # letter is read as a cell edge.
        # A key is *located* on the mask and its value *read* off the
        # `keep_get` view of the same span — two questions, two texts, one set
        # of offsets. `b = Get(a);` states `b` and only references `a`, so the
        # locator must not see that `a` (else the phase is reported as stating
        # an edge it never wrote, and `ga = Get(al);` refuses on a missing `al`)
        # while the value read must.
        masked_lines = list(zip(chunk.split("\n"),
                                _blank_sites(mchunk).split("\n"),
                                _blank_sites(gchunk).split("\n")))
        #: ``declared parameter -> the first cell key that resolved through it``,
        #: for this phase. A second key reaching the same parameter is the
        #: format's other coupled-edge idiom, and the pair is what gets reported
        #: — the parameter itself is not a cell key and has nowhere on the phase
        #: to live, which is exactly why the coupling used to vanish.
        from_symbol: dict[str, str] = {}
        for key in _CELL_KEYS:
            stated = [(orig, gmask) for orig, mask, gmask in masked_lines
                      if re.search(rf"\b{key}\b", mask)]
            read = None
            for _orig, gmask in stated:
                # `phase.cell` is this key's *local* scope: the keys already
                # read for this phase, which is what a `Get(a)` on a coupled
                # edge names. `_CELL_KEYS` is in a/b/c/al/be/ga order, so the
                # edge a coupling refers back to has been read by the time the
                # coupled one is; a forward reference resolves to nothing and
                # refuses, which is the honest answer to `b = Get(c);` above `c`.
                if (read := _read(key, gmask, symbols,
                                  getters=phase.cell)) is not None \
                        and read.value is not None:
                    break
                read = None
            if read is None:
                # A **stated** key that could not be read refuses, naming the
                # key and the line. Defaulting it is `to_structure` putting
                # `c["a"]` in for a length or 90° in for an angle, so whether
                # the cell is right turns on whether the author happened to
                # *name* the edge — which no caller can see. `c = a*1.633;`
                # unnamed came back 3.0 for a stated 4.899 (63 % low), and an
                # unresolvable `be = …;` made a monoclinic phase orthorhombic.
                # An *absent* line is a different fact and keeps its default.
                if stated:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read {key} from cell "
                        f"line: {stated[0][0].strip()!r} — the phase states {key} "
                        f"and this reader could not resolve its value, so "
                        f"building it would substitute "
                        f"{'90 deg' if key in ('al', 'be', 'ga') else 'a'} for "
                        f"a number the file states. A phase that states no "
                        f"{key} at all is a different fact and keeps its "
                        f"default.")
                continue
            phase.cell[key] = read.value
            if read.vary is not None:
                phase.vary[key] = read.vary
            elif any(symbol_reads[r].vary for r in read.refs
                     if r in symbol_reads):
                # **A cell edge resolved through a declared parameter inherits
                # that parameter's refine flag.** `prm edge @ 5.0` with
                # `a = edge;` is a refined cell edge, and reading the number
                # alone made it byte-identical to a file declaring a constant —
                # a Structure saying "this cell was not refined" about a fit
                # that refined it. The equation is a *constraint* (§2.4), so the
                # edge is a dependent parameter and has no flag of its own to
                # read; the flag it depends on is the one it is dependent on.
                # Any source, because a dependent value moves when any of them
                # does. Where the phase's symmetry ties the key this is absorbed
                # (a tied entry is not a column of theta), so the inheritance
                # costs nothing where the tie already carries it and restores a
                # refined edge where it does not.
                phase.vary[key] = True
            # A key resolved through another cell key (`b = Get(a);`) or through
            # a parameter a second key also names (`a = edge; b = edge;`) was
            # **coupled** to it, and resolution copies only the number. Both
            # idioms are recorded from this key's own equation — not from the
            # line, which may state several — and reported past the guards
            # below, where the space group can say whether the model reproduces
            # the tie or has dropped it.
            for g in _GET.finditer(read.expr or ""):
                if g["name"] in _CELL_KEYS and g["name"] != key:
                    cell_couplings.append(
                        (phase.name, phase.space_group, key, g["name"],
                         f"`Get({g['name']})`"))
            for ref in read.refs:
                if (twin := from_symbol.get(ref)) is not None and twin != key:
                    cell_couplings.append(
                        (phase.name, phase.space_group, key, twin,
                         f"the parameter `{ref}` that {twin} also names"))
                from_symbol.setdefault(ref, key)
            # TOPAS bounds a cell explicitly (`min 3.61 max 3.66;`). Those
            # are part of the author's model: without them a phase the data
            # cannot see is a flat direction and its cell runs away.
            lo = re.search(rf"\bmin\s*=?\s*({_NUM})", read.rest)
            hi = re.search(rf"\bmax\s*=?\s*({_NUM})", read.rest)
            if lo or hi:
                phase.cell_limits[key] = (float(lo.group(1)) if lo else None,
                                          float(hi.group(1)) if hi else None)
        if "a" not in phase.cell:
            if macro := _cell_macro(chunk, symbols):
                phase.cell.update(macro[0])
                phase.vary.update(macro[1])
            elif bad := [n for n in _UNDEFINED_CELL_MACROS
                         if re.search(rf"\b{n}_?\(", chunk)]:
                raise TopasInpError(
                    f"{path}: {phase.name}: {bad[0]}(...) states this phase's "
                    f"only cell, and it is not one of this format's cell macros "
                    f"— {_CELL_MACRO_LIST} are the ones this reader reads, and "
                    f"nothing establishes which cell key each argument of "
                    f"{'an' if bad[0][0] in 'AEIOU' else 'a'} "
                    f"{bad[0]} carries. Reading it would be a guess at a cell; "
                    f"write the a/b/c/al/be/ga lines out instead.")
            # A **stated** cell macro this reader could not read refuses too,
            # the same way a stated-but-unreadable `a` line does 40 lines up.
            # `continue`-ing past it instead left `phase.cell` empty, and an
            # empty cell is the *absent* fact: `to_structure` then said "phase
            # states no cell, so it cannot be built", sending the reader of the
            # message looking for a line that is missing rather than at the
            # `Cubic(4.1, 9.9)` two lines above it. One question, one answer —
            # `_UNDEFINED_CELL_MACROS` above is the same shape.
            elif unread := [(n, m) for n in _CELL_MACROS
                            if (m := re.search(rf"\b{n}_?\([^)\n]*\)", chunk))]:
                name, call = unread[0]
                n_args = len(_CELL_MACROS[name].slots)
                raise TopasInpError(
                    f"{path}: {phase.name}: {call.group().strip()!r} states "
                    f"this phase's only cell and this reader could not read it "
                    f"— {name} takes {n_args} "
                    f"argument{'' if n_args == 1 else 's'}, each resolving to a "
                    f"number. Taking the arguments that "
                    f"happened to parse would put an unrelated number in a cell "
                    f"key, and reporting the phase as stating no cell at all is "
                    f"a different fact about the file. Write the a/b/c/al/be/ga "
                    f"lines out instead.")
        read = _read("scale", chunk, symbols)
        phase.scale = read.value if read else None
        if read is not None and read.vary is not None:
            phase.vary["scale"] = read.vary
        phase.weight_percent = _field("weight_percent", chunk, symbols)

        # Sites are split token-wise, not per line (WP-1118): TOPAS is
        # whitespace-insensitive, so `site A1 … beq b 0.5 site B1 x 0.5 …` is
        # two atoms on one line and a per-line scan read one, dropping the
        # second silently — `_SITE_KEYWORDS` already lists `site` as an
        # occupancy terminator, so the grammar half knew. The boundaries come
        # off THE masked chunk, so a `site` inside a quoted path or a macro
        # (`Out_X_Ycalc("site.xy")`) is not one; the segments are sliced from the
        # *original* chunk, so an `x`/`y`/`z` written as an `A1(…)` coordinate
        # macro — which the mask blanks — is still there to read.
        site_pos = [m.start() for m in re.finditer(r"\bsite\b", mchunk)]
        bounds = site_pos + [len(chunk)]
        site_texts = [chunk[site_pos[i]:bounds[i + 1]]
                      for i in range(len(site_pos))]
        for text in site_texts:
            label = re.match(r"\s*site\s+(\S+)", text)
            occs = _site_occupancies(text, symbols)
            if not (label and occs):
                raise TopasInpError(
                    f"{path}: {phase.name}: no label/occ in site: {text.strip()!r}")
            # One read per field, so the value and its flag come off one match.
            reads: dict[str, _Read] = {}
            for axis in "xyz":
                read = _read(axis, text, symbols)
                if read is None or read.value is None:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read {axis} from "
                        f"site line: {text.strip()!r}")
                reads[axis] = read
            # A **stated** `beq` the reader cannot resolve refuses, naming the
            # line, exactly as `x` on the same line already does — defaulting it
            # is seeding 0.5 for a number the file states, the silent-default
            # class this reader exists to avoid (WP-1118, finding 4). A site that
            # states no `beq` at all is a different fact: it keeps the None that
            # becomes the 0.5 seed at build time, so `model.phases` stays "what
            # the file states" and a caller can tell a seed from a stated value.
            beq_read = _read("beq", text, symbols)
            if re.search(r"\bbeq\b", text) and (beq_read is None
                                                or beq_read.value is None):
                raise TopasInpError(
                    f"{path}: {phase.name}: cannot read beq from site line: "
                    f"{text.strip()!r} — the site states beq and this reader "
                    f"could not resolve its value, so building it would seed 0.5 "
                    f"for a number the file states. A site that states no beq at "
                    f"all is a different fact and keeps that seed.")
            if beq_read is not None:
                reads["beq"] = beq_read
            beq = beq_read.value if beq_read is not None else None
            # The anisotropic displacement tensor, carried as what the file
            # states (WP-1118, finding 1), in both spellings: the six-slot
            # positional `ADPs { … }` block (the archive's live form, 6 files)
            # and the named `u11 … u23` site keywords. A component the site
            # states but this reader cannot resolve refuses, naming the line —
            # the same rule beq and x follow, extended to the tensor: defaulting
            # it would put 0 in for a stated U^ij. `to_structure` builds it
            # behind `aniso=True` and refuses to seed 0.5 over it otherwise.
            adps: dict | None = None
            brace = _ADPS_BRACE.search(text)
            named_scan = (text if brace is None
                          else text[:brace.start()] + text[brace.end():])
            if brace is not None:
                slots = _read_adps_slots(brace.group(1), symbols)
                if slots is None or any(r.value is None for r in slots):
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read the ADPs block on "
                        f"site line: {text.strip()!r} — the site states a "
                        f"six-slot anisotropic tensor and this reader could not "
                        f"resolve every slot (a `Get(...)` reference, or a slot "
                        f"that is not a value of the grammar), so building it "
                        f"would substitute a number the file does not state.")
                adps = dict(zip(_ADP_KEYS, (r.value for r in slots)))
                for u, r in zip(_ADP_KEYS, slots):
                    if r.vary is not None:
                        reads[u] = r
            elif _ADP_TOKEN.search(named_scan):
                adps = {}
                for u in _ADP_KEYS:
                    if not re.search(rf"\b{u}\b", named_scan):
                        continue                 # off-diagonal absent -> 0 later
                    uread = _read(u, named_scan, symbols)
                    if uread is None or uread.value is None:
                        raise TopasInpError(
                            f"{path}: {phase.name}: cannot read {u} from site "
                            f"line: {text.strip()!r} — the site states an "
                            f"anisotropic tensor and this reader could not "
                            f"resolve {u}, so building it would substitute 0 for "
                            f"a number the file states.")
                    adps[u] = uread.value
                    if uread.vary is not None:
                        reads[u] = uread
            elif _ADPS_KW.search(text):
                # `ADPs` with no brace and no named component: TOPAS generates
                # the tensor at run time, so the file says "anisotropic" and
                # states no numbers this reader could carry.
                raise TopasInpError(
                    f"{path}: {phase.name}: site line states `ADPs` but no "
                    f"tensor components this reader can read: {text.strip()!r} "
                    f"— building it isotropic would discard a stated "
                    f"anisotropy.")
            # The site's magnetic moment, carried as what the file states
            # (WP-1328). A stated component this reader cannot resolve refuses
            # naming the line, the same rule `beq`, `x` and the ADP tensor
            # follow: substituting 0 for a stated `mlx` is a moment pointing
            # somewhere else, and |F_m|² is quadratic in it so the error does
            # not announce itself as an obviously broken pattern.
            moment: dict | None = None
            for key in _MOMENT_KEYS:
                if not re.search(rf"\b{key}\b", text):
                    continue
                mread = _read(key, text, symbols)
                if mread is None or mread.value is None:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read {key} from site "
                        f"line: {text.strip()!r} — the site states a magnetic "
                        f"moment and this reader could not resolve {key}, so "
                        f"building it would substitute 0 for a number the file "
                        f"states.")
                moment = {} if moment is None else moment
                moment[key] = mread.value
                if mread.vary is not None:
                    reads[key] = mread
            # A site carrying several `occ` tokens is a **mixed** site: one atom
            # per species, sharing this site's label, coordinates and B, exactly
            # as the two-`site`-line spelling already builds (WP-1118, finding 2).
            # The species and its occupancy travel together off
            # `_site_occupancies`, so `occ Al+3 occ Cr+3 0.1` no longer gives Al
            # the value that is Cr's (finding 3); a species stating no value at
            # all keeps the format's own 1.0.
            base_vary = {f: r.vary for f, r in reads.items() if r.vary is not None}
            for species, occ_read in occs:
                # A stated occupancy the reader cannot resolve refuses too — the
                # 1.0 default is for an occupancy the file *omits*, not for one it
                # states and this reader could not read (finding 4).
                if occ_read is not None and occ_read.value is None:
                    raise TopasInpError(
                        f"{path}: {phase.name}: cannot read occ for species "
                        f"{species!r} from site line: {text.strip()!r} — the "
                        f"site states this occupancy and this reader could not "
                        f"resolve its value, so building it would substitute the "
                        f"format's 1.0 default for a number the file states. An "
                        f"occupancy the file omits is a different fact and keeps "
                        f"1.0.")
                occupancy = occ_read.value if occ_read is not None else None
                vary = dict(base_vary)
                if occ_read is not None and occ_read.vary is not None:
                    vary["occ"] = occ_read.vary
                norm_species = normalize_species(species)
                if norm_species != species:
                    # path to this atom-to-be: this phase's future index, this
                    # site's index within it (both before their appends)
                    species_rewrites.setdefault(species, (norm_species, []))[1].append(
                        f"phases.{len(model.phases)}.atoms.{len(phase.sites)}.species")
                phase.sites.append(TopasSite(
                    label=label.group(1), species=norm_species,
                    occupancy=occupancy if occupancy is not None else 1.0,
                    beq=beq, adps=dict(adps) if adps is not None else None,
                    moment=dict(moment) if moment is not None else None,
                    vary=vary,
                    **{axis: reads[axis].value for axis in "xyz"}))
        # A site token that read no atom is a silently wrong structure factor, so
        # every segment produced at least one atom above or raised; the count of
        # site *tokens* landed in phases is what the file-level guard balances.
        parsed_site_tokens += len(site_texts)
        model.phases.append(phase)

    # The macro arm (#649): a library macro states a construct the way a
    # keyword does, and is written inside a phase or at dataset level alike, so
    # it is scanned over the whole active text and attributed to the phase
    # whose chunk holds it, or to none. A `for` body stating only macros is not
    # a reason to expand the loop (`_bears_on_the_model`): left where it is
    # written it is still met here, unattributed, and reported rather than
    # refused for a target TOPAS would not have found.
    for m in _MACRO_CALL.finditer(_unquoted(active)):
        owner = next((name for start, end, name in phase_spans
                      if start <= m.start() < end), "")
        covered.setdefault(m.group(1), set()).add(owner)
    # Set before the site-count guard's refusal has a chance to fire, so that on
    # every path where a model exists at all it carries its own coverage.
    model.coverage = _coverage.classify(
        covered, _unread_calls(_unquoted(active), stripped))

    # A file-level count of `site` tokens, computed over THE masked text and so
    # independent of how the file was split into blocks (WP-1118). A splitter
    # error — a `macro` truncating a `str`, a `str` chunk cut short — that drops
    # sites is invisible to a per-phase count read off that same truncated chunk;
    # this one is not: every `site` token the reader saw must land in a phase (as
    # one or more atoms) or be recorded on a skipped block. Over the mask, not
    # `active`, so a `site` inside a quoted path (`xdd "C:\data\site\run1.xy"`)
    # or a macro is not counted and does not refuse a file that dropped nothing.
    # Counted in `site` **tokens**, not atoms: a mixed site (`occ A occ B`) is
    # one token and several atoms (WP-1118, finding 2), so the balance is over
    # the tokens landed in phases (`parsed_site_tokens`), not `len(ph.sites)`.
    declared = len(re.findall(r"\bsite\b", masked))
    parsed = parsed_site_tokens
    skipped = sum(sb.n_sites for sb in model.skipped_blocks)
    if declared != parsed + skipped:
        raise TopasInpError(
            f"{path}: counted {declared} `site` tokens in the file but read "
            f"{parsed} into phases and recorded {skipped} on blocks that could "
            f"not be named as phases — the {declared - parsed - skipped} "
            f"unaccounted for are sites dropped by how the file split into "
            f"blocks. Read `model.phases` for what was parsed.")

    # Report the two repairs that reached the model, and the `str` blocks the
    # reader saw but could not name as phases (finding 4). Emitted only past the
    # site-count guard above, so a file that is about to refuse does not also
    # leave a half-list of diagnostics behind on the caller's list.
    if diagnostics is not None:
        # The `Run_Number` arm (WP-1433). A condition on `Run_Number` was read as
        # the first run's, which is the only run a file with no `num_runs` has;
        # where it states more, later runs read other branches, and the model
        # here is run 0's — said, because nothing in the model shows it.
        runs = _num_runs(active, conditionals.params)
        if conditionals.run_dependent and runs != 1:
            stated = ("a `num_runs` this reader could not evaluate"
                      if runs is None else f"num_runs = {runs:g}")
            diagnostics.append(Diagnostic(
                level="warning", code="TOPAS_FIRST_RUN_READ",
                message=(f"{path}: a `#if`/`#elseif` here tests `Run_Number`, "
                         f"and the file states {stated}; the branches were "
                         f"read as the first run (Run_Number 0) reads them. "
                         f"A later run pre-processes the same file into other "
                         f"text, so this is run 0's model"),
                where=["Run_Number"]))
        for raw, (canonical, where) in species_rewrites.items():
            diagnostics.append(Diagnostic(
                level="info", code="TOPAS_SPECIES_NORMALISED",
                message=(f"species {raw!r} in {path} read as {canonical!r} "
                         f"(IUCr digit-first order)"),
                where=where))
        # The coupled-edge arm. `b = Get(a);` is *read* now where it used to
        # refuse the whole file, and the trade costs the tie: resolution copies
        # `a`'s number into `b` and nothing carries "these move together". Where
        # the phase's symmetry ties them anyway the built model states what the
        # file did, so there is nothing to report and this stays silent — which
        # is why the archive's four PbPdO2/PdO fits (tetragonal and cubic) raise
        # none of these. Where it does not, one edge refines and the other sits
        # frozen at the value it was copied: a third thing neither the file nor
        # rietx meant, and a repair the reader may make only because it can say
        # here that it made it.
        for phase_name, sg, key, source, via in cell_couplings:
            if _symmetry_reproduces(sg, key, source):
                continue
            diagnostics.append(Diagnostic(
                level="warning", code="TOPAS_CELL_COUPLING_DROPPED",
                message=(f"{path}: {phase_name}: {key} is written through "
                         f"{via}, so the file ties it to {source}; the value "
                         f"was copied but the tie was not, and space group "
                         f"{sg!r} does not tie them either. The two edges are "
                         f"independent in the built model and may refine apart. "
                         f"Tie them in the refinement plan, or read "
                         f"`model.phases` for what the file states"),
                where=[f"phases.{phase_name}.cell.{key}"]))
        # The coverage arm (:mod:`.coverage`): a `.inp` states more than a
        # structure, and the constructs in between used to be dropped exactly as
        # silently as the ones that do not matter. One diagnostic per stance,
        # not per keyword — a file stating six convolutions is one partial
        # import, and a caller reading a message wants the feature's name.
        if model.coverage.reported:
            diagnostics.append(Diagnostic(
                level="warning", code="TOPAS_FEATURES_NOT_IMPORTED",
                message=(f"{path}: this import is partial — the file states "
                         f"{model.coverage.summary_of(model.coverage.reported)}"
                         f", and none of it reaches the built structure. The "
                         f"numbers that do are unaffected; what is missing is "
                         f"the model around them. Read `model.coverage` for the "
                         f"list, and `model.phases` for what the file states"),
                where=[f"coverage.reported.{h.feature.name}"
                       for h in model.coverage.reported]))
        if model.coverage.unread_calls:
            names = ", ".join(f"`{n}(…)`" for n in model.coverage.unread_calls)
            diagnostics.append(Diagnostic(
                level="warning", code="TOPAS_FEATURES_NOT_IMPORTED",
                message=(f"{path}: the file calls {names}, which it does not "
                         f"define and this reader does not read. A macro from "
                         f"an include this reader has not seen and a misspelt "
                         f"name look the same from here, and either way "
                         f"whatever the call states is missing from the built "
                         f"structure. A name this reader has no row for is listed "
                         f"too, so a real library macro can appear here. "
                         f"Read `model.coverage.unread_calls`"),
                where=[f"coverage.unread_calls.{n}"
                       for n in model.coverage.unread_calls]))
        if model.coverage.refused:
            diagnostics.append(Diagnostic(
                level="warning", code="TOPAS_FEATURE_REFUSED",
                message=(f"{path}: the file states "
                         f"{model.coverage.summary_of(model.coverage.refused)}"
                         f", which `to_structure` refuses rather than drops — "
                         f"building the phase without it would misrepresent the "
                         f"refinement, not merely simplify it. The model is "
                         f"still an honest account of the text: read "
                         f"`model.phases`"),
                where=[f"coverage.refused.{h.feature.name}"
                       for h in model.coverage.refused]))
        for k, constructs in model.time_of_flight.items():
            diagnostics.append(Diagnostic(
                level="warning", code="TOPAS_FEATURE_REFUSED",
                message=(f"{path}: "
                         f"{'the file' if k is None else f'dataset {k}'} is "
                         f"time of flight (it states {', '.join(constructs)}), "
                         f"and this build models constant-wavelength "
                         f"diffraction only — time of flight is issue #193 — "
                         f"so `to_structure` refuses its phases rather than "
                         f"build them as if from a constant-wavelength "
                         f"pattern. Read `model.phases` for what the file "
                         f"states and `model.time_of_flight` for which "
                         f"datasets are time of flight"),
                where=[f"time_of_flight.{k}"]))
        for phase_name, raw, canonical in origin_translations:
            diagnostics.append(Diagnostic(
                level="info", code="TOPAS_ORIGIN_TRANSLATED",
                message=(f"space group {raw!r} on phase {phase_name!r} in {path} "
                         f"read as {canonical!r} — the suffix selects the origin"),
                where=[f"phases.{phase_name}.space_group"]))
        # The other half of the same question (issue #101).  A trailing `Z`/`S`/
        # `R`/`H` is TOPAS saying which setting it meant, and the line above
        # reports the translation; a symbol written **bare** says nothing, and
        # `.inp` carries no operators to settle it the way a `.gpx` does.  So it
        # is reported as assumed, from the package-wide builder, at read.
        for phase in model.phases:
            if not phase.space_group:
                continue
            cell = phase.cell
            try:
                diagnostics.extend(setting_diagnostics(
                    phase.space_group,
                    source=f"{path}: phase {phase.name!r}",
                    # by name, as `TOPAS_ORIGIN_TRANSLATED` addresses the very
                    # same field of the very same phase two rows up: one field
                    # reached two ways is worse for a consumer than either way
                    where=[f"phases.{phase.name}.space_group"],
                    cell=([cell[k] for k in ("a", "b", "c", "al", "be", "ga")]
                          if all(k in cell for k in
                                 ("a", "b", "c", "al", "be", "ga")) else None),
                    sites=[(s.species, s.x, s.y, s.z, s.occupancy)
                           for s in phase.sites] or None))
            except ValueError:
                # an unresolvable symbol is `to_structure`'s refusal to make,
                # naming the file; a read's report must not raise
                pass
        # The skipped-block "report" arm (WP-1118): a `str` block that stated no
        # `phase_name`/`space_group` is recorded on `model.skipped_blocks`
        # regardless, so the read never drops it in silence. When a channel is
        # passed it is *reported* here too, naming what the block lacked and what
        # it did carry. This does not turn the block's build-time refusal into a
        # silent drop — `to_structure` still refuses to build a `Structure` that
        # omits a cell-bearing block while other phases build (the weight
        # fractions would no longer sum), because that refusal must hold whether
        # or not a caller passed a list. Report at read; refuse at build; drop
        # never.
        for i, sb in enumerate(model.skipped_blocks):
            diagnostics.append(Diagnostic(
                level="warning", code="TOPAS_BLOCK_SKIPPED",
                message=(f"{path}: {sb} — read onto `model.skipped_blocks`, not "
                         f"built as a phase"),
                where=[f"skipped_blocks.{i}"],
                suggestion=_skipped_remedy([sb])))
    return model


def _magnetic_group_number(mag_space_group: str | None) -> str | None:
    """The BNS or OG number a ``mag_space_group`` value *is*, or ``None``.

    TOPAS's grammar writes ``mag_space_group $symbol``, and the files write a
    number there: the Durham LaMnO₃ magnetic tutorial's ``mag_space_group
    62.448`` and ``mag_space_group 1.1`` (the latter under a ``'BNS:1.1 P1``
    comment ISODISTORT's TOPAS export writes). Two dotted integers are a BNS
    number and three an OG one, which is exactly the syntax
    :class:`~rietx.schemas.structure.MagneticSymmetry` resolves (spglib, the
    standard setting); anything else is a Shubnikov symbol, and no dependency
    here parses one (M-5 D-c), so it returns ``None`` and the group has to come
    from the caller.
    """
    if mag_space_group is None:
        return None
    text = mag_space_group.strip()
    return text if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", text) else None


def _magnetic_specs(model: TopasModel, phases_in, magnetic_symmetry
                    ) -> tuple[dict[str, object], set[str]]:
    """``{phase name: magnetic-symmetry spec}``, or a refusal naming the phase.

    The rule, and the whole of WP-1328's TOPAS stance in one place:

    * a phase whose sites state **no** moment is nuclear and gets nothing —
      passing a group for it would put a magnetic space group on a phase with
      no moment, which the schema allows and which means nothing;
    * a phase whose sites **do** state a moment needs a group. A
      ``mag_space_group`` stating a BNS or OG number is one
      (:func:`_magnetic_group_number`) and is used where the caller supplied
      none for that phase; a symbol is not (M-5 D-c: no dependency here parses
      a Shubnikov symbol). With a spec supplied it is used; without one the
      build **refuses by name**;
    * a spec naming a phase that is not being built, or one that states no
      moment, refuses too — a caller who passes ``{"Cr2WO6": 58.395}`` and gets
      silence because the phase is spelled differently in the file has been
      handed a nuclear structure that looks complete, which is the exact
      failure this whole registry exists to prevent.

    A bare spec (an ``int``, a number string, a
    :class:`~rietx.schemas.structure.MagneticSymmetry`) is accepted where
    exactly **one** phase being built states a moment; with two, the mapping
    form is required, because guessing which phase a single group belongs to is
    a choice a reader does not get to make.

    Returns the resolved specs and the names of the phases whose group came
    from the file's own number rather than from the caller.
    """
    magnetic_phases = [ph.name for ph in phases_in
                       if any(s.moment is not None for s in ph.sites)]
    from_file = {ph.name: number for ph in phases_in
                 if ph.name in magnetic_phases
                 and (number := _magnetic_group_number(ph.mag_space_group))}
    if magnetic_symmetry is None:
        if not magnetic_phases:
            return {}, set()
        unresolved = [n for n in magnetic_phases if n not in from_file]
        if unresolved:
            named = "; ".join(
                f"{ph.name!r} (mag_space_group "
                f"{ph.mag_space_group!r}, moments on "
                f"{', '.join(repr(s.label) for s in ph.sites if s.moment)})"
                for ph in phases_in if ph.name in unresolved)
            raise TopasInpError(
                f"{model.path or '<model>'}: {len(unresolved)} phase"
                f"{'' if len(unresolved) == 1 else 's'} "
                f"state{'s' if len(unresolved) == 1 else ''} site magnetic "
                f"moments and this build was not given a magnetic space "
                f"group: {named}. A BNS or OG number in mag_space_group is "
                f"read as the group; this states a Shubnikov *symbol* (or "
                f"none), and rietx's model is the operator list — no "
                f"dependency here parses a symbol, and guessing one is how a "
                f"fit lands under the wrong group — so the group has to come "
                f"from the caller: pass to_structure(magnetic_symmetry=<BNS/"
                f"OG/UNI number or operator list>), or {{phase name: spec}} "
                f"for more than one. Building the phase without its moments "
                f"would return the nuclear half of a magnetic refinement, and "
                f"`model.phases[i].sites[j].moment` is what the file states.")
        specs = dict(from_file)
    elif isinstance(magnetic_symmetry, dict) and not (
            set(magnetic_symmetry) <= {"operations", "centerings", "bns_number",
                                       "og_number", "uni_number", "symbol",
                                       "setting"}):
        specs = dict(magnetic_symmetry)
    elif not magnetic_phases:
        # No phase being built states a moment, so a group has nowhere to
        # attach. Refused with the same sentence the named-phase arm below
        # uses, because it is the same mistake: a magnetic space group on a
        # phase with no moment constrains nothing and contributes nothing.
        raise TopasInpError(
            f"{model.path or '<model>'}: magnetic_symmetry was given and no "
            f"phase being built states a site moment: none of "
            f"{', '.join(repr(ph.name) for ph in phases_in)} writes "
            f"mlx/mly/mlz. A magnetic space group on a phase with no moment "
            f"constrains nothing and contributes nothing, so it is refused "
            f"rather than stored as a claim the file does not make.")
    else:
        if len(magnetic_phases) != 1:
            raise TopasInpError(
                f"{model.path or '<model>'}: magnetic_symmetry was given as one "
                f"spec and {len(magnetic_phases)} phases being built state "
                f"moments ({', '.join(map(repr, magnetic_phases))}). Which "
                f"phase it belongs to is not something this reader may guess: "
                f"pass {{phase name: spec}}.")
        specs = {magnetic_phases[0]: magnetic_symmetry}
    building = {ph.name for ph in phases_in}
    unknown = sorted(set(specs) - building)
    if unknown:
        raise TopasInpError(
            f"{model.path or '<model>'}: magnetic_symmetry names phase"
            f"{'' if len(unknown) == 1 else 's'} "
            f"{', '.join(map(repr, unknown))}, which "
            f"{'is' if len(unknown) == 1 else 'are'} not being built here. "
            f"This file states {', '.join(repr(n) for n in sorted(building))}. "
            f"A misspelled phase name would otherwise hand back a nuclear "
            f"structure with no magnetic model and nothing said.")
    momentless = sorted(set(specs) - set(magnetic_phases))
    if momentless:
        raise TopasInpError(
            f"{model.path or '<model>'}: magnetic_symmetry was given for phase"
            f"{'' if len(momentless) == 1 else 's'} "
            f"{', '.join(map(repr, momentless))}, whose sites state no "
            f"mlx/mly/mlz. A magnetic space group on a phase with no moment "
            f"constrains nothing and contributes nothing, so it is refused "
            f"rather than stored as a claim the file does not make.")
    # a phase the caller's mapping leaves out takes the file's own number
    taken_from_file = {n for n in set(magnetic_phases) - set(specs)
                       if n in from_file} | (
        set(specs) if magnetic_symmetry is None else set())
    for n in taken_from_file:
        specs.setdefault(n, from_file[n])
    missing = sorted(set(magnetic_phases) - set(specs))
    if missing:
        raise TopasInpError(
            f"{model.path or '<model>'}: phase"
            f"{'' if len(missing) == 1 else 's'} "
            f"{', '.join(map(repr, missing))} "
            f"state{'s' if len(missing) == 1 else ''} site moments and "
            f"magnetic_symmetry names no group for "
            f"{'it' if len(missing) == 1 else 'them'}. Every phase with a "
            f"moment needs one, or its moments would be dropped in silence.")
    # Resolved here rather than at `rx.Phase(...)`, so a spec this schema
    # cannot read is refused naming the *argument* and the phase instead of
    # arriving as a pydantic report about a field. The commonest such spec is a
    # BNS number written as a float: `58.395` is a dotted pair of integers, not
    # a number — as a float it is the same value as 58.3950, which is a
    # different entry — so the schema takes an int (UNI) or a string, and this
    # says which.
    from ...schemas.structure import MagneticSymmetry

    resolved: dict[str, object] = {}
    for name, spec in specs.items():
        try:
            resolved[name] = (spec if isinstance(spec, MagneticSymmetry)
                              else MagneticSymmetry.model_validate(spec))
        except Exception as exc:
            hint = (" A BNS or OG number is a dotted pair of integers and has "
                    "to be a *string* — '58.395', not 58.395 — because as a "
                    "float it is the same value as 58.3950, a different entry; "
                    "a UNI number is a plain int."
                    if isinstance(spec, float) else "")
            raise TopasInpError(
                f"{model.path or '<model>'}: magnetic_symmetry for phase "
                f"{name!r} is not a magnetic space group this schema can read "
                f"({spec!r}): {exc}.{hint}") from exc
    return resolved, taken_from_file


def _nuclear_groups(model: TopasModel, phases_in, specs) -> dict:
    """``{phase name: nuclear group}`` for every phase stating none.

    A ``str`` with ``mag_space_group`` and no ``space_group`` — TOPAS's own
    magnetic examples, the Durham LaMnO₃ tutorial — has its atoms generated by
    the magnetic group's operators, so its nuclear group is the magnetic
    group's operators with time reversal dropped: tier 2 of
    :func:`~rietx.crystallography.magcif.resolve_nuclear_symmetry` (issue
    #457's rule), there being no parent for tier 1 to try, or tier 3 — the
    operation list under a bracketed label — where no tabulated setting has
    exactly those operations. The value is the group object
    (``gemmi.SpaceGroup`` or ``symmetry.OperatorGroup``). The magnetic group
    is the phase's spec where it has one, else the file's own number (a phase
    stating no moment still needs its nuclear group); a phase with neither is
    refused, naming the symbol it wrote.
    """
    from ...crystallography.magcif import MagCifError, resolve_nuclear_symmetry
    from ...schemas.structure import MagneticSymmetry

    path = model.path or "<model>"
    out: dict[str, str] = {}
    for ph in phases_in:
        if ph.space_group:
            continue
        spec = specs.get(ph.name)
        if spec is None and (number := _magnetic_group_number(
                ph.mag_space_group)) is not None:
            # built inside the guard, as every schema object a conversion
            # builds is (io/CLAUDE.md): a number the schema cannot resolve
            # (``999.1``) raises naming the file and the phase, never as a
            # bare pydantic report about a field (review of #478, item 2)
            try:
                spec = MagneticSymmetry.model_validate(number)
            except Exception as exc:
                raise TopasInpError(
                    f"{path}: phase {ph.name!r} states no space_group, and its "
                    f"mag_space_group {ph.mag_space_group!r} is not a magnetic "
                    f"space group this schema can resolve, so there is no "
                    f"operator list to derive the nuclear group from: "
                    f"{exc}") from exc
        if spec is None:
            raise TopasInpError(
                f"{path}: phase {ph.name!r} states no space_group, and its "
                f"mag_space_group {ph.mag_space_group!r} is a Shubnikov "
                f"symbol rather than a BNS or OG number, so there is no "
                f"operator list to derive the nuclear group from — no "
                f"dependency here parses a symbol. State the nuclear "
                f"space_group beside it, write the BNS number, or pass "
                f"to_structure(magnetic_symmetry={{{ph.name!r}: <number>}}) "
                f"where the phase states moments.")
        try:
            group = resolve_nuclear_symmetry(
                None, spec, f"{path}: phase {ph.name!r}",
                nuclear_group="file")
        except MagCifError as exc:
            raise TopasInpError(str(exc)) from exc
        out[ph.name] = group
    return out


def _magnetic_build_diagnostics(model: TopasModel, phases_in, specs,
                                group_from_file=frozenset(),
                                nuclear_groups=None) -> list[Diagnostic]:
    """What the magnetic build assumed, said once per phase it applies to.

    Four things, each an assumption or a derivation rather than a reading,
    which is exactly why they are on a channel instead of in a comment:

    * ``TOPAS_MAGNETIC_GROUP_READ`` — the magnetic group is the file's own
      ``mag_space_group`` number, resolved to operators in the standard BNS
      setting (the caller supplied none for that phase), and, where the ``str``
      stated no ``space_group``, the nuclear group was derived from it
      (:func:`_nuclear_groups`). The file's coordinates are taken to be in that
      standard setting, as TOPAS takes them to be in the setting of its own
      table. Nothing here compares the two tables, but the phase does: a
      number whose standard-setting operations are not a symmetry of the
      file's nuclear ``space_group``, cell and sites (a b-unique 14.79 beside
      ``P 1 1 21/b``) is refused when the phase is read, by
      :func:`~rietx.crystallography.magnetic.scattering.check_group_is_structure_symmetry`
      (issue #597), never read into a different structure.
    * ``TOPAS_MOMENT_CONVENTION`` — ``mlx mly mlz`` are read as
      **fractional-basis** components and stored as crystal-axis μ_B
      (component × edge; :attr:`TopasSite.moment` carries the evidence). The
      reading is the TOPAS Technical Reference's own formula, and it is
      **measured** against TOPAS's own calculated intensities, so the
      diagnostic says both.
    * ``TOPAS_MOMENT_ION_UNCHARGED`` — the magnetic form factor is keyed by
      oxidation state and the site's own species is what supplies it. TOPAS
      files usually write ``occ Cr+3``, which normalises to ``Cr3+`` and
      resolves; a site written ``occ Cr`` gets the *neutral* atom's ⟨j₀⟩, which
      is a different curve, so the substitution is reported.
    """
    out: list[Diagnostic] = []
    path = model.path or "<model>"
    nuclear_groups = nuclear_groups or {}
    for ip, ph in enumerate(phases_in):
        derived = nuclear_groups.get(ph.name)
        if ph.name in group_from_file or derived is not None:
            parts = []
            if ph.name in group_from_file:
                parts.append(
                    f"magnetic group from the file's mag_space_group "
                    f"{ph.mag_space_group!r} as a BNS/OG number, operators in "
                    f"its standard setting")
            if derived is not None:
                parts.append(
                    f"no space_group stated, so the positions refine under "
                    f"{derived.xhm()!r}, the magnetic group's operators with time "
                    f"reversal dropped")
            out.append(Diagnostic(
                level="info", code="TOPAS_MAGNETIC_GROUP_READ",
                where=[f"phases.{ip}.magnetic_symmetry"] * (
                    ph.name in group_from_file)
                + [f"phases.{ip}.space_group"] * (derived is not None),
                message=f"{path}: phase {ph.name!r}: " + "; ".join(parts),
                suggestion=("the file's coordinates and moments are taken to "
                            "be in the standard setting of that number (a "
                            "setting whose operations are not a symmetry of "
                            "the file's space_group and cell is refused, not "
                            "read); pass to_structure(magnetic_symmetry=...) "
                            "with an operator list if the file uses another "
                            "setting")))
        if ph.name not in specs:
            continue
        moment_sites = [s for s in ph.sites if s.moment is not None]
        out.append(Diagnostic(
            level="info", code="TOPAS_MOMENT_CONVENTION",
            where=[f"phases.{ip}.atoms.{j}.moment"
                   for j, s in enumerate(ph.sites) if s.moment is not None],
            message=(f"{path}: phase {ph.name!r}: mlx/mly/mlz on "
                     f"{', '.join(repr(s.label) for s in moment_sites)} read as "
                     f"fractional-basis components (m = mlx*a + mly*b + "
                     f"mlz*c) and stored as crystal-axis mu_B, (mlx*|a|, "
                     f"mly*|b|, mlz*|c|)"),
            suggestion=("the reading is the TOPAS Technical Reference § 13 "
                        "(Fmagc = L*Fmag; MM_CrystalAxis_Display gives mxc = "
                        "mlx*a), and it is measured: TOPAS 6's own calculated "
                        "magnetic intensities on a monoclinic cell match it "
                        "pair by pair and in |m|, and match neither a "
                        "crystal-axis nor a Cartesian reading; a file's "
                        "MM_CrystalAxis_Display values are the stored "
                        "components, to check against")))
        # `mg` is refinable in TOPAS (Technical Reference § 13: "The Lande
        # splitting factor can be refined using the site-dependent parameter
        # mg") and `Moment.g` is a plain float, so a refined g arrives held at
        # the file's value: one free parameter fewer than the file's own
        # refinement, the same loss `TOPAS_CELL_COUPLING_DROPPED` reports for
        # a cell tie.
        g_free = [(j, s) for j, s in enumerate(ph.sites)
                  if s.moment is not None and s.vary.get("mg")]
        if g_free:
            out.append(Diagnostic(
                level="warning", code="TOPAS_MOMENT_G_HELD",
                where=[f"phases.{ip}.atoms.{j}.moment.g" for j, _ in g_free],
                message=(f"{path}: phase {ph.name!r}: the file refines the "
                         f"Landé g (`mg`) on "
                         + ", ".join(f"{s.label!r} (g = {s.moment['mg']:g})"
                                     for _, s in g_free)
                         + "; rietx's Moment.g is a fixed number, so g is "
                           "read as held at that value and the built model "
                           "has fewer free parameters than the file's "
                           "refinement"),
                suggestion=("g enters only the ⟨j₂⟩ weight of the form factor, "
                            "(2/g − 1); set Atom.moment.g on the built "
                            "structure to try another value, and compare with "
                            "the file's figures knowing g did not move")))
        bare =[s for s in moment_sites if re.fullmatch(r"[A-Za-z]{1,2}",
                                                        s.species)]
        if bare:
            out.append(Diagnostic(
                level="info", code="TOPAS_MOMENT_ION_UNCHARGED",
                where=[f"phases.{ip}.atoms.{j}.moment.ion"
                       for j, s in enumerate(ph.sites) if s in bare],
                message=(f"{path}: phase {ph.name!r}: "
                         f"{', '.join(repr(s.label) for s in bare)} state a "
                         f"moment and an uncharged species, so the magnetic "
                         f"form factor is the neutral atom's"),
                suggestion="the magnetic form factor is keyed by oxidation "
                           "state; write the site's `occ` with its charge "
                           "(`occ Cr+3`) so the ion resolves"))
    return out


def to_structure(model: TopasModel, *, cell_limits: bool = True,
                 aniso: bool = False, dataset: int | None = None,
                 magnetic_symmetry=None,
                 diagnostics: list[Diagnostic] | None = None):
    """Build a :class:`~rietx.schemas.Structure` from a parsed model.

    A **module-level** name, not a package export. WP-1118 is "read a refinement
    in, **write one back**", so this format grows four things, not two — a reader,
    a writer, this model-to-:class:`~rietx.schemas.Structure` conversion and its
    inverse — and ``to_structure`` / ``from_structure`` is the symmetry that pair
    wants; renaming one half would make it awkward later. The collision with
    #111's own ``to_structure`` is resolved one level up, in the **package
    export**: ``io/projects/__init__.py`` exports only the format-named entry
    points (``read_topas_inp``, ``TopasInpError``), so this is reached as
    ``projects.topas.to_structure`` and there is nothing for a sibling module's
    ``to_structure`` to shadow.

    ``beq`` is TOPAS's B and rietx's ``biso`` is also B — no 8π² conversion. A
    site that states no ``beq`` gets a **0.5 seed here**, at build time, not on
    ``model.phases`` — the model is "what the ``.inp`` states", and a seed a
    caller cannot tell from a stated value is the silent-default class this
    reader avoids (WP-1118).
    ``cell_limits`` applies the file's own ``min``/``max`` where it stated them
    **and where the stated value lies inside them**. A bound the value falls
    outside is *dropped* and the value kept, one bound at a time: TOPAS writes
    the converged value back into the ``.inp``, so an edited or re-run window
    can end up on the wrong side of it, and the value is the measurement while
    the bound is the author's search window. So ``a lpa 6.2977 min 6.26 max
    6.29`` builds 6.2977 carrying the ``min`` and **no** ``max`` — see ``_p()``
    for why keeping both is not an option a reader has.

    ``aniso`` is the opt-in for the **anisotropic displacement tensor**, the same
    one :func:`~rietx.crystallography.cif.structure_from_cif` uses and for the
    same reason: reading a file must not silently change which parameters a
    refinement plan will free. TOPAS's ``u11``…``u23`` are U^ij in Å² — the CIF
    ``_atom_site_aniso_U_ij`` convention rietx's :class:`~rietx.AnisoU` holds, so
    the numbers transfer unchanged (a NaCl ``u11 = 0.013`` is B_eq = 8π²·0.013 =
    1.026, not the 0.5 an ADP-blind reader seeds). With ``aniso=True`` a site's
    tensor becomes an :class:`~rietx.AnisoU` block that alone drives the
    Debye-Waller factor (``biso`` is then the inert record the schema requires,
    ``vary=False``); a site without a tensor stays isotropic either way, so a
    mixed file yields a mixed structure. **What it may not do is seed 0.5 in
    silence:** with the default ``aniso=False``, a site that *states* a tensor is
    refused, naming the site — the same report-or-refuse this reader applies to a
    dropped phase — rather than built isotropic with the anisotropy discarded.
    The numbers stay readable on ``model.phases`` either way.

    A **negative** ``beq`` is read as the file states it. A slightly negative
    refined B is an ordinary outcome of a converged refinement (the column
    absorbs absorption and normalisation error), and 75 sites across 11
    archive files state one. Its bound is widened to hold it rather than the
    number being moved to zero (PR #663), which ``BISO_BOUND_WIDENED`` reports,
    and a fit that keeps it reports ``BISO_NEGATIVE``. Every structure reader
    treats it the same way.

    ``magnetic_symmetry`` names a **magnetic** phase's group where the file
    does not. A ``mag_space_group`` stating a BNS or OG number (``62.448``,
    ``1.1`` — how the Durham LaMnO₃ tutorial and ISODISTORT's TOPAS export
    write it) *is* the group, resolved to its standard-setting operators and
    reported as ``TOPAS_MAGNETIC_GROUP_READ``; a Shubnikov *symbol*
    (``mag_space_group "P n' n m"``) is not, because rietx's model is the
    operator list and no dependency here parses a symbol — spglib exposes UNI,
    BNS and OG *numbers* and no symbol table, and guessing one is how a fit
    lands under the wrong group (M-5, decision D-c). For a symbol the group has
    to come from here: pass a BNS/OG/UNI number, a
    :class:`~rietx.schemas.structure.MagneticSymmetry`, or a ``{phase name:
    spec}`` mapping when the file has more than one magnetic phase; a spec
    passed here outranks the file's number for its phase.

    A ``str`` stating ``mag_space_group`` and **no** ``space_group`` is built
    under its magnetic group's operators with time reversal dropped — the
    nuclear group TOPAS generates its atoms with — through tier 2 of
    :func:`~rietx.crystallography.magcif.resolve_nuclear_symmetry`, the magCIF
    reader's rule (:func:`_nuclear_groups`). The moments ``mlx mly mlz`` are
    fractional-basis components and are stored as crystal-axis μ_B,
    component × edge (:attr:`TopasSite.moment`, ``TOPAS_MOMENT_CONVENTION``).

    A phase whose sites state a moment and for which no group was supplied or
    read is **refused, naming the phase, the sites and the symbol the file
    wrote** — building it without the moments would return the nuclear half of
    a magnetic refinement, which is the failure every one of this reader's
    magnetic refusals existed to prevent; and building it *with* them is not
    possible, since a moment with no ``magnetic_symmetry`` has no allowed
    subspace and no orbit and the schema refuses it. Pass
    ``magnetic_symmetry={...}`` to build the magnetic model, or drop the
    moments from the phase to declare that the nuclear subset is what you want.
    ``mag_only``/``mag_only_for_mag_sites`` stay refused (:mod:`.coverage`'s
    ``magnetic-only phase`` row says why dropping them is not an option).
    """
    import rietx as rx

    # **A phase belongs to a pattern, and this reader will not concatenate two.**
    # The manual's own keyword tree (Technical Reference S5.1) makes `str` a
    # child of `xdd`, and `xdd` an array: `[xdd $file ...]...` whose children are
    # `[str | dummy_str]...`. So a file stating several datasets states several
    # *specimens*, and putting all of their phases into one `Structure` builds a
    # model that never existed. It is not a subtle error either -- of the 23
    # multi-dataset archive files, every one that reaches the weight-percent
    # oracle states a sum of 189, 300, 400 or 600 %, which is exactly N
    # specimens' phase fractions added together.
    #
    # `io/CLAUDE.md`'s rule for the pattern readers, one rank up: a multi-range
    # file's ranges are *scans selected by* `scan=`, **never concatenated**. Here
    # the selector is `dataset=`, and the refusal names it rather than picking.
    stated = sorted({ph.dataset for ph in model.phases}, key=lambda d: (d is not None, d))
    if dataset is not None:
        phases_in = [ph for ph in model.phases if ph.dataset == dataset]
        if not phases_in:
            raise TopasInpError(
                f"{model.path or '<model>'}: no phase belongs to dataset "
                f"{dataset}; this file states "
                f"{', '.join(repr(d) for d in stated) or 'none'}.")
    elif len(stated) > 1:
        raise TopasInpError(
            f"{model.path or '<model>'}: this file states {len(stated)} datasets "
            f"({', '.join(repr(d) for d in stated)}) and its "
            f"{len(model.phases)} phases are not all one specimen's — `str` is a "
            f"child of `xdd` and `xdd` repeats, so building them together would "
            f"be a Structure that never existed and weight fractions that sum "
            f"over every pattern in the file. Pass dataset=N to build one of "
            f"them, or read `model.phases` (each carries its own `.dataset`).")
    else:
        phases_in = list(model.phases)

    # **Refuse the constructs whose absence would misrepresent the file**, and
    # refuse them here rather than at read (:mod:`.coverage`). The split is the
    # skipped-block one: `read_topas_inp` returns what the text states, so a
    # caller can always look; `to_structure` is where a *claim about a
    # refinement* is made, and that is where a claim it cannot support has to
    # stop. Filtered to the phases actually being built, so `dataset=` selecting
    # a specimen without the rigid body still builds.
    # **A time-of-flight dataset is refused by name** (issue #193), the same
    # read-reports/build-refuses split as the coverage arm below, at dataset
    # rather than phase scope — so `dataset=` selecting a constant-wavelength
    # dataset of a mixed file still builds.
    tof = sorted({ph.dataset for ph in phases_in
                  if ph.dataset in model.time_of_flight},
                 key=lambda d: (d is not None, d or 0))
    if tof:
        stated = "; ".join(
            f"{'the file' if d is None else f'dataset {d}'}: "
            f"{', '.join(model.time_of_flight[d])}" for d in tof)
        raise TopasInpError(
            f"{model.path or '<model>'}: the phases asked for belong to a "
            f"time-of-flight pattern ({stated}), and this build models "
            f"constant-wavelength diffraction only — neutron time of flight "
            f"is issue #193. Building them would put a time-of-flight bank's "
            f"scale and refine flags into a constant-wavelength model. Pass "
            f"dataset=N for a constant-wavelength dataset of this file, or "
            f"read `model.phases` for what the file states.")
    building = {ph.name for ph in phases_in}
    blocked = [h for h in model.coverage.refused
               if not h.phases or building.intersection(h.phases)]
    if blocked:
        raise TopasInpError(
            f"{model.path or '<model>'}: "
            f"{model.coverage.summary_of(blocked)} — this reader has no model "
            f"for it, and building the phase without it would not simplify the "
            f"refinement but misrepresent it: "
            f"{'; '.join(h.feature.why for h in blocked if h.feature.why)}. "
            f"Read `model.phases` for what the file states, and "
            f"`model.coverage` for every construct this import does not carry.")

    # **The magnetic arm** (WP-1328). A phase whose sites state a moment needs
    # an operator list, and the file states a *symbol*: so either the caller
    # supplied the group or this refuses, naming the phase, the sites and the
    # symbol. Resolved before anything is built, so a two-phase file with one
    # magnetic phase refuses before the nuclear one is half-constructed.
    magnetic_specs, group_from_file = _magnetic_specs(model, phases_in,
                                                      magnetic_symmetry)
    nuclear_groups = _nuclear_groups(model, phases_in, magnetic_specs)
    if diagnostics is not None:
        diagnostics.extend(_magnetic_build_diagnostics(
            model, phases_in, magnetic_specs, group_from_file,
            nuclear_groups))

    phases = []
    for ph in phases_in:
        # Report or refuse, never drop. A phase whose cell could not be read
        # used to be skipped here with nothing said, while `model.phases` still
        # carried its `weight_percent` — so the QPA numbers looked complete with
        # a phase missing from the `Structure`, which is worse than the dropped-
        # *site* case this reader already makes a hard error.
        if "a" not in ph.cell:
            raise TopasInpError(
                f"{model.path or '<model>'}: phase {ph.name!r} states no cell, "
                f"so it cannot be built — and dropping it would leave its "
                f"weight_percent reporting for a phase the Structure lacks. "
                f"Read `model.phases` for what the file does state.")
        for s in ph.sites:
            # A stated tensor the caller did not ask for is refused, never
            # collapsed to the isotropic seed in silence (WP-1118, finding 1):
            # NaCl at U = 0.013 is B_eq = 8π²·0.013 = 1.026 against the seeded
            # 0.5 — max |ΔI|/I_max 3.6 % across the pattern and +34.7 % on the
            # strongest 90-140° peak, with nothing raised. Same opt-in shape as
            # `structure_from_cif(aniso=...)`, and for the same reason: reading
            # a file must not silently change which parameters a plan will free.
            if s.adps is not None and not aniso:
                raise TopasInpError(
                    f"{model.path or '<model>'}: phase {ph.name!r}: site "
                    f"{s.label!r} states an anisotropic displacement tensor "
                    f"({', '.join(k for k in _ADP_KEYS if k in s.adps)}) and "
                    f"this build was not asked to carry one — building it "
                    f"isotropic would discard the stated anisotropy"
                    f"{' and seed 0.5 over it' if s.beq is None else ''} in "
                    f"silence. Pass aniso=True to build the tensor, or read "
                    f"`model.phases` for the file's own numbers.")
            if s.adps is not None and any(u not in s.adps
                                          for u in ("u11", "u22", "u33")):
                # An off-diagonal the file omits is 0 by the format's own
                # convention; a *diagonal* it omits has no such default, and
                # filling one in would be a number no file states.
                raise TopasInpError(
                    f"{model.path or '<model>'}: phase {ph.name!r}: site "
                    f"{s.label!r} states a partial anisotropic tensor "
                    f"({', '.join(k for k in _ADP_KEYS if k in s.adps)}) — a "
                    f"missing off-diagonal is 0 by convention, but a missing "
                    f"diagonal U has no default this reader may invent.")
        c = ph.cell

        def _p(key: str, default: float):
            lo, hi = ph.cell_limits.get(key, (None, None)) if cell_limits else (None, None)
            value = c.get(key, default)
            kw = {}
            # A stated bound that excludes the stated value is dropped, not
            # enforced. The two disagree in real files — TOPAS writes the
            # converged value back into the .inp, so an edited or re-run bound
            # can end up on the wrong side of it — and the *value* is the
            # measurement while the bound is the author's search window. Keeping
            # both raised a pydantic error out of a reader, which this package's
            # readers may not do.
            if lo is not None and value >= lo:
                kw["min"] = lo
            if hi is not None and value <= hi:
                kw["max"] = hi
            if (free := ph.vary.get(key)) is not None:
                kw["vary"] = free
            return rx.Parameter(value=value, **kw)

        def _sp(site, field_: str, value: float, **kw):
            """A site parameter, carrying the file's own refine flag."""
            if (free := site.vary.get(field_)) is not None:
                kw["vary"] = free
            return rx.Parameter(value=value, **kw)

        def _atom(s):
            """One atom; a tensor site builds its `AnisoU` (guarded above)."""
            if s.adps is not None and aniso:
                # TOPAS u_ij are U^ij (Å², CIF convention) — see `_ADP_KEYS`.
                # `biso` is the schema's inert record when `aniso` is present
                # (vary must be False): the file's own beq where stated, else
                # 8π²·U_eq from the trace — the same fallback the CIF path
                # uses — never the 0.5 seed over a stated tensor.
                b_record = (s.beq if s.beq is not None else
                            8.0 * math.pi ** 2
                            * (s.adps["u11"] + s.adps["u22"] + s.adps["u33"]) / 3.0)
                block = rx.AnisoU(**{
                    u: rx.Parameter(value=s.adps.get(u, 0.0), unit="A^2",
                                    **({"vary": s.vary[u]} if u in s.vary else {}))
                    for u in _ADP_KEYS})
                displacement = {
                    "biso": rx.Parameter(value=b_record, vary=False,
                                         **biso_bounds(b_record)),
                    "aniso": block}
            else:
                # The file's own number, not `max(beq, 0.0)`: a negative one is
                # kept rather than moved. A site that stated none is
                # seeded 0.5 here, at build time — the model keeps it as None.
                b_iso = 0.5 if s.beq is None else s.beq
                displacement = {"biso": _sp(s, "beq", b_iso,
                                            **biso_bounds(b_iso))}
            magnetic = {}
            if s.moment is not None and ph.name in magnetic_specs:
                # `mlx/mly/mlz` are fractional-basis components (see
                # `TopasSite.moment`), so the crystal-axis mu_B rietx stores is
                # each one times its own edge in Å — `MM_CrystalAxis_Display`'s
                # mxc = mlx*a — never a rotation, on any cell. The edges are
                # the ones the `Cell` below is built from. A component the file
                # did not state is 0, which is what a moment along one axis
                # writes. The ion is the
                # site's own species where TOPAS wrote a charge (`occ Cr+3`
                # normalises to `Cr3+`, which is a magnetic form-factor key);
                # where it did not, the neutral atom is used and the diagnostic
                # says so, because <j0> for Mn and for Mn3+ are different
                # curves.
                edges = (c["a"], c.get("b", c["a"]), c.get("c", c["a"]))
                magnetic["moment"] = rx.Moment.from_values(
                    [s.moment.get(k, 0.0) * edge
                     for k, edge in zip(_MOMENT_COMPONENT_KEYS, edges)],
                    ion=s.species,
                    g=s.moment.get("mg"),
                    vary=any(s.vary.get(k) for k in _MOMENT_COMPONENT_KEYS))
            return rx.Atom(label=s.label, species=s.species,
                           x=_sp(s, "x", s.x), y=_sp(s, "y", s.y),
                           z=_sp(s, "z", s.z),
                           occ=_sp(s, "occ", s.occupancy), **displacement,
                           **magnetic)

        # Every schema refusal from here is converted at this boundary: a
        # reader raises naming the file, and pydantic's report names a field.
        # Reached in practice by a phase whose site lines all sat inside a
        # disabled #ifdef branch, which arrives as "phase has no atoms".
        #
        # `rx.Cell(...)` and the `atoms` comprehension used to sit *above* this
        # try, one line up from the only handler that converts them — so
        # `beq bA 26.0` left as a raw `pydantic_core.ValidationError`. The
        # truncation pin cannot catch that class: a ragged cut rarely leaves a
        # well-formed line carrying an out-of-range number, so the case has its
        # own test.
        try:
            cell = rx.Cell(a=_p("a", c["a"]), b=_p("b", c["a"]), c=_p("c", c["a"]),
                           alpha=_p("al", 90.0), beta=_p("be", 90.0),
                           gamma=_p("ga", 90.0))
            atoms = [_atom(s) for s in ph.sites]
            phases.append(rx.Phase(
                name=ph.name,
                space_group=(nuclear_groups[ph.name].xhm()
                             if ph.name in nuclear_groups else ph.space_group),
                symmetry_operations=(
                    list(nuclear_groups[ph.name].xyz)
                    if isinstance(nuclear_groups.get(ph.name), OperatorGroup)
                    else None),
                cell=cell, atoms=atoms,
                magnetic_symmetry=magnetic_specs.get(ph.name),
                # `or 1e-4` substituted the seed for a *stated* zero: 20 real
                # phases across 9 files record `scale 0`, a phase refined to
                # absent, and this repo already treats that as a real state
                # (`weight_percent cBN_wtpct 0.000`). None is the only absence.
                scale=rx.Parameter(value=1e-4 if ph.scale is None else ph.scale,
                                   min=0.0, transform="softplus",
                                   **({"vary": ph.vary["scale"]}
                                      if "scale" in ph.vary else {}))))
            from ...crystallography.magnetic.scattering import check_group_is_structure_symmetry
            check_group_is_structure_symmetry(phases[-1])
        except TopasInpError:
            raise
        except Exception as exc:
            raise TopasInpError(
                f"{model.path or '<model>'}: phase {ph.name!r}: {exc}") from exc

    # Report or refuse, never drop — the skipped-block half (WP-1118). A `str`
    # block that could not be read as a phase but *plainly states a cell or a
    # site* is a phase in all but its name, and `skipped_blocks` was quoted only
    # in the zero-phase branch below — so when another phase read, the nameless
    # one vanished and the weight fractions no longer summed, silently. There is
    # no diagnostics channel on this branch to report through on a successful
    # return (io/CLAUDE.md: a reader repairs only where it can say it did), so
    # the choice consistent with "report or refuse, never drop" and with the
    # dropped-site and no-cell hard errors this reader already raises is to
    # refuse, naming what was dropped.
    carrying = [sb for sb in model.skipped_blocks if sb.cell or sb.n_sites]
    if phases and carrying:
        # The pronouns agree in number with the blocks, as the verbs already do:
        # "1 block … states … so IT cannot be built — and dropping IT", "2
        # blocks … state … so THEY cannot be built — and dropping THEM".
        one = len(carrying) == 1
        raise TopasInpError(
            f"{model.path or '<model>'}: {len(carrying)} `str` block"
            f"{'' if one else 's'} here state"
            f"{'s' if one else ''} a cell or a site "
            f"but no phase_name/space_group, so {'it' if one else 'they'} "
            f"cannot be built — and "
            f"dropping {'it' if one else 'them'} while {len(phases)} other phase"
            f"{'' if len(phases) == 1 else 's'} build"
            f"{'s' if len(phases) == 1 else ''} would leave the weight "
            f"fractions no longer summing. " + "; ".join(str(sb) for sb in carrying)
            + f"; {_skipped_remedy(carrying)}, or read `model.phases` for what "
            f"the file does state.")

    if not phases:
        # Never "this file has no phases" about a file whose `str` blocks this
        # reader saw and could not name: that is the same confident wrong
        # diagnosis a UTF-16 decode and a `STR(` macro used to get.
        why = ("A Pawley or indexing-only .inp is legal and has none"
               if not model.skipped_blocks else
               f"{len(model.skipped_blocks)} `str` block"
               f"{'' if len(model.skipped_blocks) == 1 else 's'} here could not "
               f"be read as a phase — "
               + "; ".join(str(sb) for sb in model.skipped_blocks)
               + f"; {_skipped_remedy(model.skipped_blocks)}")
        raise TopasInpError(
            f"{model.path or '<model>'}: no phase carries a cell, so there is no "
            f"structure to build. {why} — read `model.phases` directly for what "
            f"it does state.")
    try:
        structure = rx.Structure(phases=phases)
    except Exception as exc:
        # e.g. a phase whose site lines were all inside a disabled #ifdef branch
        raise TopasInpError(f"{model.path or '<model>'}: {exc}") from exc
    if diagnostics is not None and (
            widened := biso_widening_diagnostic(structure, str(model.path or '<model>'))) is not None:
        diagnostics.append(widened)
    return structure


def _tail(param: Parameter) -> str:
    """One value grammar, one direction: ``@ <value>`` (free) or ``! <value>``
    (held) — Technical Reference §2.1's ``@``/``!`` spellings, never the bare
    "a name is itself the refine flag" form, so nothing here depends on a
    symbol table. ``repr`` rather than a fixed format: it is the shortest
    decimal that reads back to the same double (:func:`_arith`/``_NUM`` parse
    ordinary decimal and exponent notation alike), which is what a *value*
    round trip needs — a fixed precision would round every number written.

    A **non-finite** value is refused. ``Parameter`` does not forbid one and a
    converged fit cannot reach one, but ``repr`` spells it ``inf``/``nan``,
    which TOPAS does not parse — so the file would be written and fail
    somewhere else, in someone else's program. Surfaced by the review pass on
    this writer and answered for all three GSAS/TOPAS/FullProf writers at once
    (WP-1118). The check lives in :func:`_number`, not here, because an
    anisotropic site's ``beq`` is the one number this writer spells without a
    tail — held unconditionally, whatever its ``vary`` says — and a guard only
    the tail carried would have let exactly that one through.
    """
    return f"{'@' if param.vary else '!'} {_number(param.value)}"


def _number(value: float) -> str:
    """One value, as the shortest decimal that reads back to the same double.

    See :func:`_tail` for why ``repr``, and for why the non-finite refusal is
    at this rank rather than one up.
    """
    if not math.isfinite(value):
        raise ValueError(
            f"a parameter's value is {value!r}, which `repr` spells "
            f"'{value}' and TOPAS does not parse — refused here rather "
            f"than written into a file that fails in another program")
    return repr(value)


def _operation_set(group) -> frozenset[str]:
    """A nuclear group's operations as a set, translations wrapped into [0, 1).

    ``gemmi.SpaceGroup`` and :class:`~...symmetry.OperatorGroup` both answer
    ``operations()``, so a symbol and a list compare as the groups they are,
    never by spelling.
    """
    return frozenset(op.wrap().triplet() for op in group.operations())


def _magnetic_group_line(phase) -> str | None:
    """The ``mag_space_group`` value to write for ``phase``, or a refusal.

    ``None`` for a nuclear phase.  TOPAS names a magnetic group only by its
    BNS number or symbol from its own table (Technical Reference § 13,
    ``[mag_space_group $symbol]``; there is no operator-list form), and
    :func:`to_structure` resolves a number to spglib's **standard-setting**
    operators.  So the writer states the number exactly when the phase's
    operator set *is* that number's standard setting, and refuses by name
    otherwise, because the file would propagate the moments over a
    different group than the one they refined under.  Three more things
    TOPAS's ``str`` cannot state are refused rather than dropped:

    * a phase whose **nuclear** group is not the magnetic group's family group
      (its operations with time reversal dropped).  TOPAS generates a magnetic
      ``str``'s atoms with the magnetic operators, and TOPAS's own magnetic
      examples comment ``space_group`` out beside ``mag_space_group``, so the
      writer states no ``space_group`` and the reader derives the family group
      (tier 2 of :func:`~...magcif.resolve_nuclear_symmetry`).  A phase refined
      under a larger parent (issue #457's tier 1, Cr₂WO₆'s ``Pn'nm`` in
      ``P4₂/mnm``) lists one site per *parent* orbit, which the magnetic group
      splits, so part of each such orbit would vanish from the file;
    * a magnetic group on a phase with **no** site moment: the reader carries
      no group back for it (:func:`_magnetic_specs`), so the write would lose
      it — and a group with no moment constrains nothing;
    * a **propagation vector** in either of its two forms: the parent k a
      supercell records (``MagneticSymmetry.propagation_vector_parent``) and
      a phase's own k hypothesis (``Phase.propagation_vector``).  A ``str``
      states neither, and the file would read back as k = 0 in its cell.
    """
    from ...crystallography.magcif import MagCifError, resolve_nuclear_symmetry
    from ...crystallography.magnetic.operators import identification
    from ...crystallography.symmetry import resolve_group
    from ...schemas.structure import MagneticSymmetry

    where = f"phase {phase.name!r} cannot be written to a TOPAS `.inp`"
    if getattr(phase, "propagation_vector", None) is not None:
        raise ValueError(
            f"{where}: it carries the propagation vector k = "
            f"({', '.join(phase.propagation_vector)}), and a TOPAS `str` has no "
            f"keyword for one, so the file would read back as k = 0. The "
            f"Structure's own JSON (Structure.model_dump_json) carries a k "
            f"hypothesis; no CIF this package writes does")
    mag = phase.magnetic_symmetry
    if mag is None:
        return None
    moments = [a for a in phase.atoms if a.moment is not None]
    if not moments:
        raise ValueError(
            f"{where}: it carries a magnetic group and no site moment, and a "
            f"TOPAS reader builds no magnetic group for a phase whose sites "
            f"state no mlx/mly/mlz, so the group would be lost on the way "
            f"back. A group with no moment constrains nothing; drop "
            f"magnetic_symmetry, or give the magnetic sites their moments")
    if mag.propagation_vector_parent is not None:
        raise ValueError(
            f"{where}: it is a magnetic supercell built from the parent "
            f"propagation vector k = ({', '.join(mag.propagation_vector_parent)}"
            f"), and a TOPAS `str` has no keyword for the parent k, so the file "
            f"would read back as a k = 0 structure in this cell. A magCIF "
            f"(Structure.to_cif) states it the same way, as k = 0 in this "
            f"cell, and drops the parent k too; the Structure's own JSON "
            f"(Structure.model_dump_json) is the export that keeps it")
    group = mag.group()
    found = identification(group)
    if not found.named:
        raise ValueError(
            f"{where}: its magnetic group ({group.order} operations) is not "
            f"one of the tabulated magnetic space groups ({found.reason}), and "
            f"TOPAS states a magnetic group only by its number or symbol. A "
            f"magCIF (Structure.to_cif) carries the operator list")
    number = found.bns_number
    standard = MagneticSymmetry.model_validate(number)
    if set(standard.group().all_operations()) != set(group.all_operations()):
        raise ValueError(
            f"{where}: its magnetic group is BNS {number} in a setting other "
            f"than the standard one, and TOPAS's `mag_space_group {number}` "
            f"generates the standard setting's operators, so the moments "
            f"would be propagated over a different set of operations than the "
            f"one they refined under. Transform the phase to the standard "
            f"setting first, or export a magCIF (Structure.to_cif), which "
            f"carries the operator list")
    try:
        family = resolve_nuclear_symmetry(None, standard, f"phase {phase.name!r}",
                                          nuclear_group="file")
    except MagCifError as exc:  # pragma: no cover - a named group has a family
        raise ValueError(f"{where}: {exc}") from exc
    nuclear = resolve_group(phase.space_group, phase.symmetry_operations)
    if _operation_set(family) != _operation_set(nuclear):
        raise ValueError(
            f"{where}: its positions refine under {phase.space_group!r} and "
            f"its moments under BNS {number}, whose family group (its "
            f"operations with time reversal dropped) is {family.xhm()!r}. A "
            f"TOPAS magnetic `str` generates its atoms with the magnetic "
            f"operators alone, so the sites listed for the larger group would "
            f"each generate only part of their orbit. Restate the phase under "
            f"{family.xhm()!r} (a magCIF read with nuclear_group='file' does "
            f"this), or export a magCIF (Structure.to_cif)")
    for atom in moments:
        if atom.moment.ion != atom.species:
            raise ValueError(
                f"{where}: site {atom.label!r} has species {atom.species!r} "
                f"and magnetic ion {atom.moment.ion!r}, and TOPAS takes the "
                f"magnetic form factor from the site's `occ` species, so the "
                f"file cannot state the two apart. Set the species to the ion "
                f"(or the ion to the species) first")
    return number


def from_structure(structure: Structure, *,
                   diagnostics: list[Diagnostic] | None = None) -> str:
    """Serialise ``structure`` as TOPAS ``.inp`` text — the inverse of
    :func:`to_structure`.

    Carries exactly what :func:`to_structure` reads back and nothing more:
    per phase, the space group, the six cell edges, and every atom's
    coordinates, occupancy and displacement (isotropic ``beq`` or, when
    ``atom.aniso`` is set, the six ``u11``…``u23`` components alongside a
    held ``beq`` record — the same asymmetry :func:`to_structure` builds).
    Each :class:`~rietx.schemas.Parameter`'s own ``vary`` is written as the
    format's ``@``/``!`` flag, never a bare backtick, so reading the file back
    needs no symbol table to recover it (WP-1118's own finding: a *name* also
    means "free" in TOPAS's primary spelling, but that form ties the flag to
    a fresh symbol per parameter for no gain here).

    **A magnetic phase** (WP-1328) is written the way TOPAS's own magnetic
    examples state one: ``mag_space_group`` with the BNS number and no
    ``space_group``, and on each moment-bearing site ``mlx mly mlz`` in
    TOPAS's fractional basis (the stored crystal-axis μ_B divided by the
    edge, :func:`_moment_tail`) plus ``mg`` where a Landé g is stated.  The
    round trip returns each component within one ulp, most to the bit.
    What such a ``str`` cannot state is refused by name
    (:func:`_magnetic_group_line`): a group in a non-standard setting or with
    no number, a nuclear group larger than the magnetic group's family group,
    a group with no moment, a magnetic ion different from the site's species,
    and a propagation vector in either form.  ``mag_only`` and
    ``mag_only_for_mag_sites`` are never written, because the model has no
    magnetic-only phase; nor is a Fourier-component moment, which the model
    has no form for.  The group's ``symbol`` rides as a comment and its
    ``setting``/``og_number``/``uni_number`` come back as the number's own.

    **What does not round-trip, because it is not built from a ``.inp`` at
    all**: the emission profile and instrument geometry TOPAS states are on
    ``TopasModel``, not ``Structure`` — :func:`to_structure` never builds an
    ``Instrument`` — and cell/site bound windows (``min``/``max``) are
    dropped rather than written, since :func:`to_structure`'s own ``_p()``
    only ever narrows a *stated* bound and a Structure carries no window a
    caller cannot already see on the ``Parameter`` itself. Extinction,
    preferred orientation and sample broadening are not TOPAS constructs
    :func:`to_structure` reads either, so a phase carrying a non-default
    value there loses it in silence — the same silence :func:`to_structure`
    itself keeps about them on the way in, so this is symmetric rather than a
    new gap.

    Space groups are written ``get_spacegroup(phase.space_group).xhm()``,
    never the phase's own stored spelling: the ``:1``/``:2``/``:H``/``:R``
    suffix a bare symbol can leave ambiguous is what a reader may have
    *resolved* (root CLAUDE.md § "Where a file states its symmetry twice"),
    and re-exporting the stored string would launder that resolution back
    into the ambiguous form. ``normalize_space_group`` only strips a
    *trailing* TOPAS-shaped suffix letter (``Z``/``S``/``R``/``H``), so a
    colon-suffixed ``xhm()`` string passes through unrecognised and lands on
    ``phase.space_group`` exactly as written; compare space groups with
    ``get_spacegroup(...).xhm()`` on both sides, not by string, since the
    written spacing (``"P n -3 m"``) need not match a caller's own.

    A species is written as the atom rietx computes, in TOPAS's spelling
    (:func:`topas_species`), and none is refused. Where rietx computes the
    neutral atom for an ion its table lacks (``Fe+``), the file states the
    neutral element. Pass ``diagnostics=`` a list to have each such label
    named, ``TOPAS_SPECIES_WRITTEN_NEUTRAL``. A site carrying a moment keeps
    its ion (``Fe4+`` → ``Fe+4``), since TOPAS reads the magnetic form factor
    from it and rietx computes the moment from that ion.

    Four refusals besides the phase-name quote check above, the fourth being
    :func:`_tail`'s on a non-finite value. A label or
    species carrying whitespace: a ``site`` line is space-separated, so an
    embedded space is read back as an extra, silently dropped token rather
    than part of the name. A label or species carrying a single quote:
    unlike ``phase_name``, a site's label and species are not quoted, so an
    unquoted ``'`` opens a line comment (:func:`strip_comments`) and drops
    everything after it on that line, x/y/z/occ/beq included.
    """
    from ..._about import DIST_NAME

    lines: list[str] = [f"' Written by {DIST_NAME}.io.projects.topas.write_topas_inp"]
    for phase in structure.phases:
        if '"' in phase.name:
            raise ValueError(
                f"phase name {phase.name!r} cannot be written to a TOPAS "
                f"`.inp`: it contains a double quote, which the reader takes "
                f"as the closing one")
        if "\n" in phase.name or "\r" in phase.name:
            raise ValueError(
                f"phase name {phase.name!r} cannot be written to a TOPAS "
                f"`.inp`: it carries a line break, and an `.inp` is read line "
                f"by line — the name comes back cut at the break, a silent "
                f"rename rather than a failure, and the remainder is read as "
                f"a keyword line of its own.  The same accident the `.EXP` "
                f"writer's `write_record` refuses one format over")
        refuse_operation_list(phase, "a TOPAS `.inp`")
        magnetic_number = _magnetic_group_line(phase)
        lines.append("str")
        lines.append(f'  phase_name "{phase.name}"')
        if magnetic_number is None:
            sg = get_spacegroup(phase.space_group).xhm()
            lines.append(f'  space_group "{sg}"')
        else:
            # No `space_group` beside it: TOPAS generates a magnetic `str`'s
            # atoms with the magnetic operators, and the reader derives the
            # nuclear group from the number (`_magnetic_group_line` checked
            # that it is this phase's own). The symbol is metadata the number
            # does not carry, so it rides as a comment, the way ISODISTORT's
            # TOPAS export writes `'BNS:1.1 P1`, and is not read back.
            lines.append(f"  mag_space_group {magnetic_number}")
            symbol = phase.magnetic_symmetry.symbol
            if symbol and "\n" not in symbol and "\r" not in symbol:
                lines.append(f"  ' magnetic group symbol (not read): {symbol}")
        lines.append(f"  scale {_tail(phase.scale)}")
        cell = phase.cell
        for key, param in (("a", cell.a), ("b", cell.b), ("c", cell.c),
                           ("al", cell.alpha), ("be", cell.beta),
                           ("ga", cell.gamma)):
            lines.append(f"  {key} {_tail(param)}")
        for atom in phase.atoms:
            if any(ch.isspace() for ch in atom.label) or any(
                    ch.isspace() for ch in atom.species):
                raise ValueError(
                    f"phase {phase.name!r}: atom label {atom.label!r} / "
                    f"species {atom.species!r} contains whitespace, which a "
                    f"`site` line cannot carry — the line is space-separated "
                    f"and a space inside either field is read as an extra, "
                    f"silently dropped token rather than part of the name")
            if "'" in atom.label or "'" in atom.species:
                raise ValueError(
                    f"phase {phase.name!r}: atom label {atom.label!r} / "
                    f"species {atom.species!r} contains a single quote — "
                    f"unlike `phase_name`, a `site` line's label and species "
                    f"are not quoted, so `strip_comments` reads an unquoted "
                    f"``'`` as opening a line comment and drops everything "
                    f"after it on that line, including x/y/z/occ/beq")
            # A magnetic site keeps its ion. TOPAS takes the magnetic form
            # factor from the `occ` species, and rietx computes the moment's
            # from that ion (moment.ion == species, checked above), so the
            # X-ray table's fallback (Fe4+ → Fe) is not what rietx computed.
            species = (topas_species(atom.species) if atom.moment is None
                       else _sign_first(atom.species))
            site = (f"  site {atom.label} x {_tail(atom.x)} y {_tail(atom.y)} "
                    f"z {_tail(atom.z)} occ {species} {_tail(atom.occ)}")
            if atom.aniso is not None:
                # `to_structure` always builds an aniso site's `biso` held
                # (`vary=False`) — it is the schema's inert record, not a
                # refinable column — so the write-back forces `!` rather than
                # trusting `atom.biso.vary`, which keeps a malformed input
                # Structure from round-tripping into a file that lies about
                # which number the fit actually moved.
                tensor = " ".join(f"{u} {_tail(getattr(atom.aniso, u))}"
                                  for u in _ADP_KEYS)
                site = f"{site} beq ! {_number(atom.biso.value)} {tensor}"
            else:
                site = f"{site} beq {_tail(atom.biso)}"
            if atom.moment is not None:
                site = f"{site} {_moment_tail(atom.moment, cell)}"
            lines.append(site)
    if diagnostics is not None:
        from ...crystallography.scattering import written_neutral_diagnostics
        diagnostics.extend(written_neutral_diagnostics(
            structure, code="TOPAS_SPECIES_WRITTEN_NEUTRAL", program="TOPAS"))
    return "\n".join(lines) + "\n"


def _moment_tail(moment, cell) -> str:
    """``mlx … mly … mlz … [mg …]`` for one site: :func:`to_structure` inverted.

    The stored components are crystal-axis μ_B and ``mlx mly mlz`` are
    fractional-basis ones (:attr:`TopasSite.moment`, measured against TOPAS),
    so each is divided by its own edge.  ``(m / a) * a`` is not always ``m``
    in floating point, and no neighbouring double does better: over 20 000
    moments on real edges 88 % come back to the bit and every other one
    within one ulp, and trying the quotient's two neighbours hit on none of
    the misses (``test_projects_topas``'s
    ``test_write_topas_inp_moment_round_trips_within_one_ulp``).  One
    refine flag for all three, because the block is what refines — the
    components' ``vary`` is the intent that frees the moment's DOFs
    (:class:`~rietx.schemas.structure.Moment`) — and the reader gives all
    three the flag any one of them carries.  ``mg`` is written only where the
    model states a Landé g: ``None`` is the spin-only default, which TOPAS
    takes from its own table.
    """
    flag = "@" if moment.vary else "!"
    parts = [f"{key} {flag} {_number(value / edge)}"
             for key, value, edge in zip(
                 _MOMENT_COMPONENT_KEYS, moment.values(),
                 (cell.a.value, cell.b.value, cell.c.value))]
    if moment.g is not None:
        parts.append(f"mg ! {_number(moment.g)}")
    return " ".join(parts)


def write_topas_inp(structure: Structure, path: str | Path, *,
                    diagnostics: list[Diagnostic] | None = None) -> None:
    """Write ``structure`` to ``path`` as a TOPAS ``.inp``. See
    :func:`from_structure` for exactly what carries and what does not."""
    Path(path).write_text(from_structure(structure, diagnostics=diagnostics),
                          encoding="utf-8")
