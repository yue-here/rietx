"""v1.3 cross-engine acceptance: the two PowderLine recipes (WP-1306).

Every other acceptance suite in this directory has **one** reference.  This one
has two, GSAS-II and TOPAS, both committed by upstream for the same specimens —
and that turns out to be the whole point of it, because on the two-phase
DRX_33 cathode **the two references disagree by 2 665 ppm on the cubic cell**.
No answer can be within the ±300 ppm the FAP suite uses of both, so the bar
here is the *envelope* the two engines span, widened by that same ±300 ppm at
each end.  It still fails on a translation error, which is what it is for; it
does not assert an agreement neither reference achieves.

The disagreement is upstream's own and it is documented there: GSAS-II reports
two soft (SVD) Hessian singularities on this recipe and a 100 % correlation
between each phase's ``Mustrain;mx`` and ``Mustrain;i``, then returns a
**negative** crystallite size for the monoclinic phase, while TOPAS returns
5×10⁸ µm — no size broadening at all.  ``tests/data/README.md`` § v1.3 has the
full table.  What this suite measures is where this package lands in that
argument, and the answer is close to TOPAS: **10-96 ppm on all five free cell
parameters**, at Rwp 7.322 % against TOPAS's 7.326 %, while sitting the same
365-2 570 ppm from GSAS-II that TOPAS does.

LaB6 is the other kind of fixture — an instrument-profile calibration with the
SRM cell **held**, so there is no cell to compare and the check is the profile
itself: this fit's drawn peak widths against the widths GSAS-II's own
``y_calc`` shows, reflection by reflection.  Three model differences are stated
rather than fitted around, and together they are why the Rwp is 8.80 % against
GSAS-II's 6.53 % (and beside TOPAS's 8.52 %):

1. GSAS-II's ``Z``, a constant Lorentzian term, has no counterpart here.
2. Its refined ``Y`` is **negative** (−15.81 centideg; TOPAS's is −8.97), and
   this package's Lorentzian coefficients are softplus-bounded because a width
   is not a shape when it is negative.  With Y negative GSAS-II's total gamma
   goes negative above ~6.5 °2θ and is clamped at its 0.001 centideg floor, so
   **26 of its 49 reflections carry no Lorentzian at all** — a shape a monotone
   width cannot make (measured in ``test_recipe.py``).
3. The recipe leaves the size/strain magnitudes null, which GSAS-II fills with
   its own project defaults of 1 µm and 1000 microstrain — 0.057°·tanθ, a
   quarter of the peak width at the top of the range.  Another engine's project
   default is not adopted here; it is reported (``RECIPE_ENGINE_DEFAULT_DECLINED``).

Given all three, the widths agreeing to a **median 0.5 %** (1.2 % on 1.9.0) is the result, and
it is what this suite asserts.
"""

import csv
import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.recipe import read_recipe, write_recipe_tables
from rietx.strategy.staged import CLOSING_WINDOW_TOL, INTERMEDIATE_FTOL

DATA = Path(__file__).parent / "data" / "powderline"
pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("powderline")]

#: ±300 ppm, the FAP suite's cross-code consistency band, applied to each end
#: of the two reference engines' own span rather than to one of them.
ENVELOPE_PPM = 300.0


def _cell_report(path: Path) -> dict[str, float]:
    return {r[0]: float(r[1])
            for r in csv.reader(path.read_text(encoding="utf-8").splitlines()[1:]) if r}


def _gsas_rwp(path: Path) -> float:
    for line in path.read_text(encoding="utf-8").splitlines():
        if "Final refinement wR" in line:
            return float(line.split("wR =")[1].split("%")[0]) / 100.0
    raise AssertionError(f"no wR line in {path}")


def _topas_rwp(path: Path) -> float:
    for row in csv.reader(path.read_text(encoding="utf-8").splitlines()):
        if row and row[0] == "r_wp":
            return float(row[1]) / 100.0
    raise AssertionError(f"no r_wp row in {path}")


