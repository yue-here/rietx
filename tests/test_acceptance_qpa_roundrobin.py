"""v0.3 QPA acceptance: IUCr CPD Quantitative Phase Analysis Round Robin.

Samples 1a-1h (corundum/zincite/fluorite, trace→major for each phase),
sample 2 (+ platy brucite → preferred orientation) and sample 4
(corundum/magnetite/zircon → microabsorption), measured on the CPD's Philips
3020 Bragg-Brentano goniometer with the Cu Kα doublet and a diffracted-beam
graphite monochromator (full instrument record and the weighed "truth" table:
``tests/data/README.md``).  References: Madsen, Scarlett, Cranswick & Lwin
(2001) J. Appl. Cryst. 34, 409 (samples 1a-1h); Scarlett et al. (2002)
J. Appl. Cryst. 35, 383 (samples 2-4).

Unlike the FAP acceptance there is no other code's protocol to mirror — the
comparison target is the *weighed composition*, not another Rietveld result —
so the protocol is this package's own lab QPA plan, stated here and identical
for every mixture: scale+background → zero+displacement → cells → instrument
profile → per-phase size/strain broadening → Kα2 ratio + axial → Biso, with
atomic coordinates held at single-crystal literature values, no internal
standard, and (sample 2) a March-Dollase r on brucite's (001) as the only
texture parameter.  Fractions are Hill-Howard ZMV over the modelled
crystalline phases (``RefinementResult.qpa``).

Tolerances are referenced to the **published participant spread**, per the
validation policy (docs/DESIGN.md) and the WP-0310 brief: even for the
deliberately well-behaved sample 1, participant-returned fractions scatter
over several wt % around the weighed values (Madsen 2001, Fig. 2 ternary —
"note the spread of results"); matching the weighed composition much better
than that spread would be suspicious, not a triumph.  Hence: **6 wt % absolute
per major phase, 2 wt % for trace phases (< 5 wt % weighed)** for sample 1,
the same majors band for sample 2, and *no accuracy band at all* for sample 4
— which the round robin designed to defeat the Brindley model ("really beyond
the limits of the Brindley model in this case", Scarlett 2002) and which this
suite treats as a characterisation: the test asserts the bias *shape*, that
the µR fence fires, and that the correction moves the extreme phases toward
the weighed values, not that the numbers land.

**Measured results** (2026-07-24, recorded in docs/milestones/v0.3.md):
sample-1 worst |ΔW| = 5.1 wt % (1f zincite), traces ≤ 1.3 wt %; the signed
errors have a stable shape — zincite low (mean −2.7), corundum high (+1.7),
fluorite mildly high (+1.0) — consistent in direction with untreated
microabsorption for the corundum/zincite pair (µ ≈ 128 vs 282 cm⁻¹), and
asserted as a shape below rather than absorbed into a wider band.  Sample 2:
worst 2.9 wt % with brucite March-Dollase r ≈ 0.68 (< 1 = platy in
Bragg-Brentano reflection geometry, the expected habit).  Sample 4
uncorrected: corundum +24, magnetite −15, zircon −9 wt %; Brindley with
order-of-magnitude radii improves corundum and magnetite but not zircon, and
the BRINDLEY_OUTSIDE_REGIME fence fires on magnetite/zircon — the WP-0305
machinery correctly refusing confidence outside its regime.

The statistical σ(W) propagated from the correlated scale covariance is
0.1-0.4 wt % throughout — an order of magnitude below the measured errors.
That is not a defect of the propagation: QPA accuracy on real mixtures is
dominated by intensity-level systematics (microabsorption, residual texture,
fixed-structure approximations) that no scale covariance can see.  The tests
assert σ(W) is present and positive, and the tolerances above never lean on it.
"""

from pathlib import Path

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.schemas.instrument import BackgroundChebyshev
from pxrdref.schemas.structure import PreferredOrientation

DATA = Path(__file__).parent / "data" / "qarr"
OUT = Path(__file__).parent / "output"

