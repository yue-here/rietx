"""#562 S3 (WP-1997): composition, the contact term and the priors.

Public and synthetic structures only: WP-1466's 21 phases
(``tests/data/polyhedra_phases.json``), and textbook cells built here.

The four acceptance bars, each revert-checked against a deliberately broken
variant (the handover records which and how each failed):

1. **The contact set equals** :func:`rietx.model.geometry._neighbours`'s out to
   3.5 Å on all 21 phases, image for image: same neighbour site, same
   fractional vector to 1e-7.
2. **An atom shifted past an inversion image clashes**, where the source run's
   shifted-before-wrapped search found nothing; the same search does find the
   mirror case below ½, so the stand-in reproduces the defect and nothing else.
3. **A planted wrong coordination is caught by the prior and not by the data
   alone.**  Cd(OH)₂ (P -3 m 1), Cu Kα, X-ray: H moved from (⅓, ⅔, z) to
   (⅔, ⅓, z) has no O within 0.8-1.2 Å.  Its noise-free Δχ²_data is 2.5 at a
   10⁴-count peak, under :data:`~rietx.indexing.extinction.DECISIVE_DELTA_BIC`,
   and on one Poisson draw the data alone rank it *above* the truth; the
   coordination prior costs it 20 and the truth 0.
4. **chi2_data is identical** with and without priors at fixed coordinates.
"""

import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.indexing.extinction import DECISIVE_DELTA_BIC
from rietx.model.forward import compile_model, d_spacings
from rietx.model.geometry import CONTACT_MAX_ANG, _neighbours, _shell
from rietx.model.restraints import _metric_g
from rietx.params.vector import ParameterTable
from rietx.schemas.pattern import PatternData
from rietx.solve import chemistry as ch
from rietx.solve.cost import SolveCost

pytestmark = pytest.mark.xdist_group("solve-chemistry")

DATA = Path(__file__).parent / "data"
MEASURED = json.loads((DATA / "polyhedra_phases.json").read_text(encoding="utf-8"))
_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")


#: The numbers the module declares no default for (the caller supplies them),
#: held here at the values its first review round ran at.
FRACTION, SIGMA, COORDINATION_WEIGHT = 0.8, 0.1, DECISIVE_DELTA_BIC


def _sp(**kw):
    """A ``SolvePriors`` with the caller-supplied numbers filled in."""
    kw.setdefault("weights", ch.PriorWeights(coordination=COORDINATION_WEIGHT))
    return ch.SolvePriors(sigma=SIGMA, fraction=FRACTION, **kw)


def _p(v):
    return rx.Parameter(value=float(v))


def _cell(*v):
    return rx.Cell(**{k: _p(x) for k, x in zip(_KEYS, v)})


def _atom(label, species, x, y, z, occ=1.0, biso=0.5):
    return rx.Atom(label=label, species=species, x=_p(x), y=_p(y), z=_p(z),
                   occ=_p(occ), biso=_p(biso))


def _phase(name, sg, cell, atoms):
    return rx.Phase(name=name, space_group=sg, cell=_cell(*cell), atoms=atoms,
                    scale=_p(1.0))


def _measured(row) -> rx.Phase:
    return rx.Phase(name=row["name"], space_group=row["space_group"],
                    symmetry_operations=row["symmetry_operations"],
                    cell=_cell(*row["cell"]),
                    atoms=[_atom(lb, sp, x, y, z, occ)
                           for lb, sp, x, y, z, occ in row["atoms"]])


def _xyz(phase):
    return np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])


# -- 1. the contact set against the geometry table's ----------------------------

