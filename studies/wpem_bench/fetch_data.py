"""Download the WPEM ``CASES`` datasets this benchmark runs on.

Source: https://github.com/Bin-Cao/PyWPEM/tree/main/CASES, the repository the
paper's data-availability statement points to.  Nothing here is committed —
the files stay in ``studies/wpem_bench/data/`` and are gitignored.

For each case we take the **raw** pattern (``intensity.csv``, 2theta vs counts,
background included) plus WPEM's own published outputs — refined cells, mass
fractions — so the comparison quotes their numbers from their files rather than
from the paper's prose alone.  Their ``no_bac_intensity.csv`` /``bac.csv`` are
pulled for the two head-to-head cases only, to document what WPEM fitted.

Usage:  .venv/bin/python studies/wpem_bench/fetch_data.py
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
BASE = "https://raw.githubusercontent.com/Bin-Cao/PyWPEM/main/"

# local path -> path in the PyWPEM repo
FILES: dict[str, str] = {
    # -- PbSO4, Fig. 2a
    "pbso4/intensity.csv": "CASES/PbSO4/intensity.csv",
    "pbso4/no_bac_intensity.csv": "CASES/PbSO4/no_bac_intensity.csv",
    "pbso4/peak0.csv": "CASES/PbSO4/peak0.csv",
    "pbso4/wpem_lattice.csv":
        "CASES/PbSO4/WPEMFittingResults/LatticeConstances_2026.2.5_15.39.csv",
    "pbso4/wpem_profile.csv":
        "CASES/PbSO4/WPEMFittingResults/WPEMfittingProfile_2026.2.5_15.39.csv",
    "pbso4/wpem_peakparas.csv":
        "CASES/PbSO4/WPEMFittingResults/WPEMPeakParas_2026.2.5_15.39.csv",
    "pbso4/wpem_hkl0.csv":
        "CASES/PbSO4/WPEMFittingResults/hkl0_2026.2.5_15.39.csv",
    # WPEM's own PbSO4 CIF: a pymatgen P1 expansion of a tripled,
    # axis-permuted cell labelled Pb3(SO6)2 — kept only as evidence.
    "pbso4/PSO.cif": "Tutorial/class_4_simulation/data/PSO.cif",

    # -- Tb2BaCoO5, Fig. 2b
    "tb2bacoo5/intensity.csv": "CASES/Tb2BaCoO5/intensity.csv",
    "tb2bacoo5/no_bac_intensity.csv": "CASES/Tb2BaCoO5/no_bac_intensity.csv",
    "tb2bacoo5/peak0.csv": "CASES/Tb2BaCoO5/peak0.csv",
    "tb2bacoo5/wpem_lattice.csv":
        "CASES/Tb2BaCoO5/WPEMFittingResults/LatticeConstances_2026.2.5_15.45.csv",
    "tb2bacoo5/wpem_profile.csv":
        "CASES/Tb2BaCoO5/WPEMFittingResults/WPEMfittingProfile_2026.2.5_15.45.csv",
    "tb2bacoo5/wpem_hkl0.csv":
        "CASES/Tb2BaCoO5/WPEMFittingResults/hkl0_2026.2.5_15.45.csv",

    # -- Ti-15Nb, Fig. 2d
    "ti15nb/intensity.csv": "CASES/Ti-15Nb_three phase/intensity.csv",
    "ti15nb/wpem_lattice.csv":
        "CASES/Ti-15Nb_three phase/WPEMFittingResults/LatticeConstances_2026.2.6_9.29.csv",
    "ti15nb/wpem_massfrac.txt":
        "CASES/Ti-15Nb_three phase/WPEMFittingResults/MassFraction_estimate_2026.2.6_9.29.txt",
    "ti15nb/wpem_profile.csv":
        "CASES/Ti-15Nb_three phase/WPEMFittingResults/WPEMfittingProfile_2026.2.6_9.29.csv",

    # -- Egyptian make-up, Fig. 4
    "egypt/intensity.csv": "CASES/EgyptianMakeup/WPEMfitting/intensity.csv",
    "egypt/wpem_lattice.csv":
        "CASES/EgyptianMakeup/WPEMfitting/WPEMFittingResults/LatticeConstances_2026.2.8_17.5.csv",
    "egypt/wpem_massfrac.txt":
        "CASES/EgyptianMakeup/WPEMfitting/WPEMFittingResults/MassFraction_estimate_2026.2.8_17.5.txt",

    # -- Ru-Mn oxide, Fig. 3b
    "mnru/intensity.csv": "CASES/Mn-Ru2O3/intensity.csv",
    "mnru/Mn2O3.cif": "CASES/Mn-Ru2O3/Mn2O3.cif",
    "mnru/wpem_lattice.csv":
        "CASES/Mn-Ru2O3/WPEMFittingResults/LatticeConstances_2023.6.16_11.43.csv",

    # -- operando LixNiyO2, Fig. 3a (the 157 patterns are added below)
    "insitu/LiNiO2.cif": "CASES/Insitu XRD/LiNiO2.cif",
}

# -- NaCl / Li2CO3 weighed mixtures, Fig. 2e.  Only the 10 % folder ships the
# CIFs; the other two reuse them.
for pct, tag in (("10percent", "10"), ("40percent", "40"), ("50percent", "50")):
    FILES[f"nacl_li2co3/{tag}/intensity.csv"] = \
        f"CASES/StandardSample/{pct}/intensity.csv"
for stamp, tag in (("2026.2.6_14.17", "10"), ("2026.2.6_14.42", "40"),
                   ("2026.2.6_15.21", "50")):
    folder = {"10": "10percent", "40": "40percent", "50": "50percent"}[tag]
    FILES[f"nacl_li2co3/{tag}/wpem_massfrac.txt"] = \
        f"CASES/StandardSample/{folder}/WPEMFittingResults/MassFraction_estimate_{stamp}.txt"
    FILES[f"nacl_li2co3/{tag}/wpem_lattice.csv"] = \
        f"CASES/StandardSample/{folder}/WPEMFittingResults/LatticeConstances_{stamp}.csv"
FILES["nacl_li2co3/10/NaCl.cif"] = "CASES/StandardSample/10percent/NaCl.cif"
FILES["nacl_li2co3/10/Li2CO3.cif"] = "CASES/StandardSample/10percent/Li2CO3.cif"

# -- the operando series
for i in range(1, 158):
    FILES[f"insitu/data/{i}.xlsx"] = f"CASES/Insitu XRD/data/{i}.xlsx"


def main() -> None:
    got = skipped = failed = 0
    for local, remote in FILES.items():
        dst = DATA / local
        if dst.exists():
            skipped += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(BASE + urllib.parse.quote(remote), dst)
            got += 1
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"FAIL {local}: {exc}")
            failed += 1
    print(f"downloaded {got}, already present {skipped}, failed {failed}")


if __name__ == "__main__":
    main()
