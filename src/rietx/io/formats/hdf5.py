"""NeXus / HDF5 — an in-situ reel, N patterns against one shared axis (WP-1316).

Spec: the HDF5 file format specification (the superblock signature) and the
NeXus format standard's ``NXdata`` base class (https://www.nexusformat.org).
The signature, the class attribute and the attribute names below are interface
facts, written down here; the parser is this package's own, ported from a
maintainer-local prototype's *rules* and not from its code::

    offset 0   \\x89 H D F \\r \\n \\x1a \\n          the HDF5 signature
    <group>    @NX_class = "NXdata"
               @signal   = "<name of the intensity dataset>"
               @axes     = ["<axis of dim 0>" or ".", "<axis of dim 1>"]
               @<axis>_indices = <the dim that axis spans>   (optional)
      <signal>            1-D (one pattern) or 2-D (one pattern per row)
      <signal>_errors     same shape, the esds                (optional)
      <axis>              1-D, one value per point of its dim
    @default   on the root and on an NXentry: the group to show first

**Dispatch is structural**: the eight-byte signature at offset 0, which no
other registered format can imitate (a file with a userblock, its signature at
512, 1024, …, is not recognised and meets ``xy``'s "looks binary" refusal).
Recognising the file needs nothing; reading
it needs h5py, which is the ``hdf5`` extra and **not** a dependency, so without
it the file is refused by name with the install line rather than falling to the
ASCII catch-all as "it looks binary".  There is no pure-python HDF5, so the
extra gates the format instead of accelerating a path (``io/CLAUDE.md`` § Per
format, the numba precedent).

**Two tiers of authority, cheapest first.**  An ``NXdata`` group's
``@signal``/``@axes`` is schema-named: it says which dataset is the intensity and
which is the axis of each dimension, and it cannot disagree with itself, so it is
trusted — and a declaration that does contradict itself (an axis whose length is
not its dimension's) is refused, never repaired, as is one that does not say
which dimension a name labels (an ``@axes`` shorter than the signal's rank with
no ``@<axis>_indices``).  ``@default`` is followed from the root, or from the
one NXentry where the root names nothing; a file of several NXentry groups each
declaring a pattern is refused, since ``@default`` names what to show and not
that the rest is not data.  A file with no usable
``NXdata`` (attribute-less HDF5, as some beamlines write) is **searched**: a 2-D
numeric block, and a 1-D numeric dataset whose length matches one of the block's
dimensions, is strictly monotonic, and spans what a 2θ scan can
(0 ≤ x₀ < 180°, x₁ ≤ 180°, a span over :data:`MIN_TWO_THETA_SPAN_DEG`) or what a
Q axis can (0 ≤ x₀ < 30 Å⁻¹, x₁ ≤ 30, a span over
:data:`MIN_Q_SPAN_PER_ANGSTROM`).  The matching length picks the block's
orientation.  Those discriminators are also what refuse the machine-learning
trap — a naive "2-D and big enough" test would take a 256×256 weight matrix for
a reel.  A temperature (by name or unit) is never taken for the axis, however
2θ-like its span.  A found axis is inference, so it always reads with
``PATTERN_X_AXIS_ASSUMED``, whatever it is called.

**The axis rule is the package's, unchanged** (:func:`base.check_axis`): a
recognisable 2θ reads silently, a recognisable something else (a Q axis, a
d-spacing, an ω rocking curve, a φ ring) is refused naming it, and an
unrecognisable one reads as 2θ and says so.  Q is refused rather than
converted, since the conversion needs a wavelength the reader must not assume.

**σ, in the tiers the other formats use**: the ``errors`` dataset where the
group declares one (structural, trusted); the Poisson fallback where every
intensity in the scan is a whole number (counts); and otherwise **withheld**
with ``PATTERN_INTENSITY_SCALED`` (:func:`base.sigma_by_arithmetic`), since a
normalised block's scale cannot be verified from the file.

**A series coordinate is surfaced only where the file names it** (WP-1110 item
17): the ``NXdata`` axis declared for the reel's other dimension labels each
scan, and becomes ``temperature_k`` only when it is a temperature in kelvin.
An axis the search found is never read as a coordinate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..._about import DIST_NAME, HDF5_EXTRA
from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import (
    PatternFormat,
    ScanInfo,
    ascending,
    check_axis,
    head,
    multiscan_default,
    pattern_data,
    sigma_by_arithmetic,
)

#: The HDF5 superblock signature, at offset 0 of every file this reader takes.
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"

#: No scattering angle exceeds 180°, so neither end of a 2θ axis may.
MAX_TWO_THETA_DEG = 180.0
#: The narrowest span a found axis may have and still be taken for a powder
#: 2θ scan.  A discriminator for the search tier only, from the prototype's
#: rules (issue #135); a declared axis is never held to it.
MIN_TWO_THETA_SPAN_DEG = 5.0
#: The largest Q a found axis may reach and still be taken for a momentum
#: transfer in Å⁻¹ — the prototype's bound, which a found axis is refused at.
MAX_Q_PER_ANGSTROM = 30.0
#: The narrowest span a found axis may have and still be taken for a Q axis.
MIN_Q_SPAN_PER_ANGSTROM = 1.0


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9å]", "", text.lower())


#: Axis names that are 2θ, normalised.  ``polar_angle`` is the NeXus name for
#: the scattering angle (NXmonopd, NXdetector).
_TWO_THETA_NAMES = frozenset({"twotheta", "2theta", "tth", "2th", "polarangle"})

_Q = ("a momentum transfer Q, which becomes 2θ only through a wavelength this "
      "reader must not assume")
#: Axis names that are recognisably **not** 2θ, with what each one measures.
_OTHER_NAMES: dict[str, str] = {
    "q": _Q, "qq": _Q, "momentumtransfer": _Q,
    "d": "a d-spacing", "dspacing": "a d-spacing",
    "omega": "a rocking curve about ω, which measures crystal misorientation "
             "at one fixed 2θ",
    "phi": "a φ rotation — one ring of a pole figure",
    "chi": "a χ tilt — one arc of a pole figure",
    "tof": "a neutron flight time, which this reader does not read",
    "timeofflight": "a neutron flight time, which this reader does not read",
    "energy": "a photon energy — an energy-dispersive scan",
}
#: Units that say what an axis is when its name does not, normalised.
_OTHER_UNITS: dict[str, str] = {
    **{u: _Q for u in ("1angstrom", "angstrom1", "1å", "å1", "1a", "a1",
                       "1nm", "nm1", "invangstrom")},
    **{u: "a neutron flight time, which this reader does not read"
       for u in ("us", "µs", "microsecond", "microseconds")},
    **{u: "a photon energy — an energy-dispersive scan" for u in ("ev", "kev")},
    **{u: "an angle in radians, which this reader does not convert to degrees"
       for u in ("rad", "radian", "radians", "mrad")},
    **{u: "a d-spacing" for u in ("a", "å", "ang", "angstrom", "angstroms",
                                  "nm", "nanometre", "nanometer")},
}
#: Series-axis names that are the specimen temperature, normalised.
_TEMPERATURE_NAMES = frozenset({"temperature", "temp", "sampletemperature"})
#: Units of a temperature, normalised (``°C`` normalises to ``c``).
_TEMPERATURE_UNITS = frozenset({"k", "kelvin", "c", "degc", "celsius"})


@dataclass(frozen=True)
class _Reel:
    """Where the patterns are, and what said so."""

    #: the intensity block's path: 1-D (one pattern) or 2-D (one per row/column)
    block: str
    #: the axis dataset's path
    axis: str
    #: the block dimension the axis runs along
    x_dim: int
    #: True where an NXdata group declared it, False where the search found it
    declared: bool
    #: the NXdata group, for the messages, when ``declared``
    group: str | None = None
    #: the esd dataset's path, same shape as the block
    errors: str | None = None
    #: the declared axis of the *other* dimension: the series coordinate
    series: str | None = None


def _h5py(path: Path) -> Any:
    """h5py, or a refusal naming the file and the install line."""
    try:
        import h5py
    except ImportError:
        raise ValueError(
            f"{path.name} is an HDF5 file (NeXus .nxs/.h5), and reading one needs "
            f"h5py, which this install lacks: pip install '{DIST_NAME}[{HDF5_EXTRA}]'"
        ) from None
    return h5py


def _text(value: Any) -> str | None:
    """An attribute or scalar dataset value as text, else ``None``."""
    if isinstance(value, np.ndarray):
        if value.size != 1:
            return None
        value = value.reshape(-1)[0]
    if isinstance(value, (bytes, np.bytes_)):
        return bytes(value).decode("utf-8", "replace")
    if isinstance(value, str):
        return value
    return None


def _attr(obj: Any, key: str) -> str | None:
    return _text(obj.attrs.get(key))


def _names(value: Any) -> list[str] | None:
    """``@axes`` as a list: an array of names, or one name, or the older
    ``"a:b"`` / ``"a,b"`` string form."""
    if value is None:
        return None
    if isinstance(value, np.ndarray) and value.size > 1:
        out = [_text(v) for v in value.reshape(-1)]
        return None if any(v is None for v in out) else [str(v) for v in out]
    one = _text(value)
    if one is None:
        return None
    return [n.strip() for n in re.split(r"[:,]", one)]


def _classify(name: str, units: str | None) -> tuple[bool, str | None]:
    """``(is 2θ, what else it is)`` from the axis's own name and units.

    A unit that says what the axis is outranks the name, so ``two_theta`` in
    radians is refused rather than read as degrees.  A name carrying its unit
    as a suffix (pyFAI writes ``2th_deg``, ``q_nm^-1``; other writers
    ``two_theta_rad``) is split at the last ``_`` that leaves a vocabulary word
    before it, when the whole name is not already one."""
    raw = name.rsplit("/", 1)[-1]
    key = _norm(raw)
    known = _TWO_THETA_NAMES | set(_OTHER_NAMES)
    if key not in known:
        cuts = [i for i, c in enumerate(raw) if c == "_"]
        for i in reversed(cuts):
            if _norm(raw[:i]) in known:
                key, units = _norm(raw[:i]), units or raw[i + 1:]
                break
    said = _OTHER_UNITS.get(_norm(units or ""))
    if said is not None:
        return False, said
    if key in _TWO_THETA_NAMES:
        return True, None
    return False, _OTHER_NAMES.get(key)


def _is_temperature(f: Any, axis: str) -> bool:
    """A series coordinate by its name or its unit, so never an abscissa."""
    return (_norm(axis.rsplit("/", 1)[-1]) in _TEMPERATURE_NAMES
            or _norm(_attr(f[axis], "units") or "") in _TEMPERATURE_UNITS)


def _stated(f: Any, axis: str) -> str:
    units = _attr(f[axis], "units")
    name = axis.rsplit("/", 1)[-1]
    return f"{name} [{units}]" if units else name


def _numeric(obj: Any, h5py: Any) -> bool:
    return isinstance(obj, h5py.Dataset) and obj.dtype.kind in "iuf"


def _nxdata_groups(f: Any, h5py: Any) -> list[str]:
    found: list[str] = []

    def visit(name: str, obj: Any) -> None:
        if isinstance(obj, h5py.Group) and _attr(obj, "NX_class") == "NXdata":
            found.append(obj.name)

    f.visititems(visit)
    return found


def _entries(f: Any, h5py: Any) -> list[str]:
    """The root's NXentry groups."""
    return [g.name for g in f.values()
            if isinstance(g, h5py.Group) and _attr(g, "NX_class") == "NXentry"]


