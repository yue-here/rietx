"""WP-1327 acceptance on real data: the Cr₂WO₆ moment at 4 K, and the null at 150 K.

Two HB-2A patterns (HFIR, λ = 2.4067 Å) from the GSAS-II tutorial
*Magnetic-II*, vendored verbatim (``tests/data/README.md``): Cr₂WO₆ at 4 K,
below its ordering temperature, and at 150 K, above it.  The protocol is the
one the 2026-09-23 acceptance re-run on PR #433 reconstructed, with one change
forced by licensing — the tutorial's structure file is an ICSD entry and is
not redistributable, so the nuclear model starts from the **ideal trirutile
positions** (P 4₂/mnm; W on 2a, Cr on 4e at z = ⅓, O1 on 4f and O2 on 8j at
x = 0.3, z = ⅓) and the 150 K refinement moves them:

1. 150 K, nuclear only: scale + 4 Chebyshev → zero → cell → u, v, w, x →
   coordinate DOFs → B_iso, cumulative;
2. 4 K, nuclear only, warm-started from (1) — the negative control;
3. 4 K with Cr³⁺ carrying a moment under BNS 58.395, warm-started from (2):
   moment + scale + background, then everything;
4. 150 K with the same moment model, warm-started from (1) — **the null**.

What the suite asserts is the *shape* the re-run reported, with tolerances
rather than digits: at 4 K a moment the report calls supported, lying along
**a** whichever in-plane direction it is seeded along, that removes about
half the nuclear-only misfit; at 150 K a moment the report calls
**unsupported** and an Rwp the moment does not move.  The null is WP-1327's
own acceptance item and the one check that separates "no moment" from a small
invented one.

**Dispersion** is not a choice here: a neutron source has no ``dispersion``
channel (``NeutronSource`` carries one wavelength and no f′/f″), so nothing
is inherited from the X-ray default.  The convergence schedule is declared
explicitly, ``intermediate_ftol=1e-6``, the value the re-run ran at.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.schemas.common import Parameter

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("magnetic-cr2wo6")]

DATA = Path(__file__).parent / "data"
#: the tutorial's ``ICONS`` line; ``read_gsas_prm`` refuses the file's PNCR
#: profile (PRCF type 3, no verified coefficient layout), so the wavelength
#: is taken from it and the width seeded by hand, as the re-run did
LAMBDA = 2.4067
FWHM_SEED_DEG = 0.35

SCALE = "phases.0.scale"
BKG = [f"instrument.background.c{i}" for i in range(4)]
ZERO = "instrument.zero_shift"
CELL = "phases.0.cell.*"
UVWX = [f"instrument.profile.{k}" for k in "uvwx"]
COORD = "phases.0.atoms.*.dof.*"
BISO = "phases.0.atoms.*.biso"
MOMENT = "phases.0.atoms.*.moment.dof*"

_B = [SCALE, *BKG]
NUCLEAR_STAGES = [
    ("scale_bkg", _B),
    ("zero", _B + [ZERO]),
    ("cell", _B + [ZERO, CELL]),
    ("widths", _B + [ZERO, CELL, *UVWX]),
    ("coords", _B + [ZERO, CELL, *UVWX, COORD]),
    ("biso", _B + [ZERO, CELL, *UVWX, COORD, BISO]),
]
MAGNETIC_STAGES = [
    ("moment_scale_bkg", _B + [MOMENT]),
    ("final", _B + [MOMENT, ZERO, CELL, *UVWX, COORD, BISO]),
]


def _plan(stages) -> rx.RefinementPlan:
    return rx.RefinementPlan(
        stages=[rx.Stage(name=n, turn_on=list(t), max_iter=200) for n, t in stages],
        intermediate_ftol=1e-6)


def _p(value: float, **kw) -> Parameter:
    return Parameter(value=value, **kw)


def _atom(label, species, xyz) -> rx.Atom:
    x, y, z = xyz
    return rx.Atom(label=label, species=species, x=_p(x), y=_p(y), z=_p(z),
                   occ=_p(1.0), biso=_p(0.5, unit="A^2"))


def _trirutile() -> rx.Structure:
    """The ideal trirutile start (ZnSb₂O₆ type), in the tutorial's setting."""
    phase = rx.Phase(
        name="Cr2WO6", space_group="P 42/m n m",
        cell=rx.Cell(a=_p(4.58), b=_p(4.58), c=_p(8.85),
                     alpha=_p(90.0), beta=_p(90.0), gamma=_p(90.0)),
        atoms=[_atom("W1", "W", (0.0, 0.0, 0.0)),
               _atom("Cr1", "Cr", (0.0, 0.0, 1.0 / 3.0)),
               _atom("O1", "O", (0.3, 0.3, 0.0)),
               _atom("O2", "O", (0.3, 0.3, 1.0 / 3.0))])
    return rx.Structure(phases=[phase])


def _instrument() -> rx.Instrument:
    inst = rx.Instrument.constant_wavelength_neutron(LAMBDA)
    inst.profile.w.value = (FWHM_SEED_DEG / 2.0) ** 2
    inst.profile.x.value = FWHM_SEED_DEG
    return inst