def _fit(name: str):
    recipe = read_recipe(DATA / name / "input.json")

    # **Anomalous scattering is declined, and `read_recipe` declined it** —
    # asserted here rather than inherited, because a suite whose numbers move
    # when a default moves is not pinning a protocol.  λ = 0.1665 Å is 74.5 keV,
    # outside the bundled Cromer-Liberman table's 3-70 keV band, and every edge
    # of every species in these recipes is more than an order of magnitude
    # below it — so f = f₀ is the correct limit rather than a concession, and
    # extrapolating the table is what would be wrong.  The reader says so with
    # `RECIPE_DISPERSION_DECLINED`; setting it again makes the declaration
    # local to the numbers below.
    assert recipe.instrument.source.dispersion is None
    recipe.instrument.source.dispersion = None

    # **`intermediate_ftol` stays at the shipped value**, so these figures are
    # what a caller's own `read_recipe` → `fit` produces rather than a
    # converge-everything variant nothing ships.  The plan is this package's
    # route to the recipe's single free set (§ the module docstring), and its
    # last stage takes the solver default either way — so the schedule can only
    # affect how the intermediate stages hand over, which is exactly the thing
    # a user would meet.
    assert recipe.plan.intermediate_ftol == INTERMEDIATE_FTOL
    # and the shipped closing stage, for the same reason (WP-2002)
    assert recipe.plan.closing_window_tol == CLOSING_WINDOW_TOL

    ref = rx.Refinement(recipe.structure, recipe.instrument, history=False)
    result = ref.fit(recipe.pattern, plan=recipe.plan,
                     two_theta_limits=recipe.limits)
    return recipe, ref, result


def _plot(result, stem: str) -> None:
    """Fit plot for visual inspection (tests/output/, gitignored)."""
    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / f"{stem}.png"))


@pytest.fixture(scope="module")
def lab6():
    return _fit("example_LaB6")


@pytest.fixture(scope="module")
def drx():
    return _fit("example_DRX_33")


# --- DRX_33: two phases, two references, one envelope -----------------------


def test_drx_cells_land_inside_the_two_engines_envelope(drx):
    _, ref, result = drx
    _plot(result, "powderline_drx33_fit")
    assert result.status == "converged"

    for name in ("DRX_33", "Li4MgWO6_SG12"):
        g = _cell_report(DATA / "example_DRX_33" /
                         f"output/{name}_unit_cell_report.csv")
        t = _cell_report(DATA / "example_DRX_33" /
                         f"output/topas/{name}_unit_cell_report.csv")
        phase = next(p for p in ref.fitted_structure.phases if p.name == name)
        mine = dict(zip(("cell_a", "cell_b", "cell_c",
                         "cell_alpha", "cell_beta", "cell_gamma"),
                        phase.cell.lengths_angles()))
        for key, value in mine.items():
            lo, hi = sorted((g[key], t[key]))
            slack = ENVELOPE_PPM * 1e-6 * max(abs(lo), abs(hi))
            assert lo - slack <= value <= hi + slack, (
                f"{name}.{key}: {value} outside [{lo}, {hi}] ±{slack:.2g} "
                f"(GSAS-II {g[key]}, TOPAS {t[key]})")


def test_drx_agrees_with_topas_far_more_closely_than_the_engines_agree(drx):
    """The finding, not just the gate: this package is on TOPAS's side of it."""
    _, ref, _ = drx
    worst_to_topas = 0.0
    worst_engine_gap = 0.0
    for name in ("DRX_33", "Li4MgWO6_SG12"):
        g = _cell_report(DATA / "example_DRX_33" /
                         f"output/{name}_unit_cell_report.csv")
        t = _cell_report(DATA / "example_DRX_33" /
                         f"output/topas/{name}_unit_cell_report.csv")
        phase = next(p for p in ref.fitted_structure.phases if p.name == name)
        mine = dict(zip(("cell_a", "cell_b", "cell_c",
                         "cell_alpha", "cell_beta", "cell_gamma"),
                        phase.cell.lengths_angles()))
        for key, value in mine.items():
            if not getattr(phase.cell, key.split("_")[1]).vary:
                continue
            worst_to_topas = max(worst_to_topas,
                                 abs(1e6 * (value - t[key]) / t[key]))
            worst_engine_gap = max(worst_engine_gap,
                                   abs(1e6 * (t[key] - g[key]) / g[key]))
    assert worst_to_topas < 200.0        # measured 96 ppm (98 on 1.9.0)
    assert worst_engine_gap > 1000.0     # measured 2 668 ppm
    assert worst_to_topas < worst_engine_gap / 10.0