def _holds_signal(group: Any, h5py: Any) -> bool:
    """An NXdata group declaring a 1-D or 2-D numeric signal."""
    name = _signal(group, h5py)
    return (name is not None and _numeric(group[name], h5py)
            and group[name].ndim in (1, 2))


def _default_group(f: Any, h5py: Any) -> str | None:
    """The NXdata the file's ``@default`` chain names, if it names one: from
    the root, or, where the root names nothing, from its one NXentry."""
    node = f
    if _attr(f, "default") is None:
        entries = _entries(f, h5py)
        if len(entries) != 1:
            return None
        node = f[entries[0]]
    for _ in range(3):
        name = _attr(node, "default")
        if name is None or name not in node:
            return None
        node = node[name]
        if not isinstance(node, h5py.Group):
            return None
        if _attr(node, "NX_class") == "NXdata":
            return node.name
    return None


def _signal(group: Any, h5py: Any) -> str | None:
    """The group's signal dataset name: ``@signal``, else a child carrying the
    older ``@signal=1``."""
    name = _attr(group, "signal")
    if name is not None:
        return name if name in group else None
    for key, child in group.items():
        flag = child.attrs.get("signal") if _numeric(child, h5py) else None
        if flag is not None and _is_one(flag):
            return key
    return None


def _is_one(flag: Any) -> bool:
    text = _text(flag)
    try:
        return float(text if text is not None
                     else np.asarray(flag).reshape(-1)[0]) == 1.0
    except (TypeError, ValueError):
        return False