@pytest.mark.parametrize("row", MEASURED, ids=[r["name"] for r in MEASURED])
def test_contact_set_is_the_geometry_tables(row):
    phase = _measured(row)
    sites = compile_phase_sites(phase)
    values = {f"phases.0.atoms.{j}.{c}": getattr(a, c).value
              for j, a in enumerate(phase.atoms) for c in "xyz"}
    g = _metric_g(row["cell"])
    shifts = _shell(g, CONTACT_MAX_ANG)
    chem = ch.compile_chemistry(phase, _sp())
    xyz = _xyz(phase)
    pos = chem.positions(xyz)
    found = ch.contacts(pos, chem.g, CONTACT_MAX_ANG, centres=chem.first)
    for i in range(sites.n_asym):
        assert np.allclose(pos[chem.first[i]], xyz[i] - np.floor(xyz[i]))
        oracle = sorted(
            (j, *np.round(rot @ xyz[j] + tran + n - xyz[i], 7))
            for j, rot, tran, n, _d in _neighbours(sites, values, 0, i, g, shifts,
                                                    CONTACT_MAX_ANG))
        sel = found.a == chem.first[i]
        mine = sorted((int(chem.site_of[b]), *np.round(pos[b] + s - pos[chem.first[i]], 7))
                      for b, s in zip(found.b[sel], found.shift[sel]))
        assert mine == oracle, f"{row['name']} atom {i}"
        assert np.all(found.d[sel] <= CONTACT_MAX_ANG)


@pytest.mark.parametrize("row", MEASURED, ids=[r["name"] for r in MEASURED])
def test_clash_term_sums_the_oracle_checked_contacts(row):
    """The 27-cell clash sum is the contact set's own sum, at an r₀ wide enough
    to make every contact out to 3 Å a clash, but for pairs the occupancy rule
    skips: the mixed Mg/Fe olivine's coincident 0.9 + 0.1 sites."""
    phase = _measured(row)
    chem = ch.compile_chemistry(phase, _sp())
    pos = chem.positions(_xyz(phase))
    coexist = chem.occupancy[:, None] + chem.occupancy[None, :] > 1.0 + 1e-9
    r0 = np.where(coexist, 3.0, 0.0)
    assert ch.clash_cells_suffice(chem.g, r0)
    c = ch.contacts(pos, chem.g, 3.0)
    keep = coexist[chem.site_of[c.a], chem.site_of[c.b]]
    c = ch.Contacts(c.a[keep], c.b[keep], c.shift[keep], c.d[keep])
    expected = 0.5 * float(np.sum(((3.0 - c.d) / 0.1) ** 2))
    got = ch.clash_energy(pos, chem.site_of, chem.g, r0, SIGMA)
    assert got == pytest.approx(expected, rel=1e-12, abs=1e-12)
    assert ch.clash_count(pos, chem.site_of, chem.g, r0) == len(c.d) // 2


def test_site_clash_is_the_per_move_difference_of_the_total():
    """With w_same = ½ the change of one site's energy under its move is the
    change of the structure's total: what a Metropolis step reads."""
    phase = _phase("toy", "P 21/c", (5.1, 6.2, 7.3, 90, 101, 90),
                   [_atom("A", "O2-", 0.11, 0.23, 0.31), _atom("B", "O2-", 0.42, 0.18, 0.07),
                    _atom("C", "Mg2+", 0.27, 0.61, 0.44)])
    chem = ch.compile_chemistry(phase, _sp())
    xyz = _xyz(phase)
    moved = xyz.copy()
    moved[1] = [0.13, 0.27, 0.36]
    p0, p1 = chem.positions(xyz), chem.positions(moved)
    e0 = ch.clash_energy(p0, chem.site_of, chem.g, chem.r0, SIGMA)
    e1 = ch.clash_energy(p1, chem.site_of, chem.g, chem.r0, SIGMA)
    s = ch.site_clash(np.stack([p0, p1]), chem.site_of, np.array([1, 1]), chem.g, chem.r0, SIGMA)
    assert e1 > e0
    assert s[1] - s[0] == pytest.approx(e1 - e0, rel=1e-12)


def test_site_clash_refuses_what_its_27_cells_cannot_hold():
    g = _metric_g((2.0, 8.0, 8.0, 90, 90, 90))
    with pytest.raises(ValueError, match="27 cells"):
        ch.site_clash(np.zeros((1, 1, 3)), np.zeros(1, int), np.zeros(1, int), g,
                      np.array([[3.5]]), SIGMA)
    with pytest.raises(ValueError, match="outside"):
        ch.site_clash(np.zeros((1, 1, 3)), np.array([1]), np.zeros(1, int), g,
                      np.array([[1.0]]), SIGMA)


# -- 2. the inversion image the source run missed -------------------------------

