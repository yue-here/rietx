"""Reduced total-scattering files — G(r), S(Q), F(Q) — recognised in order to be refused.

A pair distribution function analysis reduces a total-scattering measurement to
a function of the scattering vector Q (the structure factor S(Q), the reduced
structure function F(Q) = Q[S(Q) − 1]) and transforms that into a function of a
real-space distance r (the reduced PDF G(r)).  Three writers account for almost
every such file a user holds: PDFgetX2, PDFgetX3 (and the diffpy tools that
share its output layout), and a bare two-column export.  None of them is a
powder pattern, and none has a 2θ axis.

**What went wrong before this entry existed** (issue #1240).  Every one of these
files fell to the ASCII catch-all, which read the r or Q column as 2θ in degrees
and raised nothing a reader would act on: a ``.gr`` running 0.01–20 Å came back
as a scan from 0.01° to 20°, and a ``.sq``'s constant ``d_Q`` column became σ.
The maintainer reproduced it on issue #192 with a small file carrying a
``#L r(A) G(r)`` line.  Total scattering is fenced (``ROADMAP`` § v2+, #192), so
this module reads nothing; it only stops a silent misread.

**The evidence is tiered, as ``peaklist.py`` tiers it** (WP-1407): a refusal
claims only what its evidence allows, and the message says which tier matched.

- **The file's own column labels**, whatever its suffix: a SPEC-style ``#L``
  line whose first two labels are a distance r and a G or g, or a Q and an S or
  F.  PDFgetX2, PDFgetX3 and PDFgui all write that line, and a diffraction scan
  never labels its abscissa r.
- **A writer's header**, whatever its suffix: PDFgetX2 opens with a ``History
  written`` line and a ``Get_XPDF`` banner; PDFgetX3 with a ``[DEFAULT]``
  configuration section, bare (2.1.0) or behind ``#`` (1.0), holding a
  ``qmaxinst`` key or a PDFgetX3 version.  Every output either writes is on a Q or an r axis.  The banner is
  read here because PDFgetX2's ``#L`` line sits past the 4 kB sniff window in
  real files (about 6 kB in), so the labels alone would miss them.
- **The suffix alone**: a ``.gr``, ``.sq`` or ``.fq`` with neither.  A bare
  two-column G(r) cannot be told from a pattern by its numbers, so the suffix is
  the only evidence there is, and the message says it matched the name and not
  the columns.  The escape is the one ``peaklist.py`` offers: under any other
  name the file reaches the ASCII reader.

A comment that merely *mentions* G(r) claims nothing: only an ``#L`` label line
counts, so an ordinary ``.xy`` opens as before.

**The refusal carries a code** (``PATTERN_TOTAL_SCATTERING``), unlike the peak-list
refusals, because a caller that passed ``diagnostics=`` should be able to branch
on what the file *is* rather than on the wording of an exception.  The code is
appended to that list before :class:`TotalScatteringRefused` is raised, and the
exception carries the same :class:`~rietx.schemas.common.Diagnostic`.

**Its position** is with the other refusals, directly above ``xy``: it can
shadow no reader above it, and it is the one entry the ASCII catch-all needs to
be told apart from.

Clean room: the header shapes are output facts, read from files the writers
produced and from PDFgetX3's published description (Juhás et al., J. Appl.
Cryst. 46, 560–566, 2013); no writer's source was opened.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, head, looks_binary

#: The suffixes the PDF writers use for their outputs, with the function each
#: holds.  PDFgetX2 states this mapping in its own header (``grfilesurfix=.gr``),
#: and PDFgetX3 and PDFgui use the same three.
_SUFFIXES: dict[str, str] = {
    ".gr": "G(r), a real-space pair distribution function",
    ".sq": "S(Q), a total-scattering structure factor on a Q axis",
    ".fq": "F(Q), a reduced structure function on a Q axis",
}

#: A SPEC-style column-label line, its first two labels captured.
_LABEL_LINE = re.compile(r"^#L[ \t]+(\S+)[ \t]+(\S+)", re.M)

#: An abscissa label: the letter, then a unit in parentheses or nothing.
#: ``r(A)`` and ``r(Å)`` from the writers; ``Q(/A)`` and ``Q(Å$^{-1}$)``.
_R_LABEL = re.compile(r"^r(?:\(.*\))?$", re.I)
_Q_LABEL = re.compile(r"^Q(?:\(.*\))?$", re.I)
#: The ordinate labels that make the pair a total-scattering function: G(r) or
#: g(r) on an r axis, S(Q) or F(Q) on a Q axis.  ``I(Q)`` is not here — an
#: intensity on a Q axis is a diffraction pattern in another variable, and is
#: not what this code says.
_G_LABEL = re.compile(r"^[Gg](?:\(.*\))?$")
_SF_LABEL = re.compile(r"^[SF](?:\(.*\))?$")

#: PDFgetX2's header: the opening history line and the program's banner.  A
#: line may end in ``\r``: the real files were written on Windows, and ``$``
#: under ``re.M`` matches only before ``\n``.
_PDFGETX2_HISTORY = re.compile(r"\AHistory written:")
_PDFGETX2_BANNER = re.compile(r"^#+[ \t]*Get_XPDF[ \t]*#+[ \t\r]*$", re.M)

#: PDFgetX3's header: its configuration section and one key only it writes.
#: Version 1.0 writes the block behind ``#`` (``#[DEFAULT]``, ``#qmaxinst = 27``,
#: ``#version = pdfgetx3-1.0-…``); 2.1.0 writes it bare (``version =
#: diffpy.pdfgetx-2.1.0``).  Both are matched.
_PDFGETX3_SECTION = re.compile(r"\A\s*#?\[DEFAULT\][ \t\r]*$", re.M)
_PDFGETX3_KEY = re.compile(
    r"^#?(?:qmaxinst[ \t]*=|version[ \t]*=[ \t]*(?:diffpy\.pdfgetx|pdfgetx3))",
    re.M)

#: What a caller can do, the same in every message.
_REMEDY = (
    "rietx does not read total-scattering data yet (issue #192 tracks it), "
    "and refining this file as a pattern would fit a Bragg model to a function "
    "of r or Q while reporting a plausible Rwp. Refine the diffraction pattern "
    "the reduction started from instead")


class TotalScatteringRefused(ValueError):
    """A total-scattering file handed to :func:`rietx.read_pattern`.

    ``diagnostic`` is the ``PATTERN_TOTAL_SCATTERING`` record the message was
    built from, so a caller can branch on the code rather than the wording.
    """

    def __init__(self, diagnostic: Diagnostic):
        self.diagnostic = diagnostic
        super().__init__(f"{diagnostic.code}: {diagnostic.message}")


def _labelled(text: str) -> tuple[str, str] | None:
    """``(the function, the labels as written)`` from the first ``#L`` line
    that labels one, else ``None``."""
    for x, y in _LABEL_LINE.findall(text):
        if _R_LABEL.match(x) and _G_LABEL.match(y):
            held = (_SUFFIXES[".gr"] if y[0] == "G"
                    else "g(r), a real-space pair distribution function")
            return held, f"{x} {y}"
        if _Q_LABEL.match(x) and _SF_LABEL.match(y):
            return _SUFFIXES[".sq" if y[0] == "S" else ".fq"], f"{x} {y}"
    return None


def _writer(text: str) -> str | None:
    """``"PDFgetX2"`` or ``"PDFgetX3"`` where the head is that writer's header."""
    if _PDFGETX2_HISTORY.search(text) and _PDFGETX2_BANNER.search(text):
        return "PDFgetX2"
    if _PDFGETX3_SECTION.search(text) and _PDFGETX3_KEY.search(text):
        return "PDFgetX3"
    return None


