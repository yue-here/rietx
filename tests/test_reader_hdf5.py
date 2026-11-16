"""The NeXus/HDF5 reel reader behind the ``hdf5`` extra (WP-1316).

Every file here is synthesized (``tests/writers_hdf5.py``): no archive
``.nxs``/``.h5`` may ship.  The acceptance bar, row by row: with h5py absent the
build imports, refuses the format by name and reports it unavailable; with it,
the declared-``@axes`` file reads silently, the bare-HDF5 file reads with
``PATTERN_X_AXIS_ASSUMED``, a Q axis raises naming Q, and a 256×256 matrix is
refused.
"""

from __future__ import annotations

import sys

import numpy as np
import pytest

import rietx as rx
from rietx._about import DIST_NAME, HDF5_EXTRA
from rietx.io.readers import identify_format, list_scans
from tests.writers_hdf5 import (
    reel,
    write_bare_hdf5,
    write_nexus,
    write_weights_hdf5,
)

h5py = pytest.importorskip("h5py")


def _read(path, **options):
    found = []
    return rx.read_pattern(path, diagnostics=found, **options), found


# ------------------------------------------------------------ without h5py
def test_without_h5py_the_file_is_recognised_and_refused_by_name(tmp_path,
                                                                 monkeypatch):
    tt, block = reel()
    path = write_nexus(tmp_path / "reel.nxs", tt, block)
    monkeypatch.setitem(sys.modules, "h5py", None)        # how an import is blocked

    assert identify_format(path).name == "hdf5"           # magic, not h5py
    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(path)
    message = str(refusal.value)
    assert "reel.nxs" in message
    assert f"pip install '{DIST_NAME}[{HDF5_EXTRA}]'" in message
    with pytest.raises(ValueError, match="reel.nxs"):
        list_scans(path)

    entry = {r.name: r for r in rx.capabilities().reader_formats}["hdf5"]
    assert entry.available is False and entry.requires == "h5py"


def test_with_h5py_capabilities_reports_the_format_available():
    entry = {r.name: r for r in rx.capabilities().reader_formats}["hdf5"]
    assert entry.available is True
    assert "scan" in entry.options
    # every format the base install reads says so, and needs nothing
    assert all(r.available and r.requires is None
               for r in rx.capabilities().reader_formats if r.name != "hdf5")


# ------------------------------------------------------- the declared tier
def test_a_declared_reel_reads_silently_and_scan_selects_a_row(tmp_path):
    tt, block = reel(n_scans=4)
    path = write_nexus(tmp_path / "reel.nxs", tt, block, title="ramp",
                       sample="specimen A")

    pat, found = _read(path, scan=2)
    assert found == []
    assert pat.two_theta == pytest.approx(list(tt))
    assert pat.intensity == list(block[2])
    assert pat.sigma is None                    # whole numbers: Poisson fallback
    meta = pat.metadata
    assert meta["format"] == "hdf5" and meta["scan"] == "2"
    assert meta["scan_count"] == "4"
    assert meta["scan_axis"] == "two_theta [degrees]"
    assert meta["title"] == "ramp" and meta["sample"] == "specimen A"


def test_no_scan_named_reads_scan_0_and_says_so(tmp_path):
    tt, block = reel(n_scans=3)
    pat, found = _read(write_nexus(tmp_path / "reel.nxs", tt, block))
    assert pat.intensity == list(block[0])
    assert [d.code for d in found] == ["PATTERN_MULTISCAN_DEFAULTED"]


def test_a_scan_past_the_reel_is_refused_naming_the_file(tmp_path):
    tt, block = reel(n_scans=3)
    path = write_nexus(tmp_path / "reel.nxs", tt, block)
    with pytest.raises(ValueError, match=r"reel\.nxs holds 3 scan"):
        rx.read_pattern(path, scan=3)


def test_the_declaration_sets_the_orientation_not_the_shape(tmp_path):
    """Stored one pattern per *column*, declared that way: the reader follows
    the declaration."""
    tt, block = reel(n_scans=5)
    path = write_nexus(tmp_path / "cols.nxs", tt, block, transpose=True)
    pat, _ = _read(path, scan=4)
    assert pat.intensity == list(block[4])
    assert [s.label.split()[0] for s in list_scans(path)][:1] == [
        "/entry/data/counts[:,"]


