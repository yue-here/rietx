"""The ILL D1B Co₃O₄ quench series reads, is what was vendored, and is documented.

WP-2003 family D (issue #1150): ten Co₃O₄ samples quenched from 300-1173 K,
each measured at 1.5 K, some at 100 K and 300 K, with the experiment's garnet
standard and empty vanadium can, plus three planted known-bad patterns for a
series' quarantine and ``on_error``.  Provenance, licence and the reference
values (Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019)) are in
``tests/data/README.md`` § "WP-2003 family D".

No fit runs here and nothing is asserted about what a series does with the
planted files: that is a measurement, and it belongs to the tiering session.
These tests pin only the files: that every one reads through
``rx.read_pattern`` with the shape the README states, that the bytes are the
ones the manifest lists, that the README names every file, and that the
planted files are exactly what ``make_planted.py`` builds.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pytest

import rietx as rx

DATA = Path(__file__).parent / "data"
SERIES = DATA / "d1b_co3o4_quench"

#: Real file → (quench temperature in K, or ``None`` for the two reference
#: scans; the temperature the heading's ``TEMP`` line states first, which is
#: what the reader takes as ``temperature_k``).  ``None`` in the second slot is
#: ``300q-1p5K_1.dat``, a spreadsheet export with no ``XYDATA`` heading.
#: ``vanadium_can_120K.dat`` reads 330 K: its heading's first ``TEMP`` value is
#: 330.000 while the second and third (120.037, 120.000) are the 120 K its
#: name and the experiment give (README).
REAL = {
    "300q-1p5K_1.dat": (300, None),
    "300q-100K.dat": (300, 99.738),
    "300q-300K.dat": (300, 306.427),
    "773q-1p5K_1.dat": (773, 1.4255),
    "773q-100K.dat": (773, 99.765),
    "823q-1p5K_1.dat": (823, 1.6062),
    "823q-100K.dat": (823, 99.794),
    "823q-300K_1.dat": (823, 297.36),
    "873q-1p5K_1.dat": (873, 1.4465),
    "873q-300K.dat": (873, 298.377),
    "923q_1p5K_1.dat": (923, 1.4116),
    "973q-1p5K_1.dat": (973, 1.4149),
    "973q-300K.dat": (973, 298.788),
    "1023q_1p5K.dat": (1023, 1.4193),
    "1023q_300K_1.dat": (1023, 297.099),
    "1073q_1p5K.dat": (1073, 1.4008),
    "1073q_300K_1.dat": (1073, 298.338),
    "1123q-1p5K_1.dat": (1123, 1.6538),
    "1123q-100K.dat": (1123, 99.784),
    "1123q_300K.dat": (1123, 297.707),
    "1173q-1p5K_1.dat": (1173, 1.6663),
    "1173q-300K.dat": (1173, 302.776),
    "standard_garnet_300K_1.dat": (None, 296.954),
    "vanadium_can_120K.dat": (None, 330.0),
}

PLANTED = (
    "PLANTED_shuffled_counts_from_873q-1p5K_1.dat",
    "PLANTED_nan_block_from_1023q_1p5K.dat",
    "PLANTED_wrong_sample_garnet_titled_co3o4.dat",
)


def _make_planted():
    spec = importlib.util.spec_from_file_location(
        "make_planted", SERIES / "make_planted.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_series_is_ten_samples_at_1p5_k_with_twelve_warmer_scans():
    quenches = sorted({q for q, _ in REAL.values() if q is not None})
    assert quenches == [300, 773, 823, 873, 923, 973, 1023, 1073, 1123, 1173]
    at_1p5 = [n for n in REAL if "1p5K" in n]
    assert len(at_1p5) == 10
    assert len([n for n in REAL if REAL[n][0] is not None]) == 22
    # the 923 K sample has its 1.5 K scan only (the 723q → 923q rename)
    assert [n for n in REAL if REAL[n][0] == 923] == ["923q_1p5K_1.dat"]


@pytest.mark.parametrize("name", sorted(REAL))
def test_every_real_file_reads_with_the_stated_shape(name):
    diagnostics = []
    pattern = rx.read_pattern(SERIES / name, diagnostics=diagnostics)
    x = np.asarray(pattern.two_theta)
    y = np.asarray(pattern.intensity)
    assert pattern.sigma is not None
    assert np.all(np.isfinite(y))
    np.testing.assert_allclose(np.diff(x), 0.1, atol=1e-9)
    assert x[-1] == pytest.approx(128.69)
    codes = {d.code for d in diagnostics}
    if name == "300q-1p5K_1.dat":
        # row 1 carries a seventh field (the normaliser, 246699) and is
        # dropped, so this scan starts one step later than the others
        assert (len(x), x[0]) == (1279, pytest.approx(0.89))
        assert "PATTERN_ROWS_DROPPED" in codes
        assert pattern.metadata.get("temperature_k") is None
    else:
        assert (len(x), x[0]) == (1280, pytest.approx(0.79))
        assert float(pattern.metadata["temperature_k"]) == pytest.approx(REAL[name][1])


@pytest.mark.parametrize("name", PLANTED)
def test_every_planted_file_reads(name):
    pattern = rx.read_pattern(SERIES / name)
    assert len(np.asarray(pattern.two_theta)) == 1280


def test_the_bytes_are_the_manifests():
    listed = {}
    for line in (SERIES / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        digest, name = line.split(maxsplit=1)
        listed[name] = digest
    on_disk = {p.name for p in SERIES.glob("*.dat")}
    assert set(listed) == on_disk == set(REAL) | set(PLANTED)
    for name, digest in listed.items():
        assert hashlib.sha256((SERIES / name).read_bytes()).hexdigest() == digest


def test_the_readme_names_every_file():
    readme = (DATA / "README.md").read_text(encoding="utf-8")
    missing = [p.name for p in sorted(SERIES.iterdir())
               if p.is_file() and not p.name.startswith(".")
               and f"`d1b_co3o4_quench/{p.name}`" not in readme]
    assert missing == []


def test_the_planted_files_regenerate_byte_for_byte():
    built = _make_planted().build()
    assert sorted(built) == sorted(PLANTED)
    for name, data in built.items():
        assert data == (SERIES / name).read_bytes(), name
