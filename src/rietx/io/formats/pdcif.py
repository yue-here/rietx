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
_PDCIF_BKG_CALC = "_pd_proc_intensity_bkg_calc"
#: A net column whose every point stands at least this many σ above zero is
#: reported as carrying a background.  The pdCIF dictionary defines the item as
#: the intensities "after background subtraction", and a subtracted pattern
#: returns to within a few σ of zero between its peaks; one that never does
#: still holds its background.  5 is far below what four unrelated deposits
#: labelled net show (minimum y/σ 14 to 6 000, COD 2242872, 2017714,
#: 2242532, 2310780; see ``_audit.ROWS``) and far above where a true zero
#: baseline sits (|y|/σ of order 1).
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
    w = 1/σ² (its pdCIF definition), so σ = 1/√w.  With none of these, a
    negative weight, a missing one (``?`` or ``.``), or no positive weight at
    all, ``sigma`` is left unset and the Poisson fallback applies downstream;
    ``PATTERN_WEIGHT_UNUSABLE`` (info) says so when a weight column was there
    and could not be used.

    A weight of **0** is the dictionary's mark of "a data point not used for
    refinement" (``_pd_proc.ls_weight``), so it excludes that point and only
    that one: each run of zero-weight points becomes an ``excluded_regions``
    entry, its σ is the Poisson value √max(y, 1) as a placeholder the fit never
    reads, and ``PATTERN_ZERO_WEIGHT_EXCLUDED`` (info) counts them.  Every other
    point keeps σ = 1/√w.  Before, one zero dropped the whole column to the
    Poisson fallback and said nothing.

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
        if wt is not None and len(wt) == len(y):
            if np.all(wt >= 0) and np.any(wt > 0):
                # σ = ∞ marks a zero weight through ``ascending``, which may
                # reverse or thin the columns; it never reaches the pattern
                with np.errstate(divide="ignore"):
                    sigma = 1.0 / np.sqrt(wt)
            elif diagnostics is not None:
                # a column with no positive weight would exclude every point,
                # a negative one has no σ and a CIF null (``?`` or ``.``,
                # which gemmi reads as NaN) states none: each reads as no
                # weight column, and each is counted on its own
                n_neg = int((wt < 0).sum())
                n_null = int(np.isnan(wt).sum())
                parts = ([f"{n_neg} negative weight(s)"] if n_neg else []) + (
                    [f"{n_null} missing weight(s)"] if n_null else [])
                found = " and ".join(parts) if parts else "no positive weight"
                diagnostics.append(Diagnostic(
                    level="info", code="PATTERN_WEIGHT_UNUSABLE",
                    message=(f"{p.name}: _pd_proc_ls_weight holds {found} "
                             f"in {wt.size} points, so the column is not read. "
                             f"The Poisson σ = √max(y, 1) is used instead."),
                    value=float(n_neg + n_null), where=["_pd_proc_ls_weight"]))

    tt, y, sigma = ascending(tt, y, sigma, path=p, fmt=PDCIF,
                             diagnostics=diagnostics)
    used = np.ones(tt.size, dtype=bool)
    excluded: list[tuple[float, float]] = []
    if sigma is not None and np.isinf(sigma).any():
        used = ~np.isinf(sigma)
        sigma = np.where(used, sigma, np.sqrt(np.maximum(y, 1.0)))
        excluded = _runs(tt, ~used)
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="info", code="PATTERN_ZERO_WEIGHT_EXCLUDED",
                message=(f"{p.name}: {int((~used).sum())} of {tt.size} points "
                         f"carry _pd_proc_ls_weight = 0, which the pdCIF "
                         f"dictionary defines as 'a data point not used for "
                         f"refinement'. They became {len(excluded)} excluded "
                         f"region(s); every other point keeps σ = 1/√w."),
                value=float((~used).sum()), where=["_pd_proc_ls_weight"]))
    net = y_tag == _PDCIF_NET
    if net and diagnostics is not None:
        diagnostics.extend(_net_findings(p, tt[used], y[used],
                                         None if sigma is None else sigma[used],
                                         len(chosen.find_loop(_PDCIF_BKG_CALC)) > 0))
    data = pattern_data(p, tt, y, sigma,
                        source_file=p.name, format="pdcif", block=chosen.name,
                        intensity_item=y_tag if net else None)
    if excluded:
        data.excluded_regions = excluded
    return data


def _runs(tt: np.ndarray, mask: np.ndarray) -> list[tuple[float, float]]:
    """Each run of ``mask`` as a closed 2θ interval holding that run's points
    and no other: an edge lies halfway to the neighbouring point, so a run of
    one point is still an interval and a variable step cannot reach a used
    point."""
    idx = np.flatnonzero(mask)
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    ends = np.concatenate((idx[breaks], [idx[-1]]))
    last = tt.size - 1
    out = []
    for s, e in zip(starts, ends):
        left = tt[s] - tt[s - 1] if s > 0 else tt[min(s + 1, last)] - tt[s]
        right = tt[e + 1] - tt[e] if e < last else tt[e] - tt[max(e - 1, 0)]
        out.append((float(tt[s] - 0.5 * left), float(tt[e] + 0.5 * right)))
    return out


def _net_findings(p: Path, tt: np.ndarray, y: np.ndarray,
                  sigma: np.ndarray | None,
                  has_bkg_calc: bool = False) -> list[Diagnostic]:
    """What reading a ``_pd_proc_intensity_net`` column says, and whether its
    numbers agree with its label.

    The σ is the one the pattern will be fitted with: the file's, else the
    Poisson fallback √max(y, 1) that ``PatternData.sig()`` applies.  A file that
    also states ``_pd_proc_intensity_bkg_calc`` has a background curve of its
    own, which the suggestion names as one of the two fixes.
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
                     f"y = {y[i]:.6g} at 2θ = {tt[i]:.6g}°, {z[i]:.3g}σ). "
                     f"Either a background was left in, or the fitted range "
                     f"holds no empty baseline. The intensities are read as "
                     f"the file states them."),
            value=float(z[i]), where=[_PDCIF_NET],
            suggestion=(
                "tell the two readings apart before choosing a background: "
                + (f"compare y with y - {_PDCIF_BKG_CALC}, which the file "
                   "states, and look for an empty stretch of baseline. "
                   if has_bkg_calc else
                   "look for an empty stretch of baseline in the range. ")
                + "If a background was left in, "
                + (f"hold {_PDCIF_BKG_CALC} additively "
                   "(BackgroundFixedPlusChebyshev, with a refinable Chebyshev "
                   "on top) when y - it reaches zero, otherwise "
                   if has_bkg_calc else "")
                + "refine a Chebyshev background (with a HumpComponent for a "
                "broad amorphous or capillary hump); if the range holds no "
                "empty baseline, the column may already be subtracted and "
                "holding the background at zero is right")))
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
           "as w = 1/σ² (a zero weight excludes its point, per the "
           "dictionary), else the Poisson fallback"),
    matches=lambda p: p.suffix.lower() == ".cif",
    read=read_pdcif,
    options=("block",),
)
