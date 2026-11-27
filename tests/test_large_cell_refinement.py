"""Real large cells through a refinement (WP-2317).

No other refinement test carries a cell over ~1 000 Å³ with tens of sites in
the asymmetric unit, and a large cell is slow in rietx for reasons a small one
never reaches (WP-2314 to WP-2316). These tests put two published structures
from the Crystallography Open Database through the fit paths a user takes:

- COD 2107344, Nb₁₈W₁₆O₉₃ (Stephenson 1968), Pbam, 12.195 × 36.740 × 3.951 Å,
  V = 1 770 Å³, 43 sites, nine of them Nb/W pairs sharing a position. The
  cell is the closest real one to the 12 × 36 × 4 Å cell a user reported.
- COD 2107337, H-Nb₂O₅ (Kato 1976), P2/m, 21.153 × 3.823 × 19.356 Å,
  β = 119.8°, V = 1 358 Å³, 51 sites, the monoclinic case.

Both files carry Uiso = 0 for every site, so the Biso values here are
declared (`BISO_METAL`, `BISO_O`), and dispersion is declined on the
instrument. Each pattern is **simulated** from the published model and
Poisson-sampled at a fixed seed. These tests therefore **verify**: they ask
whether a fit recovers the model that made its data. They validate nothing
about either compound (DESIGN-RULES Rule 2).

Every start has the cell 500 ppm high. A Rietveld start also has every free
coordinate displaced by a seeded draw and the scale halved, on the truth's
instrument, so a converged fit can reach the truth exactly. A Pawley start
has generic widths instead, which ``mccusker_default`` frees. Each recovered
value is judged against its own esd. A Rietveld test ties each co-sited Nb/W
pair (its site-symmetry steps and its Biso), as a refiner would
(`tie_co_sited`).

The ranges are cut to keep each fit to a few seconds; the bench's
`bigcell-*` cases carry the full ranges and the timing.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.strategy.staged import RefinementPlan, Stage

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"
NB18W16O93 = DATA / "cod_2107344.cif"
H_NB2O5 = DATA / "cod_2107337.cif"

#: Å², declared because both COD files carry Uiso = 0 for every site
BISO_METAL, BISO_O = 0.5, 1.0
#: the number of sites in each file's asymmetric unit, pinned so a reader
#: change that drops or merges a site is seen here first
N_SITES = {NB18W16O93: 43, H_NB2O5: 51}


def large_cell_phase(cif: Path, *, scale: float, drift: float = 0.0) -> rx.Phase:
    """The published model with declared Biso, the cell scaled by ``1 + drift``.

    Each site's Biso is ``BISO_O`` for oxygen and ``BISO_METAL`` otherwise,
    bounded to [0, 25] Å². Widths are a Lorentzian size term alone.
    """
    phase = structure_from_cif(cif).phases[0]
    for name in ("a", "b", "c"):
        par = getattr(phase.cell, name)
        par.value *= 1.0 + drift
        par.min = 1.0
    for atom in phase.atoms:
        biso = BISO_O if atom.species.startswith("O") else BISO_METAL
        atom.biso = rx.Parameter(value=biso, min=0.0, max=25.0)
    phase.scale = rx.Parameter(value=scale, min=0.0)
    phase.lor_size = rx.Parameter(value=0.03, min=0.0)
    phase.lor_strain = rx.Parameter(value=0.0, min=0.0)
    return phase


def co_sited(phase: rx.Phase) -> list[tuple[int, int]]:
    """(later, first) atom-index pairs at one position, to 1e-4 in each coordinate."""
    first: dict[tuple[float, float, float], int] = {}
    pairs = []
    for j, atom in enumerate(phase.atoms):
        key = (round(atom.x.value, 4), round(atom.y.value, 4), round(atom.z.value, 4))
        if key in first:
            pairs.append((j, first[key]))
        else:
            first[key] = j
    return pairs


def tie_co_sited(ref: rx.Refinement, phase_index: int = 0) -> int:
    """Tie every atom sharing a position with an earlier one to that one.

    Each site-symmetry step (``…dof.k``) and the Biso follow the first atom
    at the position. Two species on one site otherwise carry two sets of
    coordinate columns whose derivatives differ only by the ratio of their
    form factors, a near-flat direction no refiner leaves free. Returns the
    number of ties made.
    """
    phase = ref.structure.phases[phase_index]
    paths = {row.path for row in ref.parameters()}
    made = 0
    for j, i in co_sited(phase):
        src = f"phases.{phase_index}.atoms.{i}."
        for path in sorted(p for p in paths if p.startswith(src + "dof.")):
            suffix = path[len(src):]
            ref.tie(f"phases.{phase_index}.atoms.{j}.{suffix}", path)
            made += 1
        ref.tie(f"phases.{phase_index}.atoms.{j}.biso", src + "biso")
        made += 1
    return made


def large_cell_instrument() -> rx.Instrument:
    """Cu Kα doublet, graphite monochromator, FCJ on, four Chebyshev terms."""
    from rietx.schemas.instrument import BackgroundChebyshev

    ins = rx.Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=250.0,
                                       monochromator_two_theta=26.6)
    ins.background = BackgroundChebyshev.with_terms(4)
    ins.background.coefficients[0].value = 900.0
    ins.source.dispersion = None    # declared: a test pinning numbers says which
    ins.geometry.axial_sl.value = 0.03
    ins.geometry.axial_hl.value = 0.03
    ins.profile.w.value = 0.006
    ins.profile.x.value = 0.02
    return ins


def simulate(phase: rx.Phase, two_theta: np.ndarray, seed: int = 1) -> rx.PatternData:
    """The model's pattern, Poisson-sampled at ``seed``."""
    structure = rx.Structure(phases=[phase])
    ins = large_cell_instrument()
    blank = rx.PatternData(two_theta=two_theta.tolist(),
                           intensity=np.ones_like(two_theta).tolist())
    model = compile_model(structure, ins, blank)
    table = ParameterTable(structure, ins)
    y = np.asarray(model.evaluate(table.decode(table.x0())))
    counts = np.random.default_rng(seed).poisson(np.clip(y, 1.0, None))
    return rx.PatternData(two_theta=two_theta.tolist(),
                          intensity=counts.astype(float).tolist())


