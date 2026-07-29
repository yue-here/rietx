"""Inline the plots into the two self-contained HTML reports.

`*_template.html` carries `__filename.png__` placeholders; this downscales each
PNG from `out/`, re-encodes it as a JPEG data URI and substitutes it, so the
published page needs no external requests.
"""
from __future__ import annotations

import base64
import re

from common import HERE, OUT
from PIL import Image

#: template -> the out/ images it embeds, with the width each is downscaled to
REPORTS = {
    "report_template.html": ("guillemot_report.html", {
        "FeSb_19RBM_fit.png": 1150, "KD1-2_5_NaCoO2_fit.png": 1150,
        "MnSb_33_BM_fit.png": 1150, "MnSb_34_impure_fit.png": 1150,
        "HL2-1_pawley_fit.png": 1150, "HL2-1_peaks.png": 1250,
        "MnSb_33_BM_panels.png": 1150,
    }),
    "audit_template.html": ("guillemot_audit.html", {
        "audit_indexer_light.png": 1150, "audit_indexer_dark.png": 1150,
        "audit_radius_light.png": 1150, "audit_radius_dark.png": 1150,
    }),
}


def data_uri(name: str, width: int, quality: int = 85) -> str:
    im = Image.open(OUT / name).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    tmp = OUT / f".{name}.jpg"
    im.save(tmp, "JPEG", quality=quality, optimize=True)
    uri = "data:image/jpeg;base64," + base64.b64encode(tmp.read_bytes()).decode()
    tmp.unlink()
    return uri


def main() -> None:
    for template, (target, images) in REPORTS.items():
        html = (HERE / template).read_text()
        for name, width in images.items():
            html = html.replace(f"__{name}__", data_uri(name, width))
        html = html.replace("__WORKDIR__", "studies/guillemot/")
        left = set(re.findall(r"__[A-Za-z0-9._\-]+__", html))
        if left:
            raise SystemExit(f"{template}: unsubstituted placeholders {left}")
        (HERE / target).write_text(html)
        print(f"{target}  {(HERE / target).stat().st_size / 1024:.0f} kB")


if __name__ == "__main__":
    main()
