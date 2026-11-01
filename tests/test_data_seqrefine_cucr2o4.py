"""The vendored GSAS-II SeqRefine CuCr₂O₄ series reads, and its README rows hold.

WP-2003 series family B (``tests/data/README.md`` § WP-2003 series family B):
17 APS 11-BM patterns of CuCr₂O₄ with a CuO minor phase on a 6.8-288.7 K
cryostat ramp, the tutorial's one GSAS-I instrument file and its two starting
CIFs, all byte-identical to the tutorial's ``SeqTut.zip``.  Nothing here fits:
the reference values the README carries (the transition near 130 K, the
cells, the CuO fraction) are for the chain-action measurements, which run
elsewhere.  These tests only pin that every file opens through rietx's own
readers and that the README's per-file table states the bytes and the header
temperatures that are actually committed, so the series is usable without
the zip.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif

DATA = Path(__file__).parent / "data"
SERIES = DATA / "seqrefine_cucr2o4"
README = DATA / "README.md"

PATTERNS = ("OH_00", "OH_04", "OH_09", "OH_14", "OH_19", "OH_22", "OH_24",
            "OH_26", "OH_28", "OH_30", "OH_32", "OH_35", "OH_38", "OH_41",
            "OH_45", "OH_49", "OH_53")
OTHERS = ("OH_00.prm", "CuCr2O4.cif", "CuO.cif")
#: The tutorial's ``OH_00.prm`` ``ICONS`` line, and every header's
#: ``Calibrated wavelength``.
WAVELENGTH = 0.413263

_ROW = re.compile(r"^\| `seqrefine_cucr2o4/(?P<name>[^`]+)` \|(?P<cells>.*)\|\s*$")
_SHA = re.compile(r"`([0-9a-f]{64})`")


def _readme_rows() -> dict[str, list[str]]:
    """The per-file table of the README's family-B section, keyed by file name."""
    text = README.read_text(encoding="utf-8")
    start = text.index("\n## WP-2003 series family B")
    end = text.find("\n## ", start + 1)
    rows = {}
    for line in text[start:end if end != -1 else None].splitlines():
        m = _ROW.match(line)
        if m:
            assert m["name"] not in rows, f"{m['name']}: two rows"
            rows[m["name"]] = [c.strip() for c in m["cells"].split("|")]
    return rows


def _header(path: Path, key: str) -> str:
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("BANK"):
            break
        if line.startswith(f"# {key}"):
            return line.split("=", 1)[1].strip()
    raise AssertionError(f"{path.name}: no '# {key}' header line")


def test_the_directory_holds_exactly_the_vendored_files():
    names = {p.name for p in SERIES.iterdir()
             if not p.name.startswith("._") and p.name != ".DS_Store"}
    assert names == {f"{s}.fxye" for s in PATTERNS} | set(OTHERS)


def test_every_file_has_a_readme_row_with_its_sha256():
    rows = _readme_rows()
    assert set(rows) == {p.name for p in SERIES.iterdir()
                         if not p.name.startswith("._") and p.name != ".DS_Store"}
    for name, cells in rows.items():
        shas = _SHA.findall(" ".join(cells))
        assert shas, f"{name}: the README row states no SHA-256"
        assert hashlib.sha256((SERIES / name).read_bytes()).hexdigest() == shas[-1], name


@pytest.mark.parametrize("stem", PATTERNS)
def test_pattern_reads_through_read_pattern(stem):
    path = SERIES / f"{stem}.fxye"
    data = rx.read_pattern(path)
    tt = np.asarray(data.two_theta)
    assert tt.size == 12799
    assert tt[0] == pytest.approx(0.5) and tt[-1] == pytest.approx(26.096)
    assert np.allclose(np.diff(tt), 0.002)
    assert np.isfinite(np.asarray(data.intensity)).all()
    assert (np.asarray(data.sigma) > 0).all()
    assert float(_header(path, "Calibrated wavelength")) == WAVELENGTH


@pytest.mark.parametrize("stem", PATTERNS)
def test_readme_states_each_header_temperature(stem):
    cells = _readme_rows()[f"{stem}.fxye"]
    run, temperature = cells[0], cells[1]
    path = SERIES / f"{stem}.fxye"
    assert run == _header(path, "Run no.")
    assert float(temperature) == float(_header(path, "Temp (K)"))


def test_the_ramp_crosses_the_transition_from_both_sides():
    temps = [float(_header(SERIES / f"{s}.fxye", "Temp (K)")) for s in PATTERNS]
    assert temps == sorted(temps)
    # The paper's transition is near 130 K (README § WP-2003 series family B).
    assert sum(t < 130 for t in temps) == 7 and sum(t > 130 for t in temps) == 10


def test_prm_reads_through_read_gsas_prm():
    inst = rx.read_gsas_prm(SERIES / "OH_00.prm")
    lines = inst.source.lines
    assert len(lines) == 1 and lines[0].wavelength.value == WAVELENGTH
    assert inst.source.polarization.value == pytest.approx(0.99)


@pytest.mark.parametrize(("name", "setting"), [("CuCr2O4.cif", "F d d d:2"),
                                               ("CuO.cif", "C 1 2/c 1")])
def test_starting_cifs_read_in_the_settings_they_state(name, setting):
    # Fddd has two origin choices; the file's operator list (it holds
    # -x,-y,-z) is origin choice 2, the setting the paper's Table I states.
    phase = structure_from_cif(SERIES / name).phases[0]
    assert phase.space_group == setting