def _declared_reel(f: Any, gname: str, *, path: Path, h5py: Any) -> _Reel | None:
    """The reel an NXdata group declares, ``None`` if it declares no 1-/2-D
    numeric signal, or a refusal where the declaration contradicts itself."""
    group = f[gname]
    sname = _signal(group, h5py)
    if sname is None or not _numeric(group[sname], h5py):
        return None
    signal = group[sname]
    if signal.ndim not in (1, 2):
        return None
    axes = (_names(group.attrs.get("axes"))
            or _names(signal.attrs.get("axes")) or [])
    if len(axes) != signal.ndim:
        # a name's position is its dimension only in a full list: a short one
        # read by position puts a square reel's 2θ on the wrong dimension, and
        # no length check can see it
        bare = [n for n in axes if n not in (".", "")
                and f"{n}_indices" not in group.attrs]
        if bare:
            raise ValueError(
                f"{path.name}: {gname} @axes names {len(axes)} "
                f"{'axis' if len(axes) == 1 else 'axes'} for its "
                f"{signal.ndim}-D signal {sname!r}, and "
                f"{', '.join(repr(f'{n}_indices') for n in bare)} "
                f"{'is' if len(bare) == 1 else 'are'} not given, so which "
                "dimension each name labels is not stated. Declare one "
                "@axes entry per dimension ('.' for the scan dimension) or "
                "@<axis>_indices")
    by_dim: dict[int, str] = {}
    for position, name in enumerate(axes):
        if name in (".", ""):
            continue
        indices = group.attrs.get(f"{name}_indices")
        dim = int(np.asarray(indices).reshape(-1)[0]) if indices is not None \
            else position
        if not 0 <= dim < signal.ndim:
            raise ValueError(
                f"{path.name}: {gname} declares {name!r} as the axis of dimension "
                f"{dim} of its signal {sname!r}, which has {signal.ndim}")
        if name not in group or not _numeric(group[name], h5py) \
                or group[name].ndim != 1 or not 0 <= dim < signal.ndim:
            raise ValueError(
                f"{path.name}: {gname} declares {name!r} as an axis of its signal "
                f"{sname!r}, and it is not a 1-D numeric dataset of that group")
        if group[name].shape[0] != signal.shape[dim]:
            raise ValueError(
                f"{path.name}: {gname} declares {name!r} ({group[name].shape[0]} "
                f"points) as the axis of dimension {dim} of {sname!r}, which has "
                f"{signal.shape[dim]} — the declaration contradicts itself")
        by_dim[dim] = group[name].name
    if not by_dim:
        raise ValueError(
            f"{path.name}: {gname} declares a signal {sname!r} and no axis for it, "
            "so the file states no abscissa to read the pattern against")

    x_dim = _x_dim(f, by_dim, signal.ndim, path=path, gname=gname)
    other = 1 - x_dim if signal.ndim == 2 else None
    errors = None
    for name in (f"{sname}_errors", _attr(signal, "uncertainties"), "errors"):
        if name and name in group and _numeric(group[name], h5py):
            if group[name].shape != signal.shape:
                raise ValueError(
                    f"{path.name}: {gname}/{name} has shape {group[name].shape} and "
                    f"the signal it is the esds of has {signal.shape}")
            errors = group[name].name
            break
    return _Reel(block=signal.name, axis=by_dim[x_dim], x_dim=x_dim,
                 declared=True, group=gname, errors=errors,
                 series=by_dim.get(other) if other is not None else None)


