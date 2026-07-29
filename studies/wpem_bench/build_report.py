"""Assemble the standalone HTML report from results/*.json + *_trace.json.

Everything the page needs is inlined: the numbers as one JSON blob, the
diffraction traces as decimated arrays the page redraws on canvas in the
reader's own theme.  No external requests (the Artifact CSP blocks them).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "wpem_report.html")

TEMPLATE = ROOT / "report_template.html"


def collect() -> dict:
    cases, traces = {}, {}
    for path in sorted(RESULTS.glob("*.json")):
        if path.stem.endswith("_trace"):
            traces[path.stem[:-6]] = json.loads(path.read_text())
        else:
            cases[path.stem] = json.loads(path.read_text())
    return {"cases": cases, "traces": traces}


def main() -> None:
    data = collect()
    html = TEMPLATE.read_text()
    blob = json.dumps(data, separators=(",", ":"))
    html = html.replace("/*__DATA__*/null", blob)
    OUT.write_text(html)
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} kB) "
          f"with {len(data['cases'])} cases, {len(data['traces'])} traces")


if __name__ == "__main__":
    main()
