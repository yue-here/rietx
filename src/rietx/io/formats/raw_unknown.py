"""A binary ``.raw`` no reader claimed — declined without naming a vendor.

``.raw`` is written by **six unrelated vendors**: Bruker/Siemens DIFFRAC, GSAS,
Rigaku, Scintag, Shimadzu and Stoe.  The suffix settles nothing, which is why
dispatch in this package is content-first and ``extensions`` is informational.
By the time a file reaches this entry every reader in the registry has already
declined it, so what is left to say is exactly that — and it is worth saying,
because the alternative message ("not a powder pattern this build can read")
invites the reasonable but wrong conclusion that the file is corrupt.

**This entry deliberately claims to recognise nothing.**  The format most likely
to land here is Stoe's, and Stoe has *no description in any licence anywhere*:
it is absent from xylib, CrysFML, GSAS-II and PyXRD alike, and the only tool
that reads it is the closed-source PowDLL.  That is the footing Bruker ``.raw``
v1 was refused on.  With no description there is no magic to test, so asserting
"this is a Stoe file" would be precisely the guess this whole area exists to
prevent.  The message names the six candidates, says which this build reads,
and points at the vendor's own ASCII export.

**It is last in the registry**, after the ASCII catch-all rather than among the
binary formats.  That position is load-bearing and is the reason this entry
cannot shadow a reader: it is reached only when everything else has already
been asked, so no ordering mistake can route a real Bruker or Philips file here.

This is where a Stoe reader hangs if the files ever arrive.  The cheap ask that
would unblock one: a few ``.raw`` files paired with the WinXPOW ASCII export of
the *same* scans, including at least one multi-range file.  That pairing is an
exact oracle and beats any written description.
"""

from __future__ import annotations

from pathlib import Path

from ...schemas.pattern import PatternData
from .base import PatternFormat, head, looks_binary

#: Everyone who writes ``.raw``, for the message.  Data rather than prose in the
#: sentence so the count and the list cannot drift apart.
_RAW_VENDORS = ("Bruker/Siemens DIFFRAC", "GSAS", "Rigaku", "Scintag",
                "Shimadzu", "Stoe")


def looks_unclaimed_raw(p: Path) -> bool:
    return p.suffix.lower() == ".raw" and looks_binary(head(p))


def read_unknown_raw(path: str | Path, *, diagnostics=None) -> PatternData:
    """Always raises — the refusal *is* the behaviour (see the module docstring)."""
    p = Path(path)
    raise ValueError(
        f"{p.name} is a binary .raw that none of this build's readers claimed. "
        f"The suffix is written by {len(_RAW_VENDORS)} unrelated vendors "
        f"({', '.join(_RAW_VENDORS)}) and says nothing about which, so this is "
        "not a statement that the file is corrupt. What this build reads is "
        "Bruker/Siemens DIFFRAC v2 (single-range), v3 and v4, and Philips PC-APD "
        "(.rd/.sd, which also turns up named .raw); Bruker v1 is refused by "
        "name. "
        "Nothing here can tell you which vendor wrote this one — claiming "
        "otherwise would be a guess, and a wrongly-parsed pattern looks "
        "perfectly plausible. Export the scan as ASCII from the instrument "
        "software instead: .xy, .udf, .uxd, .xrdml, .cpi and GSAS .fxye all "
        "open here")


RAW_UNKNOWN = PatternFormat(
    name="raw_unclaimed",
    title="Unrecognised binary .raw",
    extensions=(".raw",),
    sniff=("a binary file named .raw that every reader above declined — matched "
           "last, so it claims nothing except that the readers were all asked. "
           "Six unrelated vendors write .raw and this entry does not guess "
           "between them"),
    sigma="none — the file is refused before any σ question arises",
    refuses=("the .raw suffix is shared by six unrelated vendors and this file "
             "matched none of the readers. Not a claim that it is corrupt, and "
             "not a claim about which vendor wrote it"),
    matches=looks_unclaimed_raw,
    read=read_unknown_raw,
)