def _x_dim(f: Any, by_dim: dict[int, str], ndim: int, *, path: Path,
           gname: str) -> int:
    """Which declared axis is the pattern's abscissa, the other being the
    series coordinate.  A temperature never is; a 2θ name decides; failing one,
    a name the axis rule refuses (so the refusal is reached).  Failing both,
    an unclassified axis is taken only where nothing else could be the
    abscissa — a 1-D signal's, or the one declared on a 2-D signal's last
    dimension, NeXus's fastest-varying — and reads with
    ``PATTERN_X_AXIS_ASSUMED``; any other unclassified declaration is refused,
    since choosing between two unknown axes is the caller's."""
    # a temperature is the series coordinate, never what the points are against
    candidates = {d: a for d, a in by_dim.items() if not _is_temperature(f, a)}
    if not candidates:
        raise ValueError(
            f"{path.name}: {gname} declares only "
            f"{', '.join(repr(a.rsplit('/', 1)[-1]) for a in by_dim.values())} "
            "as an axis, a temperature — the series coordinate of a reel, not the "
            "abscissa its points were measured against")
    kinds = {d: _classify(a, _attr(f[a], "units")) for d, a in candidates.items()}
    two_theta = [d for d, (tt, _) in kinds.items() if tt]
    if len(two_theta) == 2:
        raise ValueError(
            f"{path.name}: {gname} declares a 2θ axis on both dimensions, so its "
            "signal is a two-angle map, not a reel of powder patterns")
    if two_theta:
        return two_theta[0]
    named = [d for d, (_, other) in kinds.items() if other is not None]
    if len(named) == 1:
        return named[0]
    if ndim == 1 or list(candidates) == [ndim - 1]:
        return ndim - 1
    shown = ", ".join(repr(a.rsplit("/", 1)[-1]) for a in candidates.values())
    raise ValueError(
        f"{path.name}: {gname} declares {shown} as the axes of its 2-D signal, "
        "and no name or unit says which one is the scattering angle, so which "
        "dimension holds the patterns is not the reader's to choose")


