"""LaMnO3 at 50 K, its structure and its instrument, for `docs/docs/guides/magnetic.md`.

The pattern, the structure file and the instrument file are the NIST BT-1 files of
the GSAS-II *Magnetic-I* tutorial that the repository vendors in `tests/data/`
(provenance and licence in `tests/data/README.md`). They are not in the wheel, so
this guide runs from a checkout of the repository.

The instrument is read the way `tests/test_acceptance_magnetic_lamno3.py` reads it:
λ from the `ICONS` line, the Gaussian widths and the axial terms from the type-3
profile records, the widths converted from GSAS's centideg² to deg². The fit range
and the excluded contaminant line are the tutorial's (its Steps 2 and 7).

The guide script skips this file by its leading underscore.
"""

from pathlib import Path

import rietx as rx
from rietx.io.recipe import GAUSS_CENTIDEG2_TO_DEG2
from rietx.schemas.common import Parameter

DATA = Path(__file__).resolve().parents[2] / "tests" / "data"
LIMITS = (6.0, 156.0)         # degrees 2θ, the tutorial's Step 2
CONTAMINANT = (15.25, 16.05)  # the line at 15.69° no model explains, its Step 7
N_BACKGROUND = 6

SCALE = "phases.0.scale"
BACKGROUND = [f"instrument.background.c{i}" for i in range(N_BACKGROUND)]
#: each nuclear stage's name and what it adds to the stages before it
NUCLEAR_STEPS = [
    ("scale_bkg", []),
    ("zero", ["instrument.zero_shift"]),
    ("cell", ["phases.0.cell.*"]),
    ("widths", [f"instrument.profile.{k}" for k in "uvwx"]),
    ("coords", ["phases.0.atoms.*.dof.*"]),
    ("biso", ["phases.0.atoms.*.biso"]),
]
REST = [path for _, added in NUCLEAR_STEPS for path in added]


def _record(key: str) -> list[float]:
    text = (DATA / "gsas2_bt1_cu311.inst").read_text(encoding="ascii")
    (line,) = [ln for ln in text.splitlines() if ln[6:12].strip() == key]
    return [float(f) for f in line[12:].split()]


def pattern() -> rx.PatternData:
    data = rx.read_pattern(DATA / "gsas2_bt1_lamno3_50K.gsas")
    return data.model_copy(update={"excluded_regions": [CONTAMINANT]})


def structure() -> rx.Structure:
    return rx.Structure.from_cif(DATA / "gsas2_bt1_lamno3.cif")


def instrument() -> rx.Instrument:
    inst = rx.Instrument.constant_wavelength_neutron(_record("ICONS")[0])
    for name, g in zip("uvw", _record("PRCF31")[:3]):
        getattr(inst.profile, name).value = g * GAUSS_CENTIDEG2_TO_DEG2
    inst.geometry.axial_sl.value, inst.geometry.axial_hl.value = _record("PRCF32")[2:4]
    inst.background.coefficients = [Parameter(value=0.0) for _ in range(N_BACKGROUND)]
    return inst


def nuclear_plan() -> rx.RefinementPlan:
    """Scale and background, then zero, cell, widths, coordinates and Biso, cumulative."""
    free = [SCALE, *BACKGROUND]
    stages = []
    for name, added in NUCLEAR_STEPS:
        free = free + added
        stages.append(rx.Stage(name=name, turn_on=free, max_iter=200))
    return rx.RefinementPlan(stages=stages, intermediate_ftol=1e-6)
