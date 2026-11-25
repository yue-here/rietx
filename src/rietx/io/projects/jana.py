"""Jana ``.m50``/``.m40``/``.m41`` project reader (WP-1314, first slice).

A Jana refinement is a file *set* sharing one stem: ``.m50`` states the crystal
(cell, symmetry, atom types, and the program control sections), ``.m40`` the
structure parameters with their refinement keys, and ``.m41`` the powder
profile and instrument parameters with theirs. :func:`read_jana` takes any one
of the three (or the stem) and reads the set into a :class:`JanaModel`, which
is what the files state and nothing seeded; :func:`to_structure` builds a
:class:`~rietx.schemas.Structure` from it, carrying the refinement keys onto
``vary``.

**Specification, and how thin it is.** Written from Jana's own documentation
with every program source closed (``ATTRIBUTION.md`` row "Jana"):

- [M98] Petříček & Dušek, *JANA98 — The crystallographic computing system*
  (manual, Praha 2000), § 2.2.8 and Table 9 (pp. 77–82) for the ``.m50``
  keyword grammar, § 3.1.1 and Table 10 (pp. 93–121) for the ``.m40`` layout
  in symbolic form, the refinement-key rule (p. 97) and the U-form
  temperature factor (E14, p. 120), and the REFINE section's ``autkeys``
  default (p. 236).
- [M2000] Petříček & Dušek (eds. Dušek, Petříček, Fejfarová, Palatinus),
  *Jana2000 user manual, part 1* (Praha 2003), pp. 31 and 50–54: the
  multiphase powder organisation of all three files, and the only annotated
  ``.m41`` there is.

Jana2006 and Jana2020 publish **no** file-format description (the Jana98 and
Jana2000 part-1 manuals are the only ones the authors list), so this reader
implements the Jana98/Jana2000 grammar and refuses anything outside it by
name. Neither manual states a Fortran format or a column range for any record,
so numbers are read as a stream of decimal numbers rather than by column
(Jana's numbers run together when a negative value fills its field, as in
``0.500000-0.063340``), and every number is required to carry a decimal point,
which separates it from the digit-only refinement-key string that ends a
keyed line.

**The refinement keys** (M98 p. 97): a keyed line states its values, then one
digit per value, ``1`` refined and ``0`` fixed. On an atom's displacement line
the ten keys cover occupancy, x, y, z, then U11..U23. REFINE's **automatic
mode** ignores the ``.m40`` keys of everything except scales, occupancies and
twin volumes and refines "all refinable parameters" (M98 p. 225, Table 13),
and M98 gives ``autkeys 1`` as the default (p. 236). The keys are carried as
written either way; a set that does not state ``autkeys 0`` in its REFINE
section is reported (``JANA_KEYS_MAY_BE_IGNORED``), because then the file does not
establish that its keys are the refined set.

**Refused by name** (:class:`JanaError`), each a construct whose model a
:class:`~rietx.schemas.Structure` cannot hold or this grammar cannot place:
modulation (``ndim`` > 3, ``qi``/``qr``, ``commen``/``tzero``, a superspace
group symbol, a non-zero wave count on an atom, the ``.m40`` commands
section), composites (``ncomp`` > 1, ``wmatrix``), twins, rigid-body
molecules, anharmonic and TLS displacement, the beta form of the temperature
factor, and any ``.m50`` keyword outside Table 9 — which is where a Jana2006 or
Jana2020 magnetic or other newer construct lands, since no document describes
those keywords. A commensurate magnetic phase therefore refuses here, unlike
the TOPAS and ``.pcr`` readers (WP-1328): the reader cannot recognise one
without a description of how Jana writes it.

**Unverified assumptions.** Three conventions come from the manuals' prose
alone and have not been measured against Jana's own output, which root
``CLAUDE.md`` § Conventions requires of a foreign format's unit: ``ai`` as the
occupancy over the site's symmetry order (M98 p. 116, whose "multiplicity"
reads either as that order or as the Wyckoff multiplicity, a factor of two
apart on 2a of Pbam), the ``.m40`` displacement parameters as U in Å² with
Biso = 8π²·U (M98 E14, p. 120), and the ``.m41`` cell in Å and degrees (M2000
pp. 50-54). The reference output that settles all three is the CIF Jana
exports of a refinement with an atom on a special position, read here and
compared field by field; no such pair is in reach (WP-1314's task to verify
them). Until that task is done the reader stays out of ``PROJECT_FORMATS``,
so nothing dispatches to it and every caller names it.

**A statement made twice is refused, not picked** (``io/CLAUDE.md``): a
single-valued ``.m50`` keyword repeated in its scope (the file, a phase, an
atom type), a repeated ``autkeys``, and a second REFINE section, since no page
of either manual says which of two such statements Jana uses.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ...schemas.common import Diagnostic

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ...schemas import Structure

EIGHT_PI_SQUARED = 8.0 * math.pi ** 2

SUFFIXES = (".m50", ".m40", ".m41")

#: The ``.m40`` displacement line's six tensor keys, in its order (M98 p. 118),
#: which is ``adp_basis``'s Voigt order.
U_LABELS = ("U11", "U22", "U33", "U12", "U13", "U23")

#: A Jana number: always written with a decimal point, optionally signed, with
#: an optional exponent (``E`` or Fortran's ``D``).  Requiring the point is what
#: tells a value from the digit-only refinement-key string after it.
_NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eEdD][-+]?\d+)?")

#: The standard centring translations of each lattice letter (ITA Vol. A,
#: Table 1.5.4.1), applied to the operator list a ``.m50`` writes, which M98
#: p. 81 says omits them.
_CENTRING = {
    "P": [(0, 0, 0)],
    "A": [(0, 0, 0), (0, .5, .5)],
    "B": [(0, 0, 0), (.5, 0, .5)],
    "C": [(0, 0, 0), (.5, .5, 0)],
    "I": [(0, 0, 0), (.5, .5, .5)],
    "F": [(0, 0, 0), (0, .5, .5), (.5, 0, .5), (.5, .5, 0)],
    "R": [(0, 0, 0), (2 / 3, 1 / 3, 1 / 3), (1 / 3, 2 / 3, 2 / 3)],
}


class JanaError(ValueError):
    """A Jana file set this reader cannot read or convert, naming the file."""


# ---------------------------------------------------------------- the stances
#
# One stance per ``.m50`` keyword of M98 Table 9 (pp. 80-82) plus six it
# carries without a Table 9 row, with its arity.  A keyword not here is
# refused, so this table is the reader's whole ``.m50`` vocabulary.  The six:
#   - ``monangle`` and ``end``: M98's own ``.m50`` listing (Figure 55, p. 78),
#     which writes them though Table 9 does not list them;
#   - ``lattvec``: Table 9 prints the entry as ``lattvect``, while its own
#     text names "the lattvec command" (pp. 81, twice), which is the spelling
#     taken;
#   - ``phase``, ``chemform`` and ``datcolltemp``: the Jana2000 part-1
#     multiphase listings (M2000 pp. 50-54; ``phase`` and the table layout at
#     p. 53), which M98 does not describe.
# Arity: an int is that many tokens; "line" takes the rest of its line;
# "ndim" takes three (the only dimension read); "formtab" takes a count and
# then that many numbers.

@dataclass(frozen=True)
class Stance:
    """What the reader does with one ``.m50`` keyword, and why."""

    arity: int | str
    stance: str  # "read", "ignored" or "refused"
    why: str


M50_STANCES: dict[str, Stance] = {
    "title": Stance("line", "read", "the set's title"),
    "cell": Stance(6, "read", "the phase's cell"),
    "esdcell": Stance(6, "read", "the cell's esds; not carried onto a Structure"),
    "lambda": Stance(1, "read", "the wavelength"),
    "radtype": Stance(1, "read", "1 X-rays, 2 neutrons"),
    "lpfactor": Stance(1, "read", "monochromator geometry; not carried"),
    "monangle": Stance(1, "read", "monochromator angle; not carried"),
    "datcolltemp": Stance(1, "read", "measurement temperature; not carried"),
    "spgroup": Stance("line", "read", "symbol, number and crystal system; "
                      "the setting is taken from the operators"),
    "lattice": Stance(1, "read", "the centring letter"),
    "lattvec": Stance("ndim", "read", "an explicit centring vector"),
    "centro": Stance(0, "read", "inversion at the origin, its images not listed"),
    "symmetry": Stance("line", "read", "one operator; three components only"),
    "sgshift": Stance("ndim", "read", "origin shift in ITA's convention (M98 "
                      "p. 81); no page says the listed operators include it, "
                      "so a nonzero shift is refused at build"),
    "ndim": Stance(1, "read", "above 3 is a modulated structure: refused"),
    "ncomp": Stance(1, "read", "above 1 is a composite: refused"),
    "qi": Stance(3, "refused", "a modulation vector"),
    "qr": Stance(3, "refused", "a modulation vector"),
    "wmatrix": Stance(0, "refused", "composite matrices"),
    "commen": Stance(3, "refused", "a commensurate modulated refinement"),
    "tzero": Stance(1, "refused", "a commensurate modulated refinement"),
    "twin": Stance(0, "refused", "twin domains, which a powder Structure "
                   "cannot hold"),
    "unitsnumb": Stance(1, "read", "formula units per cell; not carried"),
    "chemform": Stance("line", "read", "the formula; not carried"),
    "atom": Stance(1, "read", "opens one atom type; .m40's type index counts these"),
    "atweight": Stance(1, "read", "atomic weight; not carried"),
    "atradius": Stance(1, "read", "atomic radius; not carried"),
    "dmax": Stance(1, "ignored", "a distance limit for listings"),
    "formula": Stance(1, "read", "atoms of this type per formula unit; not carried"),
    "f'": Stance(1, "read", "anomalous f'; rietx computes its own"),
    'f"': Stance(1, "read", "anomalous f''; rietx computes its own"),
    "fneutron": Stance(1, "read", "neutron scattering length; rietx uses its own"),
    "formtab": Stance("formtab", "ignored", "a tabulated form factor; rietx "
                      "uses its own"),
    "noofref": Stance(1, "ignored", "a reflection count for single-crystal data"),
    "slimits": Stance(8, "ignored", "R-factor statistics limits"),
    "flimits": Stance(8, "ignored", "R-factor statistics limits"),
    "phase": Stance("line", "read", "opens one powder phase (M2000 p. 53)"),
    "end": Stance(0, "read", "closes part I"),
}

#: REFINE section commands that tie or fix parameters beyond the ``.m40`` keys
#: (M98 p. 224).  Their grammar is not described closely enough to apply, so a
#: set using one is read and the commands are reported as not carried.
CONSTRAINT_COMMANDS = ("equation", "restric", "fixed", "keep")

#: The single-valued ``.m50`` keywords, by the scope a statement of one holds
#: for: the whole set (M2000 p. 53 puts the experiment keywords before the
#: first ``phase``), one phase, or one ``atom`` block.  A second statement in
#: the same scope is refused rather than letting the later one win in silence
#: (``io/CLAUDE.md``: "A row the format states two ways is refused, not
#: picked").  The repeatable keywords (``symmetry``, ``lattvec``, ``atom``,
#: ``phase``) and the ignored ones are in none of the three.
ONCE_PER_SET = frozenset({"title", "lambda", "radtype", "lpfactor", "monangle",
                          "datcolltemp"})
ONCE_PER_PHASE = frozenset({"cell", "esdcell", "spgroup", "lattice", "centro",
                            "sgshift", "ndim", "ncomp", "unitsnumb", "chemform"})
ONCE_PER_ATOM_TYPE = frozenset({"atweight", "atradius", "formula", "f'", 'f"',
                                "fneutron", "formtab"})


# ------------------------------------------------------------- the model

@dataclass
class JanaAtomType:
    """One ``atom`` block of a ``.m50`` phase."""

    symbol: str
    values: dict[str, float] = field(default_factory=dict)


@dataclass
class JanaPhase:
    """One phase as the ``.m50`` states it (a single-phase set has one, unnamed)."""

    name: str | None = None
    cell: tuple[float, ...] | None = None
    esdcell: tuple[float, ...] | None = None
    space_group: str | None = None
    space_group_number: int | None = None
    crystal_system: int | None = None
    lattice: str = "P"
    lattvec: list[tuple[float, float, float]] = field(default_factory=list)
    centro: bool = False
    symmetry: list[str] = field(default_factory=list)  # x1/x2/x3 read as x/y/z
    sgshift: tuple[float, ...] | None = None
    atom_types: list[JanaAtomType] = field(default_factory=list)
    other: dict[str, str] = field(default_factory=dict)


@dataclass
class Keyed:
    """A keyed line (or lines): its values and one refinement key per value."""

    values: list[float]
    keys: list[bool]


@dataclass
class JanaAtom:
    """One ``.m40`` atom of the non-modulated layout (M98 pp. 116-120)."""

    label: str
    type_index: int  # 1-based index into the phase's ``atom_types``
    adp_type: int    # 1 isotropic, 2 anisotropic
    ai: float        # occupancy x site multiplicity / general multiplicity
    xyz: tuple[float, float, float]
    adp: tuple[float, ...]   # U11 U22 U33 U12 U13 U23 (U in U11 when isotropic)
    keys: tuple[bool, ...]   # ai, x, y, z, U11..U23
    # half a unit in each token's own last printed digit, as the CIF reader
    # reads a file's precision (cif._printed_half); no width is assumed
    ai_half: float = 0.0
    adp_half: tuple[float, ...] = ()


@dataclass
class JanaM41Phase:
    """One ``### phase`` block of a ``.m41``: its keyed sections by title."""

    name: str | None
    sections: dict[str, Keyed] = field(default_factory=dict)