def _with_moment(structure: rx.Structure, seed) -> rx.Structure:
    s = structure.model_copy(deep=True)
    s.phases[0].magnetic_symmetry = "58.395"
    cr = next(a for a in s.phases[0].atoms if a.label == "Cr1")
    cr.moment = rx.Moment.from_values(tuple(seed), "Cr3+", vary=True)
    return rx.Structure.model_validate(s.model_dump())


def _fit(structure, instrument, data, stages):
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(data, plan=_plan(stages))
    return ref, result


@pytest.fixture(scope="module")
def cr2wo6(cr2wo6_nuclear):
    # the nuclear fits are the session's (``conftest.cr2wo6_nuclear``), shared
    # with the satellite arm's acceptance, which refines the same two files
    # from the same start
    d4, d150 = cr2wo6_nuclear["d4"], cr2wo6_nuclear["d150"]
    ref150, nuc150 = cr2wo6_nuclear["ref150"], cr2wo6_nuclear["nuc150"]
    ref4, nuc4 = cr2wo6_nuclear["ref4"], cr2wo6_nuclear["nuc4"]
    ordered = {}
    for name, seed in (("a", (2.0, 0.0, 0.0)), ("b", (0.0, 2.0, 0.0))):
        ref, res = _fit(_with_moment(ref4.structure, seed),
                        ref4.instrument.model_copy(deep=True), d4, MAGNETIC_STAGES)
        ordered[name] = (res, ref.report().magnetic)
    ref_null, null = _fit(_with_moment(ref150.structure, (2.0, 0.0, 0.0)),
                          ref150.instrument.model_copy(deep=True), d150,
                          MAGNETIC_STAGES)
    return {"nuc150": nuc150, "nuc4": nuc4, "ordered": ordered,
            "null": (null, ref_null.report().magnetic)}


def test_the_4k_moment_is_supported_and_lies_along_a(cr2wo6):
    """Below T_N the moment is measured: ~2.1 μ_B along a, far above its esd.

    Tolerances, not digits.  |m| is held to 1.9-2.3 μ_B, a band that holds the
    re-run's 2.078 ± 0.066 (from the tutorial's own starting structure), this
    protocol's value, and GSAS-II's 2.121 ± 0.019 on the tutorial's steps (a
    black-box run, 2026-09-06) — an envelope, since neither protocol is
    adopted here.  The support ratio is held above 10, where the rule's own
    bar is 3.  The moment removes about half of the nuclear-only misfit.
    """
    nuc4 = cr2wo6["nuc4"]
    result, rows = cr2wo6["ordered"]["a"]
    assert nuc4.status == "converged" and result.status == "converged"
    assert len(rows) == 1
    row = rows[0]
    assert row.ion == "Cr3+"
    assert 1.9 <= row.magnitude <= 2.3, row.magnitude
    assert row.magnitude_esd is not None and row.magnitude_esd < 0.15
    assert row.magnitude / row.magnitude_esd > 10.0
    assert row.supported is True
    # along a: the a component carries the whole modulus, sign free
    assert abs(row.crystalaxis[0]) / row.magnitude > 0.99, row.crystalaxis
    assert result.statistics.rwp < 0.65 * nuc4.statistics.rwp, (
        result.statistics.rwp, nuc4.statistics.rwp)


def test_the_4k_moment_does_not_depend_on_its_in_plane_seed(cr2wo6):
    """Seeded along a or along b, the fit lands on the same moment.

    The re-run's "four in-plane seeds agree", two of them here: a moment
    that went wherever it was put would be a statement about the seed.
    """
    (res_a, (row_a,)), (res_b, (row_b,)) = (cr2wo6["ordered"]["a"],
                                           cr2wo6["ordered"]["b"])
    assert res_a.statistics.rwp == pytest.approx(res_b.statistics.rwp, rel=1e-6)
    assert abs(row_a.magnitude - row_b.magnitude) < 0.1 * row_a.magnitude_esd
    assert abs(abs(row_a.crystalaxis[0]) - abs(row_b.crystalaxis[0])) < (
        0.1 * row_a.magnitude_esd)


def test_the_150k_null_finds_no_moment(cr2wo6):
    """Above T_N the same moment model is reported unsupported, not small.

    WP-1327's null: refined against the paramagnetic pattern, the modulus is
    inside its own esd (or at its floor), ``supported`` is ``False`` with the
    note saying so, and the moment buys nothing — Rwp within 1e-3 relative of
    the nuclear-only fit on the same pattern.
    """
    nuc150 = cr2wo6["nuc150"]
    null, rows = cr2wo6["null"]
    assert nuc150.status == "converged" and null.status == "converged"
    (row,) = rows
    assert row.supported is False, (row.magnitude, row.magnitude_esd, row.note)
    assert row.magnitude_esd is not None
    assert row.magnitude < 3.0 * row.magnitude_esd
    assert "unsupported, not as a small moment" in row.note
    assert null.statistics.rwp == pytest.approx(nuc150.statistics.rwp, rel=1e-3)