def _evidence(p: Path) -> tuple[str, str, bool] | None:
    """``(what the file holds, what said so, whether the contents said so)``,
    or ``None`` when nothing does."""
    h = head(p)
    if looks_binary(h):
        return None
    suffix = p.suffix.lower()
    labelled = _labelled(h.text)
    writer = _writer(h.text)
    if writer is not None:
        held = (labelled[0] if labelled is not None else _SUFFIXES.get(
            suffix, "a function of Q or r (that writer's outputs are I(Q), "
            "S(Q), F(Q) and G(r), none on a 2θ axis)"))
        return held, f"its header is {writer}'s", True
    if labelled is not None:
        return (labelled[0],
                f"its #L line labels the columns '{labelled[1]}'", True)
    if suffix in _SUFFIXES:
        return _SUFFIXES[suffix], (
            f"its {suffix} suffix is the one the PDF writers give that "
            "function. This was matched on the name and not the columns: a "
            "bare two-column file cannot be told from a pattern by its "
            "numbers"), False
    return None


def looks_total_scattering(p: Path) -> bool:
    return _evidence(p) is not None


def read_total_scattering(path: str | Path, *,
                          diagnostics: list[Diagnostic] | None = None) -> PatternData:
    """Always raises — the refusal *is* the behaviour (see the module docstring).

    The ``PATTERN_TOTAL_SCATTERING`` record goes onto ``diagnostics`` first,
    when a list was passed, and rides on the exception either way.
    """
    p = Path(path)
    found = _evidence(p)
    held, why, by_content = found if found is not None else (
        "a total-scattering function", "it was handed to this reader by name",
        False)
    escape = ("" if by_content
              else " If it really is a 2θ scan, it opens under any other name.")
    d = Diagnostic(
        level="error", code="PATTERN_TOTAL_SCATTERING",
        message=(
            f"{p.name} holds {held}, not a powder pattern on a 2θ axis "
            f"({why}). {_REMEDY}.{escape}"),
    )
    if diagnostics is not None:
        diagnostics.append(d)
    raise TotalScatteringRefused(d)


TOTAL_SCATTERING = PatternFormat(
    name="total_scattering",
    title="Total-scattering function (.gr, .sq, .fq — PDFgetX2, PDFgetX3, bare)",
    extensions=tuple(_SUFFIXES),
    sniff=("an #L line labelling r against G, or Q against S or F; a PDFgetX2 "
           "or PDFgetX3 header; or, with neither, the .gr/.sq/.fq suffix alone "
           "— the message says which matched"),
    sigma="none — the file is refused before any σ question arises",
    refuses=("a reduced total-scattering function, G(r) on an r axis or S(Q) or "
             "F(Q) on a Q axis, not a powder pattern; rietx does not read one "
             "yet (#192)"),
    matches=looks_total_scattering,
    read=read_total_scattering,
)
