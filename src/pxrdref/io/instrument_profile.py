"""Instrument-profile files: export a calibrated instrument, import it frozen.

The calibrate → freeze → refine-sample workflow (the reason the profile is
split into instrument ⊕ sample terms — see ``profiles.caglioti``):

1. **Calibrate** — refine a line-profile standard (NIST SRM 660c LaB6) with
   the ``lab_bragg_brentano`` plan; the instrument resolution function
   (U V W X Y), axial ratios, zero and emission-line ratio absorb everything
   the standard cannot broaden.
2. **Freeze** — :func:`save_instrument_profile` writes those values to a JSON
   file, *excluding* what belongs to the measurement rather than the
   instrument: the background model and the specimen displacement /
   transparency (properties of the mounted sample, reset to 0 on load).
3. **Refine the sample** — :func:`load_instrument_profile` returns an
   ``Instrument`` with every stored parameter ``vary=False``; run the
   ``lab_sample_refine`` plan, which frees only the four sample broadening
   terms (lor_size, lor_strain, gauss_size, gauss_strain), displacement,
   cell, scale/background and Biso.

This mirrors the instrument-parameter-file practice of GSAS-II (.instprm)
and FullProf (resolution files), with the whole instrument schema in one
typed JSON document.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ..schemas.instrument import BackgroundChebyshev, Instrument

FORMAT_KEY = "pxrdref_instrument_profile"
FORMAT_VERSION = "1"


def save_instrument_profile(instrument: Instrument, path: str | Path) -> None:
    """Write the instrument's calibrated state to a JSON profile file.

    The background, the specimen displacement/transparency and any surface
    roughness are stripped: they describe one measurement, not the goniometer.
    Roughness is a property of how *this* specimen was packed and pressed, so
    carrying it into the next sample's refinement would be worse than useless —
    it would silently pre-bias that sample's ADPs.
    """
    ins = instrument.model_copy(deep=True)
    ins.geometry.sample_displacement.value = 0.0
    ins.geometry.sample_transparency.value = 0.0
    ins.geometry.surface_roughness = None
    doc = {
        FORMAT_KEY: FORMAT_VERSION,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "instrument": ins.model_dump(mode="json", exclude={"background"}),
    }
    Path(path).write_text(json.dumps(doc, indent=1))


def load_instrument_profile(path: str | Path) -> Instrument:
    """Read a profile file back as a **frozen** instrument.

    Every stored parameter comes back with ``vary=False`` — the calibration
    is data, not a starting guess.  The background is a fresh default
    (attach the model the new measurement needs); displacement and
    transparency are 0 and refinable per the sample plan, and surface
    roughness is absent (attach a block per specimen if the fit needs one).
    """
    doc = json.loads(Path(path).read_text())
    if doc.get(FORMAT_KEY) != FORMAT_VERSION:
        raise ValueError(
            f"{path}: not a pxrdref instrument-profile file "
            f"(missing/unknown {FORMAT_KEY!r} tag)")
    ins = Instrument.model_validate({**doc["instrument"],
                                     "background": BackgroundChebyshev().model_dump(mode="json")})
    for p in _iter_parameters(ins):
        p.vary = False
    return ins


def _iter_parameters(ins: Instrument):
    yield ins.zero_shift
    yield ins.source.polarization
    for line in ins.source.lines:
        yield line.weight
    g = ins.geometry
    yield from (g.sample_displacement, g.sample_transparency, g.axial_sl, g.axial_hl)
    p = ins.profile
    yield from (p.u, p.v, p.w, p.x, p.y)