def test_a_single_1d_pattern_is_one_scan(tmp_path):
    tt, block = reel(n_scans=1)
    pat, found = _read(write_nexus(tmp_path / "one.nxs", tt, block[0]))
    assert found == [] and pat.intensity == list(block[0])
    assert pat.metadata["scan_count"] == "1"


def test_the_errors_dataset_is_the_sigma(tmp_path):
    tt, block = reel(n_scans=2, counts=False)
    errors = np.full_like(block, 3.25) + np.arange(block.shape[1]) * 0.01
    pat, found = _read(write_nexus(tmp_path / "e.nxs", tt, block, errors=errors),
                       scan=1)
    assert found == []
    assert pat.sigma == pytest.approx(list(errors[1]))


def test_a_scaled_block_without_errors_withholds_sigma_and_says_so(tmp_path):
    tt, block = reel(n_scans=2, counts=False)
    pat, found = _read(write_nexus(tmp_path / "rate.nxs", tt, block,
                                   signal_units="counts/s"), scan=0)
    assert pat.sigma is None
    assert [d.code for d in found] == ["PATTERN_INTENSITY_SCALED"]
    assert "counts/s" in found[0].message
    assert pat.metadata["intensity_unit"] == "counts/s"


def test_a_declared_temperature_series_labels_each_scan(tmp_path):
    tt, block = reel(n_scans=3)
    path = write_nexus(tmp_path / "vt.nxs", tt, block,
                       series=("temperature", [300.0, 350.0, 400.0], "K"))
    scans = list_scans(path)
    assert [s.temperature_k for s in scans] == [300.0, 350.0, 400.0]
    assert scans[1].label.startswith("temperature = 350 K")
    assert scans[0].n_points == len(tt)
    assert scans[0].two_theta_range == pytest.approx((tt[0], tt[-1]))
    pat, _ = _read(path, scan=2)
    assert pat.metadata["temperature_k"] == "400.0"


def test_a_series_that_is_not_a_kelvin_temperature_labels_but_is_not_one(tmp_path):
    tt, block = reel(n_scans=2)
    path = write_nexus(tmp_path / "t.nxs", tt, block,
                       series=("time", [0.0, 60.0], "s"))
    scans = list_scans(path)
    assert scans[1].label.startswith("time = 60 s")
    assert all(s.temperature_k is None for s in scans)


def test_an_unrecognised_declared_axis_reads_as_2theta_and_says_so(tmp_path):
    tt, block = reel(n_scans=1)
    pat, found = _read(write_nexus(tmp_path / "x.nxs", tt, block[0],
                                   axis_name="x", axis_units=None))
    assert [d.code for d in found] == ["PATTERN_X_AXIS_ASSUMED"]
    assert pat.intensity == list(block[0])


@pytest.mark.parametrize("name,units", [("Q", "1/angstrom"), ("x", "1/angstrom"),
                                        ("q", None)])
def test_a_declared_q_axis_is_refused_naming_q(name, units, tmp_path):
    q = np.linspace(0.5, 8.0, 300)
    _, block = reel(n_scans=2)
    path = write_nexus(tmp_path / "q.nxs", q, block, axis_name=name,
                       axis_units=units)
    with pytest.raises(ValueError, match="momentum transfer Q") as refusal:
        rx.read_pattern(path)
    assert "q.nxs" in str(refusal.value)


@pytest.mark.parametrize("name,what", [("omega", "rocking curve"),
                                       ("phi", "pole figure"),
                                       ("d_spacing", "d-spacing")])
def test_other_declared_axes_are_refused_naming_what_they_are(name, what,
                                                              tmp_path):
    x = np.linspace(10.0, 40.0, 300)
    _, block = reel(n_scans=1)
    path = write_nexus(tmp_path / "o.nxs", x, block[0], axis_name=name)
    with pytest.raises(ValueError, match=what):
        rx.read_pattern(path)


def test_an_axis_whose_length_contradicts_its_dimension_is_refused(tmp_path):
    tt, block = reel(n_scans=2)
    path = write_nexus(tmp_path / "bad.nxs", tt[:-1], block)
    with pytest.raises(ValueError, match="contradicts itself") as refusal:
        rx.read_pattern(path)
    assert "bad.nxs" in str(refusal.value)