@dataclass
class JanaModel:
    """What a Jana file set states, unseeded: ``None`` where a file is silent."""

    path: str
    files: dict[str, str]
    title: str | None = None
    wavelength: float | None = None
    radtype: int | None = None
    experiment: dict[str, str] = field(default_factory=dict)
    phases: list[JanaPhase] = field(default_factory=list)
    autkeys: int | None = None
    constraints: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    scale: Keyed | None = None
    overall_temperature: float | None = None
    extinction: Keyed | None = None
    atoms: list[list[JanaAtom]] = field(default_factory=list)
    m40_trailing: int = 0
    m41_header: dict[str, str] = field(default_factory=dict)
    m41_common: dict[str, Keyed] = field(default_factory=dict)
    m41_phases: list[JanaM41Phase] = field(default_factory=list)


# ------------------------------------------------------------- the file set

def _sibling(path: Path, suffix: str) -> Path | None:
    for candidate in (path.with_suffix(suffix), path.with_suffix(suffix.upper())):
        if candidate.is_file():
            return candidate
    return None


def resolve_set(path: str | Path) -> dict[str, Path]:
    """The ``.m50``/``.m40``/``.m41`` files sharing ``path``'s stem.

    ``path`` may be any of the three or the bare stem.  All three are
    required: the ``.m41`` is the powder half, and a set without one is a
    single-crystal project, which is not this reader's (WP-1314 non-goals).
    """
    p = Path(path)
    stem = p.with_suffix("") if p.suffix.lower() in SUFFIXES else p
    found = {s: _sibling(stem.with_name(stem.name + s), s) for s in SUFFIXES}
    missing = [s for s in SUFFIXES if found[s] is None]
    if missing:
        raise JanaError(
            f"{path}: a Jana set needs {' and '.join(missing)} beside it "
            f"(stem {stem.name!r}); found "
            f"{', '.join(s for s, f in found.items() if f) or 'none'}")
    return {s: f for s, f in found.items() if f is not None}


