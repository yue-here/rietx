"""The legacy LANSCE ``.iparm`` layout: :func:`read_lansce_iparm`.

Instrument files written at LANSCE deviate from the layout the GSAS Technical
Manual documents (Larson & Von Dreele 2004, LAUR 86-748, p. 221-223) in three
ways, none described there.
:func:`rietx.io.instrument_tof.read_gsas_tof_iparm` refuses all three and
stays that way.  This reader accepts them on request, each reported as
``GSAS_IPARM_LEGACY_LAYOUT`` (level ``info``):

1. **An 8-coefficient type-1 ``PRCF`` block** — the default set declares
   ``PTYP 1, NCOF 8`` in two coefficient records, where the manual documents
   twelve names for profile function 1 (p. 144: ``alp-0 alp-1 bet-0 bet-1
   sig-0 sig-1 sig-2 s1ec s2ec rstr rsta rsca``).  **Read as slots 1-8 of the
   documented twelve**, slots 9-12 zero, by restating the header's ``NCOF`` as
   12 and adding a ``PRCFn3`` record of zeros, then handing the records to the
   strict reader's own body — so every column check, the anisotropic-term
   refusal (slot 8 is ``s1ec``) and the variance-sign check apply unchanged.
   **Slots 1, 5 and 8 are read as ``alp-0``, ``sig-0`` and ``s1ec`` because
   the manual's order is the source**: GSAS-II v5.8.2 carrying those three
   slots under no name is silence, not contradiction.
2. **A non-zero fifth ``ICOFF`` pair of ITYP 1/2** — P₁₀ and P₁₁, a pair the
   manual's printed series stops short of.  The strict reader refuses it
   because it holds to the documented layout, so this reader passes it
   through that reader's body with the one switch the body offers
   (``fifth_pair=True``) and nothing else changed.  The pair is carried on
   :class:`~rietx.schemas.instrument.IncidentSpectrum` as written, and a fit
   evaluates it as P₁₀·exp(−P₁₁·T⁵), T in ms, the exponent measured by
   conformance (:mod:`rietx.model.tof_spectrum`).
3. **A ``BNKPAR`` value one field too wide** — a TTHETA such as ``46.60``
   written in columns 30-34, across the TTHETA/TILT boundary, which the
   strict column check refuses.  **That one record, and no other**, is
   re-read by whitespace tokens (up to five reals DIST TTHETA TILT SEPN HGHT,
   then up to two integers NTUBE ITUBE), each token restated right-aligned in
   its own columns and the record handed on; a token that is not a number of
   its field's kind, or does not fit its field, leaves the record as it was
   for the strict reader to refuse.  GSAS-II v5.8.2 reads such a record as
   the value the token read takes.

A file carrying none of the three is read by the strict reader and returned
exactly as it returns it.  The tests (``tests/test_lansce_iparm.py``) build
synthetic files carrying the three deviations at the layout's own column
widths; none of their numbers is a real bank's.

**How the layout was confirmed — GSAS-II as a black box, nothing read.**
GSAS-II v5.8.2 (revision 5841), run through its public scripting API only:
``G2sc.G2Project(newgpx=…)``, ``.add_powder_histogram(flat.xye, file.prm,
fmthint="xye", instbank=b)``, then ``hist.data["Instrument Parameters"]``.
Synthetic files with a distinct sentinel in one slot at a time place every
slot (:data:`GSAS2_PRCF1_DESTINATIONS`): slots 2, 3, 4, 6, 7 land under
``alpha, beta-0, beta-1, sig-1, sig-2``, and slots 1, 5, 8 under no name at
all — and a 12-slot type-1 block gives the same destinations slot for slot.
So GSAS-II reads the 8-slot block as the 12-slot block cut short, which is the
restatement above.  No GSAS-II source was opened.
"""

from __future__ import annotations

from pathlib import Path

from ...schemas.common import Diagnostic
from ...schemas.instrument import Instrument
from ..instrument_tof import (
    _BNKPAR_FIELDS,
    _ITYP_FIELDS,
    _PRCF_FIELDS,
    PRCF_COEFFICIENT_NAMES,
    _banks_from_records,
    _note,
    _read_records,
    _Record,
    read_gsas_tof_iparm,
)

#: The legacy block's declared coefficient count for profile function 1.
LEGACY_PRCF1_NCOF = 8

#: The eight slots, named as slots 1-8 of the documented twelve (GSAS
#: Technical Manual p. 144) — confirmed by GSAS-II v5.8.2 reading an 8-slot and
#: a 12-slot block slot for slot alike (module docstring).
LEGACY_PRCF1_SLOT_NAMES: tuple[str, ...] = PRCF_COEFFICIENT_NAMES[1][:LEGACY_PRCF1_NCOF]