def _span(x: np.ndarray) -> tuple[bool, bool]:
    """``(a 2θ scan could span this, a Q axis could)`` for a found axis, which
    must also be finite and strictly monotonic to be either."""
    if x.size < 2 or not np.all(np.isfinite(x)):
        return False, False
    step = np.diff(x)
    if not (np.all(step > 0) or np.all(step < 0)):
        return False, False
    lo, hi = float(x.min()), float(x.max())
    two_theta = (0.0 <= lo < MAX_TWO_THETA_DEG and hi <= MAX_TWO_THETA_DEG
                 and hi - lo > MIN_TWO_THETA_SPAN_DEG)
    q = (0.0 <= lo < MAX_Q_PER_ANGSTROM and hi <= MAX_Q_PER_ANGSTROM
         and hi - lo > MIN_Q_SPAN_PER_ANGSTROM)
    return two_theta, q


def _found_reel(f: Any, *, path: Path, h5py: Any) -> _Reel:
    """The search tier: one 2-D block and one axis matching a dimension of it."""
    blocks: list[str] = []
    lines: list[tuple[str, int]] = []

    def visit(name: str, obj: Any) -> None:
        if not _numeric(obj, h5py):
            return
        if obj.ndim == 2 and min(obj.shape) >= 2:
            blocks.append(obj.name)
        elif obj.ndim == 1 and obj.shape[0] >= 2:
            lines.append((obj.name, int(obj.shape[0])))

    f.visititems(visit)
    dims = {int(d) for b in blocks for d in f[b].shape}
    # a temperature is a series coordinate, by name or unit, as in the
    # declared tier, however 2θ-like its span
    axes = [name for name, n in lines
            if n in dims and not _is_temperature(f, name)
            and any(_span(np.asarray(f[name][()], dtype=np.float64)))]
    pairs = [(b, dim, a) for b in blocks for dim, n in enumerate(f[b].shape)
             for a in axes if f[a].shape[0] == n]
    if len(pairs) > 1:
        # a name that says what the axis is outranks one that says nothing
        named = [p for p in pairs if any(_classify(p[2], _attr(f[p[2]], "units")))]
        pairs = named or pairs
    if not pairs:
        raise ValueError(
            f"{path.name} holds no NXdata group declaring a signal, and no 2-D "
            "numeric block with a 1-D axis that matches one of its dimensions, "
            f"runs in one direction and spans what a 2θ scan (over "
            f"{MIN_TWO_THETA_SPAN_DEG:g}°, within 0–{MAX_TWO_THETA_DEG:g}°) or a "
            f"Q axis can — so nothing in it reads as a reel of powder patterns")
    if len(pairs) > 1:
        shown = "; ".join(f"{b} along dimension {d} against {a}"
                          for b, d, a in pairs[:5])
        raise ValueError(
            f"{path.name} declares no NXdata group, and its search finds "
            f"{len(pairs)} ways to read it as a reel ({shown}). Choosing between "
            "them is yours: declare one with an NXdata group's @signal and @axes")
    block, x_dim, axis = pairs[0]
    return _Reel(block=block, axis=axis, x_dim=x_dim, declared=False)