def test_two_nxdata_groups_are_chosen_by_default_or_refused(tmp_path):
    tt, block = reel(n_scans=2)
    for default in (True, False):
        path = write_nexus(tmp_path / f"two_{default}.nxs", tt, block,
                           default=default)
        with h5py.File(path, "a") as f:
            g = f["entry"].create_group("other")
            g.attrs["NX_class"] = "NXdata"
            g.attrs["signal"] = "y"
            g.attrs["axes"] = ["tth"]
            g["y"] = block[1] * 2
            g["tth"] = tt
        if default:
            pat, _ = _read(path, scan=1)
            assert pat.intensity == list(block[1])
        else:
            with pytest.raises(ValueError, match="names none of them"):
                rx.read_pattern(path)


def test_a_temperature_is_never_taken_for_the_abscissa(tmp_path):
    """Declared on the other dimension with an unrecognised x name, it is still
    the series; declared alone, the group states no abscissa (review, WP-1316)."""
    tt, block = reel(n_scans=3)
    path = write_nexus(tmp_path / "vt.nxs", tt, block, axis_name="x",
                       axis_units=None,
                       series=("temperature", [10.0, 50.0, 100.0], "K"))
    pat, found = _read(path, scan=1)
    assert pat.intensity == list(block[1])
    assert [d.code for d in found] == ["PATTERN_X_AXIS_ASSUMED"]
    with h5py.File(path, "a") as f:
        f["entry/data"].attrs["axes"] = ["temperature", "."]
    with pytest.raises(ValueError, match="a temperature"):
        rx.read_pattern(path)


def test_two_unknown_axes_or_one_on_the_first_dimension_are_refused(tmp_path):
    """Which dimension holds the patterns is not the reader's to guess (the
    generality review, WP-1316)."""
    tt, block = reel(n_scans=3)
    path = write_nexus(tmp_path / "u.nxs", tt, block, axis_name="x",
                       axis_units=None, series=("time", [0.0, 60.0, 120.0], "s"))
    with h5py.File(path, "a") as f:
        f["entry/data/time"].attrs["units"] = "frame"
    with pytest.raises(ValueError, match="not the reader's to choose"):
        rx.read_pattern(path)
    with h5py.File(path, "a") as f:
        f["entry/data"].attrs["axes"] = ["time", "."]
    with pytest.raises(ValueError, match="not the reader's to choose"):
        rx.read_pattern(path)


def test_a_2theta_axis_in_radians_is_refused_not_read_as_degrees(tmp_path):
    tt, block = reel(n_scans=1)
    path = write_nexus(tmp_path / "rad.nxs", np.radians(tt), block[0],
                       axis_units="rad")
    with pytest.raises(ValueError, match="radians"):
        rx.read_pattern(path)


@pytest.mark.parametrize("name,refused", [("2th_deg", False), ("q_nm^-1", True),
                                          ("q_A^-1", True)])
def test_a_unit_suffixed_axis_name_is_classified(name, refused, tmp_path):
    """pyFAI writes the unit into the axis name."""
    tt, block = reel(n_scans=1)
    path = write_nexus(tmp_path / "s.nxs", tt, block[0], axis_name=name,
                       axis_units=None)
    if refused:
        with pytest.raises(ValueError, match="momentum transfer Q"):
            rx.read_pattern(path)
    else:
        pat, found = _read(path)
        assert found == [] and pat.intensity == list(block[0])


# ---------------------------------------------------------- the search tier
def test_a_bare_reel_reads_with_the_axis_assumed(tmp_path):
    tt, block = reel(n_scans=3)
    path = write_bare_hdf5(tmp_path / "bare.h5", tt, block)
    pat, found = _read(path, scan=1)
    assert [d.code for d in found] == ["PATTERN_X_AXIS_ASSUMED"]
    assert "inference" in found[0].message
    assert pat.intensity == list(block[1])
    assert len(list_scans(path)) == 3


def test_a_bare_block_stored_by_column_is_oriented_by_the_axis_length(tmp_path):
    tt, block = reel(n_scans=4)
    pat, _ = _read(write_bare_hdf5(tmp_path / "t.h5", tt, block.T), scan=3)
    assert pat.intensity == list(block[3])