def _shifted_before_wrapped(phase, i):
    """The source run's defect, as WP-1513 describes it: each symmetry image
    R·x + t is shifted by ±1 cell without first being brought into the cell."""
    from rietx.crystallography.structure_factor import select_orbit_ops
    from rietx.crystallography.symmetry import resolve_group

    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    g = _metric_g(tuple(getattr(phase.cell, k).value for k in _KEYS))
    xyz = _xyz(phase)
    out = []
    for j in range(len(xyz)):
        rot, tran = select_orbit_ops(sg, xyz[j])
        for r, t in zip(rot, tran):
            img = r @ xyz[j] + t
            for n in np.ndindex(3, 3, 3):
                d = img + np.array(n) - 1 - xyz[i]
                dist = float(np.sqrt(d @ g @ d))
                if dist > 1e-3:
                    out.append(dist)
    return min(out)


@pytest.mark.parametrize("x, defect_finds_it", [(0.95, False), (0.05, True)])
def test_an_atom_past_its_inversion_image_clashes(x, defect_finds_it):
    """O at (x, ½, ½) in P -1 sits 0.5 Å from its inversion image either way."""
    phase = _phase("P-1 toy", "P -1", (5.0, 5.2, 5.4, 88, 92, 91),
                   [_atom("O1", "O2-", x, 0.5, 0.5)])
    chem = ch.compile_chemistry(phase, _sp())
    xyz = _xyz(phase)
    pos = chem.positions(xyz)
    assert ch.clash_count(pos, chem.site_of, chem.g, chem.r0) == 1
    assert ch.clash_energy(pos, chem.site_of, chem.g, chem.r0, SIGMA) > 100.0
    c = ch.contacts(pos, chem.g, 1.0)
    assert len(c.d) == 2 and np.allclose(c.d, c.d[0]) and 0.49 < c.d[0] < 0.53
    # the term reads unwrapped images the same way: R·x + t straight off the ops
    raw = np.concatenate([np.einsum("mab,b->ma", r, xyz[j]) + t
                          for j, (r, t) in enumerate(chem.ops)])
    assert np.any(raw > 1.0) or np.any(raw < 0.0) or x < 0.5
    assert ch.site_clash(raw[None], chem.site_of, np.array([0]), chem.g, chem.r0, SIGMA)[0] \
        == pytest.approx(ch.site_clash(pos[None], chem.site_of, np.array([0]), chem.g,
                                       chem.r0, SIGMA)[0], rel=1e-12)
    assert (_shifted_before_wrapped(phase, 0) < float(chem.r0[0, 0])) is defect_finds_it


# -- 3. a planted wrong coordination ---------------------------------------------

CDOH2 = (3.4950, 3.4950, 4.7017, 90, 90, 120)
H_TRUE = (1 / 3, 2 / 3, 0.413)
H_PLANTED = (2 / 3, 1 / 3, 0.413)   # no O within 0.8-1.2 Å
PEAK_COUNTS = 1e4
COORDINATION = ch.CoordinationPrior("H", "O", 0.8, 1.2, 1, 1)


def _cdoh2(h):
    return rx.Structure(phases=[_phase(
        "Cd(OH)2", "P -3 m 1", CDOH2,
        [_atom("Cd", "Cd2+", 0, 0, 0, biso=0.6), _atom("O", "O2-", 1 / 3, 2 / 3, 0.2286, biso=0.7),
         _atom("H", "H", *h, biso=1.5)])])


def _values(structure, instrument):
    table = ParameterTable(structure, instrument)
    return table.decode(table.x0())


def _f2(structure, instrument, data):
    model = compile_model(structure, instrument, data, mode="rietveld")
    v = _values(structure, instrument)
    cp = model.phases[0]
    cell = tuple(v[f"phases.0.cell.{k}"] for k in _KEYS)
    return model, np.asarray(model._total_f2(0, d_spacings(cp.reflections.index, *cell),
                                             v, cell))