def _lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise JanaError(f"{path}: cannot be read ({exc})") from exc


# ------------------------------------------------------------- numbers

def _float(text: str) -> float:
    value = float(text.replace("D", "E").replace("d", "e"))
    if not math.isfinite(value):
        raise ValueError(text)
    return value


def _values(text: str, *, where: str) -> list[float]:
    """Every number on ``text``, refusing a run-together positive value.

    A negative value that fills its field fuses with its neighbour and the
    sign separates them (``0.500000-0.063340``, M2000 p. 52).  A *positive*
    one would fuse with nothing to separate it (``4.31000090.000000``), and
    a decimal-point split would cut it in a plausible wrong place, so a
    number that starts straight after a digit is refused rather than read.
    """
    matches = list(_NUMBER.finditer(text))
    for m in matches:
        if (m.start() > 0 and text[m.start() - 1].isdigit()
                and m.group()[0] not in "+-"):
            raise JanaError(f"{where}: two values run together on "
                            f"{text.strip()!r}; their boundary cannot be read")
    try:
        return [_float(m.group()) for m in matches]
    except (ValueError, OverflowError) as exc:
        raise JanaError(f"{where}: a non-finite value on {text.strip()!r}") from exc


def _keyed_line(line: str, *, where: str, n_keys: int | None = None) -> Keyed:
    """Values then a digit-only key string, one digit per value (M98 p. 97).

    ``n_keys`` names the one exception the manual states: an atom's
    displacement line carries six values and ten keys (pp. 116-120).
    """
    matches = list(_NUMBER.finditer(line))
    if not matches:
        raise JanaError(f"{where}: no number on a line that must hold values: "
                        f"{line.strip()!r}")
    between = _NUMBER.sub(" ", line[:matches[-1].end()])
    tail = line[matches[-1].end():].strip()
    if between.strip() or (tail and not tail.isdigit()):
        raise JanaError(f"{where}: unreadable field on {line.strip()!r} "
                        f"(numbers must carry a decimal point; the line ends "
                        f"in a digit-only key string)")
    values = _values(line[:matches[-1].end()], where=where)
    want = len(values) if n_keys is None else n_keys
    if len(tail) != want:
        raise JanaError(
            f"{where}: {len(values)} value(s) but "
            f"{'no' if not tail else len(tail)} refinement key(s) on "
            f"{line.strip()!r}; this line takes {want}")
    return Keyed(values, [c != "0" for c in tail])


def _halves(text: str) -> list[float]:
    """Half a unit in the last printed digit of each number on ``text``.

    Read off the token itself, as ``cif._printed_half`` does for a CIF value,
    so no print width is assumed (the manuals state none): ``0.012347`` stands
    for any value within 5e-7, ``0.0123`` within 5e-5, ``1.5E-3`` within
    5e-5 (the exponent scales it).
    """
    from decimal import Decimal

    from ...crystallography.cif import _printed_half

    return [float(_printed_half(Decimal(m.group().replace("D", "E")
                                        .replace("d", "e"))))
            for m in _NUMBER.finditer(text)]


def _numbers(text: str, *, where: str) -> list[float]:
    if _NUMBER.sub(" ", text).strip():
        raise JanaError(f"{where}: unreadable field on {text.strip()!r}")
    return _values(text, where=where)


# ------------------------------------------------------------- .m50

def _keyword(token: str, *, where: str) -> str:
    """The Table 9 keyword ``token`` names, allowing unique abbreviation (M98 p. 77)."""
    low = token.lower()
    if low in M50_STANCES:
        return low
    hits = [k for k in M50_STANCES if k.startswith(low)]
    if len(hits) == 1:
        return hits[0]
    raise JanaError(
        f"{where}: keyword {token!r} is not in the Jana98 .m50 grammar this "
        f"reader implements (M98 Table 9). Jana2006/Jana2020 constructs "
        f"(magnetic phases among them) are not described in any published "
        f"document, so they are refused rather than guessed")


def _part_one_end(lines: list[str], where: str) -> int:
    """The ``end`` closing part I (M98 Fig. 55); a file without one is cut short."""
    for i, raw in enumerate(lines):
        text = raw.split("!")[0].strip()
        if text.lower() == "end":
            return i
    raise JanaError(f"{where}: no 'end' line closes the keyword part, so the "
                    f"file is cut short or is not a Jana file")