def _displace(ref: rx.Refinement, step: float, seed: int) -> list[str]:
    """Move every free site-symmetry step of an untied atom by N(0, ``step``)."""
    rows = [r for r in ref.parameters() if ".dof." in r.path and r.refinable
            and r.tie is None]
    shifts = np.random.default_rng(seed).normal(0.0, step, len(rows))
    ref.set_values({r.path: r.value + s for r, s in zip(rows, shifts)})
    return [r.path for r in rows]


def _coordinates(structure: rx.Structure) -> np.ndarray:
    return np.array([[a.x.value, a.y.value, a.z.value]
                     for a in structure.phases[0].atoms])


def _draw(result, stem: str) -> None:
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{stem}.png"))


def _z(result, path: str, truth: float) -> float:
    row = next(r for r in result.parameters if r.path == path)
    assert row.stderr, f"{path} carries no esd"
    return (row.value - truth) / row.stderr


#: the cell content each file's formula and Z give
CONTENT = {NB18W16O93: {"Nb": 18.0, "W": 16.0, "O": 93.0},
           H_NB2O5: {"Nb": 28.0, "O": 70.0}}


def _images(phase: rx.Phase) -> list[tuple[np.ndarray, str, float]]:
    """Every distinct image in the cell: (fractional xyz, element, occupancy)."""
    import gemmi

    ops = list(gemmi.SpaceGroup(phase.space_group).operations())
    out = []
    for atom in phase.atoms:
        element = atom.species.rstrip("+-0123456789")
        seen: list[np.ndarray] = []
        for op in ops:
            f = np.mod(np.array(op.apply_to_xyz([atom.x.value, atom.y.value,
                                                 atom.z.value])), 1.0)
            if not any(np.all(np.abs((f - g + 0.5) % 1.0 - 0.5) < 1e-4) for g in seen):
                seen.append(f)
        out += [(f, element, atom.occ.value) for f in seen]
    return out