#: CPD "Weighed and Measured Values" (8 Nov 1999), mass %.  XRF cross-checks
#: on the same page agree with these to < 1 wt %.
WEIGHED = {
    "cpd-1a": {"corundum": 1.15, "zincite": 4.04, "fluorite": 94.81},
    "cpd-1b": {"corundum": 94.31, "zincite": 1.36, "fluorite": 4.33},
    "cpd-1c": {"corundum": 5.04, "zincite": 93.59, "fluorite": 1.36},
    "cpd-1d": {"corundum": 13.53, "zincite": 32.89, "fluorite": 53.58},
    "cpd-1e": {"corundum": 55.12, "zincite": 15.25, "fluorite": 29.62},
    "cpd-1f": {"corundum": 27.06, "zincite": 55.22, "fluorite": 17.72},
    "cpd-1g": {"corundum": 31.37, "zincite": 34.21, "fluorite": 34.42},
    "cpd-1h": {"corundum": 35.12, "zincite": 30.19, "fluorite": 34.69},
    "cpd-2": {"corundum": 21.27, "zincite": 19.94, "fluorite": 22.53,
              "brucite": 36.26},
    "cpd-4": {"corundum": 50.46, "magnetite": 19.64, "zircon": 29.90},
}

SAMPLE1 = tuple(f"cpd-1{c}" for c in "abcdefgh")
MAJOR_TOL = 6.0   # wt %, referenced to the sample-1 participant spread
TRACE_TOL = 2.0   # wt %, phases weighed below 5 wt %


def _p(v, **kw):
    return pr.Parameter(value=v, **kw)


def _phase(name, sg, cell, atoms, **kw):
    a, b, c, al, be, ga = cell
    return pr.Phase(
        name=name, space_group=sg,
        cell=pr.Cell(a=_p(a, min=1.0), b=_p(b, min=1.0), c=_p(c, min=1.0),
                     alpha=_p(al), beta=_p(be), gamma=_p(ga)),
        atoms=[pr.Atom(label=lab, species=sp, x=_p(x), y=_p(y), z=_p(z),
                       biso=_p(biso, min=0.0, max=25.0))
               for lab, sp, x, y, z, biso in atoms],
        scale=_p(1e-3, min=0.0, transform="softplus"),
        lor_size=_p(0.02, min=0.0, transform="softplus"),
        lor_strain=_p(0.0, min=0.0, transform="softplus"),
        **kw)


def corundum_phase() -> pr.Phase:
    """α-Al₂O₃, R-3c (hexagonal axes); Lewis, Schwarzenbach & Flack (1982)
    Acta Cryst. A38, 733."""
    return _phase("corundum", "R -3 c", (4.7593, 4.7593, 12.9917, 90, 90, 120),
                  [("Al", "Al", 0.0, 0.0, 0.35216, 0.30),
                   ("O", "O", 0.30624, 0.0, 0.25, 0.30)])


def zincite_phase() -> pr.Phase:
    """ZnO wurtzite, P6₃mc; Kihara & Donnay (1985) Can. Mineral. 23, 647."""
    return _phase("zincite", "P 63 m c", (3.2499, 3.2499, 5.2066, 90, 90, 120),
                  [("Zn", "Zn", 1 / 3, 2 / 3, 0.0, 0.55),
                   ("O", "O", 1 / 3, 2 / 3, 0.3826, 0.55)])


def fluorite_phase() -> pr.Phase:
    """CaF₂, Fm-3m, a = 5.4631 Å; both sites fully fixed by symmetry."""
    return _phase("fluorite", "F m -3 m", (5.4631, 5.4631, 5.4631, 90, 90, 90),
                  [("Ca", "Ca", 0.0, 0.0, 0.0, 0.55),
                   ("F", "F", 0.25, 0.25, 0.25, 0.75)])


def brucite_phase(*, textured: bool = False) -> pr.Phase:
    """Mg(OH)₂, P-3m1; Zigan & Rothbauer (1967) Z. Kristallogr. 125, 425
    (neutron, D → H).  H is invisible to X-rays but carries 3.5 % of the
    molar mass — omitting it would bias the ZMV fraction by that much, so it
    stays in the model with its Biso *held* (the biso stage below frees only
    Mg and O).  ``textured`` attaches the March-Dollase block on (001), the
    plate normal of this strongly platy mineral."""
    kw = {}
    if textured:
        kw["preferred_orientation"] = PreferredOrientation(axis=(0, 0, 1))
    return _phase("brucite", "P -3 m 1", (3.142, 3.142, 4.766, 90, 90, 120),
                  [("Mg", "Mg", 0.0, 0.0, 0.0, 0.70),
                   ("O", "O", 1 / 3, 2 / 3, 0.2216, 0.90),
                   ("H", "H", 1 / 3, 2 / 3, 0.4303, 2.5)], **kw)