def _read_m50(lines: list[str], model: JanaModel, where: str) -> None:
    end = _part_one_end(lines, where)
    phase = JanaPhase()
    phases: list[JanaPhase] = []
    explicit = False
    in_table = False  # inside a formtab's numbers, which may wrap lines
    stated: dict[tuple, int] = {}  # a single-valued keyword's scope -> its line
    n_phase = n_atom = 0
    for n, raw in enumerate(lines[:end], start=1):
        here = f"{where} line {n}"
        text = raw.split("!")[0]
        if text.lstrip().startswith("*") or not text.strip():
            continue
        if set(text.strip()) <= {"-"}:
            continue  # the separator the multiphase examples write
        tokens = text.split()
        i = 0
        while i < len(tokens):
            if in_table:
                if _NUMBER.fullmatch(tokens[i]) or tokens[i].lstrip("+-").isdigit():
                    i += 1
                    continue
                in_table = False
            key = _keyword(tokens[i], where=here)
            stance = M50_STANCES[key]
            if stance.stance == "refused":
                raise JanaError(f"{here}: {key!r} states {stance.why}, which "
                                f"this reader refuses by name")
            if stance.arity == "line":
                arg = " ".join(tokens[i + 1:])
                i = len(tokens)
            else:
                count = (3 if stance.arity == "ndim" else 1
                         if stance.arity == "formtab" else int(stance.arity))
                args = tokens[i + 1:i + 1 + count]
                if len(args) != count:
                    raise JanaError(f"{here}: {key!r} needs {count} value(s), "
                                    f"has {len(args)}")
                arg = " ".join(args)
                i += 1 + count
            if key == "formtab":
                # the table's numbers follow, eight a line (M2000 p. 53); what
                # a negative count means is not documented, so the numbers are
                # taken up to the next keyword rather than counted
                in_table = True
            if key == "phase":
                n_phase, n_atom = n_phase + 1, 0
            elif key == "atom":
                n_atom += 1
            scope = (("the set", key) if key in ONCE_PER_SET
                     else (f"phase {n_phase}", key) if key in ONCE_PER_PHASE
                     else (f"atom type {n_atom} of phase {n_phase}", key)
                     if key in ONCE_PER_ATOM_TYPE else None)
            if scope is not None:
                if scope in stated:
                    raise JanaError(
                        f"{here}: {key!r} is stated twice for {scope[0]} (first "
                        f"at line {stated[scope]}); no page of the Jana manuals "
                        f"says which statement Jana uses, so neither is picked")
                stated[scope] = n
            try:
                phase, explicit = _apply(key, arg, phase, phases, explicit, model)
            except JanaError as exc:
                raise JanaError(f"{here}: {exc}") from exc
            except (ValueError, IndexError) as exc:
                raise JanaError(f"{here}: {key!r} has an unreadable value "
                                f"{arg!r}") from exc
    phases.append(phase)
    model.phases = phases
    _read_control_sections(lines[end + 1:], model, where, first_line=end + 2)


def _apply(key: str, arg: str, phase: JanaPhase, phases: list[JanaPhase],
           explicit: bool, model: JanaModel) -> tuple[JanaPhase, bool]:
    nums = arg.split()
    if key == "title":
        model.title = arg or None
    elif key == "lambda":
        model.wavelength = abs(_float(arg))  # M98 p. 81: a negative is flipped
    elif key == "radtype":
        model.radtype = int(arg)
    elif key == "phase":
        if explicit:
            phases.append(phase)
        elif phase != JanaPhase():
            raise JanaError("a phase-level keyword comes before the first "
                            "'phase' line, so which phase it belongs to is not "
                            "stated")
        phase, explicit = JanaPhase(name=arg or None), True
    elif key in ("cell", "esdcell", "sgshift"):
        setattr(phase, key, tuple(_float(v) for v in nums))
    elif key == "spgroup":
        if len(nums) != 3:
            raise JanaError(f"spgroup must state a symbol, a number and a crystal "
                            f"system; got {arg!r}")
        if "(" in nums[0]:
            raise JanaError(f"spgroup {nums[0]!r} is a superspace group: a "
                            f"modulated structure, refused by name")
        phase.space_group = nums[0]
        phase.space_group_number = int(nums[1])
        phase.crystal_system = int(nums[2])
    elif key == "lattice":
        phase.lattice = arg.upper()
    elif key == "lattvec":
        phase.lattvec.append(tuple(_float(v) for v in nums))
    elif key == "centro":
        phase.centro = True
    elif key == "symmetry":
        if len(nums) != 3:
            raise JanaError(f"symmetry {arg!r} has {len(nums)} components; only "
                            f"three-dimensional operators are read")
        phase.symmetry.append(",".join(
            t.lower().replace("x1", "x").replace("x2", "y").replace("x3", "z")
            for t in nums))
    elif key == "ndim" and int(arg) != 3:
        raise JanaError(f"ndim {arg} is a modulated structure, refused by name")
    elif key == "ncomp" and int(arg) != 1:
        raise JanaError(f"ncomp {arg} is a composite structure, refused by name")
    elif key == "atom":
        phase.atom_types.append(JanaAtomType(arg))
    elif key in ("atweight", "atradius", "formula", "f'", 'f"', "fneutron",
                 "formtab"):  # formtab: the count; its table is not kept
        if not phase.atom_types:
            raise JanaError(f"{key!r} before any 'atom' line")
        phase.atom_types[-1].values[key] = _float(arg)
    elif key in ("lpfactor", "monangle", "datcolltemp"):
        model.experiment[key] = arg  # global in M2000 p. 53's multiphase set
    elif key in ("unitsnumb", "chemform"):
        phase.other[key] = arg
    return phase, explicit


def _read_control_sections(lines: list[str], model: JanaModel, where: str, *,
                           first_line: int = 1) -> None:
    """Part II: one section per program, each closed by ``end`` (M98 p. 79).

    Only REFINE's ``autkeys`` and its constraint commands are read.  A second
    REFINE section, and a second ``autkeys``, are refused: neither manual says
    which of the two Jana uses.  A repeated section of another program is
    skipped, as every other program's section is, so nothing read changes.
    """
    current: str | None = None
    autkeys_line: int | None = None
    for n, raw in enumerate(lines, start=first_line):
        text = raw.split("!")[0].strip()
        if not text or text.startswith("*"):
            continue
        tokens = text.split()
        head = tokens[0].lower()
        if current is None:
            current = head
            if _names(head, "refine") and any(_names(s, "refine")
                                              for s in model.sections):
                raise JanaError(
                    f"{where} line {n}: a second REFINE section; "
                    f"no page of the Jana manuals says which of the two Jana "
                    f"reads, so neither is picked")
            if head in model.sections:
                current = "<repeat>"
            else:
                model.sections.append(head)
            # a command may follow the program's name on its own line
            # (``refine restric O1 1``): read the rest as a line of the section
            if len(tokens) == 1:
                continue
            text, tokens = text.split(None, 1)[1], tokens[1:]
            head = tokens[0].lower()
        if head == "end":
            current = None
            continue
        if not _names(current, "refine"):
            continue
        for j, token in enumerate(tokens):
            if _names(token.lower(), "autkeys") and j + 1 < len(tokens):
                if autkeys_line is not None:
                    raise JanaError(
                        f"{where} line {n}: autkeys is stated twice in the "
                        f"REFINE section (first at line {autkeys_line}); "
                        f"no page of the Jana manuals says which one Jana uses, "
                        f"so neither is picked")
                autkeys_line = n
                try:
                    model.autkeys = int(tokens[j + 1])
                except ValueError as exc:
                    raise JanaError(f"{where}: autkeys {tokens[j + 1]!r} is not "
                                    f"an integer") from exc
        if any(_names(head, c) for c in CONSTRAINT_COMMANDS):
            model.constraints.append(text)


def _names(token: str, word: str) -> bool:
    """``token`` spells ``word`` or abbreviates it (M98 p. 77), in three letters or more."""
    return len(token) >= 3 and word.startswith(token)


# ------------------------------------------------------------- .m40

def _ints(line: str, *, where: str) -> list[int]:
    try:
        return [int(t) for t in line.split()]
    except ValueError as exc:
        raise JanaError(f"{where}: expected integers, got {line.strip()!r}") from exc


