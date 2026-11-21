"""Write the TOPAS input for this fixture from ``spec.json``.

``python tests/data/tof/topas_synthetic/generate.py OUTDIR`` writes, for each
case, ``<case>.inp`` (``rietx.io.projects.topas_tof.from_tof`` with
``iters 0`` and ``convolution_step 4``, plus one ``Out_X_Ycalc`` line) and the
all-zero ``flat.xye`` the ``.inp`` names as its data file.  TOPAS run on each
``.inp`` writes ``<case>_ycalc.txt``, which is what this directory vendors
(gzipped); ``tests/test_tof_topas_synthetic.py`` builds the same model from
the same ``spec.json`` and compares.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def models(case: str):
    """``(Structure, Instrument)`` for one case of ``spec.json``."""
    from rietx.schemas.common import Parameter
    from rietx.schemas.instrument import BackgroundChebyshev, Instrument, ProfileTOF
    from rietx.schemas.structure import Atom, Cell, Phase, Structure

    spec = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))

    def p(v):
        return Parameter(value=float(v))

    structure = Structure(phases=[Phase(
        name=ph["name"], space_group=ph["space_group"], scale=p(ph["scale"]),
        cell=Cell(a=p(ph["a"]), b=p(ph["a"]), c=p(ph["a"]),
                  alpha=p(90.0), beta=p(90.0), gamma=p(90.0)),
        atoms=[Atom(label=lab, species=sp, x=p(x), y=p(y), z=p(z), occ=p(o),
                    biso=p(b)) for lab, sp, x, y, z, o, b in ph["atoms"]])
        for ph in spec["phases"]])
    bank = spec["bank"]
    instrument = Instrument.tof_neutron_bank(
        bank["difc"], two_theta_bank_deg=bank["two_theta_bank_deg"],
        difa=bank["difa"], tzero=bank["tzero"], difb=bank["difb"],
        profile=ProfileTOF(**{k: p(v) for k, v in spec["cases"][case].items()}))
    instrument = instrument.model_copy(update={"background": BackgroundChebyshev(
        coefficients=[p(c) for c in bank["background"]])})
    return structure, instrument


def grid() -> np.ndarray:
    lo, hi, step = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))["grid_us"]
    return np.arange(lo, hi + 0.5 * step, step)


def main(out: Path) -> None:
    from rietx.io.projects.topas_tof import from_tof

    out.mkdir(parents=True, exist_ok=True)
    x = grid()
    np.savetxt(out / "flat.xye", np.column_stack([x, np.zeros_like(x), np.ones_like(x)]),
               fmt="%.3f")
    for case in json.loads((HERE / "spec.json").read_text(encoding="utf-8"))["cases"]:
        structure, instrument = models(case)
        text = from_tof(structure, instrument, data_file="flat.xye",
                        x_range=(float(x[0]), float(x[-1])), iters=0,
                        convolution_step=4)
        lines = []
        for line in text.splitlines():
            lines.append(line)
            if line.startswith("xdd "):
                lines.append(f"   Out_X_Ycalc({case}_ycalc.txt)")
        (out / f"{case}.inp").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
