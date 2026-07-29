"""Retrieve the structural models the WPEM benchmark needs, from COD.

WPEM's own fits carry no atomic structure at all (its notebooks pass only
``Lattice_constants``), so nothing usable as a Rietveld starting model ships
with the CASES data.  The one CIF that does — ``CASES/.../PSO.cif`` — is a
pymatgen P1 expansion of a *tripled, axis-permuted* cell labelled
``Pb3(SO6)2`` (a=6.985, b=8.535, c=16.120, V=961 Å^3 ≈ 3 x anglesite), i.e.
not the PbSO4 model anyone refined.  So every structure is taken from the
Crystallography Open Database instead, and recorded here with its COD id.

Usage:  .venv/bin/python studies/wpem_bench/fetch_cifs.py
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
from pathlib import Path

CIFS = Path(__file__).resolve().parent / "cifs"

# name -> (COD id, provenance note).  Ids verified by pulling each candidate
# and checking composition, space group and cell before choosing; see
# REPORT.md.  Five of them are the entries WPEM itself started from — its
# notebook starting cells reproduce these to every printed digit.
ENTRIES: dict[str, tuple[str, str]] = {
    "pbso4_anglesite": ("9015524", "PbSO4 anglesite, Pbnm setting of Pnma, Antao 2012, with ADPs"),
    "y2banio5_template": ("1001501", "Y2BaNiO5 Immm — structure type for Tb2BaCoO5, which COD lacks"),
    "li2co3": ("9009641", "Li2CO3 zabuyelite, C2/c, Idemoto 1998"),
    "nacl": ("1000041", "NaCl halite, Fm-3m — the entry WPEM shipped"),
    "ti_alpha": ("1532765", "alpha-Ti hcp P6_3/mmc a=2.9064 c=4.6667 — WPEM's start"),
    "ti_beta": ("9012924", "beta-Ti bcc Im-3m a=3.282 — WPEM's start"),
    "gypsum": ("2300259", "CaSO4.2H2O I2/c, Schofield 2009 — WPEM's start"),
    "phosgenite": ("9009573", "Pb2Cl2CO3 P4/mbm, Giuseppetti 1974 — WPEM's start"),
    "cerussite": ("9008411", "PbCO3 cerussite Pmcn, Antao 1992 — WPEM's start"),
    "galena": ("9008694", "PbS galena Fm-3m a=5.9362"),
    "laurionite": ("9008250", "PbOHCl laurionite Pcmn, Venetopoulos 1975 — WPEM's start"),
    # Found by the FitReport, not by us.  Its Layer-0 unmatched-peak list on
    # the Tb2BaCoO5 residual reads 23.82 / 23.94 / 24.08 / 24.20 / 27.78 deg,
    # which is witherite 111 / 021 / 002 at Cu Kα.  Unreacted BaCO3 is the
    # standard leftover of a Ba-bearing solid-state synthesis.
    "witherite": ("9006838", "BaCO3 witherite Pmcn, Antao 2000 — Tb2BaCoO5 impurity"),
    # Mn-Ru oxide case.  The Mn2O3 that WPEM ships (COD 1010586) is
    # Zachariasen's 1928 determination in I2₁3; bixbyite is Ia-3 and the
    # modern refinement is used here instead.
    "bixbyite": ("1514238", "Mn2O3 bixbyite Ia-3 a=9.4173, Geller-type 2007"),
    "ruo2": ("2101930", "RuO2 rutile P4_2/mnm a=4.49307 c=3.10639, Bolzan 1997"),
}


def cod_search(text: str) -> list[str]:
    url = "https://www.crystallography.net/cod/result.php?" + urllib.parse.urlencode(
        {"text": text, "format": "lst"})
    with urllib.request.urlopen(url, timeout=60) as fh:
        return fh.read().decode().split()


def cod_fetch(cod_id: str, *, tries: int = 6) -> str:
    """COD resets the connection under rapid repeat requests; back off and retry."""
    url = f"https://www.crystallography.net/cod/cif/{cod_id}.cif"
    last: Exception | None = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as fh:
                return fh.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 - retry on any transport failure
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"COD fetch failed for {cod_id}: {last}")


def main() -> None:
    CIFS.mkdir(parents=True, exist_ok=True)
    for name, (cod_id, note) in ENTRIES.items():
        dst = CIFS / f"{name}_cod{cod_id}.cif"
        if dst.exists():
            print(f"have  {dst.name}")
            continue
        dst.write_text(cod_fetch(cod_id))
        print(f"got   {dst.name}  ({note})")
        time.sleep(1.0)


if __name__ == "__main__":
    main()
