"""A series carry names the atom the built structure has, not the declared index (#1264).

``_fit_one`` reads the carry's displaced DOF paths in the declared atom numbering.
When the built structure's atom order differs (a ``prepare`` hook dropped an atom
ahead of the site), the path has to follow its atom by label, or the hook's tie
sits on the right atom and ``_reanchor_carried`` never sees it.
"""

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.twins import matched_site_paths, numbering_moves
from rietx.refine import Stage
from rietx.schemas import Atom, Cell, Parameter, PatternData, Phase, Structure
from rietx.sequential import SequentialRefinement, _displaced_as_built
from rietx.strategy.staged import RefinementPlan

pytestmark = pytest.mark.filterwarnings("ignore")


def P(v):
    return Parameter(value=v)


def atom(label, sp, x, y, z):
    return Atom(label=label, species=sp, x=P(x), y=P(y), z=P(z), occ=P(1.0), biso=P(0.5))


def phase(atoms):
    return Phase(name="p", space_group="P n m a", atoms=atoms,
                 cell=Cell(a=P(8.4), b=P(5.4), c=P(6.9), alpha=P(90), beta=P(90),
                           gamma=P(90)))


BASE = [atom("Pb", "Pb", .188, .25, .167), atom("S", "S", .185, .25, .684),
        atom("O1", "O", .908, .25, .596), atom("O2", "O", .190, .25, .543),
        atom("O3", "O", .081, .025, .810)]  # O3: general position, last
INSTR = rx.Instrument.constant_wavelength_neutron(1.5)


def _pattern(atoms):
    ref = rx.Refinement(Structure(phases=[phase(atoms)]), INSTR, history=False)
    tt = np.arange(10.0, 90.0, 0.05)
    y = 100.0 + 1e3 * np.asarray(ref.predict(tt))
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                       sigma=np.sqrt(y).tolist())


def _run(drop):
    truth = [a.model_copy(update={"z": P(a.z.value + 0.01)}) if a.label == "O3" else a
             for a in BASE]
    data, started = _pattern(truth), {}

    def prepare(index, data, structure, instrument):  # pattern 2 loses one atom
        if index == 1 and drop:
            ph = structure.phases[0]
            ph.atoms = [a for a in ph.atoms if a.label != drop]

    def constrain(index, ref):  # tie O3's z to a variable
        j = [a.label for a in ref.structure.phases[0].atoms].index("O3")
        ref.add_variable("dz", 0.0, min=-0.05, max=0.05)
        ref.tie(f"phases.0.atoms.{j}.dof.2", "vars.dz")
        inner = ref.fit

        def fit(*a, **k):
            started[index] = (j, ref.structure.phases[0].atoms[j].z.value)
            return inner(*a, **k)
        ref.fit = fit

    plan = RefinementPlan(stages=[Stage("dz", ["vars.*"], max_iter=8)])
    series = SequentialRefinement(Structure(phases=[phase(BASE)]), INSTR).fit(
        [data, data], plan=plan, prepare=prepare, constrain=constrain)
    z0 = {p.path: p.value for p in series[0].parameters}[
        f"phases.0.atoms.{started[0][0]}.z"]
    return started, z0


@pytest.mark.parametrize("drop", [None, "O1"])
def test_pattern_two_starts_where_pattern_one_left_the_atom(drop):
    started, z0 = _run(drop)
    assert started[1][0] == (4 if drop is None else 3)  # the positive arm: it did move
    assert started[1][1] == pytest.approx(z0, abs=1e-6)


def test_displaced_paths_follow_their_atom_by_label():
    declared = Structure(phases=[phase(BASE)])
    built = Structure(phases=[phase([a for a in BASE if a.label != "O1"])])
    out = _displaced_as_built(
        ["phases.0.atoms.4.dof.2", "phases.0.atoms.2.dof.0", "phases.0.cell.a"],
        numbering_moves(declared, built), matched_site_paths(declared, built))
    # O3 follows to 3; the removed O1 drops out; a non-atom path is unchanged
    assert out == ["phases.0.atoms.3.dof.2", "phases.0.cell.a"]
