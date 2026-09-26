"""WP-1466 task 3: the polyhedra defaults, measured on a wider phase set.

    .venv/bin/python docs/wp/1466-measure/measure.py [CACHE] [--fixture=PATH]

Run from the repository root.  Each phase is a Crystallography Open Database
entry, fetched once into CACHE (default: ``rietx-1466-cod`` in the system
temp directory), or one of the test CIFs, or built here.  For every site that
can be a centre it prints the shell the largest gap closes, the largest and
second-largest gap ratios, what the server draws with the gap threshold
lowered to 1.0 (so only the geometric conditions turn a shell away), and what
it draws by default.  ``EXPECTED`` is the picture a solid-state chemist would
draw first, written down before the run; the script says where the default
departs from it.  ``--fixture`` writes the phases and ``EXPECTED`` as the JSON
``tests/test_structure3d.py`` holds the default picture to, so the test needs
no network.
"""

from __future__ import annotations

import json
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.schemas.structure import Atom, Parameter

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "tests" / "data"

#: name → COD entry (or a test CIF), with anything unusual about it
PHASES: dict[str, tuple[str, str]] = {
    "LaB6": ("tests/cod_1000055.cif", ""),
    "NAC": ("tests/cod_1000236.cif", ""),
    "fluorapatite": ("tests/fluorapatite.cif", ""),
    "spinel MgAl2O4": ("5000120", ""),
    "perovskite SrTiO3": ("1512124", ""),
    "garnet grossular": ("9002677", "at 103 K"),
    "rutile TiO2": ("9015662", ""),
    "olivine forsterite": ("9007377", ""),
    "zircon ZrSiO4": ("9002554", ""),
    "corundum Al2O3": ("1000032", ""),
    "fluorite CaF2": ("1000043", ""),
    "wurtzite ZnO": ("2300450", ""),
    "quartz SiO2": ("5000035", ""),
    "calcite CaCO3": ("2100992", ""),
    "gypsum CaSO4.2H2O": ("2300258", "with H"),
    "pyrite FeS2": ("7700358", ""),
    "baryte BaSO4": ("8107510", ""),
    "andalusite Al2SiO5": ("9003990", ""),
    "CsCl": ("9009743", ""),
    "high cristobalite SiO2": ("9008230", "at 221 °C, O split six ways at 1/6"),
    "olivine (Mg0.9Fe0.1)2SiO4": ("9007377", "forsterite with Fe beside Mg on M1 and M2"),
}

#: The picture drawn first, written down before the run: for each centre
#: element, the shell sizes a chemist draws by default, empty where none is.
EXPECTED: dict[str, dict[str, list[int]]] = {
    "LaB6": {"La": []},
    "NAC": {"Al": [6], "Ca": [], "Na": []},
    "fluorapatite": {"P": [4], "Ca": []},
    "spinel MgAl2O4": {"Mg": [4], "Al": [6]},
    "perovskite SrTiO3": {"Ti": [6], "Sr": []},
    "garnet grossular": {"Si": [4], "Al": [6], "Ca": []},
    "rutile TiO2": {"Ti": [6]},
    "olivine forsterite": {"Si": [4], "Mg": [6]},
    "zircon ZrSiO4": {"Si": [4], "Zr": []},
    "corundum Al2O3": {"Al": [6]},
    "fluorite CaF2": {"Ca": []},
    "wurtzite ZnO": {"Zn": [4]},
    "quartz SiO2": {"Si": [4]},
    "calcite CaCO3": {"Ca": [6], "C": []},
    "gypsum CaSO4.2H2O": {"S": [4], "Ca": []},
    "pyrite FeS2": {"Fe": [6]},
    "baryte BaSO4": {"S": [4], "Ba": []},
    # Al1 is octahedral and Al2 a trigonal bipyramid
    "andalusite Al2SiO5": {"Si": [4], "Al": [5, 6]},
    "CsCl": {"Cs": []},
    "high cristobalite SiO2": {"Si": []},
    "olivine (Mg0.9Fe0.1)2SiO4": {"Si": [4], "Mg": [6]},
}


def load(name: str, cache: Path):
    ref, _ = PHASES[name]
    if ref.startswith("tests/"):
        return structure_from_cif(str(DATA / ref.removeprefix("tests/")))
    path = cache / f"cod_{ref}.cif"
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(
            f"https://www.crystallography.net/cod/{ref}.cif", timeout=60).read())
    structure = structure_from_cif(str(path))
    if name.startswith("olivine (Mg"):
        phase = structure.phases[0]
        for atom in list(phase.atoms):
            if atom.species.startswith("Mg"):
                atom.occ = Parameter(value=0.9)
                phase.atoms.append(Atom(label=f"Fe{atom.label}", species="Fe",
                                        x=atom.x, y=atom.y, z=atom.z,
                                        occ=Parameter(value=0.1)))
    return structure