def _reel(f: Any, *, path: Path, h5py: Any) -> _Reel:
    """The declared tier if the file has one, else the search tier."""
    # one NXentry per measurement is a common layout, and @default names the
    # entry to show, not that the others are not data: reading one would be a
    # silent selection, and no option selects an entry yet
    measured = [e for e in _entries(f, h5py)
                if any(_holds_signal(f[g], h5py) for g in _nxdata_groups(f[e], h5py))]
    if len(measured) > 1:
        raise ValueError(
            f"{path.name} holds {len(measured)} NXentry groups each declaring a "
            f"pattern ({', '.join(measured[:5])}), and which entry is the "
            "measurement is not the reader's to choose (@default names the one "
            "to show, not that the others are not data). Save the entry you "
            "mean to a file of its own")
    chosen = _default_group(f, h5py)
    if chosen is not None:
        reel = _declared_reel(f, chosen, path=path, h5py=h5py)
        if reel is not None:
            return reel
    reels = [r for g in _nxdata_groups(f, h5py)
             if (r := _declared_reel(f, g, path=path, h5py=h5py)) is not None]
    if len(reels) > 1:
        named = ("names none of them with @default" if chosen is None else
                 f"its @default names {chosen}, which declares no 1-D or 2-D "
                 "signal")
        raise ValueError(
            f"{path.name} holds {len(reels)} NXdata groups with a 1-D or 2-D "
            f"signal ({', '.join(r.group or '' for r in reels[:5])}) and "
            f"{named}, so which one is the pattern is not the reader's to "
            "choose")
    if reels:
        return reels[0]
    return _found_reel(f, path=path, h5py=h5py)


