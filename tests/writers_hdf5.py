"""Writers for synthesized NeXus/HDF5 files (WP-1316).

None of the archive's real ``.nxs``/``.h5`` files may ship, so every HDF5
fixture is built here with h5py, and ``writers_xrd.py``'s first rule holds: the
NeXus structure is written **literally** — ``NX_class``, ``NXdata``,
``@signal``, ``@axes``, ``<signal>_errors`` — and nothing is imported from the
reader, so a writer cannot only confirm that the reader agrees with itself.
The names are the NeXus standard's own (``NXdata`` base class,
https://www.nexusformat.org).  The real files' facts (block shapes, the
discriminators) are in ``tests/data/README.md`` without the files.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def write_nexus(path: Path, axis, block, *, axis_name="two_theta",
                axis_units="degrees", errors=None, series=None,
                transpose=False, default=True, signal_units=None,
                title=None, sample=None) -> Path:
    """One NXentry holding one NXdata: ``block`` (1-D, or 2-D with one pattern
    per row) declared as the signal against ``axis``.

    ``series`` is ``(name, values, units)``, declared as the axis of the other
    dimension; ``transpose`` stores the block with one pattern per *column*, and
    the declaration follows it.
    """
    import h5py

    block = np.asarray(block, dtype=np.float64)
    with h5py.File(path, "w") as f:
        entry = f.create_group("entry")
        entry.attrs["NX_class"] = "NXentry"
        if title is not None:
            entry["title"] = title
        if sample is not None:
            s = entry.create_group("sample")
            s.attrs["NX_class"] = "NXsample"
            s["name"] = sample
        data = entry.create_group("data")
        data.attrs["NX_class"] = "NXdata"
        data.attrs["signal"] = "counts"
        stored = block.T if transpose else block
        data["counts"] = stored
        if signal_units is not None:
            data["counts"].attrs["units"] = signal_units
        data[axis_name] = np.asarray(axis, dtype=np.float64)
        if axis_units is not None:
            data[axis_name].attrs["units"] = axis_units
        if block.ndim == 1:
            axes = [axis_name]
        else:
            other = "." if series is None else series[0]
            axes = [axis_name, other] if transpose else [other, axis_name]
            if series is not None:
                name, values, units = series
                data[name] = np.asarray(values, dtype=np.float64)
                if units is not None:
                    data[name].attrs["units"] = units
        data.attrs["axes"] = axes
        if errors is not None:
            e = np.asarray(errors, dtype=np.float64)
            data["counts_errors"] = e.T if transpose else e
        if default:
            f.attrs["default"] = "entry"
            entry.attrs["default"] = "data"
    return path


def write_bare_hdf5(path: Path, axis, block, *, axis_name="tth",
                    group="entry1/data") -> Path:
    """Attribute-less HDF5: a 2-D block and its axis, nothing declaring either
    — the layout some beamlines write, which only the search tier reads."""
    import h5py

    with h5py.File(path, "w") as f:
        g = f.create_group(group)
        g["counts"] = np.asarray(block, dtype=np.float64)
        g[axis_name] = np.asarray(axis, dtype=np.float64)
        # bystanders a reel search must step past: a scalar, a short monotonic
        # vector that matches no dimension, and a string
        g["monitor"] = 1.0
        g["temperatures"] = np.linspace(290.0, 310.0, 3)
        g["note"] = "synthesized"
    return path


def write_weights_hdf5(path: Path, *, n=256, layers=3, seed=0) -> Path:
    """The machine-learning trap: square weight matrices and bias vectors, which
    a naive "2-D and big enough" test would take for a reel."""
    import h5py

    rng = np.random.default_rng(seed)
    with h5py.File(path, "w") as f:
        for i in range(layers):
            g = f.create_group(f"model/layer_{i}")
            g["kernel"] = rng.normal(size=(n, n))
            g["bias"] = rng.normal(size=n)
    return path


def reel(n_scans=4, n_points=300, *, start=10.0, step=0.05, counts=True):
    """A 2θ axis and an ``(n_scans, n_points)`` block of peaks on a background,
    whole numbers when ``counts``, else the same scaled to a rate."""
    tt = start + step * np.arange(n_points)
    rows = []
    for k in range(n_scans):
        centre = start + step * n_points * (0.3 + 0.1 * k)
        peak = 900.0 * np.exp(-0.5 * ((tt - centre) / 0.08) ** 2)
        rows.append(np.round(120.0 + 7.0 * k + peak))
    block = np.array(rows)
    return tt, (block if counts else block / 3.7)