def shells(payload: dict) -> dict[str, tuple[int, float, int, float]]:
    """Per site label, ``(n, gap, n2, gap2)``: the two largest gaps.

    Brunner & Schwarzenbach's window, read independently of the server: every
    ligand out to ``SHELL_REACH`` times the shortest, the window's edge
    standing in for the next distance.
    """
    lattice = np.array(payload["lattice"])
    cell = [a for a in payload["atoms"] if not a["boundary"]]
    frac = np.array([a["frac"] for a in cell])
    # translations enough for a 12 Å window from anywhere in the cell
    span = np.ceil(12.0 * np.linalg.norm(np.linalg.inv(lattice), axis=0)).astype(int) + 1
    grid = np.stack(np.meshgrid(*[np.arange(-r, r + 1) for r in span], indexing="ij"),
                    axis=-1).reshape(-1, 3)
    # the server's own reading of which sites are cations
    owner = [a["site"] for a in cell]
    elements = [payload["sites"][j]["element"] for j in owner]
    cart = ((frac[None, :, :] + grid[:, None, :]) @ lattice).reshape(-1, 3)
    source = np.tile(np.arange(len(cell)), len(grid))
    cations = s3._cation_sites(payload["sites"], {"frac": frac, "elements": elements,
                                                  "owner": owner, "cart": cart,
                                                  "source": source}, lattice.T)
    out = {}
    for atom in cell:
        site = payload["sites"][atom["site"]]
        if site["label"] in out or atom["site"] not in cations:
            continue
        centre = np.array(atom["pos"])
        found = {}                        # one position once, however many sites share it
        for other, f in zip(cell, frac):
            if other["site"] not in cations and s3.is_ligand(
                    site["element"], payload["sites"][other["site"]]["element"]):
                points = (f + grid) @ lattice
                r = np.linalg.norm(points - centre, axis=1)
                for p, x in zip(points, r):
                    if x >= s3.BOND_MIN:
                        found[tuple(np.round(p, 2))] = x
        if not found:
            continue
        d = np.sort(list(found.values()))
        window = s3.SHELL_REACH * d[0]
        assert window <= 12.0, (site["label"], window)
        d = np.append(d[d <= window], window)
        if len(d) < 2:
            continue
        ratios = d[1:] / d[:-1]
        order = np.argsort(ratios)[::-1]
        n2 = int(order[1]) + 1 if len(order) > 1 else 0
        out[site["label"]] = (int(order[0]) + 1, float(ratios[order[0]]), n2,
                              float(ratios[order[1]]) if len(order) > 1 else 1.0)
    return out


def main(cache: Path, fixture_path: Path | None = None) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    fixture: list | None = [] if fixture_path else None
    default = s3.POLYHEDRON_GAP
    for name, (ref, remark) in PHASES.items():
        structure = load(name, cache)
        s3.POLYHEDRON_GAP = 1.0
        loose = s3.build(structure)
        s3.POLYHEDRON_GAP = default
        drawn = s3.build(structure)
        where = ref if ref.startswith("tests/") else f"COD {ref}"
        print(f"\n{name} ({where}{', ' + remark if remark else ''})")
        geometric = {loose["sites"][p["site"]]["label"]: p for p in loose["polyhedra"]}
        chosen = {drawn["sites"][p["site"]]["label"]: p for p in drawn["polyhedra"]}
        for label, (n, gap, n2, gap2) in shells(loose).items():
            site = next(s for s in loose["sites"] if s["label"] == label)
            ok = geometric.get(label)
            got = chosen.get(label)
            print(f"  {label:6} {site['element']:2} occ {site['occ']:.2f}  "
                  f"gap after {n:2} ×{gap:.2f}, next after {n2:2} ×{gap2:.2f}  "
                  f"{'polyhedron' if ok else 'not a polyhedron':16} "
                  f"{'drawn' if got and got['drawn_by_default'] else 'hidden' if got else '—'}")
        have = default_picture(drawn)
        if have != {e: sorted(set(v)) for e, v in EXPECTED[name].items() if v}:
            print(f"  ! expected {EXPECTED[name]}, the default draws {have}")
        if fixture is not None:
            phase = structure.phases[0]
            fixture.append({
                "name": name, "source": f"COD {ref}" if not ref.startswith("tests/")
                else ref, "remark": remark, "space_group": phase.space_group,
                "symmetry_operations": phase.symmetry_operations,
                "cell": list(phase.cell.lengths_angles()),
                "atoms": [[a.label, a.species, a.x.value, a.y.value, a.z.value, a.occ.value]
                          for a in phase.atoms],
                "expected": {e: v for e, v in EXPECTED[name].items() if v},
            })
    if fixture_path is not None:
        fixture_path.write_text("[\n" + ",\n".join(json.dumps(row) for row in fixture) + "\n]\n", encoding="utf-8")


def default_picture(payload: dict) -> dict[str, list[int]]:
    """For each centre element, the shell sizes the default draws."""
    out: dict[str, set[int]] = {}
    for p in payload["polyhedra"]:
        if p["drawn_by_default"]:
            out.setdefault(payload["sites"][p["site"]]["element"], set()).add(p["coordination"])
    return {e: sorted(v) for e, v in out.items()}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--fixture=")]
    written = [Path(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("--fixture=")]
    main(Path(args[0]) if args else Path(tempfile.gettempdir()) / "rietx-1466-cod",
         written[0] if written else None)
