"""Read the ``CASES/Insitu XRD/data/*.xlsx`` patterns without a spreadsheet
dependency.

Each file is a two-column sheet (2theta, counts), 329 rows, 10.09-61.78 deg.
``openpyxl`` is not a pxrdref dependency and this study should not add one, so
the sheet XML is parsed directly — an xlsx is a zip of XML and these files
carry no shared strings, no styles that matter and no formulas.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np

import pxrdref as pr

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")


def read_xlsx_xy(path: str | Path) -> pr.PatternData:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    two_theta: list[float] = []
    intensity: list[float] = []
    for row in root.findall(f".//{NS}row"):
        cells: dict[str, float] = {}
        for cell in row.findall(f"{NS}c"):
            match = _CELL_RE.match(cell.get("r") or "")
            value = cell.find(f"{NS}v")
            if match is None or value is None or value.text is None:
                continue
            cells[match.group(1)] = float(value.text)
        if "A" in cells and "B" in cells:
            two_theta.append(cells["A"])
            intensity.append(cells["B"])
    if not two_theta:
        raise ValueError(f"no numeric rows in {path}")
    return pr.PatternData(two_theta=two_theta, intensity=intensity,
                          metadata={"source_file": Path(path).name})


def series(directory: str | Path, n: int = 157) -> list[pr.PatternData]:
    """Patterns 1..n in acquisition order."""
    directory = Path(directory)
    return [read_xlsx_xy(directory / f"{i}.xlsx") for i in range(1, n + 1)]


if __name__ == "__main__":
    data = read_xlsx_xy(Path(__file__).parent / "data/insitu/data/1.xlsx")
    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity)
    print(f"{len(tt)} points, {tt[0]:.3f}-{tt[-1]:.3f} deg, "
          f"step {np.median(np.diff(tt)):.4f}")
    order = np.argsort(y)[::-1]
    peaks = []
    for i in order:
        if all(abs(tt[i] - p) > 1.0 for p in peaks):
            peaks.append(float(tt[i]))
        if len(peaks) == 8:
            break
    print("strongest 2theta:", [round(p, 3) for p in sorted(peaks)])