def magnetite_phase() -> pr.Phase:
    """Fe₃O₄ inverse spinel, Fd-3m origin choice 2 (gemmi's bare symbol
    resolves to origin 1, so the ``:2`` is load-bearing); Fleet (1981)
    Acta Cryst. B37, 917."""
    return _phase("magnetite", "F d -3 m:2", (8.3941, 8.3941, 8.3941, 90, 90, 90),
                  [("FeT", "Fe", 0.125, 0.125, 0.125, 0.40),
                   ("FeO", "Fe", 0.5, 0.5, 0.5, 0.50),
                   ("O", "O", 0.2549, 0.2549, 0.2549, 0.60)])


def zircon_phase() -> pr.Phase:
    """ZrSiO₄, I4₁/amd origin choice 2; Hazen & Finger (1979) Am. Mineral.
    64, 196."""
    return _phase("zircon", "I 41/a m d:2", (6.6042, 6.6042, 5.9796, 90, 90, 90),
                  [("Zr", "Zr", 0.0, 0.75, 0.125, 0.35),
                   ("Si", "Si", 0.0, 0.25, 0.375, 0.35),
                   ("O", "O", 0.0, 0.0660, 0.1951, 0.55)])


def qarr_instrument() -> pr.Instrument:
    """The CPD standard-data-set instrument: Philips Bragg-Brentano, 17.3 cm
    radius, Cu Kα doublet on the NIST/Hölzer wavelength scale (what the
    ``CuKa`` preset ships and what the SRM 676a certificate uses — the
    Sietronics header's 1.54056 Å is the same line quoted at its older
    nominal value), diffracted-beam graphite monochromator (2θ_m ≈ 26.6° →
    polarization K ≈ 0.556)."""
    ins = pr.Instrument.bragg_brentano(radiation="CuKa",
                                       goniometer_radius_mm=173.0,
                                       monochromator_two_theta=26.6)
    ins.background = BackgroundChebyshev.with_terms(6)
    return ins


def seed_scales(structure: pr.Structure, ins: pr.Instrument,
                data: pr.PatternData) -> None:
    """Scale the phases so the summed calculated intensity matches the data
    (equal split between phases; stage 1 apportions).  Deterministic, and
    keeps TRF's first stage within the softplus transform's live range."""
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable

    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    obs = np.asarray(data.intensity)
    ratio = float((obs.sum() - obs.min() * len(obs)) / max(float(y.sum()), 1e-9))
    for ph in structure.phases:
        ph.scale.value *= ratio / len(structure.phases)


def qpa_plan(*, biso_globs: tuple[str, ...] = ("phases.*.atoms.*.biso",),
             texture: bool = False) -> pr.RefinementPlan:
    """The QPA protocol of this module's docstring.  The sample-broadening
    stage seeds its softplus terms off the exact-zero floor (lor_strain and
    the gauss terms start at 0, where the softplus gradient is dead)."""
    stages = [
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("zero_disp", ["instrument.zero_shift",
                               "instrument.geometry.sample_displacement"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        pr.Stage("sample_broadening",
                 ["phases.*.lor_size", "phases.*.lor_strain",
                  "phases.*.gauss_size", "phases.*.gauss_strain"], seed=1e-4),
        pr.Stage("lines_axial", ["instrument.source.lines.*.weight",
                                 "instrument.geometry.axial_sl"]),
        pr.Stage("biso", list(biso_globs)),
    ]
    if texture:
        stages.append(pr.Stage("po", ["phases.*.preferred_orientation.r"]))
    return pr.RefinementPlan(stages=stages)


def _require_data():
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")


def _fit(sample: str, phases: list[pr.Phase], *, plan: pr.RefinementPlan):
    data = pr.read_pattern(DATA / f"{sample}.prn")
    structure = pr.Structure(phases=phases)
    ins = qarr_instrument()
    seed_scales(structure, ins, data)
    ref = pr.Refinement(structure, ins)
    result = ref.fit(data, plan=plan)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"qarr_{sample}.png"))
    result.plot(path=str(OUT / f"qarr_{sample}_lowangle.png"),
                two_theta_range=(15.0, 60.0))
    import matplotlib.pyplot as plt
    plt.close("all")   # plot() hands back live figures; 24 of them add up
    return ref, result