@pytest.mark.parametrize("cif", [NB18W16O93, H_NB2O5], ids=["Nb18W16O93", "H-Nb2O5"])
def test_a_cod_large_cell_reads_whole(cif):
    """Each file reads to its published site count and cell content, and no
    two images sit closer than 1.6 Å except a mixed site's two species at
    one position.

    A COD entry can be wrong (an atom swap was once found in another one), so
    the composition and the shortest approach are checked on the file as
    vendored. The table must also build, which is where a site disagreeing
    with its symmetry would raise.
    """
    import gemmi

    phase = large_cell_phase(cif, scale=1.0)
    assert len(phase.atoms) == N_SITES[cif]
    images = _images(phase)
    content: dict[str, float] = {}
    for _, element, occ in images:
        content[element] = content.get(element, 0.0) + occ
    assert content == pytest.approx(CONTENT[cif], abs=1e-6)

    cell = phase.cell
    uc = gemmi.UnitCell(cell.a.value, cell.b.value, cell.c.value,
                        cell.alpha.value, cell.beta.value, cell.gamma.value)
    assert uc.volume > 1000.0
    orth = np.array(uc.orth.mat.tolist())
    frac = np.array([f for f, _, _ in images])
    d = frac[:, None, :] - frac[None, :, :]
    d -= np.round(d)
    shortest = np.inf
    # every neighbouring cell: in an oblique cell the nearest image need not
    # be the one rounding the fractional difference gives
    for shift in np.ndindex(3, 3, 3):
        r = np.linalg.norm((d + np.array(shift) - 1) @ orth.T, axis=-1)
        shortest = min(shortest, r[r > 1e-3].min())
    assert shortest > 1.6, shortest
    ParameterTable(rx.Structure(phases=[phase]), large_cell_instrument())


def _structural_plan() -> RefinementPlan:
    b = ["phases.*.scale", "instrument.background.*"]
    cell = ["phases.*.cell.*"]
    coords = ["phases.*.atoms.*.dof.*"]
    return RefinementPlan(stages=[
        Stage("scale_bkg", b),
        Stage("cell", b + cell),
        Stage("coordinates", b + cell + coords),
        Stage("biso", b + cell + coords + ["phases.*.atoms.*.biso"]),
    ])


def _rms_angstrom(phase: rx.Phase, delta: np.ndarray) -> float:
    """Root-mean-square length of per-atom fractional displacements, in Å."""
    import gemmi

    c = phase.cell
    uc = gemmi.UnitCell(c.a.value, c.b.value, c.c.value,
                        c.alpha.value, c.beta.value, c.gamma.value)
    cart = delta @ np.array(uc.orth.mat.tolist()).T
    return float(np.sqrt(np.mean(np.sum(cart ** 2, axis=1))))


# Counts are kept to a lab pattern's (strongest peak ~10⁵): at ten times more,
# the fit from the truth itself lands at a GoF of 1.3, because the simulator
# and the fit cut each peak's window at different places and that tail is then
# above the noise. Measured 2026-11-27 on both cells.
@pytest.mark.parametrize("cif, scale, two_theta_max", [
    pytest.param(NB18W16O93, 1e-4, 80.0, id="Nb18W16O93"),
    pytest.param(H_NB2O5, 3e-4, 70.0, id="H-Nb2O5", marks=pytest.mark.slow)])