@pytest.fixture(scope="module")
def cdoh2():
    """The truth's pattern, Cu Kα₁,₂, 15-100° 2θ, scaled to a 10⁴-count
    strongest point over a 3 % flat background: noise-free, and one Poisson draw."""
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.source.dispersion = None
    truth = _cdoh2(H_TRUE)
    tt = np.arange(15, 100, 0.02)
    flat = PatternData(two_theta=list(tt), intensity=list(np.ones_like(tt)))
    y = np.asarray(compile_model(truth, ins, flat, mode="rietveld")
                   .evaluate(_values(truth, ins)))
    y = y / y.max() * PEAK_COUNTS + 0.03 * PEAK_COUNTS
    out = {}
    for name, yo in (("expected", y),
                     ("poisson", np.random.default_rng(0).poisson(y).astype(float))):
        data = PatternData(two_theta=list(tt), intensity=list(yo),
                           sigma=list(np.sqrt(np.maximum(yo, 1.0))))
        model, f_true = _f2(truth, ins, data)
        cost = SolveCost.from_model(model, _values(truth, ins))
        _, f_planted = _f2(_cdoh2(H_PLANTED), ins, data)
        out[name] = (cost, f_true, f_planted)
    return out


def _chem(h, priors):
    phase = _cdoh2(h).phases[0]
    return ch.compile_chemistry(phase, priors), _xyz(phase)


def test_a_planted_coordination_is_caught_by_the_prior_and_not_by_the_data(cdoh2):
    priors = _sp(coordination=(COORDINATION,))
    true_chem, true_xyz = _chem(H_TRUE, priors)
    bad_chem, bad_xyz = _chem(H_PLANTED, priors)
    assert true_chem.terms(true_xyz).coordination[0].counts == {2: 1.0}
    assert bad_chem.terms(bad_xyz).coordination[0].counts == {2: 0.0}

    # the data alone: not decisive in expectation, and wrong on this draw
    cost, f_true, f_bad = cdoh2["expected"]
    right = ch.candidate_cost(cost, f_true, true_chem, true_xyz)
    wrong = ch.candidate_cost(cost, f_bad, bad_chem, bad_xyz)
    assert 0.0 < wrong.chi2_data - right.chi2_data < DECISIVE_DELTA_BIC
    # the prior: zero on the truth, decisive on the plant
    assert right.chi2_prior == {"clash": 0.0, "coordination": 0.0}
    assert wrong.total - right.total >= DECISIVE_DELTA_BIC
    assert wrong.chi2_prior["coordination"] == pytest.approx(2 * COORDINATION_WEIGHT)

    cost, f_true, f_bad = cdoh2["poisson"]
    right = ch.candidate_cost(cost, f_true, true_chem, true_xyz)
    wrong = ch.candidate_cost(cost, f_bad, bad_chem, bad_xyz)
    assert wrong.chi2_data < right.chi2_data          # the data alone prefer the plant
    assert wrong.total > right.total                  # the prior puts the truth first


def test_composition_holds_for_the_truth_and_the_plant():
    """The plant moves H within its multiplicity: the gate cannot see it."""
    comp = ch.Composition("CdO2H2", z=1)
    for h in (H_TRUE, H_PLANTED):
        check = comp.require(_cdoh2(h).phases[0])
        assert check.inventory_matches and check.expected == {"Cd": 1, "O": 2, "H": 2}


# -- 4. chi2_data does not move with the priors ----------------------------------

def test_chi2_data_is_identical_with_and_without_priors(cdoh2):
    cost, _f_true, f_bad = cdoh2["poisson"]
    arms = [_sp(),
            _sp(coordination=(COORDINATION,)),
            _sp(coordination=(COORDINATION,)).control(),
            _sp(coordination=(COORDINATION,),
                           exclude=(ch.ExcludedContact("H", "Cd", 3.0),),
                           weights=ch.PriorWeights(clash=7.0, coordination=3.0))]
    got = []
    for priors in arms:
        chem, xyz = _chem(H_PLANTED, priors)
        got.append(ch.candidate_cost(cost, f_bad, chem, xyz))
    assert {c.chi2_data for c in got} == {cost.chi2(f_bad)[0]}
    assert any(sum(c.chi2_prior.values()) > 0.0 for c in got)


def test_the_zero_weight_control_measures_every_term_and_weighs_none(cdoh2):
    cost, _f_true, f_bad = cdoh2["poisson"]
    priors = _sp(coordination=(COORDINATION,),
                            exclude=(ch.ExcludedContact("H", "Cd", 3.0),))
    chem, xyz = _chem(H_PLANTED, priors.control())
    terms = chem.terms(xyz)
    assert terms.chi2_prior == {"clash": 0.0, "coordination": 0.0}
    assert terms.raw["coordination"] == 2.0 and terms.raw["clash"] > 0.0
    c = ch.candidate_cost(cost, f_bad, chem, xyz)
    assert c.total == c.chi2_data and c.prior_share == 0.0