def _read_m40(lines: list[str], model: JanaModel, where: str) -> None:
    rows = [(n, line) for n, line in enumerate(lines, start=1) if line.strip()]
    if not rows:
        raise JanaError(f"{where}: empty")
    if rows[0][1].split()[0].lower() == "commands":
        raise JanaError(f"{where} line {rows[0][0]}: a commands section "
                        f"(maxsc/wave/ortho, M98 p. 105) is a modulated or "
                        f"multi-scale construct, refused by name")
    pos = 0

    def take() -> tuple[int, str]:
        nonlocal pos
        if pos >= len(rows):
            raise JanaError(f"{where}: ends early, after line "
                            f"{rows[-1][0]}, where the layout needs more")
        pos += 1
        return rows[pos - 1]

    counts: list[int] = []
    for _ in model.phases:
        n, line = take()
        header = _ints(line, where=f"{where} line {n}")
        if len(header) != 4:
            raise JanaError(
                f"{where} line {n}: header {line.strip()!r} has {len(header)} "
                f"integers; the single-part layout is Nat Nmol Itemp Irot "
                f"(M98 p. 107)")
        nat, nmol, itemp, _irot = header
        if nat < 0:
            raise JanaError(f"{where} line {n}: a negative atom count {nat}")
        if nmol:
            raise JanaError(f"{where} line {n}: {nmol} rigid-body molecule(s), "
                            f"refused by name")
        if itemp:
            raise JanaError(f"{where} line {n}: Itemp {itemp} is the beta form "
                            f"of the temperature factor, refused by name")
        counts.append(nat)
    n, line = take()
    model.scale = _keyed_line(line, where=f"{where} line {n}")
    n, line = take()
    overall = _numbers(line, where=f"{where} line {n}")
    if len(overall) != 1:
        raise JanaError(f"{where} line {n}: the overall temperature line holds "
                        f"one value, not {len(overall)}")
    model.overall_temperature = overall[0]
    ext = [_keyed_line(take()[1], where=f"{where} extinction") for _ in range(2)]
    model.extinction = Keyed(ext[0].values + ext[1].values, ext[0].keys + ext[1].keys)
    model.atoms = []
    for nat in counts:
        atoms = []
        for _ in range(nat):
            n, first = take()
            atoms.append(_atom(first, take()[1], where=f"{where} line {n}"))
        model.atoms.append(atoms)
    # what follows the declared atoms is the s.u. block (M98 pp. 93-94),
    # whose separator no document shows: counted, and named at build
    model.m40_trailing = len(rows) - pos


_ATOM_HEAD = re.compile(r"\s*(\S+)\s+(-?\d+)\s+(-?\d+)(.*)$")


def _atom(first: str, second: str, *, where: str) -> JanaAtom:
    match = _ATOM_HEAD.match(first)
    if not match:
        raise JanaError(f"{where}: not an atom line: {first.strip()!r}")
    label, ctype, ttype, rest = match.groups()
    ttype_i = int(ttype)
    if ttype_i not in (1, 2):
        what = "TLS (a molecule)" if ttype_i == 0 else f"anharmonic order {ttype_i}"
        raise JanaError(f"{where}: atom {label!r} has displacement type "
                        f"{ttype_i}, {what}, refused by name")
    values = list(_NUMBER.finditer(rest))
    if len(values) < 4:
        raise JanaError(f"{where}: atom {label!r} needs ai x y z")
    tail = rest[values[3].end():].split()
    if _NUMBER.sub(" ", rest[:values[3].end()]).strip() or len(values) > 4:
        raise JanaError(f"{where}: atom {label!r}: unreadable field on "
                        f"{first.strip()!r}")
    if tail:
        if not all(t.isdigit() for t in tail):
            raise JanaError(f"{where}: atom {label!r}: unreadable field "
                            f"{' '.join(tail)!r}")
        if any(c != "0" for t in tail for c in t):
            raise JanaError(f"{where}: atom {label!r} carries modulation "
                            f"waves or special functions ({' '.join(tail)}), "
                            f"refused by name")
    ai, x, y, z = _values(rest[:values[3].end()], where=where)
    ai_half = _halves(rest[:values[3].end()])[0]
    adp = _keyed_line(second, where=f"{where} (+1)", n_keys=10)
    adp_half = _halves(second)
    if len(adp.values) != 6:
        raise JanaError(f"{where}: atom {label!r}: the displacement line holds "
                        f"U11..U23 (M98 p. 118), not {len(adp.values)} values")
    return JanaAtom(label=label, type_index=int(ctype), adp_type=ttype_i, ai=ai,
                    xyz=(x, y, z), adp=tuple(adp.values), keys=tuple(adp.keys),
                    ai_half=ai_half, adp_half=tuple(adp_half))


# ------------------------------------------------------------- .m41

def _read_m41(lines: list[str], model: JanaModel, where: str) -> None:
    end = _part_one_end(lines, where)
    for raw in lines[:end]:
        tokens = raw.split("!")[0].split()
        for k in range(0, len(tokens) - 1, 2):
            if tokens[k].lower() == "phase":
                break
            model.m41_header.setdefault(tokens[k].lower(), tokens[k + 1])
    target = model.m41_common
    title: str | None = None
    for n, raw in enumerate(lines[end + 1:], start=end + 2):
        text = raw.rstrip()
        if not text.strip() or set(text.strip()) <= {"*"}:
            continue
        if text.startswith("###"):
            name = text.lstrip("#").strip()
            name = name[len("phase"):].strip() if name.lower().startswith("phase") else name
            model.m41_phases.append(JanaM41Phase(name or None))
            target, title = model.m41_phases[-1].sections, None
            continue
        if text.startswith("#"):
            title = text.lstrip("#").strip()
            continue
        if title is None:
            raise JanaError(f"{where} line {n}: values before any '#' section "
                            f"title: {text.strip()!r}")
        keyed = _keyed_line(text, where=f"{where} line {n}")
        if title in target:
            target[title].values.extend(keyed.values)
            target[title].keys.extend(keyed.keys)
        else:
            target[title] = keyed


# ------------------------------------------------------------- reading

def read_jana(path: str | Path, *,
              diagnostics: list[Diagnostic] | None = None) -> JanaModel:
    """Read a Jana ``.m50``/``.m40``/``.m41`` set into a :class:`JanaModel`.

    ``path`` is any of the three files or their common stem.  Every refusal
    raises :class:`JanaError` naming the file and line.  ``diagnostics``, when
    given, receives what the set states that the model does not carry.
    """
    files = resolve_set(path)
    model = JanaModel(path=str(files[".m50"]),
                      files={s: str(p) for s, p in files.items()})
    _read_m50(_lines(files[".m50"]), model, str(files[".m50"]))
    _read_m40(_lines(files[".m40"]), model, str(files[".m40"]))
    for phase_atoms, phase in zip(model.atoms, model.phases):
        for atom in phase_atoms:
            if len(atom.adp) != 6 or len(atom.keys) != 10:
                raise JanaError(
                    f"{files['.m40']}: atom {atom.label!r}: the displacement "
                    f"line holds U11..U23 and ten keys (ai, x, y, z, Uij; "
                    f"M98 p. 118), not {len(atom.adp)} values")
            if not 1 <= atom.type_index <= len(phase.atom_types):
                raise JanaError(
                    f"{files['.m40']}: atom {atom.label!r} names atom type "
                    f"{atom.type_index}, but its phase in {files['.m50']} "
                    f"declares {len(phase.atom_types)}")
    _read_m41(_lines(files[".m41"]), model, str(files[".m41"]))
    if model.m41_phases and len(model.m41_phases) != len(model.phases):
        raise JanaError(
            f"{files['.m41']}: {len(model.m41_phases)} phase block(s) for "
            f"the {len(model.phases)} phase(s) of {files['.m50']}")
    m50_names = [p.name for p in model.phases]
    m41_names = [p.name for p in model.m41_phases]
    if (model.m41_phases and all(m50_names) and all(m41_names)
            and sorted(m50_names) != sorted(m41_names)):
        raise JanaError(
            f"{files['.m41']}: phase blocks {m41_names} do not name the "
            f"phases {m50_names} of {files['.m50']}")
    if diagnostics is not None:
        _report(model, diagnostics)
    return model