def test_a_large_cell_rietveld_fit_recovers_its_coordinates(cif, scale, two_theta_max):
    """From coordinates displaced by a seeded draw, the structural fit lands
    at the noise floor with every refined coordinate within 6 esds of the
    published one, and its RMS position error is under half the start's.

    Measured 2026-11-27 (darwin/arm64, ``[dev]``), the start's RMS error
    against the fit's: Nb₁₈W₁₆O₉₃ 0.149 → 0.035 Å, largest |Δ|/esd 4.3, GoF
    1.04, 3.6 s; H-Nb₂O₅ 0.119 → 0.037 Å, 4.0, 1.03, 5.7 s. From the truth
    itself each fit lands at the same answer, so the residual error is the
    noise's, not a local minimum's. H-Nb₂O₅ is ``slow`` for its wall.
    """
    tt = np.arange(5.0, two_theta_max, 0.02)
    truth = large_cell_phase(cif, scale=scale)
    data = simulate(truth, tt)
    ref = rx.Refinement(rx.Structure(phases=[large_cell_phase(cif, scale=scale / 2,
                                                              drift=5e-4)]),
                        large_cell_instrument(), history=False)
    tie_co_sited(ref)
    displaced = _displace(ref, step=0.005, seed=7)
    start_xyz = _coordinates(ref.structure)
    result = ref.fit(data, plan=_structural_plan(), telemetry=False)
    _draw(result, f"large_cell_rietveld_{cif.stem}")

    assert result.statistics.gof < 1.1, result.statistics.gof
    true_xyz = _coordinates(rx.Structure(phases=[truth]))
    fit_xyz = _coordinates(ref.structure)
    z_fit = []
    for row in result.parameters:
        parts = row.path.split(".")
        if len(parts) == 5 and parts[2] == "atoms" and parts[4] in "xyz" and row.stderr:
            j, k = int(parts[3]), "xyz".index(parts[4])
            assert fit_xyz[j, k] == pytest.approx(row.value)
            z_fit.append((row.value - true_xyz[j, k]) / row.stderr)
    assert len(z_fit) >= len(displaced), (len(z_fit), len(displaced))
    assert np.max(np.abs(z_fit)) < 6.0, np.max(np.abs(z_fit))
    rms_start = _rms_angstrom(truth, start_xyz - true_xyz)
    rms_fit = _rms_angstrom(truth, fit_xyz - true_xyz)
    assert rms_fit < rms_start / 2, (rms_start, rms_fit)


@pytest.mark.parametrize("cif, scale, two_theta_max", [
    (NB18W16O93, 1e-4, 70.0), (H_NB2O5, 3e-4, 60.0)], ids=["Nb18W16O93", "H-Nb2O5"])
def test_a_large_cell_pawley_fit_recovers_its_cell(cif, scale, two_theta_max):
    """Pawley under ``mccusker_default`` from a cell 500 ppm high and generic
    widths: every free cell parameter lands within 4 esds of the published
    one (β included on the monoclinic cell), at a goodness of fit near 1.

    Measured 2026-11-27 (darwin/arm64, ``[dev]``): Nb₁₈W₁₆O₉₃ GoF 1.07,
    largest |Δ|/esd 0.6 (b, c), 1.6 s; H-Nb₂O₅ GoF 1.07, 1.7 (c), 2.6 s.
    """
    tt = np.arange(5.0, two_theta_max, 0.02)
    truth = large_cell_phase(cif, scale=scale)
    data = simulate(truth, tt)
    ins = large_cell_instrument()
    ins.profile.w.value = 0.010
    ins.profile.x.value = 0.01
    ref = rx.Refinement(rx.Structure(phases=[large_cell_phase(cif, scale=scale,
                                                              drift=5e-4)]),
                        ins, history=False)
    result = ref.fit(data, mode="pawley", plan=RefinementPlan.mccusker_default(),
                     telemetry=False)
    _draw(result, f"large_cell_pawley_{cif.stem}")

    assert result.statistics.gof < 1.2, result.statistics.gof
    checked = 0
    for name in ("a", "b", "c", "beta"):
        path = f"phases.0.cell.{name}"
        if any(r.path == path for r in result.parameters):
            z = _z(result, path, getattr(truth.cell, name).value)
            assert abs(z) < 4.0, (path, z)
            checked += 1
    assert checked == (4 if cif == H_NB2O5 else 3)