def test_the_prior_share_is_reported_and_no_verdict_is_read_off_it():
    c = ch.CandidateCost(chi2_data=3.0, chi2_prior={"clash": 1.0})
    assert c.prior_share == pytest.approx(0.25)
    assert ch.CandidateCost(0.0, {"clash": 0.0}).prior_share == 0.0
    assert not hasattr(c, "prior_dominant")


# -- composition ------------------------------------------------------------------

def test_composition_names_what_the_sites_lack():
    comp = ch.Composition("CdO2H2", z=1)
    phase = _cdoh2(H_TRUE).phases[0]
    phase.atoms = phase.atoms[:2]
    check = comp.check(phase)
    assert not check.inventory_matches and check.missing == {"H": 2.0}
    with pytest.raises(ch.CompositionMismatch, match="H"):
        comp.require(phase)
    assert comp.check(phase, omit=("H",)).inventory_matches


def test_composition_z_and_volume_window():
    from rietx.crystallography.atomic_volume import formula_unit_volume

    rutile = _phase("TiO2", "P 42/m n m", (4.5937, 4.5937, 2.9587, 90, 90, 90),
                    [_atom("Ti", "Ti4+", 0, 0, 0), _atom("O", "O2-", 0.3048, 0.3048, 0)])
    comp = ch.Composition("TiO2")
    check = comp.check(rutile)
    v_fu = formula_unit_volume("TiO2")[0]
    assert check.volume == pytest.approx(4.5937 ** 2 * 2.9587)
    assert check.z_implied == pytest.approx(check.volume / v_fu)
    assert check.found == {"Ti": 2.0, "O": 4.0}
    lo, hi = ch.Composition("TiO2", z=2).volume_window()
    assert (lo, hi) == pytest.approx((0.8 * 2 * v_fu, 1.25 * 2 * v_fu))
    with pytest.raises(ValueError, match="Z"):
        comp.volume_window()
    with pytest.raises(ValueError):
        ch.Composition("TiO2", z=0)


# -- occupancy, exclusions, radii -------------------------------------------------

def test_a_split_site_is_skipped_and_said_so_while_a_real_clash_fires():
    phase = _phase("split", "P 1", (6.0, 6.0, 6.0, 90, 90, 90),
                   [_atom("Oa", "O2-", 0.10, 0.10, 0.10, occ=0.5),
                    _atom("Ob", "O2-", 0.15, 0.10, 0.10, occ=0.5),   # 0.3 Å from Oa
                    _atom("Oc", "O2-", 0.60, 0.60, 0.60),
                    _atom("Od", "O2-", 0.65, 0.60, 0.60)])           # 0.3 Å from Oc
    chem = ch.compile_chemistry(phase, _sp())
    pos = chem.positions(_xyz(phase))
    assert chem.r0[0, 1] == 0.0 and chem.r0[2, 3] > 0.3
    assert any("Oa–Ob" in n for n in chem.notes)
    assert ch.clash_count(pos, chem.site_of, chem.g, chem.r0) == 1


def test_an_excluded_contact_is_a_clash_term_and_listed():
    phase = _cdoh2(H_TRUE).phases[0]
    plain = ch.compile_chemistry(phase, _sp())
    chem = ch.compile_chemistry(phase, _sp(
        exclude=(ch.ExcludedContact("Cd", "H", 2.9),)))
    assert plain.r0[0, 2] == 0.0                  # Cd²⁺ (Shannon) and H (Pyykkö): no term
    assert chem.r0[0, 2] == chem.r0[2, 0] == 2.9
    assert chem.terms(_xyz(phase)).raw["clash"] > 0.0