def _report(model: JanaModel, diagnostics: list[Diagnostic]) -> None:
    """The two read-time warnings: what the set does not establish about its keys."""
    named = model.path
    if model.autkeys != 0:
        diagnostics.append(Diagnostic(
            level="warning", code="JANA_KEYS_MAY_BE_IGNORED",
            message=(
                (f"{named} states autkeys {model.autkeys} in its REFINE section: "
                 f"Jana's automatic mode, in which REFINE ignores the .m40 keys "
                 f"of all but scales and occupancies, so the vary flags read "
                 f"from them are not the set the Jana run refined."
                 if model.autkeys is not None else
                 f"{named} does not state autkeys in a REFINE section, and the "
                 f"Jana98 manual gives automatic mode (autkeys 1) as the "
                 f"default, in which REFINE ignores the .m40 keys of all but "
                 f"scales and occupancies; so the vary flags read from them may "
                 f"not be the set the Jana run refined.")),
            suggestion=("Check which parameters the Jana run refined before "
                        "reusing its protocol.")))
    if model.constraints:
        diagnostics.append(Diagnostic(
            level="warning", code="JANA_CONSTRAINTS_NOT_CARRIED",
            message=(f"{named}: {len(model.constraints)} REFINE constraint "
                     f"command(s) are not carried, so parameters they tie or "
                     f"fix are free or held only as their own keys say: "
                     f"{'; '.join(model.constraints)}")))


#: The ``.m41`` sections :func:`to_structure` reads; any other is on the model only.
M41_READ = ("Cell parameters",)


def _title_key(title: str) -> str:
    return title.split(" - ")[0].strip()


# ------------------------------------------------------------- converting

def _operators(phase: JanaPhase) -> list[str]:
    """The full group: listed operators x centring x (inversion if centro)."""
    import gemmi

    if phase.lattice == "X":
        centring = [(0.0, 0.0, 0.0)] + list(phase.lattvec)
    elif phase.lattice in _CENTRING:
        centring = _CENTRING[phase.lattice] + list(phase.lattvec)
    else:
        raise JanaError(f"lattice {phase.lattice!r} is not a centring letter")
    if not phase.symmetry:
        raise JanaError("states no symmetry operator, not even x y z")
    listed = [gemmi.Op(t) for t in phase.symmetry]
    full = []
    for op in listed:
        variants = [op, gemmi.Op("-x,-y,-z") * op] if phase.centro else [op]
        for v in variants:
            for t in centring:
                shifted = gemmi.Op(v.triplet())
                shifted.tran = [(v.tran[i] + round(t[i] * gemmi.Op.DEN))
                                % gemmi.Op.DEN for i in range(3)]
                full.append(shifted.triplet())
    # an operator listed and also generated (an explicit -x -y -z beside
    # centro) is one operation; gemmi finds no group for a list with repeats
    return list(dict.fromkeys(full))


def _m41_block(model: JanaModel, index: int) -> JanaM41Phase:
    """The ``.m41`` block of phase ``index``: by name where both files name
    every phase, else by position."""
    name = model.phases[index].name
    if all(p.name for p in model.phases) and all(b.name for b in model.m41_phases):
        return next(b for b in model.m41_phases if b.name == name)
    return model.m41_phases[index]


def _tensor_within_print(sg, xyz, u: tuple[float, ...], halves: tuple[float, ...]
                         ) -> tuple[tuple[float, ...], list[str]]:
    """A printed Uij moved onto its site's allowed form where the print admits it.

    Each Uij stands for any value within half a unit of its own last printed
    digit (``halves``, read off the token: no print width is assumed), and a tied pair on a special site (U12 = U11/2 on a three-fold
    axis) misses its tie whenever the last digit rounds the other way.  The
    CIF reader's repair (``crystallography.cif._project_printed_adps``):
    the allowed tensor nearest the print inside that box, a zero held exact,
    and the table's own test after it.  Returns the tensor and the names of
    the components moved, none where it already lies on the form or nothing
    allowed lies within the print (left for ``ParameterTable`` to refuse).
    """
    import numpy as np

    from ...crystallography.adp import U_NAMES
    from ...crystallography.wyckoff import (
        adp_basis,
        adp_projection,
        nearest_allowed_within_print,
        stabilizer_rotations,
    )

    printed = np.asarray(u, dtype=np.float64)
    try:
        basis = adp_basis(stabilizer_rotations(sg, xyz))
    except ValueError:
        return u, []
    if adp_projection(basis, printed)[2]:
        return u, []
    half = np.where(printed != 0.0, np.asarray(halves, dtype=np.float64), 0.0)
    target = nearest_allowed_within_print(
        np.asarray(basis, dtype=np.float64).T, printed, half)
    if target is None or not adp_projection(basis, target)[2]:
        return u, []
    names = [n for n, a, t in zip(U_NAMES, printed, target, strict=True) if a != t]
    return tuple(float(t) for t in target), names


def held_directions(basis, keys: tuple[bool, ...],
                    names: tuple[str, ...]) -> list[str]:
    """The site's allowed directions its keys hold, where they free others.

    ``ParameterTable`` frees an atom's symmetry-allowed coordinates on one
    flag, and its allowed Uij on another, so keys that name only some of the
    directions the site's symmetry lets move are merged to all of them.  A
    direction (a row of ``basis``, the site's ``coordinate_basis`` or
    ``adp_basis``) counts as keyed when any component it moves carries a key,
    since Jana may key one member of a symmetry-tied set (x of an x, x, z
    site) or all of them.  A component the symmetry fixes (z on 4g of Pbam,
    U13 there) is rightly unkeyed and is in no direction.  Returns each held
    direction as the components it moves (``"z"``, ``"U11/U22/U12"``); an
    empty list when no key is set, when every direction is keyed, or when the
    site allows none.
    """
    rows = [[abs(float(c)) > 1e-12 for c in row] for row in basis]
    keyed = [any(m and k for m, k in zip(row, keys, strict=True)) for row in rows]
    if not any(keyed) or all(keyed):
        return []
    return ["/".join(n for n, m in zip(names, row, strict=True) if m)
            for row, k in zip(rows, keyed, strict=True) if not k]