def test_a_bare_q_axis_is_refused_by_name_and_by_span(tmp_path):
    _, block = reel(n_scans=2)
    q = np.linspace(0.5, 8.0, block.shape[1])
    with pytest.raises(ValueError, match="momentum transfer Q"):
        rx.read_pattern(write_bare_hdf5(tmp_path / "q.h5", q, block,
                                        axis_name="q"))
    narrow = np.linspace(0.5, 3.0, block.shape[1])     # Q, or a narrow 2θ window
    with pytest.raises(ValueError, match="cannot say which"):
        rx.read_pattern(write_bare_hdf5(tmp_path / "s.h5", narrow, block,
                                        axis_name="x"))


def test_a_file_of_weight_matrices_is_refused(tmp_path):
    """The machine-learning trap: 256×256 blocks with 256-long vectors beside
    them, none monotonic, so no axis and no reel."""
    path = write_weights_hdf5(tmp_path / "model.h5")
    assert identify_format(path).name == "hdf5"
    with pytest.raises(ValueError, match="nothing in it reads as a reel") as r:
        rx.read_pattern(path)
    assert "model.h5" in str(r.value)


def test_a_square_block_matching_its_axis_both_ways_is_refused(tmp_path):
    tt = np.linspace(10.0, 60.0, 50)
    block = np.ones((50, 50))
    with pytest.raises(ValueError, match="2 ways to read it"):
        rx.read_pattern(write_bare_hdf5(tmp_path / "sq.h5", tt, block))


def test_a_detector_frame_stack_is_not_a_reel(tmp_path):
    with h5py.File(tmp_path / "frames.nxs", "w") as f:
        g = f.create_group("entry/data")
        g.attrs["NX_class"] = "NXdata"
        g.attrs["signal"] = "data"
        g["data"] = np.ones((3, 16, 16))
    with pytest.raises(ValueError, match="frames.nxs holds no NXdata group"):
        rx.read_pattern(tmp_path / "frames.nxs")


def test_garbage_after_the_signature_is_refused_naming_the_file(tmp_path):
    path = tmp_path / "junk.h5"
    path.write_bytes(b"\x89HDF\r\n\x1a\n" + bytes(range(256)) * 4)
    assert identify_format(path).name == "hdf5"
    with pytest.raises(ValueError, match="junk.h5"):
        rx.read_pattern(path)


# --------------------------------------------- review fix-ups (PR #1607)
def _short_axes_reel(path, block, axis, *, legacy=False, indices=None):
    """A 2-D signal whose ``@axes`` names one axis only."""
    with h5py.File(path, "w") as f:
        d = f.create_group("entry/data")
        d.attrs["NX_class"] = "NXdata"
        d["I"] = block
        d["two_theta"] = axis
        if legacy:
            d["I"].attrs["signal"] = 1
            d["I"].attrs["axes"] = "two_theta"
        else:
            d.attrs["signal"] = "I"
            d.attrs["axes"] = "two_theta"
        if indices is not None:
            d.attrs["two_theta_indices"] = indices
    return path


@pytest.mark.parametrize("legacy", [False, True])
def test_a_2d_signal_whose_axes_name_one_axis_is_refused(legacy, tmp_path):
    """Square, the position fallback put the 2θ axis on dimension 0 and read a
    column for a scan with nothing said; the length check cannot see it."""
    tt, block = reel(n_scans=300, n_points=300)
    path = _short_axes_reel(tmp_path / "short.nxs", block, tt, legacy=legacy)
    with pytest.raises(ValueError, match="names 1 axis for its 2-D signal") as r:
        rx.read_pattern(path, scan=5)
    assert "two_theta_indices" in str(r.value) and "short.nxs" in str(r.value)


def test_a_short_axes_list_with_its_indices_reads(tmp_path):
    """The positive arm: ``@<axis>_indices`` states the dimension."""
    tt, block = reel(n_scans=300, n_points=300)
    path = _short_axes_reel(tmp_path / "ok.nxs", block, tt, indices=1)
    pat, found = _read(path, scan=5)
    assert found == [] and pat.intensity == list(block[5])