def test_radii_follow_the_stated_rule_and_never_mix_tables():
    assert ch.contact_radius("Ti4+", cn=6).radius == 0.745        # Shannon CR, Ti⁴⁺ VI
    assert ch.contact_radius("O2-").table == "shannon_crystal"
    assert ch.contact_radius("Fe2+", cn=6).radius == 0.75          # LS 0.75 < HS 0.92
    assert ch.contact_radius("Fe2+", cn=6, spin="HS").radius == 0.92
    assert ch.contact_radius("Ti4+", cn=4).radius == 0.56
    assert ch.contact_radius("Ti4+", cn=12) is None               # no row, no radius
    assert ch.contact_radius("Mg").table == "pyykko_r1"
    assert ch.contact_radius("Mg", anion_free=True).table == "pauling_r1"
    mixed = ch.compile_chemistry(_cdoh2(H_TRUE).phases[0], _sp())
    assert mixed.r0[1, 2] == 0.0
    assert any("O2-" in n and "H" in n and "different tables" in n for n in mixed.notes)


# -- review round 1 (#1016) -------------------------------------------------------

def _two_fe(occ):
    return _phase("fe2", "P 1", (6.0, 6.0, 6.0, 90, 90, 90),
                  [_atom("Fe1", "Fe", 0.10, 0.10, 0.10, occ=occ),
                   _atom("Fe2", "Fe", 0.30, 0.10, 0.10, occ=occ)])    # 1.2 Å apart


def test_a_declared_exclusion_outranks_the_occupancy_rule():
    phase = _two_fe(0.5)
    plain = ch.compile_chemistry(phase, _sp())
    assert plain.r0[0, 1] == 0.0 and any("Fe1–Fe2" in n for n in plain.notes)
    chem = ch.compile_chemistry(phase, _sp(
        exclude=(ch.ExcludedContact("Fe", "Fe", 2.5),)))
    assert chem.r0[0, 1] == chem.r0[1, 0] == 2.5       # its own d, not the radii's
    assert chem.terms(_xyz(phase)).raw["clash"] > 0.0
    assert any("outranks the occupancy rule" in n and "Fe1–Fe2" in n for n in chem.notes)
    assert not any("no clash term for: Fe1–Fe2" in n for n in chem.notes)


def test_the_mixed_table_note_does_not_deny_a_declared_exclusion():
    phase = _cdoh2(H_TRUE).phases[0]
    plain = ch.compile_chemistry(phase, _sp())
    assert any("different tables" in n and "no radius-derived clash term" in n
               and "declared exclusion" not in n for n in plain.notes)
    chem = ch.compile_chemistry(phase, _sp(
        exclude=(ch.ExcludedContact("O", "H", 0.8),)))
    note = next(n for n in chem.notes if "different tables" in n and "O2-" in n)
    assert "declared exclusion at 0.8 Å is its clash term" in note
    assert chem.r0[1, 2] == 0.8


def test_a_radius_past_the_27_cells_is_refused_at_compile():
    thin = _phase("thin", "P 1", (2.0, 8.0, 8.0, 90, 90, 90),
                  [_atom("H1", "H", 0.0, 0.0, 0.0), _atom("H2", "H", 0.5, 0.5, 0.5)])
    with pytest.raises(ValueError, match="27 cells"):
        ch.compile_chemistry(thin, _sp(
            exclude=(ch.ExcludedContact("H", "H", 3.5),)))
    ch.compile_chemistry(thin, _sp(
        exclude=(ch.ExcludedContact("H", "H", 1.0),)))          # a fitting one compiles


def test_an_ambiguous_cn_raises_and_names_both_rows():
    with pytest.raises(ValueError, match="IV and IVSQ"):
        ch.contact_radius("Cu2+", cn=4)
    assert ch.contact_radius("Cu2+", cn="IV").radius > 0       # the choice made
    assert ch.contact_radius("Ti4+", cn=12) is None            # untabulated stays None
    assert ch.contact_radius("Fe2+", cn=6).radius == 0.75      # both spins: still the smaller
    phase = _phase("cu", "P 1", (6.0, 6.0, 6.0, 90, 90, 90),
                   [_atom("Cu1", "Cu2+", 0.1, 0.1, 0.1)])
    with pytest.raises(ValueError, match="IVSQ"):
        ch.compile_chemistry(phase, _sp(cn={"Cu2+": 4}))