def _fractions_pct(result) -> dict[str, float]:
    return {r.name: 100.0 * r.weight_fraction for r in result.qpa.phases}


# -- reader ----------------------------------------------------------------

def test_read_prn_two_column_ascii():
    """The CPD ``col``-format ``.prn`` files (2θ°, counts) are plain two-column
    ASCII and must land in the generic xy reader: 7251 points, 5-150° at
    0.02°, no σ column → ``sigma`` unset so Poisson √max(y,1) applies
    downstream (the weighting invariant)."""
    _require_data()
    for name in ("cpd-1g", "cpd-1e", "corundum"):   # 1e carries a trailing blank line
        d = pr.read_pattern(DATA / f"{name}.prn")
        tt = np.asarray(d.two_theta)
        assert len(tt) == 7251
        assert tt[0] == pytest.approx(5.0) and tt[-1] == pytest.approx(150.0)
        # cpd-1e writes some ordinates truncated to 7 chars ("8.059999"), so
        # the grid is uniform only to ~1 µdeg
        assert np.allclose(np.diff(tt), 0.02, atol=1e-5)
        assert d.sigma is None
        assert np.all(np.asarray(d.intensity) >= 0)


# -- sample 1: eight corundum/zincite/fluorite mixtures --------------------

@pytest.fixture(scope="module")
def sample1_results():
    """Fit all eight sample-1 mixtures once, under the identical protocol."""
    _require_data()
    out = {}
    for sample in SAMPLE1:
        _, result = _fit(sample, [corundum_phase(), zincite_phase(),
                                  fluorite_phase()], plan=qpa_plan())
        out[sample] = result
    return out


@pytest.mark.slow
@pytest.mark.parametrize("sample", SAMPLE1)
def test_sample1_fractions_within_participant_spread(sample1_results, sample):
    result = sample1_results[sample]
    assert result.status == "converged"
    assert result.statistics.n_points == 7251
    assert result.statistics.rwp < 0.20
    assert result.statistics.gof < 2.0

    got = _fractions_pct(result)
    assert sum(got.values()) == pytest.approx(100.0, abs=1e-6)
    for name, w_true in WEIGHED[sample].items():
        tol = TRACE_TOL if w_true < 5.05 else MAJOR_TOL
        assert abs(got[name] - w_true) < tol, \
            f"{sample} {name}: {got[name]:.2f} vs weighed {w_true:.2f}"
    # σ(W) from the correlated scale block: present, positive, and honest
    # about being statistical-only (docstring) — never used as the tolerance
    for row in result.qpa.phases:
        assert row.weight_fraction_stderr is not None
        assert 0.0 < row.weight_fraction_stderr < 0.02


@pytest.mark.slow
def test_sample1_bias_has_the_microabsorption_shape(sample1_results):
    """The residual inaccuracy is a *characterised systematic*, not noise:
    zincite comes back low and corundum high across the whole suite — the
    direction untreated microabsorption imposes on that pair (µ ≈ 282 vs
    128 cm⁻¹; fluorite's sign shows the effect is also particle-size
    dependent, and no d50s are published to model it honestly).  Asserting
    the shape pins the explanation; a future change that breaks the shape
    (or fixes the physics) should fail here and prompt re-derivation."""
    err = {name: [_fractions_pct(sample1_results[s])[name] - WEIGHED[s][name]
                  for s in SAMPLE1]
           for name in ("corundum", "zincite", "fluorite")}
    assert np.mean(err["zincite"]) < -1.0
    assert np.mean(err["corundum"]) > 0.5
    assert abs(np.mean(err["fluorite"])) < 2.0
    assert max(abs(e) for es in err.values() for e in es) < MAJOR_TOL


# -- sample 2: + platy brucite (preferred orientation) ---------------------