def to_structure(model: JanaModel, *, phase: int | str | None = None,
                 diagnostics: list[Diagnostic] | None = None) -> Structure:
    """Build a :class:`~rietx.schemas.Structure` from a read :class:`JanaModel`.

    The **space group comes from the operators** the ``.m50`` writes, expanded
    by the centring and inversion it states (M98 pp. 81-82), and the setting is
    the tabulated one those operations are; a symbol alone is never trusted.
    A stated number that disagrees with the operators is refused.

    Each site's **occupancy** is Jana's ``ai`` times the general multiplicity
    over the site's own: ``ai`` times the site's symmetry order (the number
    of general-position images that fall on it), so 2a of Pbam, of order 4,
    has ``ai`` 1/4 for a full site.  M98 p. 116 words this as "the reciprocal
    value of its multiplicity", which only reads so if "multiplicity" means
    that order and not the Wyckoff multiplicity (that would give 1/2).  U values become ``Biso`` through 8π²;
    an anisotropic site keeps its U-form Uij (M98 E14, the CIF convention).
    **These readings, and the ``.m41`` cell's units, are unverified
    assumptions**: taken from the manuals' prose, not yet measured against a
    CIF Jana exported from the same refinement (the module docstring; a
    WP-1314 task).
    The keys map onto ``vary``: ai to ``occ``, any of x/y/z to the site's
    coordinates, the fifth to ``biso`` and any of the fifth to tenth to the
    anisotropic block; a key set narrower than the directions the site allows
    is merged to all of them and said (``JANA_REFINE_KEY_MERGED``).  The
    cell's keys come from the ``.m41`` phase block, whose cell is the refined
    one; without a ``.m41`` the ``.m50`` cell is taken and held.
    """
    import gemmi
    import numpy as np

    import rietx as rx

    from ...crystallography.adp import u_equivalent
    from ...crystallography.symmetry import site_orbit
    from ...crystallography.twins import merge_site_twins
    from ...crystallography.wyckoff import (
        adp_basis,
        coordinate_basis,
        stabilizer_rotations,
    )
    from ...params.vector import ParameterTable
    from ...schemas.instrument import Instrument

    named = model.path
    names = [p.name for p in model.phases]
    if phase is None:
        if len(model.phases) > 1:
            raise JanaError(f"{named}: {len(model.phases)} phases {names}; "
                            f"pass phase= to choose one")
        index = 0
    elif isinstance(phase, str):
        if phase not in names:
            raise JanaError(f"{named}: no phase {phase!r} (phases: {names})")
        index = names.index(phase)
    else:
        index = phase
        if not 0 <= index < len(model.phases):
            raise JanaError(f"{named}: phase {index} out of range ({names})")
    chosen = model.phases[index]
    label = chosen.name or f"phase {index}"
    try:
        ops = gemmi.GroupOps([gemmi.Op(t) for t in _operators(chosen)])
        sg = gemmi.find_spacegroup_by_ops(ops)
    except JanaError as exc:
        raise JanaError(f"{named}: phase {label!r} {exc}") from exc
    except (RuntimeError, ValueError) as exc:
        raise JanaError(f"{named}: phase {label!r}: its symmetry operators "
                        f"do not form a group this build reads ({exc})") from exc
    if sg is None:
        raise JanaError(f"{named}: phase {label!r}: its {len(chosen.symmetry)} "
                        f"listed operator(s) are not a tabulated space-group "
                        f"setting")
    if chosen.space_group_number and sg.number != chosen.space_group_number:
        raise JanaError(f"{named}: phase {label!r} states space group "
                        f"{chosen.space_group_number} ({chosen.space_group}) "
                        f"but its operators are {sg.xhm()} (No. {sg.number})")

    if chosen.sgshift is not None and any(abs(v) > 1e-9 for v in chosen.sgshift):
        raise JanaError(
            f"{named}: phase {label!r} states a nonzero origin shift "
            f"(sgshift {list(chosen.sgshift)}); M98 p. 81 gives it in ITA's "
            f"convention and no page says whether the listed operators "
            f"already include it, so the structure's origin could not be "
            f"established. The shift is on the model")
    # the refined cell is the .m41's, in the phase's block, or in the common
    # part of a single-phase file that writes no "### phase" line; a block is
    # the phase's by name where both files name them (read_jana refused two
    # lists of names that differ), by position only where either is silent
    m41 = (_m41_block(model, index).sections if model.m41_phases
           else model.m41_common if len(model.phases) == 1 else {})
    cell_section = next((v for k, v in m41.items()
                         if _title_key(k) == "Cell parameters"), None)
    not_carried: list[str] = []
    if cell_section is not None:
        if len(cell_section.values) != 6:
            raise JanaError(f"{model.files['.m41']}: phase {label!r}: the cell "
                            f"section holds {len(cell_section.values)} values, "
                            f"not six")
        cell, cell_vary = cell_section.values, cell_section.keys
    elif chosen.cell is not None and len(chosen.cell) == 6:
        cell, cell_vary = list(chosen.cell), [False] * 6
        not_carried.append("the .m41 states no cell for this phase, so the "
                           ".m50 cell is taken and held")
    else:
        raise JanaError(f"{named}: phase {label!r} states no cell")

    general = len(list(sg.operations()))
    sites, frozen, snapped, moved = [], [], [], []
    merged: list[tuple[str, str, list[str]]] = []  # (label, "xyz"/"uij", held)
    for atom in model.atoms[index]:
        xyz = np.array(atom.xyz, dtype=float)
        orbit = site_orbit(sg, xyz)
        # M98 p. 116: ai is the occupancy over the site's symmetry order, and
        # the token's own last digit bounds ai, so the occupancy is known to
        # that half-unit times the order: a full site within it reads as
        # full, and one past it is more than full, which is another
        # program's convention
        order = general / orbit.multiplicity
        occupancy = atom.ai * order
        printed = atom.ai_half * order + 1e-12
        if occupancy > 1.0 + printed:
            raise JanaError(
                f"{named}: phase {label!r}: atom {atom.label!r} has ai "
                f"{atom.ai} on a site of symmetry order {order:g}, an "
                f"occupancy of {occupancy:g}; Jana's ai of a special position "
                f"is the occupancy over that order (M98 p. 116)")
        if occupancy != 1.0 and abs(occupancy - 1.0) <= printed:
            snapped.append(atom.label)
            occupancy = 1.0
        # one flag for the three coordinates, freeing what symmetry permits,
        # as GSAS's X flag does: ParameterTable frees a site's DOFs together,
        # so a key set narrower than the site's allowed directions is merged
        keys_xyz = atom.keys[1:4]
        vary_xyz = any(keys_xyz)
        directions = coordinate_basis(list(orbit.stabilizer))
        if vary_xyz and len(directions) == 0:
            frozen.append(atom.label)
            vary_xyz = False
        held = held_directions(directions, keys_xyz, ("x", "y", "z"))
        if held:
            merged.append((atom.label, "xyz", held))
        if atom.adp_type == 2:
            try:
                tensor = adp_basis(stabilizer_rotations(sg, xyz))
            except ValueError:
                tensor = []
            held = held_directions(tensor, atom.keys[4:10], U_LABELS)
            if held:
                merged.append((atom.label, "uij", held))
        u = atom.adp
        if atom.adp_type == 2:
            u, components = _tensor_within_print(sg, xyz, u, atom.adp_half)
            if components:
                moved.append((atom.label, components))
        sites.append(dict(
            atom=atom, species=chosen.atom_types[atom.type_index - 1].symbol,
            occupancy=occupancy, vary_xyz=vary_xyz, u=u,
            aniso=u if atom.adp_type == 2 else None,
            vary_aniso=any(atom.keys[4:10])))

    # Every schema object is built here, inside one guard, and so is the
    # ParameterTable, whose symmetry refusals (a cell angle against its
    # setting, a tensor outside its site's subspace) would otherwise reach
    # the caller at fit time naming a parameter path rather than the file.
    # So is U_eq, whose Cholesky factor of the cell's metric raises on a cell
    # with a zero length or angle (numpy's LinAlgError is a ValueError).
    try:
        for s in sites:
            # an anisotropic site's biso is an inert record (Atom's docstring)
            s["biso"] = (s["u"][0] if s["aniso"] is None
                         else u_equivalent(s["u"], cell)) * EIGHT_PI_SQUARED
        structure = rx.Structure(phases=[rx.Phase(
            name=label,
            space_group=sg.xhm(),
            cell=rx.Cell(**{
                n: rx.Parameter(value=v, vary=f, **({"min": 1.0} if i < 3 else {}))
                for i, (n, v, f) in enumerate(zip(
                    ("a", "b", "c", "alpha", "beta", "gamma"), cell, cell_vary))}),
            atoms=[rx.Atom(
                label=s["atom"].label, species=s["species"],
                x=rx.Parameter(value=s["atom"].xyz[0], vary=s["vary_xyz"]),
                y=rx.Parameter(value=s["atom"].xyz[1], vary=s["vary_xyz"]),
                z=rx.Parameter(value=s["atom"].xyz[2], vary=s["vary_xyz"]),
                occ=rx.Parameter(value=s["occupancy"], min=0.0,
                                 vary=s["atom"].keys[0]),
                biso=rx.Parameter(value=s["biso"],
                                  vary=s["aniso"] is None and s["atom"].keys[4]),
                aniso=(None if s["aniso"] is None else
                       rx.AnisoU.from_values(s["aniso"], vary=s["vary_aniso"])))
                for s in sites],
            scale=rx.Parameter(value=1e-3, min=0.0))])
        ParameterTable(structure, Instrument.constant_wavelength_neutron(1.0))
    except ValueError as exc:
        raise JanaError(f"{named}: phase {label!r} states values this build "
                        f"refuses ({exc}). The file's own numbers are on the "
                        f"model") from exc

    structure = merge_site_twins(structure, diagnostics=diagnostics, source=named)
    if diagnostics is not None:
        _report_build(model, chosen, label, sites, diagnostics, not_carried=not_carried,
                      frozen=frozen, merged=merged, snapped=snapped, moved=moved)
    return structure