def test_a_prior_that_matches_nothing_says_so():
    phase = _cdoh2(H_TRUE).phases[0]
    chem = ch.compile_chemistry(phase, _sp(
        coordination=(ch.CoordinationPrior("Zn", "O", 1.8, 2.4, 6, 6),
                      ch.CoordinationPrior("Cd", "Cl", 2.0, 2.8, 6, 6)),
        exclude=(ch.ExcludedContact("Zn", "H", 2.0),),
        cn={"Ti4+": 6}, spin={"Fe2+": "HS"}))
    notes = "\n".join(chem.notes)
    assert "CoordinationPrior Zn–O: no site holds Zn, so the term is 0 and reads as satisfied" in notes
    assert "CoordinationPrior Cd–Cl: no site holds Cl" in notes
    assert "ExcludedContact Zn–H: no site holds Zn" in notes
    assert "SolvePriors.cn['Ti4+']" in notes and "SolvePriors.spin['Fe2+']" in notes
    quiet = ch.compile_chemistry(phase, _sp(
        coordination=(ch.CoordinationPrior("Cd", "O", 2.0, 2.8, 6, 6),)))
    assert not any("no site" in n for n in quiet.notes)


def test_the_radius_detail_uses_shannons_spelling():
    assert "Ti4+ CN VI" in ch.contact_radius("Ti4+", cn=6).detail
    assert "O2- CN VI" in ch.contact_radius("O2-", cn=6).detail


# -- review round 2 (#1016) -------------------------------------------------------

def test_no_clash_number_is_chosen_for_the_caller():
    """The fraction, σ and coordination weight have no default, so none is the
    package's decision on the caller's behalf until a measured one is chosen."""
    phase = _cdoh2(H_TRUE).phases[0]
    with pytest.raises(TypeError):
        ch.SolvePriors()
    with pytest.raises(TypeError):
        ch.SolvePriors(sigma=SIGMA, fraction=FRACTION)            # no weights
    with pytest.raises(TypeError):
        ch.PriorWeights()
    with pytest.raises(TypeError):
        ch.compile_chemistry(phase)
    with pytest.raises(TypeError):
        ch.clash_energy(np.zeros((1, 3)), np.zeros(1, int), np.eye(3), np.zeros((1, 1)))
    assert ch.PriorWeights(coordination=3.0).clash == 1.0          # the unit weight stays
    for name in ("CLASH_FRACTION", "CLASH_SIGMA_ANG", "COORDINATION_WEIGHT",
                 "PRIOR_SHARE_MAX", "DEFAULT_CN", "INVENTORY_TOL"):
        assert not hasattr(ch, name), name


def test_an_ion_of_unknown_coordination_takes_the_smallest_tabulated_radius():
    from rietx.crystallography import radii

    rows = [r for r in radii._shannon_rows() if r.ion == "Si" and r.charge == 4]
    assert len(rows) > 1
    got = ch.contact_radius("Si4+")
    assert got.radius == min(r.crystal_radius for r in rows)
    assert got.radius < ch.contact_radius("Si4+", cn=6).radius     # not CN VI by default
    assert "smallest" in got.detail and "CN IV" in got.detail
    # a declared CN is still that CN's own row
    assert ch.contact_radius("Si4+", cn=6).radius == radii.ionic_radius(
        "Si4+", 6, kind="crystal").radius
    # a declared spin narrows the rows the smallest is taken over
    fe = [r for r in radii._shannon_rows() if r.ion == "Fe" and r.charge == 2]
    assert ch.contact_radius("Fe2+", spin="HS").radius == min(
        r.crystal_radius for r in fe if r.spin in (None, "HS"))
    assert ch.contact_radius("Fe2+").radius == min(r.crystal_radius for r in fe)
    assert ch.contact_radius("Fe9+") is None                       # untabulated charge