def test_drx_rwp_is_reported_beside_both_engines_and_gated_at_neither(drx):
    _, _, result = drx
    gsas = _gsas_rwp(DATA / "example_DRX_33" / "output/dummy.lst")
    topas = _topas_rwp(DATA / "example_DRX_33" /
                       "output/topas/example_DRX_33_results.csv")
    assert gsas == pytest.approx(0.1083, abs=5e-5)
    assert topas == pytest.approx(0.07326, abs=5e-5)
    # Not a gate on either reference: an Rwp comparison is never this
    # package's evidence (root CLAUDE.md).  What is asserted is that this fit
    # is a fit — below the Rexp-scaled sanity ceiling — and the two reference
    # numbers are read from their own files so the record cannot go stale.
    assert result.statistics.rwp < 0.15
    assert result.statistics.rwp == pytest.approx(topas, abs=0.01)


def test_drx_phase_scales_are_the_same_answer_as_topas(drx):
    """The scale carries each code's own normalisation, so the *ratio* is the
    comparable quantity — and it is what the recipe is for (their DESCRIPTION:
    "quantify the relative phase fractions from the refined scale factors")."""
    _, ref, _ = drx
    topas = {}
    for row in csv.DictReader(
            (DATA / "example_DRX_33" /
             "output/topas/refined_parameters.csv").read_text(encoding="utf-8").splitlines()):
        if row["category"] == "scale":
            topas[row["phase_name"]] = float(row["value"])
    mine = {p.name: p.scale.value for p in ref.fitted_structure.phases}
    their_ratio = topas["DRX_33"] / topas["Li4MgWO6_SG12"]
    my_ratio = mine["DRX_33"] / mine["Li4MgWO6_SG12"]
    assert my_ratio == pytest.approx(their_ratio, rel=0.20)


# --- LaB6: the cell is held, so the check is the drawn profile --------------


def test_lab6_cell_is_held_exactly_where_the_recipe_put_it(lab6):
    _, ref, result = lab6
    _plot(result, "powderline_lab6_fit")
    (phase,) = ref.fitted_structure.phases
    for engine in ("output", "output/topas"):
        theirs = _cell_report(DATA / "example_LaB6" / engine /
                              "LaB6_unit_cell_report.csv")
        assert phase.cell.a.value == pytest.approx(theirs["cell_a"], abs=1e-9)


def test_lab6_drawn_peak_widths_match_the_reference_profile(lab6):
    """This fit's y_calc against GSAS-II's own y_calc, width by width.

    The comparison the WP asks for, made on what each code **drew** rather than
    on coefficients that do not mean the same thing: GSAS-II's U V W X Y Z sit
    beside a Z term and a clamped negative Y this package has not got, so its
    numbers and this one's are not commensurable, while the FWHM of a peak in
    the calculated pattern is.

    Bar: 5 % on every reflection.  Measured median 0.5 %, worst 1.0 % (1.2 %
    and 2.3 % on 1.9.0), over the
    first ten reflections — the range where both models are unambiguous, before
    GSAS-II's gamma reaches its floor.
    """
    recipe, _, result = lab6
    rows = [ln.split() for ln in
            (DATA / "example_LaB6" /
             "output/fit_profile.txt").read_text(encoding="utf-8").splitlines()[1:]]
    a = np.asarray([[float(v) for v in r] for r in rows])
    their_tth, their_peak = a[:, 0], a[:, 3] - a[:, 5]
    my_tth = np.asarray(result.two_theta)
    my_peak = np.asarray(result.y_calc) - np.asarray(result.y_background)

    ratios = []
    for centre in sorted(result.ticks["LaB6"])[:10]:
        mine = _fwhm(my_tth, my_peak, centre)
        theirs = _fwhm(their_tth, their_peak, centre)
        if mine is None or theirs is None:
            continue
        ratios.append(mine / theirs)
    assert len(ratios) >= 8
    assert max(abs(r - 1.0) for r in ratios) < 0.05
    assert abs(float(np.median(ratios)) - 1.0) < 0.02