def _report_build(model: JanaModel, chosen: JanaPhase, label: str, sites: list[dict],
                  diagnostics: list[Diagnostic], *, not_carried: list[str],
                  frozen: list[str], merged: list[tuple[str, str, list[str]]],
                  snapped: list[str], moved: list[tuple[str, list[str]]]) -> None:
    """What a build did, one code per kind (as the ``.EXP`` and ``.gpx`` readers split it).

    An action that moves what the Jana run held is a warning of its own
    (``JANA_REFINE_KEY_MERGED``); keys on fully fixed sites, the seeded scale
    and the two print-box repairs are infos of their own; ``JANA_NOT_CARRIED``
    is left with the omissions that differ from file to file, and is emitted
    only when one is left.
    """
    named = model.path
    labels = [s["atom"].label for s in sites]

    def at(atom: str, field: str) -> str:
        return f"phases.0.atoms.{labels.index(atom)}.{field}"

    if merged:
        parts = [f"{atom} {'coordinates' if kind == 'xyz' else 'U^ij'} "
                 f"({', '.join(held)})" for atom, kind, held in merged]
        polar = any(kind == "xyz" for _, kind, _ in merged)
        diagnostics.append(Diagnostic(
            level="warning", code="JANA_REFINE_KEY_MERGED",
            message=(
                f"{named}: phase {label!r}: a key on some of a site's allowed "
                f"directions frees all of them, since a structure carries one "
                f"flag for an atom's coordinates and one for its U^ij. These "
                f"directions the Jana run held will refine: {'; '.join(parts)}."
                + (" A held coordinate can be what fixed a polar group's "
                   "origin, and Phase.floating_origin is off by default."
                   if polar else "")),
            suggestion=("Hold those atoms' coordinates or U^ij with "
                        "Refinement.hold, or set Phase.floating_origin, before "
                        "comparing the fit with the Jana run."),
            where=[at(atom, "x" if kind == "xyz" else "aniso.u11")
                   for atom, kind, _ in merged]))
    if frozen:
        diagnostics.append(Diagnostic(
            level="info", code="JANA_COORDINATES_SYMMETRY_FIXED",
            message=(f"{named}: phase {label!r}: {len(frozen)} site(s) carry "
                     f"coordinate keys but sit on fully fixed special positions "
                     f"({', '.join(frozen)}), so their coordinates are held."),
            where=[at(atom, "x") for atom in frozen]))
    if snapped or moved:
        repairs = []
        if snapped:
            repairs.append(f"ai of {', '.join(snapped)} read as fully occupied")
        if moved:
            repairs.append(
                "U^ij of " + ", ".join(f"{n} ({', '.join(c.upper() for c in cs)})"
                                       for n, cs in moved)
                + " moved onto the form the site's symmetry allows")
        diagnostics.append(Diagnostic(
            level="info", code="JANA_PRINTED_DIGIT_REPAIRED",
            message=(f"{named}: phase {label!r}: within half a unit of each "
                     f"value's own last printed digit, " + "; ".join(repairs)
                     + "."),
            where=([at(n, "occ") for n in snapped]
                   + [at(n, f"aniso.{c}") for n, cs in moved for c in cs])))
    # f' and f'' are written for nearly every atom type and change nothing
    # rietx computes, so only the two that replace a scattering factor are said
    stated = sorted({k for t in chosen.atom_types for k in t.values
                     if k in ("fneutron", "formtab")})
    if stated:
        not_carried.append(f"the .m50's stated {', '.join(stated)}"
                           + (" (a tabulated form factor)"
                              if "formtab" in stated else "")
                           + ", rietx computing its own scattering factors")
    if model.m40_trailing:
        not_carried.append(f"{model.m40_trailing} .m40 line(s) after the "
                           f"declared atoms, taken as the s.u. block")
    if not_carried:
        diagnostics.append(Diagnostic(
            level="info", code="JANA_NOT_CARRIED",
            message=(f"{named}: phase {label!r} was built without: "
                     + "; ".join(not_carried) + ".")))
    diagnostics.append(Diagnostic(
        level="info", code="JANA_SCALE_NOT_COMPARABLE",
        message=(f"{named}: phase {label!r} was built without: the scale, "
                 f"seeded at 1e-3 (the .m40 states "
                 f"{model.scale.values if model.scale else None})."),
        suggestion="Refine the scale before you trust it.",
        where=["phases.0.scale"]))