def _check_axis(f: Any, reel: _Reel, *, path: Path,
                diagnostics: list[Diagnostic] | None) -> str:
    stated = _stated(f, reel.axis)
    two_theta, other = _classify(reel.axis, _attr(f[reel.axis], "units"))
    if reel.declared:
        check_axis(stated, path=path, field=f"the axis {reel.group}/@axes names",
                   two_theta=two_theta, other=other,
                   remedy="Export the pattern against 2θ instead.",
                   diagnostics=diagnostics)
        return stated
    if other is None and not two_theta:
        x = np.asarray(f[reel.axis][()], dtype=np.float64)
        could_be_2theta, could_be_q = _span(x)
        if could_be_q and not could_be_2theta:
            other = (f"by its span ({x.min():.4g}–{x.max():.4g}) either a "
                     "momentum transfer Q in Å⁻¹ or a 2θ window narrower than a "
                     "powder scan, and the values cannot say which")
    check_axis(reel.axis, path=path,
               field="the axis found by search (no NXdata group declares one)",
               two_theta=False, other=other,
               remedy="Declare the axis with an NXdata group's @axes.",
               note=(" Nothing in the file says which dataset is the axis: it "
                     "was found as the one monotonic 1-D dataset matching a "
                     "dimension of the block with a span a 2θ scan can have, "
                     "which is inference."),
               diagnostics=diagnostics)
    return stated


def _entry_text(f: Any, block: str, h5py: Any) -> tuple[str | None, str | None]:
    """The enclosing NXentry's ``title`` and its NXsample's ``name``."""
    parts = block.strip("/").split("/")
    for depth in range(len(parts) - 1, 0, -1):
        node = f["/" + "/".join(parts[:depth])]
        if _attr(node, "NX_class") != "NXentry":
            continue
        title = (_text(node["title"][()])
                 if "title" in node and isinstance(node["title"], h5py.Dataset)
                 else None)
        sample = None
        for child in node.values():
            if (isinstance(child, h5py.Group)
                    and _attr(child, "NX_class") == "NXsample"
                    and "name" in child
                    and isinstance(child["name"], h5py.Dataset)):
                sample = _text(child["name"][()])
                break
        return title, sample
    return None, None


def _series_value(f: Any, reel: _Reel, index: int) -> tuple[str | None, float | None]:
    """The scan's label from the declared series axis, and its temperature in K
    where that axis is one."""
    if reel.series is None:
        return None, None
    ds = f[reel.series]
    value = float(np.asarray(ds[index], dtype=np.float64))
    units = _attr(ds, "units")
    name = reel.series.rsplit("/", 1)[-1]
    label = f"{name} = {value:g}{' ' + units if units else ''}"
    kelvin = (_norm(name) in _TEMPERATURE_NAMES
              and _norm(units or "") in ("k", "kelvin") and np.isfinite(value))
    return label, value if kelvin else None


def _n_scans(f: Any, reel: _Reel) -> int:
    block = f[reel.block]
    return 1 if block.ndim == 1 else int(block.shape[1 - reel.x_dim])


def _row(ds: Any, reel: _Reel, index: int) -> np.ndarray:
    if ds.ndim == 1:
        return np.asarray(ds[()], dtype=np.float64)
    picked = ds[index, :] if reel.x_dim == 1 else ds[:, index]
    return np.asarray(picked, dtype=np.float64)


def _guarded(path: Path, work: Any) -> Any:
    """Run ``work``, converting what h5py raises into a refusal naming the file."""
    try:
        return work()
    except ValueError as exc:
        if path.name in str(exc):
            raise
        raise ValueError(f"{path.name} could not be read as HDF5: {exc}") from None
    except (OSError, KeyError, TypeError, RuntimeError, IndexError) as exc:
        raise ValueError(f"{path.name} could not be read as HDF5: {exc}") from None


