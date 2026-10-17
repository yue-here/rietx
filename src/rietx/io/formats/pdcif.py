"""Powder CIF (pdCIF) — the IUCr interchange format for a measured profile.

Spec: IUCr pdCIF dictionary; Toby (2003), "CIF applications. XIII. CIFtbx and
pdCIF", J. Appl. Cryst. **36**, 1240.  Parsed through gemmi, so the CIF grammar
is not this package's problem; what is, is which of the alternative tags to
prefer and how a weight becomes a σ.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, ascending, pattern_data

#: pdCIF tag alternatives, in preference order.  A refinement CIF this build
#: writes states one grid and one intensity, the measured ones
#: (``io/cif/powder.py``), so the order decides only a foreign file stating
#: both, and is kept as it was so such a file reads as it did.
_PDCIF_TT = ("_pd_proc_2theta_corrected", "_pd_meas_2theta_scan",
             "_pd_meas_2theta_range_inc")
#: ``_pd_proc_intensity_net`` is **last**, so a file stating a total column
#: beside it reads as it always did; a file stating only a net column (COD
#: 2242872, a TOPAS-Academic deposit) was refused before it.
_PDCIF_Y = ("_pd_proc_intensity_total", "_pd_meas_intensity_total",
            "_pd_meas_counts_total", "_pd_proc_intensity_net")
_PDCIF_NET = "_pd_proc_intensity_net"
#: A net column whose every point stands at least this many σ above zero is
#: reported as carrying a background.  The pdCIF dictionary defines the item as
#: the intensities "after background subtraction", and a subtracted pattern
#: returns to within a few σ of zero between its peaks; one that never does
#: still holds its background.  5 is far below what that file shows (COD
#: 2242872, labelled net, never comes within 14.1σ of zero; its minimum is 249
#: counts) and far above where a true zero baseline sits (|y|/σ of order 1).
NET_BACKGROUND_MIN_SIGMA = 5.0
#: an su column is the intensity column's own: ``<intensity tag>`` + one of these
_PDCIF_SU_SUFFIXES = ("_su", "_esd")


def read_pdcif(path: str | Path, *, block: str | None = None,
               diagnostics: list[Diagnostic] | None = None) -> PatternData:
    """Read a powder pattern from a pdCIF file.

    ``block`` selects a data block by substring match on its name (a pdCIF
    often carries several — e.g. the NIST SRM certification files hold both a
    ``…_meas`` and a ``…_calc`` block with identical tags); by default the
    first block containing a recognised 2θ + intensity loop is used.

    σ handling: an explicit ``…_su``/``…_esd`` column wins; then an su in
    parentheses on every intensity (``1234(35)``, the form the DDLm
    dictionaries make equivalent to a ``_su`` item); otherwise
    ``_pd_proc_ls_weight`` is interpreted as the least-squares weight
    w = 1/σ² (its pdCIF definition), so σ = 1/√w.  With none of these, or a
    weight of 0 on any point, ``sigma`` is left unset and the Poisson fallback
    applies downstream.

    Intensity: the first of ``_pd_proc_intensity_total``,
    ``_pd_meas_intensity_total``, ``_pd_meas_counts_total`` and
    ``_pd_proc_intensity_net`` the block states.  A net column is read and
    **reported, never repaired**: ``PATTERN_INTENSITY_NET`` (info) and
    ``metadata["intensity_item"]`` say which item was read, because the item
    is defined as background-subtracted and whether a background still needs
    refining is the caller's call.  Where the column never comes within
    :data:`NET_BACKGROUND_MIN_SIGMA` σ of zero the label and the numbers
    disagree, and ``PATTERN_NET_HAS_BACKGROUND`` (warning) says so; y is never
    shifted.
    """
    import gemmi

    p = Path(path)
    doc = gemmi.cif.read(str(p))
    chosen = None
    for b in doc:
        if block is not None and block not in b.name:
            continue
        if _first_loop(b, _PDCIF_TT) is not None and _first_loop(b, _PDCIF_Y) is not None:
            chosen = b
            break
    if chosen is None:
        what = "pattern block" if block is None else f"pattern block matching {block!r}"
        raise ValueError(f"no pdCIF {what} found in {p}")

    tt = _first_loop(chosen, _PDCIF_TT)
    y = _first_loop(chosen, _PDCIF_Y)
    if len(tt) != len(y):
        raise ValueError(f"2θ and intensity loops differ in length in {p}")

    # σ is read off the column y came from, never another one's: a file stating
    # both a measured and a processed intensity has an su for each
    y_tag = next(t for t in _PDCIF_Y if len(chosen.find_loop(t)) > 0)
    sigma = None
    su = _first_loop(chosen, tuple(y_tag + s for s in _PDCIF_SU_SUFFIXES))
    stated = _parenthesised_su(chosen, (y_tag,))
    if su is not None and len(su) == len(y):
        sigma = su
    elif stated is not None and len(stated) == len(y):
        sigma = stated
    else:
        wt = _first_loop(chosen, ("_pd_proc_ls_weight",))
        if wt is not None and len(wt) == len(y) and np.all(wt > 0):
            sigma = 1.0 / np.sqrt(wt)

    tt, y, sigma = ascending(tt, y, sigma, path=p, fmt=PDCIF,
                             diagnostics=diagnostics)
    net = y_tag == _PDCIF_NET
    if net and diagnostics is not None:
        diagnostics.extend(_net_findings(p, tt, y, sigma))
    return pattern_data(p, tt, y, sigma,
                   source_file=p.name, format="pdcif", block=chosen.name,
                   intensity_item=y_tag if net else None)


def _net_findings(p: Path, tt: np.ndarray, y: np.ndarray,
                  sigma: np.ndarray | None) -> list[Diagnostic]:
    """What reading a ``_pd_proc_intensity_net`` column says, and whether its
    numbers agree with its label.

    The σ is the one the pattern will be fitted with: the file's, else the
    Poisson fallback √max(y, 1) that ``PatternData.sig()`` applies.
    """
    out = [Diagnostic(
        level="info", code="PATTERN_INTENSITY_NET",
        message=(f"{p.name}: the intensities are the file's "
                 f"{_PDCIF_NET} column, which the pdCIF dictionary defines as "
                 f"the values 'after background subtraction, normalization and "
                 f"other correction factors have been applied'. Whether a "
                 f"background still needs refining is the caller's call."),
        where=[_PDCIF_NET])]
    s = sigma if sigma is not None else np.sqrt(np.maximum(y, 1.0))
    z = y / s
    i = int(np.argmin(z))
    if z[i] >= NET_BACKGROUND_MIN_SIGMA:
        out.append(Diagnostic(
            level="warning", code="PATTERN_NET_HAS_BACKGROUND",
            message=(f"{p.name}: the {_PDCIF_NET} column is labelled "
                     f"background-subtracted but never comes within "
                     f"{NET_BACKGROUND_MIN_SIGMA:g}σ of zero (minimum "
                     f"y = {y[i]:.6g} at 2θ = {tt[i]:.6g}°, {z[i]:.3g}σ), so "
                     f"the background was not subtracted. The intensities are "
                     f"read as the file states them; refine a background."),
            value=float(z[i]), where=[_PDCIF_NET],
            suggestion=("refine a background (a Chebyshev series, with a "
                        "HumpComponent for a broad amorphous or capillary "
                        "hump) rather than holding it at zero")))
    return out


def _first_loop(b, tags: tuple[str, ...]) -> np.ndarray | None:
    """First present loop column among ``tags``, parsed as float (esds stripped)."""
    import gemmi

    for tag in tags:
        col = b.find_loop(tag)
        if len(col) > 0:
            return np.array([gemmi.cif.as_number(v) for v in col], dtype=np.float64)
    return None


def _parenthesised_su(b, tags: tuple[str, ...]) -> np.ndarray | None:
    """The su written in parentheses on the first present column, if every
    value carries one (``12.5(3)`` is 0.3): the digits count in the last
    decimal place the value states (Hall, Allen & Brown 1991)."""
    for tag in tags:
        col = b.find_loop(tag)
        if len(col) == 0:
            continue
        out = []
        for v in col:
            m = _SU.fullmatch(v)
            if m is None:
                return None
            decimals = len(m["frac"] or "")
            out.append(int(m["su"]) * 10.0 ** (int(m["exp"] or 0) - decimals))
        return np.array(out, dtype=np.float64)
    return None


_SU = re.compile(r"[+-]?\d*(?:\.(?P<frac>\d*))?\((?P<su>\d+)\)(?:[eE](?P<exp>[+-]?\d+))?")


PDCIF = PatternFormat(
    name="pdcif",
    title="Powder CIF (pdCIF)",
    extensions=(".cif",),
    sniff="the .cif suffix, then a recognised 2θ + intensity loop",
    sigma=("an explicit …_su/…_esd loop on the intensity column read "
           "(_pd_proc_intensity_net, the last choice, included), else the su "
           "in parentheses on every intensity, else _pd_proc_ls_weight read "
           "as w = 1/σ², else the Poisson fallback"),
    matches=lambda p: p.suffix.lower() == ".cif",
    read=read_pdcif,
    options=("block",),
)
