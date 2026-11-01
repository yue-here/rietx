"""Cr2WO6 at 4 K and 150 K, and its starting model, for `docs/docs/guides/moment.md`.

The two patterns are the HFIR HB-2A files of the GSAS-II *Magnetic-II* tutorial
that the repository vendors in `tests/data/` (provenance in `tests/data/README.md`):
Cr2WO6 at 4 K, below its ordering temperature, and at 150 K, above it. They are
not in the wheel, so this guide runs from a checkout of the repository.

The tutorial's own structure file is an ICSD entry and is not redistributable,
so the model starts from the ideal trirutile positions (P 4_2/mnm; W on 2a, Cr on
4e at z = 1/3, O1 on 4f and O2 on 8j at x = 0.3, z = 1/3).
`tests/test_acceptance_magnetic.py` builds the same start and refines it under
the same six stages.

The guide script skips this file by its leading underscore.
"""

from pathlib import Path

import rietx as rx
from rietx.schemas.common import Parameter

DATA = Path(__file__).resolve().parents[2] / "tests" / "data"
WAVELENGTH = 2.4067  # Å, the `ICONS` line of the tutorial's instrument file
WIDTH_SEED = 0.35    # degrees, the starting FWHM

SCALE = "phases.0.scale"
BACKGROUND = [f"instrument.background.c{i}" for i in range(4)]
ZERO = "instrument.zero_shift"
CELL = "phases.0.cell.*"
PROFILE = [f"instrument.profile.{k}" for k in "uvwx"]
COORDINATES = "phases.0.atoms.*.dof.*"
BISO = "phases.0.atoms.*.biso"


def pattern(temperature: int):
    return rx.read_pattern(DATA / f"gsas2_hb2a_cr2wo6_{temperature}K.dat")


def _atom(label, species, xyz):
    x, y, z = xyz
    return rx.Atom(label=label, species=species, x=Parameter(value=x),
                   y=Parameter(value=y), z=Parameter(value=z),
                   occ=Parameter(value=1.0), biso=Parameter(value=0.5, unit="A^2"))


def trirutile() -> rx.Structure:
    phase = rx.Phase(
        name="Cr2WO6", space_group="P 42/m n m",
        cell=rx.Cell(a=Parameter(value=4.58), b=Parameter(value=4.58),
                     c=Parameter(value=8.85), alpha=Parameter(value=90.0),
                     beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[_atom("W1", "W", (0.0, 0.0, 0.0)),
               _atom("Cr1", "Cr", (0.0, 0.0, 1.0 / 3.0)),
               _atom("O1", "O", (0.3, 0.3, 0.0)),
               _atom("O2", "O", (0.3, 0.3, 1.0 / 3.0))])
    return rx.Structure(phases=[phase])


def instrument() -> rx.Instrument:
    inst = rx.Instrument.constant_wavelength_neutron(WAVELENGTH)
    inst.profile.w.value = (WIDTH_SEED / 2.0) ** 2
    inst.profile.x.value = WIDTH_SEED
    return inst


def nuclear_plan() -> rx.RefinementPlan:
    """Scale and background, then zero, cell, widths, coordinates and Biso, cumulative."""
    free = [SCALE, *BACKGROUND]
    steps = [("scale_bkg", []), ("zero", [ZERO]), ("cell", [ZERO, CELL]),
             ("widths", [ZERO, CELL, *PROFILE]),
             ("coords", [ZERO, CELL, *PROFILE, COORDINATES]),
             ("biso", [ZERO, CELL, *PROFILE, COORDINATES, BISO])]
    return rx.RefinementPlan(
        stages=[rx.Stage(name=name, turn_on=free + more, max_iter=200)
                for name, more in steps],
        intermediate_ftol=1e-6)