def _fwhm(x, y, centre, half_window=0.10):
    m = (x > centre - half_window) & (x < centre + half_window)
    xs, ys = x[m], y[m]
    if xs.size < 5 or ys.max() <= 0:
        return None
    i = int(np.argmax(ys))
    half = ys[i] / 2.0
    j = i
    while j > 0 and ys[j] > half:
        j -= 1
    lo = np.interp(half, [ys[j], ys[j + 1]], [xs[j], xs[j + 1]])
    k = i
    while k < ys.size - 1 and ys[k] > half:
        k += 1
    hi = np.interp(half, [ys[k], ys[k - 1]], [xs[k], xs[k - 1]])
    return hi - lo


def test_lab6_rwp_is_reported_beside_both_engines(lab6):
    _, _, result = lab6
    gsas = _gsas_rwp(DATA / "example_LaB6" / "output/dummy.lst")
    topas = _topas_rwp(DATA / "example_LaB6" /
                       "output/topas/example_LaB6_results.csv")
    assert gsas == pytest.approx(0.0653, abs=5e-5)
    assert topas == pytest.approx(0.08519, abs=5e-5)
    assert result.statistics.rwp < 0.12
    # beside TOPAS, which shares neither Z nor a negative-Y clamp with GSAS-II
    assert result.statistics.rwp == pytest.approx(topas, abs=0.01)


def test_lab6_declares_the_three_model_differences_it_has(lab6):
    """Each of the three is *said*, not silently absorbed."""
    recipe, _, _ = lab6
    codes = {d.code for d in recipe.diagnostics}
    assert "RECIPE_FLAG_DROPPED" in codes            # Z, and the peak's gamma
    assert "RECIPE_ENGINE_DEFAULT_DECLINED" in codes  # 1 um / 1000 microstrain
    assert "RECIPE_BACKGROUND_PEAK_DEGENERATE" in codes


def test_lab6_hump_is_the_degenerate_direction_both_engines_found(
        lab6):
    """The reader warned; the fit confirms, and both references agree it is bad.

    GSAS-II's peak ran to 8.77e10 °2θ with esd 0 — off the pattern entirely —
    and TOPAS's sits at 1.63° with an esd 188× its own value.  Here it
    correlates with the low-order background at |ρ| = 1 and the last stage
    freeing it spends its budget, which is the same statement in this package's
    vocabulary.  That is the closing stage since WP-2002: the declared
    ``extra_components`` stage stops at the intermediate tolerance first.
    """
    _, _, result = lab6
    pairs = {frozenset(d.where) for d in result.diagnostics
             if d.code == "HIGH_CORRELATION"}
    hump_pairs = [p for p in pairs
                             if any("extra_components" in w for w in p)]
    assert hump_pairs
    last = next(s for s in reversed(result.stages)
                if any("extra_components" in p for p in s.freed))
    assert last.status == "max_iter", (last.name, last.status)

    gsas = {r["descriptive_name"]: (float(r["value"]), float(r["esd"]))
            for r in csv.DictReader(
                (DATA / "example_LaB6" /
                 "output/refined_parameters.csv").read_text(encoding="utf-8").splitlines())}
    position, esd = gsas["background_peak_0_position"]
    assert position > 1e9 and esd == 0.0     # walked off, and unmeasured


# --- the round trip ---------------------------------------------------------


def test_the_written_tables_reproduce_the_answer_they_came_from(drx, tmp_path):
    recipe, ref, result = drx
    paths = write_recipe_tables(ref, tmp_path, phase_names=dict(zip(
        [p.name for p in ref.fitted_structure.phases], recipe.phase_names)))
    cells = _cell_report(paths["unit_cell:Li4MgWO6_SG12"])
    mono = next(p for p in ref.fitted_structure.phases
                if p.name == "Li4MgWO6_SG12")
    assert cells["cell_beta"] == pytest.approx(mono.cell.beta.value, rel=1e-8)
    profile = np.asarray(
        [[float(v) for v in ln.split("\t")]
         for ln in paths["fit_profile"].read_text(encoding="utf-8").splitlines()[1:]])
    assert profile.shape[0] == len(result.two_theta)
    rwp = math.sqrt(
        np.sum(profile[:, 2] * (profile[:, 1] - profile[:, 3]) ** 2)
        / np.sum(profile[:, 2] * profile[:, 1] ** 2))
    assert rwp == pytest.approx(result.statistics.rwp, rel=1e-6)