def read_hdf5(path: str | Path, *, scan: int | None = None,
              diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    h5py = _h5py(p)

    def work() -> PatternData:
        with h5py.File(p, "r") as f:
            reel = _reel(f, path=p, h5py=h5py)
            n_scans = _n_scans(f, reel)
            axis = _check_axis(f, reel, path=p, diagnostics=diagnostics)
            multiscan_default(n_scans, scan, path=p, diagnostics=diagnostics)
            index = 0 if scan is None else scan
            if not 0 <= index < n_scans:
                raise ValueError(f"{p.name} holds {n_scans} scan(s), numbered 0 "
                                 f"to {n_scans - 1}; scan={index} is not one of "
                                 "them")
            x = np.asarray(f[reel.axis][()], dtype=np.float64)
            y = _row(f[reel.block], reel, index)
            units = _attr(f[reel.block], "units")
            if reel.errors is not None:
                sigma = _row(f[reel.errors], reel, index)
            else:
                # whole numbers are counts and get the fallback; anything else
                # is withheld and says so — the block's scale is unverifiable
                sigma = sigma_by_arithmetic(y, None, units or "", path=p,
                                            diagnostics=diagnostics)
            _, temperature = _series_value(f, reel, index)
            title, sample = _entry_text(f, reel.block, h5py)
        tt, y, sig = ascending(x, y, sigma, path=p, fmt=HDF5,
                               diagnostics=diagnostics)
        return pattern_data(p, tt, y, sig, source_file=p.name, format="hdf5",
                            scan=index, scan_count=n_scans, scan_axis=axis,
                            title=title, sample=sample, intensity_unit=units,
                            temperature_k=temperature)

    return _guarded(p, work)


def list_hdf5_scans(path: str | Path) -> list[ScanInfo]:
    p = Path(path)
    h5py = _h5py(p)

    def work() -> list[ScanInfo]:
        with h5py.File(p, "r") as f:
            reel = _reel(f, path=p, h5py=h5py)
            x = np.asarray(f[reel.axis][()], dtype=np.float64)
            finite = x[np.isfinite(x)]
            if not finite.size:
                raise ValueError(f"{p.name}: its axis {reel.axis} holds no finite "
                                 "value")
            lo, hi = float(finite.min()), float(finite.max())
            name = reel.axis.rsplit("/", 1)[-1]
            out = []
            for i in range(_n_scans(f, reel)):
                label, temperature = _series_value(f, reel, i)
                where = (reel.block if f[reel.block].ndim == 1 else
                         f"{reel.block}[{i}]" if reel.x_dim == 1 else
                         f"{reel.block}[:, {i}]")
                out.append(ScanInfo(index=i,
                                    label=f"{label or where}, {name} "
                                          f"{lo:.4g}–{hi:.4g}",
                                    n_points=int(x.size),
                                    two_theta_range=(lo, hi),
                                    temperature_k=temperature))
            return out

    return _guarded(p, work)


def looks_hdf5(p: Path) -> bool:
    """The HDF5 signature at offset 0 — recognised whether or not h5py is here,
    so a file it cannot read is refused by name rather than as binary."""
    return head(p, n=len(HDF5_MAGIC)).raw == HDF5_MAGIC


HDF5 = PatternFormat(
    name="hdf5",
    title="NeXus / HDF5 reel (.nxs, .h5)",
    extensions=(".nxs", ".h5", ".hdf5", ".hdf"),
    sniff=("the HDF5 signature at offset 0; the patterns are the NXdata group's "
           "declared @signal against its @axes, or, with none declared, the one "
           "2-D block a monotonic 2θ-like axis matches. Reading needs the "
           f"'{HDF5_EXTRA}' extra (h5py)"),
    sigma=("the NXdata group's errors dataset where it declares one; the Poisson "
           "fallback for a scan of whole numbers, which are counts; otherwise "
           "withheld (PATTERN_INTENSITY_SCALED), since a normalised block's scale "
           "cannot be verified from the file"),
    matches=looks_hdf5,
    read=read_hdf5,
    options=("scan", "nonpositive_sigma"),
    scans=list_hdf5_scans,
    requires="h5py",
)