@pytest.mark.slow
def test_sample2_brucite_march_dollase():
    """Brucite is strongly platy (pure-pattern fit without texture: Rwp 55 %,
    GoF 8.5 — with March-Dollase: 19 %).  H's Biso is held (see
    ``brucite_phase``); brucite index 3 in the phase list below."""
    _require_data()
    biso = ("phases.0.atoms.*.biso", "phases.1.atoms.*.biso",
            "phases.2.atoms.*.biso", "phases.3.atoms.0.biso",
            "phases.3.atoms.1.biso")
    ref, result = _fit(
        "cpd-2",
        [corundum_phase(), zincite_phase(), fluorite_phase(),
         brucite_phase(textured=True)],
        plan=qpa_plan(biso_globs=biso, texture=True))

    assert result.status == "converged"
    assert result.statistics.rwp < 0.18
    got = _fractions_pct(result)
    for name, w_true in WEIGHED["cpd-2"].items():
        assert abs(got[name] - w_true) < MAJOR_TOL, \
            f"cpd-2 {name}: {got[name]:.2f} vs weighed {w_true:.2f}"

    # r < 1 on the (001) plate normal = platy habit in reflection geometry
    # (model/preferred_orientation.py convention) — the physically expected
    # sense, and far enough from the r = 1 identity to be a real detection
    r = ref.fitted_structure.phases[3].preferred_orientation.r.value
    assert 0.4 < r < 0.9
    # H Biso was held at its starting value, not driven to a bound
    assert ref.fitted_structure.phases[3].atoms[2].biso.value == pytest.approx(2.5)


# -- sample 4: microabsorption (designed to defeat Brindley) ---------------

@pytest.mark.slow
def test_sample4_microabsorption_characterised_not_hidden():
    """Coarse magnetite (µ ≈ 1165 cm⁻¹ at Cu Kα — Fe sits just above its K
    edge) against fine corundum (µ ≈ 128): the round robin built this sample
    to put microabsorption beyond the Brindley model, and participants'
    Rietveld fractions scattered accordingly (Scarlett 2002).  No accuracy
    band is claimed.  What *is* asserted: the bias has the microabsorption
    shape (absorbing phases suppressed, corundum inflated), the µR fence
    fires rather than the correction being trusted outside its regime, and
    the correction moves the two extreme phases toward the weighed values.
    Particle radii are order-of-magnitude estimates for the coarse fractions
    (no d50s are published with the dataset); the fence fires for any
    plausible choice — µR(magnetite) ≈ 0.06 already at R = 0.5 µm."""
    from pxrdref.optimize.qpa import BRINDLEY_MU_R_FENCE

    _require_data()
    phases = [corundum_phase(), magnetite_phase(), zircon_phase()]
    radii = {"corundum": 0.5, "magnetite": 5.0, "zircon": 1.5}
    for ph in phases:
        ph.particle_radius_um = radii[ph.name]
    _, result = _fit("cpd-4", phases, plan=qpa_plan())

    assert result.status == "converged"
    rows = {r.name: r for r in result.qpa.phases}
    err = {n: 100.0 * rows[n].weight_fraction - WEIGHED["cpd-4"][n] for n in rows}
    err_corr = {n: 100.0 * rows[n].weight_fraction_corrected - WEIGHED["cpd-4"][n]
                for n in rows}

    # the designed failure, in the microabsorption direction and far outside
    # the sample-1 band — this is what "characterise, don't tune away" means
    assert err["magnetite"] < -5.0
    assert err["zircon"] < -3.0
    assert err["corundum"] > 10.0
    assert abs(err["corundum"]) < 30.0            # regression ceiling only

    # the fence fires on the strongly absorbing coarse phases…
    fence = [d for d in result.diagnostics if d.code == "BRINDLEY_OUTSIDE_REGIME"]
    assert fence and "magnetite" in fence[0].where
    assert rows["magnetite"].mu_r > BRINDLEY_MU_R_FENCE
    # …and the correction still improves the two extreme phases (zircon it
    # does not — measured −9.2 → −9.4 wt %; that residual is the "beyond
    # Brindley" statement and is recorded, not asserted away)
    assert abs(err_corr["magnetite"]) < abs(err["magnetite"])
    assert abs(err_corr["corundum"]) < abs(err["corundum"])
    assert rows["magnetite"].brindley_tau < 1.0 < rows["corundum"].brindley_tau