def test_the_inventory_tolerance_scales_with_the_part_occupied_multiplicity():
    """A part occupancy is read as written, or as the p/q (q ≤ 12) it rounds
    (#1016, review round 4).  On a 192-fold site, ⅓ printed to two, three or
    four decimals holds 64 atoms; 0.5 is ½ and holds 96, never 87 or 90."""
    def cu(occ):
        return _phase("cu", "F m -3 m", (12.0, 12.0, 12.0, 90, 90, 90),
                      [_atom("Cu", "Cu", 0.11, 0.23, 0.37, occ=occ)])
    comp = ch.Composition("Cu", z=64)
    for occ in (0.33, 0.333, 0.3333, 1 / 3):
        check = comp.require(cu(occ))
        assert check.found["Cu"] == pytest.approx(192 * occ)
        assert check.found_as_fraction["Cu"] == pytest.approx(64.0, abs=1e-9)
        assert check.read_as == {"Cu": "1/3"}
    # the same site written as Cu2 at Z = 32: 0.33 is 0.02 short per formula
    # unit, which checkCIF's fixed 0.01 would refuse; read as ⅓ it holds 64
    assert ch.Composition("Cu2", z=32).require(cu(0.33)).inventory_matches
    # 0.34 and 0.32 round no fraction with q ≤ 12: a real excess and shortfall
    for occ, found in ((0.34, 65.28), (0.32, 61.44)):
        check = comp.check(cu(occ))
        assert check.read_as == {} and check.found_as_fraction["Cu"] == pytest.approx(found)
        assert check.missing == {"Cu": pytest.approx(64 - found)}
        with pytest.raises(ch.CompositionMismatch):
            comp.require(cu(occ))
    # review round 4's rows: 0.5 read as 0.45-0.55 passed formula × Z from 87 to
    # 105; read as ½ it holds 96 and nothing else.  0.1 is 1/10 and holds 19.2.
    assert ch.Composition("Cu", z=96).require(cu(0.5)).read_as == {"Cu": "1/2"}
    for n, occ in ((90, 0.5), (87, 0.5), (105, 0.5), (15, 0.1)):
        with pytest.raises(ch.CompositionMismatch):
            ch.Composition("Cu", z=n).require(cu(occ))
    # as written still counts: a formula that really says 0.17 per site holds
    # 0.17 × 192 = 32.64, though 0.17 also rounds ⅙ (which would hold 32)
    check = ch.Composition("Cu0.17", z=192).require(cu(0.17))
    assert check.read_as == {"Cu": "1/6"} and check.inventory_matches
    assert ch.Composition("Cu", z=32).require(cu(0.17)).inventory_matches
    # a full site has nothing to read: one atom short is still short
    full = _cdoh2(H_TRUE).phases[0]
    full.atoms = full.atoms[:2]
    assert ch.Composition("CdO2H2", z=1).check(full).read_as == {}
    assert not ch.Composition("CdO2H2", z=1).check(full).inventory_matches


def test_an_occupancy_reads_as_the_fraction_inside_its_printed_rounding():
    f = ch.occupancy_fraction
    assert ch.OCCUPANCY_MAX_DENOMINATOR == 12
    assert f(0.33) == f(0.333) == f(0.3333) == f(1 / 3) == Fraction(1, 3)
    assert f(0.5) == Fraction(1, 2) and f(0.1) == Fraction(1, 10)
    assert f(0.17) == f(0.167) == Fraction(1, 6) and f(0.083) == Fraction(1, 12)
    assert f(0.125) == Fraction(1, 8) and f(0.9) == Fraction(9, 10)
    assert f(0.34) is None and f(0.32) is None and f(0.3334) is None
    assert f(0.0769) is None                                      # 1/13 is past q ≤ 12
    assert f(1.0) is None and f(0.0) is None


def test_in_volume_window_is_a_ceiling_only():
    # WP-2030 (#1237 review): an inorganic cell lies under Hofmann's 0.8 floor,
    # so the flag must not call a correct cell outside the window
    rutile = _phase("TiO2", "P 42/m n m", (4.5937, 4.5937, 2.9587, 90, 90, 90),
                    [_atom("Ti", "Ti4+", 0, 0, 0), _atom("O", "O2-", 0.3048, 0.3048, 0)])
    true = ch.Composition("TiO2", z=2).check(rutile)
    assert true.volume_ratio < 0.8
    assert true.in_volume_window
    # two formula units declared as one: larger than the formula holds
    doubled = _phase("TiO2", "P 42/m n m", (4.5937, 4.5937, 5.9174, 90, 90, 90),
                     [_atom("Ti", "Ti4+", 0, 0, 0), _atom("O", "O2-", 0.3048, 0.3048, 0)])
    big = ch.Composition("TiO2", z=1).check(doubled)
    assert big.volume_ratio > 1.25
    assert not big.in_volume_window