#: Where GSAS-II v5.8.2 puts each of the eight slots, measured one sentinel at
#: a time (module docstring); ``None`` is a slot it carries under no name.
GSAS2_PRCF1_DESTINATIONS: tuple[str | None, ...] = (
    None, "alpha", "beta-0", "beta-1", None, "sig-1", "sig-2", None)

#: How many of ``BNKPAR``'s fields are reals (DIST TTHETA TILT SEPN HGHT); the
#: rest (NTUBE ITUBE) are integers — its documented layout, 5F10 then 2I5.
_BNKPAR_REALS = 5

_ZERO_E15 = f"{0.0:15.6E}"


def _legacy_prcf1(path: Path, number: int, line: str) -> bool:
    rec = _Record(path, number, line)
    rec.check_columns(_PRCF_FIELDS)
    return (rec.integer(13, 17, "PTYP"), rec.integer(18, 22, "NCOF")) == (
        1, LEGACY_PRCF1_NCOF)


def _fifth_pair(path: Path, number: int, line: str) -> tuple[float, float]:
    fields = _Record(path, number, line).e15_block()
    out = []
    for f in fields[1:3]:
        s = f.strip()
        try:
            out.append(float(s.replace("D", "E")) if s else 0.0)
        except ValueError:
            out.append(0.0)       # the strict reader names a non-number itself
    return out[0], out[1]


def _bnkpar_by_tokens(line: str) -> tuple[str, list[float | int]] | None:
    """A ``BNKPAR`` record's payload restated right-aligned, and the values
    its tokens took — or ``None`` where the tokens are not that record's
    fields (too many, not a number of the field's kind, wider than the field),
    so the record goes to the strict reader as written and is refused there."""
    tokens = line.rstrip("\r\n")[12:].split()
    if not 0 < len(tokens) <= len(_BNKPAR_FIELDS):
        return None
    cells, values = [], []
    for k, tok in enumerate(tokens):
        a, b, _ = _BNKPAR_FIELDS[k]
        try:
            v = float(tok) if k < _BNKPAR_REALS else int(tok)
        except ValueError:
            return None
        if len(tok) > b - a + 1:
            return None
        cells.append(tok.rjust(b - a + 1))
        values.append(v)
    return "".join(cells), values


def _scan(path: Path, records: list[tuple[str, str]]):
    """Which banks carry which deviation: ``(legacy PRCF banks, PRCF1
    continuation tags per bank, ITYP per bank, non-zero fifth pairs per bank,
    BNKPAR restatements per record index)``."""
    legacy_banks: list[int] = []
    conts: dict[int, list[int]] = {}
    fifth: dict[int, tuple[float, float]] = {}
    ityp: dict[int, int] = {}
    icoff3: dict[int, int] = {}
    bnkpar: dict[int, tuple[int, str, str, list]] = {}
    for number, (key, payload) in enumerate(records, start=1):
        line = key + payload
        bb, name = line[4:6], line[6:12]
        if not line.startswith("INS ") or not bb.strip().isdigit():
            continue           # the strict reader refuses a bad bank field
        b = int(bb)
        if name == "PRCF1 " and _legacy_prcf1(path, number, line):
            legacy_banks.append(b)
        elif name.startswith("PRCF1") and name[5].isdigit():
            conts.setdefault(b, []).append(int(name[5]))
        elif name == "I ITYP":
            rec = _Record(path, number, line)
            rec.check_columns(_ITYP_FIELDS)
            ityp[b] = rec.integer(13, 17, "ITYP")
        elif name == "ICOFF3":
            icoff3[b] = number
        elif name == "BNKPAR":
            try:
                _Record(path, number, line).check_columns(_BNKPAR_FIELDS)
            except ValueError:
                restated = _bnkpar_by_tokens(line)
                if restated is not None:
                    bnkpar[number - 1] = (b, line.rstrip("\r\n").rstrip(),
                                          *restated)
    for b, number in icoff3.items():
        if ityp.get(b) in (1, 2):
            pair = _fifth_pair(path, number, "".join(records[number - 1]))
            if pair != (0.0, 0.0):
                fifth[b] = pair
    return legacy_banks, conts, ityp, fifth, bnkpar