@pytest.mark.parametrize("name,units", [("temperature", None), ("ramp", "degC")])
def test_the_search_never_takes_a_temperature_for_the_abscissa(name, units,
                                                               tmp_path):
    """A °C ramp spans what a 2θ scan can; by name or by unit it is a series."""
    _, block = reel(n_scans=20)
    path = tmp_path / "vt.h5"
    with h5py.File(path, "w") as f:
        f["entry/I"] = block
        f[f"entry/{name}"] = np.linspace(25.0, 120.0, 20)
        if units is not None:
            f[f"entry/{name}"].attrs["units"] = units
    with pytest.raises(ValueError, match="nothing in it reads as a reel"):
        rx.read_pattern(path)
    tt, _ = reel(n_scans=20)
    with h5py.File(path, "a") as f:                     # the positive arm
        f["entry/tth"] = tt
    pat, found = _read(path, scan=3)
    assert [d.code for d in found] == ["PATTERN_X_AXIS_ASSUMED"]
    assert pat.intensity == list(block[3])
    assert pat.metadata["scan_axis"] == "tth"


def _two_nxdata_entry(path, tt, block, *, entry_default):
    with h5py.File(path, "w") as f:
        e = f.create_group("entry")
        e.attrs["NX_class"] = "NXentry"
        if entry_default:
            e.attrs["default"] = "data"
        for g, axis, x in (("data", "two_theta", tt),
                           ("data_q", "q", np.linspace(1.0, 5.0, tt.size))):
            d = e.create_group(g)
            d.attrs["NX_class"] = "NXdata"
            d.attrs["signal"] = "I"
            d.attrs["axes"] = [".", axis]
            d["I"] = block
            d[axis] = x
    return path


def test_default_on_the_entry_alone_chooses_the_group(tmp_path):
    tt, block = reel(n_scans=4)
    pat, _ = _read(_two_nxdata_entry(tmp_path / "e.nxs", tt, block,
                                     entry_default=True), scan=2)
    assert pat.intensity == list(block[2])
    assert pat.metadata["scan_axis"] == "two_theta"
    with pytest.raises(ValueError, match="names none of them with @default"):
        rx.read_pattern(_two_nxdata_entry(tmp_path / "n.nxs", tt, block,
                                          entry_default=False))


def test_several_entries_each_holding_a_pattern_are_refused(tmp_path):
    """The root's @default names the entry to show, not that the others are
    not data, so reading entry1 alone is a silent selection."""
    tt, block = reel(n_scans=2)
    path = tmp_path / "multi.nxs"
    with h5py.File(path, "w") as f:
        f.attrs["default"] = "entry1"
        for k in (1, 2):
            e = f.create_group(f"entry{k}")
            e.attrs["NX_class"] = "NXentry"
            e.attrs["default"] = "data"
            d = e.create_group("data")
            d.attrs["NX_class"] = "NXdata"
            d.attrs["signal"] = "I"
            d.attrs["axes"] = ["two_theta"]
            d["I"] = block[k - 1]
            d["two_theta"] = tt
    with pytest.raises(ValueError, match="2 NXentry groups") as r:
        rx.read_pattern(path)
    assert "/entry1" in str(r.value) and "/entry2" in str(r.value)
    with pytest.raises(ValueError, match="2 NXentry groups"):
        list_scans(path)
    with h5py.File(path, "a") as f:                     # the positive arm
        del f["entry2/data"]
    pat, found = _read(path)
    assert found == [] and pat.intensity == list(block[0])


@pytest.mark.parametrize("units", ["Angstrom", "Å", "nm"])
def test_an_axis_in_a_length_unit_is_refused_as_a_d_spacing(units, tmp_path):
    _, block = reel(n_scans=1)
    path = write_nexus(tmp_path / "d.nxs", np.linspace(0.8, 6.0, 300), block[0],
                       axis_name="x", axis_units=units)
    with pytest.raises(ValueError, match="d-spacing"):
        rx.read_pattern(path)


@pytest.mark.parametrize("name,refused", [("two_theta_rad", True),
                                          ("polar_angle_rad", True),
                                          ("two_theta_deg", False)])
def test_a_unit_suffix_after_a_multi_word_name_is_read(name, refused, tmp_path):
    """The suffix split tries every ``_``, not only the first."""
    tt, block = reel(n_scans=1)
    x = np.radians(tt) if refused else tt
    path = write_nexus(tmp_path / "s.nxs", x, block[0], axis_name=name,
                       axis_units=None)
    if refused:
        with pytest.raises(ValueError, match="radians"):
            rx.read_pattern(path)
    else:
        pat, found = _read(path)
        assert found == [] and pat.intensity == list(block[0])
