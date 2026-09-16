"""The model-format registry: which project readers exist, and the one door in.

``PATTERN_FORMATS`` answers "what did the diffractometer record"; this registry
answers "what model did someone already fit to it".  They are deliberately two
registries and not one arm of a third, for the reason
:class:`~rietx.io.formats.base.PatternFormat` gives its own existence: the
*answer's shape* differs.  A pattern reader returns a
:class:`~rietx.schemas.PatternData` and a project's ``DataRef`` records which
reader claimed the file so re-opening reproduces the reader call; a project
reader returns a whole solved model and nothing re-opens it that way.

**What the registry governs, and what it does not** (WP-1118, decided
2026-09-13).  A *project format* is a file stating someone else's **refinement**
— its phases, its instrument and, the part nobody can reconstruct from a CIF
plus a pattern, its refine flags.  Other readers in this build open a foreign
file and are *not* here, each for a stated reason:

- :func:`~rietx.io.instrument_profile.read_gsas_prm` reads a GSAS-I ``.prm``,
  which carries a machine and no model at all — no phases, no sites, no fitted
  numbers.  It is the same kind of thing as
  :func:`~rietx.io.instrument_profile.load_instrument_profile`, which is where
  it lives, and admitting it here would make every field this registry declares
  about a model empty on one member.
- :func:`~rietx.io.recipe.read_recipe` reads a PowderLine recipe, which *is* a
  refinement but carries its whole pattern inline and resolves to a
  :class:`~rietx.io.recipe.Recipe` that is ready to fit.  It is a
  build-wide feature (``capabilities().features["powderline_recipe"]``), not a
  format someone hands you to translate.
- The pattern readers under ``io/formats/``, which are the other registry.

So every member here has the same shape, and the shape is honest about what it
does not know: the reader returns **what the file states** (``TopasModel``,
``FullProfModel`` — seeded with nothing, a value the file omitted arriving as
``None``), and a separate conversion builds a :class:`~rietx.schemas.Structure`
from it.  That two-step is not ceremony.  A file states more than a
``Structure`` can hold (the run's own Rwp, the data file it points at, a
magnetic phase this package cannot model), and collapsing the two would either
discard those or invent fields for them.

**Dispatch is on content**, as ``io/CLAUDE.md`` § Dispatch requires of the
pattern readers and for the same reason: a suffix is a convention, not a fact.
``.inp`` in particular is written by several unrelated programs, so a reader
that claimed it by name would return a plausible wrong model for an Abaqus deck.

**The order is behaviour.**  Strongest evidence first, exactly as
``PATTERN_FORMATS`` does.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from ..formats.base import HEAD_BYTES, head, looks_binary
from . import fullprof, gsas, gsas2, topas
from .gsas import RECORD_BYTES

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ...schemas import Diagnostic, Structure

#: How much of a ``.inp`` a sniff may read.  Bounded for ``head()``'s reason (an
#: O(N) decode per dispatch) but larger than the pattern readers' ``HEAD_BYTES``,
#: because the evidence differs in *kind*: a pattern format and a ``.pcr`` are
#: recognised by a first line, while a ``.inp`` has no required opening at all
#: and its first block opener sits behind whatever macro-and-comment preamble
#: the author wrote.  Every format that can be claimed on a first line uses
#: ``HEAD_BYTES``; this budget is asked for by name, once, and the reason is the
#: format's grammar rather than a value that looked safe.
INP_SNIFF_BYTES = 65_536


@dataclass(frozen=True)
class ProjectFormat:
    """One foreign refinement format this build reads, and how it is recognised.

    A registry rather than a chain of imports because three consumers need the
    *same* facts and each would otherwise restate them: the dispatch in
    :func:`identify_project_format`, ``capabilities()`` (which must say what
    this build can actually open — WP-1007's rule, and its meta-test fails on a
    member missing from its arm), and the agent skill's routing row, which
    names the situation and lists the formats.
    """

    #: registry key, and what ``capabilities()`` publishes
    name: str
    #: what a person calls it
    title: str
    #: conventional suffixes — informational, never dispatch
    extensions: tuple[str, ...]
    #: how the format is recognised, in words a UI can show
    sniff: str
    #: what the file carries *beyond* a structure, in words.  The honest
    #: alternative to a union answer with optional fields: a client reads this
    #: to know what to ask for rather than reading ``None`` and guessing
    #: whether the file was silent or the reader failed
    carries: tuple[str, ...]
    #: **where this format's repairs are reported.**  A real per-format
    #: difference, not an accident to be papered over: the ``.inp`` reader
    #: normalises species and translates an origin suffix while parsing, so its
    #: channel is at read; the ``.pcr`` reader's four repairs all happen while
    #: converting codewords into a ``Structure``, so its channel is at build.
    #: ``"both"`` is the ``.EXP`` case, which arrived with the third member and
    #: is what showed the two-valued field to be a shape rather than a fact: it
    #: reports the histograms it could not carry while parsing *and* the species
    #: it normalises while building, so either single value would have dropped
    #: one channel **in silence** — the caller gets an empty list, which reads
    #: as "this file needed no repairs".  Pinned against the real signatures by
    #: a meta-test that partitions **both ways**, so a reader that grows or
    #: loses the keyword fails here rather than going quiet
    reports_at: Literal["read", "build", "both"]
    matches: Callable[[Path], bool]
    #: the format's own reader — returns what the file states
    read: Callable[..., Any]
    #: the format's own conversion to a :class:`~rietx.schemas.Structure`
    to_structure: Callable[..., Structure]
    #: why this format is recognised **in order to be refused**, or ``None`` for
    #: one that reads.  One field rather than a side table, so an entry says for
    #: itself which it is — ``PatternFormat.refuses``' reasoning, and the same
    #: filtering applies wherever a list of what the build *opens* is shown
    refuses: str | None = None


@dataclass(frozen=True)
class ProjectModel:
    """What a foreign refinement file stated, and which format stated it.

    The one type :func:`read_project_model` answers with, and deliberately
    **not** a union of every format's fields with blanks where a file was
    silent: a blank reads as an answer, and a caller cannot tell "this file
    carried none" from "the reader found none" (WP-1076's defaulted-lie trap).
    Instead this names the format and hands on the format's own model
    untouched, so every field a caller reads is one that format really has.

        model = rx.read_project_model("refined.pcr")
        model.format.name          # 'fullprof_pcr'
        model.stated.chi2          # the run's own figure, this format's field
        structure = model.to_structure()
    """

    format: ProjectFormat
    path: Path
    #: the format's own model — ``TopasModel``, ``FullProfModel``,
    #: ``GsasModel``.  Named for
    #: what it is: what the file *stated*, before any conversion
    stated: Any
    #: what the **read** reported, kept whether or not a caller asked for it.
    #: :class:`~rietx.io.recipe.Recipe` carries its own the same way and for the
    #: same reason: the keyword argument is for a caller accumulating across
    #: several files, while this is the durable record of what this one file
    #: needed repaired.  Empty here means the read repaired nothing — a fact,
    #: not the absence of one, which is the difference that matters — but only
    #: **where the format reports at read**.  Where
    #: :attr:`ProjectFormat.reports_at` is ``"build"`` the read has no channel
    #: at all, so this is always empty and says nothing either way; that
    #: format's repairs are on the list handed to :meth:`to_structure`.  Read
    #: ``format.reports_at`` before reading an empty tuple as an answer, which
    #: is WP-1076's trap in the one place this type could still spring it
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_structure(self, *, diagnostics: list[Diagnostic] | None = None,
                     **options: Any) -> Structure:
        """Build a :class:`~rietx.schemas.Structure` from what the file stated.

        ``options`` are the format's own conversion keywords — ``dataset`` for a
        multi-dataset ``.inp``, ``nuclear_only`` for a ``.pcr`` with a magnetic
        phase — passed through, so an unknown one raises naming itself rather
        than being dropped.  They are not flattened into one vocabulary here:
        two formats' options that happen to share a name would not share a
        meaning, and a registry that pretended otherwise would be inventing the
        agreement.

        ``diagnostics`` collects what *this* call repairs, which is a format's
        whole channel where :attr:`ProjectFormat.reports_at` is ``"build"``,
        none of it where that is ``"read"``, and half of it where that is
        ``"both"``.  The read's half is never lost
        either way: it is on :attr:`diagnostics` above, filled whether or not a
        caller passed a list to :func:`read_project_model`.  That is what keeps
        the asymmetry from becoming a trap — handing back an empty list reads as
        "this file needed no repairs", and a caller who passed the list to the
        other call would believe it (WP-1076).
        """
        if diagnostics is not None and self.format.reports_at in ("build", "both"):
            options["diagnostics"] = diagnostics
        return self.format.to_structure(self.stated, **options)


def _matches_fullprof_pcr(path: Path) -> bool:
    """A ``.pcr`` opens with a ``COMM`` title line.

    The sniff and the parser agree by construction: ``read_fullprof_pcr``
    refuses any file whose first non-blank line is not ``COMM``, so a file this
    claims is one that reader will at least get past its own first check.  That
    is the strongest evidence any member of this registry has, which is why it
    is first in the order.
    """
    for line in head(path, HEAD_BYTES).text.splitlines():
        if stripped := line.strip():
            return stripped.upper().startswith("COMM")
    return False


#: The top-level directives a **phase-less** ``.inp`` still states, so a Pawley
#: or indexing-only file is claimed too.  Only these are written out here: the
#: block openers come from the grammar itself, below.
_TOPAS_TOP_LEVEL = ("macro", "prm", "iters", "continue_after_convergence")

#: Block openers and top-level directives that are TOPAS's and nobody else's,
#: anchored at the start of a line.  The openers are **read from** the grammar's
#: own tuple (``topas._BLOCK_OPENERS``, the Technical Reference § 5.1 phase
#: tree) rather than restated here, because a restatement is a second grammar
#: that drifts in one direction only and in silence: an opener added there but
#: not here parses fine through ``read_topas_inp`` while ``read_project_model``
#: answers "not a refinement file this build can read".  Its order is inherited
#: with it, which is what keeps ``xdd`` behind ``xdd_scr``/``xdd_sum`` for the
#: alternation reason ``topas._BLOCK`` gives.
#:
#: ``STR`` is the one member taken out of that inheritance and spelled here as
#: ``STR(``: the macro is recognised **in order to be refused by name** — a
#: refusal naming the file is the answer, and declining to *recognise* it would
#: send the file to "no format claims this", the worse message — while a bare
#: ``STR`` token is not evidence of a ``.inp`` the way the lower-case openers
#: are.
_TOPAS_LINE = re.compile(
    r"^[ \t]*(?:"
    + "|".join([*(k for k in topas._BLOCK_OPENERS if k != "STR"),
                *_TOPAS_TOP_LEVEL])
    + r")\b"
    r"|^[ \t]*STR[ \t]*\(", re.M)


#: The record keys a ``.EXP`` is claimed on, anchored at column 0 of an
#: 80-character card.  Taken from the format's own vocabulary rather than
#: invented: ``VERSION`` is written by ``OPNEXP`` when the file is created, and
#: ``EXPR``/``CRS``/``HST`` are the experiment, phase and histogram blocks that
#: any file holding a refinement carries.  A key alone would be weak evidence —
#: ``HST`` is an ordinary word — which is why the record *width* is tested too.
#:
#: **Bytes, not text.**  These are matched against the head's raw bytes because
#: the width test below has to be, and a sniff that measured one and matched the
#: other would be two descriptions of the same card.
_EXP_KEYS = (b"     VERSION", b"      DESCR ", b" EXPR ", b"CRS", b"HST ", b"HAP")


def _matches_gsas_exp(path: Path) -> bool:
    """A ``.EXP`` is a card index: 80-character records with 12-character keys.

    Two tests together, because neither alone is safe.  The record **width** is
    a structural invariant of the format — GSAS read these files by direct
    access, so every card is exactly 80 characters — and a key from the
    format's own vocabulary sits at column 0.  A file that satisfies both is
    not plausibly anything else; a file that satisfies only the width could be
    any fixed-column table, and one satisfying only the keys could be prose
    about GSAS.

    **Measured on the head's bytes rather than its text**, which is the one
    subtle thing here.  ``head`` decodes as UTF-8 with ``errors="ignore"``, so a
    byte that is not valid UTF-8 is *dropped* — and a ``.EXP`` is a Latin-1 byte
    format whose ``DESCR`` title is whatever the experimenter typed.  One
    accented character in a title would shorten that record to 79 characters
    after decoding and make this sniff reject the whole file.  The bytes cannot
    lose a character, and the keys are ASCII, so nothing is given up by reading
    them there.

    Line endings are not part of the test.  Real files terminate each card with
    CR LF and some write the cards end to end with none at all, so the width is
    measured on whichever of the two the file turns out to be.
    """
    raw = head(path, HEAD_BYTES).raw
    if b"\n" in raw or b"\r" in raw:
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        # the last line of a bounded head read is usually truncated
        lines = lines[:-1] or lines
        if not lines or any(len(ln) != RECORD_BYTES for ln in lines):
            return False
    else:
        if len(raw) < RECORD_BYTES:
            return False
        lines = [raw[i:i + RECORD_BYTES]
                 for i in range(0, len(raw) - RECORD_BYTES + 1, RECORD_BYTES)]
    return any(ln.startswith(_EXP_KEYS) for ln in lines)


#: The tree-item labels a ``.gpx`` head carries, as bytes.  Every corpus file's
#: first 4 kB holds at least one: 33 of 34 open on ``Notebook`` and the
#: thirty-fourth on ``Phases``.  They are matched as bytes because the file is
#: one, and pickled strings carry a length prefix rather than a quote, so a
#: decoded head would only add a way to lose a byte.
_GPX_LABELS = (b"Notebook", b"Controls", b"Covariance", b"Constraints",
               b"Restraints", b"Rigid bodies", b"Phases", b"PWDR ")


def _matches_gsas2_gpx(path: Path) -> bool:
    """A ``.gpx`` is a pickle whose first item is a labelled tree item.

    Two tests, because neither alone is safe.  The stream has to **open as a
    pickle**: either the protocol-2 header byte, or the list opcode that a tree
    item starts with directly.  And one of GSAS-II's own top-level labels has to
    appear in the head.  A file passing both is not plausibly anything else; a
    file passing only the first is any pickle at all, which is exactly what this
    reader must not open on the strength of a suffix.

    **The header byte is not enough on its own, and that is measured**: 11 of
    the 34 tutorial projects carry no protocol header at all, so a sniff written
    to the protocol-2 magic alone would have declined a third of them.
    """
    raw = head(path, HEAD_BYTES).raw
    return raw[:1] in (b"\x80", b"]") and any(k in raw for k in _GPX_LABELS)


def _matches_topas_inp(path: Path) -> bool:
    """A ``.inp`` is claimed on a line-start TOPAS keyword, never on its suffix.

    ``.inp`` is an extension several unrelated programs write, so the suffix
    cannot be the evidence — ``io/CLAUDE.md`` § Dispatch, and WP-1407's rule one
    rank up, that a file extension does not name a format here.

    Anchoring at line start is what keeps the test honest rather than merely
    cheap: every keyword below also occurs inside quoted paths and prose, and a
    file holding ``xdd "C:\\data\\str\\run.xy"`` states one opener and not two.
    Comments go first for the same reason — the reader's own
    :func:`~rietx.io.projects.topas.strip_comments` handles ``'`` to end of line
    *and* nesting ``/* */`` blocks, and a sniff that reimplemented either would
    be a second grammar to keep in step.
    """
    return bool(_TOPAS_LINE.search(
        topas.strip_comments(head(path, INP_SNIFF_BYTES).text)))


#: The registry, **ordered**, and the order is behaviour: the first format whose
#: ``matches`` returns True claims the file.  ``PATTERN_FORMATS``' "strongest
#: evidence first", applied to four members rather than sixteen.  GSAS-II is
#: first because it is the one **binary** member, and ``PATTERN_FORMATS``' rule
#: that binary-claiming formats go first holds for the same reason here: every
#: other sniff decodes the head with ``errors="ignore"``, so a pickle handed to
#: them arrives as text with its bytes quietly dropped.  FullProf and GSAS then
#: test something their formats *require* — a ``COMM`` title line, and an
#: 80-character card carrying a key from a closed vocabulary — and they cannot
#: collide, so their relative order is immaterial and is left as it was.
#: TOPAS is last because its evidence is a keyword anywhere in a 64 kB head,
#: which is the one weak test here and the one a file could satisfy by accident.
PROJECT_FORMATS: tuple[ProjectFormat, ...] = (
        ProjectFormat(
            name="gsas2_gpx",
            title="GSAS-II .gpx",
            extensions=(".gpx",),
            sniff="a pickle stream whose head carries one of GSAS-II's own "
                  "top-level tree labels",
            carries=("phases", "sites", "refine flags", "the constraints and "
                     "which variables the run refined", "the instrument "
                     "coefficients and their flags", "the range fitted and any "
                     "excluded regions", "the sample broadening per phase and "
                     "histogram", "the run's own Rwp and goodness of fit"),
            reports_at="both",
            matches=_matches_gsas2_gpx,
            read=gsas2.read_gsas2_gpx,
            to_structure=gsas2.to_structure,
        ),
        ProjectFormat(
            name="fullprof_pcr",
            title="FullProf .pcr",
            extensions=(".pcr",),
            sniff="a COMM title line, which the format requires first",
            carries=("phases", "sites", "refine flags and their ties",
                     "instrument resolution function", "the run's own chi2 "
                     "and per-phase R_Bragg", "the data file it points at"),
            reports_at="build",
            matches=_matches_fullprof_pcr,
            read=fullprof.read_fullprof_pcr,
            to_structure=fullprof.to_structure,
        ),
        ProjectFormat(
            name="gsas_exp",
            title="GSAS .EXP",
            extensions=(".exp", ".EXP"),
            sniff="80-character records whose first 12 characters are a GSAS "
                  "record key — the width is a structural invariant of the "
                  "format and the key comes from its own closed vocabulary",
            carries=("phases", "sites", "refine flags", "the emission lines "
                     "and their polarization", "the excluded regions", "the "
                     "profile and background coefficients with their flags",
                     "the run's own Rwp, Rp and reduced chi-squared", "the "
                     "data and instrument files it points at"),
            reports_at="both",
            matches=_matches_gsas_exp,
            read=gsas.read_gsas_exp,
            to_structure=gsas.to_structure,
        ),
        ProjectFormat(
            name="topas_inp",
            title="TOPAS .inp",
            extensions=(".inp",),
            sniff="a TOPAS block opener or top-level directive at the start of "
                  "a line — never the suffix, which several unrelated programs "
                  "also write",
            carries=("phases", "sites", "refine flags", "the emission profile",
                     "the run's own Rwp and GoF", "the data files it points at"),
            reports_at="read",
            matches=_matches_topas_inp,
            read=topas.read_topas_inp,
            to_structure=topas.to_structure,
        ),
)


def identify_project_format(path: str | Path) -> ProjectFormat:
    """Which registered project format claims ``path`` — the dispatch, once.

    Raises ``ValueError`` naming the formats this build does read.  Saying
    **which** is the whole difference between a message and a traceback, and it
    is built from the registry rather than written out, so a format added
    tomorrow appears in it (``identify_format``'s reasoning, one registry over).

    The binary note is the other half of that same reasoning.  Every sniff here
    decodes with ``errors="ignore"``, so a vendor binary handed to this door
    reaches the refusal looking exactly like a text file nothing claimed — and
    the three readers the message then points at are all the wrong advice for
    it.  Saying so costs one head read, on the path that is already failing.
    """
    p = Path(path)
    for fmt in PROJECT_FORMATS:
        if fmt.matches(p):
            return fmt
    why = " (it looks binary)" if looks_binary(head(p)) else ""
    known = ", ".join(f"{f.title} [{', '.join(f.extensions)}]"
                      for f in PROJECT_FORMATS if f.refuses is None)
    raise ValueError(
        f"{p.name} is not a refinement file this build can read{why}. "
        f"Supported: {known}. A powder pattern goes through read_pattern, a "
        f"GSAS-I instrument-parameter file through read_gsas_prm, and a "
        f"PowderLine recipe through read_recipe.")


def read_project_model(path: str | Path, *,
                       diagnostics: list[Diagnostic] | None = None) -> ProjectModel:
    """Read a refinement another program wrote, dispatching on *content*.

    The one door for "someone handed me a file and I do not know what wrote it".
    Returns what the file stated, tagged with the format that claimed it; call
    :meth:`ProjectModel.to_structure` for a :class:`~rietx.schemas.Structure`.

    ``diagnostics`` collects what the reader **repaired or assumed** — a rewritten
    species spelling, a translated origin suffix — the same opt-in channel
    :func:`~rietx.io.read_pattern` and
    :func:`~rietx.structure_from_cif` take, and for a caller accumulating across
    several files.  Whatever the read reports lands on
    :attr:`ProjectModel.diagnostics` too, list or no list, so the answer always
    carries what its own file needed; a format reporting at build
    (:attr:`ProjectFormat.reports_at`) reports through
    :meth:`ProjectModel.to_structure` instead, and passing a list to both is
    the way to collect either without knowing which format claimed the file.

    A construct the reader cannot honour raises the format's own error — a
    ``ValueError`` naming the file and the line — never a bare parser
    exception, and never a half-built model.  That is ``io/CLAUDE.md``
    § Project readers' rule: a project reader refuses where a pattern reader
    would repair, because its output is a whole model and a caller cannot see
    which part of it is the file's.
    """
    p = Path(path)
    fmt = identify_project_format(p)
    if fmt.reports_at not in ("read", "both"):
        return ProjectModel(format=fmt, path=p, stated=fmt.read(p))
    # Read into a list of this function's own and copy the caller's in at the
    # end, rather than handing the reader the caller's list directly: the
    # answer must carry its own file's reports whether or not one was passed,
    # and a caller accumulating across several files must still see them
    # appended to theirs.  Extending rather than assigning keeps that list the
    # caller's own object, which is what ``read_pattern``'s channel promises.
    found: list[Diagnostic] = []
    try:
        stated = fmt.read(p, diagnostics=found)
    finally:
        # `finally`, not after the call, so a read that repairs three things and
        # *then* refuses still leaves those three in the caller's list — which
        # is what `read_pattern` does by handing its list straight down, and
        # this docstring claims parity with it.  They say how far the read got
        # and what it had already found, which is the most useful thing a caller
        # holding an exception has.
        if diagnostics is not None:
            diagnostics.extend(found)
    return ProjectModel(format=fmt, path=p, stated=stated,
                        diagnostics=tuple(found))