def read_lansce_iparm(path: str | Path, *,
                      diagnostics: list[Diagnostic] | None = None
                      ) -> dict[int, Instrument]:
    """Read a GSAS-I TOF ``.iparm`` that may carry the legacy LANSCE layout.

    Returns what :func:`rietx.read_gsas_tof_iparm` returns — ``{bank number:
    Instrument}``, every parameter ``vary=False`` — and is that function,
    unchanged, on a file carrying none of the three deviations the module
    docstring names.  Each deviation it accepts is reported as
    ``GSAS_IPARM_LEGACY_LAYOUT`` (level ``info``): one per ``BNKPAR`` record
    re-read by tokens (its ``where`` ends ``"BNKPAR"``), one per file for the
    8-coefficient ``PRCF`` block (``"PRCF1"``), one per file for the non-zero
    ITYP 1/2 fifth ``ICOFF`` pairs (``"ICOFF3"``), each naming its banks.
    Anything else the strict reader refuses is refused by it, with its
    message.
    """
    path = Path(path)
    records = _read_records(path)
    try:
        legacy_banks, conts, ityp, fifth, bnkpar = _scan(path, records)
    except ValueError:
        # a record this scan cannot read is the strict reader's to name, in
        # its own order; should it read the file after all, the scan's
        # refusal stands
        read_gsas_tof_iparm(path)
        raise

    if not legacy_banks and not fifth and not bnkpar:
        return read_gsas_tof_iparm(path, diagnostics=diagnostics)

    restated = list(records)
    for i, (_, _, payload, _) in bnkpar.items():
        restated[i] = (restated[i][0], payload)
    for b in legacy_banks:
        if sorted(conts.get(b, [])) != [1, 2]:
            raise ValueError(
                f"{path}: bank {b}'s PRCF set 1 declares profile function 1 with "
                f"{LEGACY_PRCF1_NCOF} coefficients and carries coefficient "
                f"records {sorted(conts.get(b, []))}; the legacy LANSCE layout "
                f"this reader accepts is exactly two records, PRCF11 and PRCF12, "
                f"and any other shape is refused rather than restated")
        for i, (key, payload) in enumerate(restated):
            if key == f"INS {b:2d}PRCF1 ":
                line = (key + payload).ljust(22)
                restated[i] = (key, (line[:17] + f"{12:5d}" + line[22:])[12:])
        restated.append((f"INS {b:2d}PRCF13", _ZERO_E15 * 4))

    out = _banks_from_records(path, restated, diagnostics, fifth_pair=bool(fifth))

    for i, (b, raw, _, values) in sorted(bnkpar.items()):
        took = ", ".join(f"{n} = {v!r}" for (_, _, n), v in zip(_BNKPAR_FIELDS, values))
        _note(diagnostics, "info", "GSAS_IPARM_LEGACY_LAYOUT",
              f"{path.name}: record {i + 1} ({raw!r}) runs a value across a "
              f"BNKPAR field boundary. It was re-read by whitespace tokens "
              f"and took {took}. GSAS-II v5.8.2 reads the same record the "
              f"same way, and no other record is token-read.",
              where=[f"bank {b}", "BNKPAR"])
    if legacy_banks:
        names = " ".join(LEGACY_PRCF1_SLOT_NAMES)
        _note(diagnostics, "info", "GSAS_IPARM_LEGACY_LAYOUT",
              f"{path.name}: PRCF set 1 of bank(s) "
              f"{', '.join(map(str, legacy_banks))} is the legacy LANSCE "
              f"layout, profile function 1 with {LEGACY_PRCF1_NCOF} "
              f"coefficients. It was read as slots 1-8 of the documented "
              f"twelve ({names}; slots 9-12 zero) and handed to the strict "
              f"reader. GSAS-II v5.8.2 reads an 8-slot and a 12-slot type-1 "
              f"block slot for slot alike, so slots 2, 3, 4, 6, 7 land under "
              f"alpha, beta-0, beta-1, sig-1, sig-2, and slots 1, 5, 8 under "
              f"no name. Those three take the manual's order.",
              where=[f"bank {b}" for b in legacy_banks] + ["PRCF1"])
    if fifth:
        pairs = "; ".join(f"bank {b} ITYP {ityp[b]}: P10 = {p10!r}, P11 = {p11!r}"
                          for b, (p10, p11) in sorted(fifth.items()))
        _note(diagnostics, "info", "GSAS_IPARM_LEGACY_LAYOUT",
              f"{path.name}: the documented layout stops short of a non-zero "
              f"fifth ICOFF pair ({pairs}). The pair was carried on the "
              f"bank's incident_spectrum as written, and a fit evaluates it "
              f"as P10·exp(−P11·T⁵), T in ms, the exponent measured by "
              f"conformance (rietx.model.tof_spectrum).",
              where=[f"bank {b}" for b in sorted(fifth)] + ["ICOFF3"])
    return out
