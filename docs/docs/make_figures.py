"""Regenerate the manual's committed figures (WP-1068).

    .venv/bin/python docs/docs/make_figures.py

They live in `figures/` beside this script, moved here from the old tree's
`using/figures/` by WP-1986.

The figures are **committed**, not built.  Two reasons: the sphinx build stays
seconds rather than minutes, and it stays offline and dependency-free — a docs
build should not have to refine a real pattern.  The cost is that a figure can
go stale, so this script is the one authority for how each was drawn, and
``tests/test_manual_api.py`` checks that every figure a page references
exists.

Each figure is written twice, ``-light`` and ``-dark``, and the pages select
between them with the ``only-light`` / ``only-dark`` classes the theme reads
(pydata-sphinx-theme).  A single
white-ground figure on a dark page is the thing this avoids.

**Every figure that shows a fit draws it from the case that is already
asserted somewhere**, never from a second copy of it: ``examples/nac_11bm.py``
for the two refinement panels and the geometry esds (a worked example has one
authority and it is ``examples/`` — root CLAUDE.md), and the fixtures of
``tests/test_data_support.py`` and ``tests/test_restraints.py`` for the two
figures whose whole content is a measured claim those files pin.  Importing
them is deliberate: a figure drawn from its own copy of a case can disagree
with the test that proves the claim, and nobody would find out.
"""

from __future__ import annotations

import functools
import re
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIGURES = Path(__file__).resolve().parent / "figures"
#: The site's colours (WP-2021), read for the light twin's ground.
TOKENS = REPO_ROOT / "docs" / "landing" / "src" / "tokens.css"
sys.path.insert(0, str(REPO_ROOT))

import rietx as rx  # noqa: E402  (needs the repo on sys.path)

STYLES = ("light", "dark")
#: Foreground for the hand-drawn figures, per style.  `plot_result` carries its
#: own palette; these are for the ones drawn here.
FG = {"light": "#222222", "dark": "#e6e6e6"}
LINES = {
    "light": ("#1f5fa8", "#c23b22", "#2a7f3f", "#8a5cc4"),
    "dark": ("#6fb1ff", "#ff8a72", "#6ede8a", "#c9a6ff"),
}
#: The exposure surface (yue-figure-style): the manual is read on a screen at
#: roughly 800 px of content width, so a figure is built at that width and its
#: type sized for it.  A 10-inch figure displayed at 7.4 has had its type
#: divided by 1.4, which is where the review's "text too small" came from.
WIDTH = 7.4
FONT = 10.5


def _rc(style: str):
    """Type at one size for every figure drawn here, in one sans face."""
    rc = {"font.size": FONT, "axes.labelsize": FONT, "axes.titlesize": FONT,
          "xtick.labelsize": FONT - 1, "ytick.labelsize": FONT - 1,
          "legend.fontsize": FONT - 1, "axes.spines.top": False,
          "axes.spines.right": False}
    return plt.style.context(([] if style == "light" else ["dark_background"])
                             + [rc])


@functools.cache
def light_ground() -> str:
    """The light page's colour, `--bg` in the token file's first (light) block.

    Comments go first, as `tests/test_landing.site_tokens` reads the file, so a
    word in the header cannot move where the light block ends."""
    text = re.sub(r"/\*.*?\*/", "", TOKENS.read_text(encoding="utf-8"), flags=re.S)
    return re.search(r"--bg:\s*(#[0-9a-fA-F]{6})", text.split("@media", 1)[0]).group(1)


def _save(fig, stem: str, style: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"{stem}-{style}.png"
    # 200 rather than the old 110: at 110 the type and the reflection marks
    # fringe on any retina display, which is where the manual is read.
    # The dark twin is saved on a transparent ground: the theme's dark page is
    # not black, so an opaque figure sits on the page as a rectangle.
    # The light twin stays opaque, because its type is dark and a transparent
    # PNG opened anywhere dark would be unreadable.  Its ground is the light
    # page's own colour rather than white (WP-2021), so on the page it shows no
    # edge: every white patch, the figure's, each panel's and each legend's,
    # takes it, which reaches `plot_result`'s figures without touching them.
    if style == "light":
        ground = light_ground()
        legends = [ax.get_legend() for ax in fig.axes] + list(fig.legends)
        for patch in [fig.patch, *(ax.patch for ax in fig.axes),
                      *(legend.get_frame() for legend in legends if legend)]:
            if tuple(patch.get_facecolor()[:3]) == (1.0, 1.0, 1.0):
                patch.set_facecolor(ground)
    fig.savefig(path, dpi=200, bbox_inches="tight", transparent=style == "dark")
    plt.close(fig)
    print(f"  {path.relative_to(REPO_ROOT)}")


def angular_signatures() -> None:
    """Why the correlated groups are correlated: their shapes in 2θ.

    Each curve is normalised to 1 at the mid-point of the range, because what
    decides separability is the *shape* over the measured range and not the
    scale — two curves that differ only by a factor are one parameter.
    """
    print("angular-signatures")
    two_theta = np.linspace(10.0, 120.0, 400)
    theta = np.radians(two_theta / 2.0)
    curves = [
        ("zero shift: constant", np.ones_like(theta)),
        ("displacement: cos θ", np.cos(theta)),
        ("cell: tan θ", np.tan(theta)),
        ("size: 1/cos θ", 1.0 / np.cos(theta)),
    ]
    # The narrow panel's claim, measured rather than asserted: over 20-40° each
    # of the four is a straight line to within this much, so four parameters
    # have a constant and a slope between them and the fit reports four numbers
    # it did not measure.  Deviation from the chord through the curve's own
    # ends, in the same normalised units the panel is drawn in.
    keep = (two_theta >= 20.0) & (two_theta <= 40.0)
    anchor = np.argmin(abs(two_theta - 30.0))
    spread = 0.0
    for _, y in curves:
        z = (y / y[anchor])[keep]
        line = np.interp(two_theta[keep], two_theta[keep][[0, -1]], z[[0, -1]])
        spread = max(spread, float(abs(z - line).max()))
    print(f"  over 20-40°, every shape is a straight line to {spread:.1%}")

    for style in STYLES:
        with _rc(style):
            fig, (wide, narrow) = plt.subplots(1, 2, figsize=(WIDTH, 3.0),
                                               sharey=True)
            for ax, lo, hi, title in (
                (wide, 10.0, 120.0, "over 110° of data the shapes separate"),
                (narrow, 20.0, 40.0, "over 20° they are one parameter"),
            ):
                window = (two_theta >= lo) & (two_theta <= hi)
                mid = np.argmin(abs(two_theta - 0.5 * (lo + hi)))
                for (label, y), colour in zip(curves, LINES[style], strict=True):
                    ax.plot(two_theta[window], (y / y[mid])[window], lw=1.6,
                            color=colour, label=label)
                ax.set_xlabel("2θ (deg)")
                ax.set_title(title, color=FG[style])
                ax.axhline(1.0, lw=0.5, ls=":", color=FG[style], alpha=0.5)
                ax.set_xlim(lo, hi)
            narrow.annotate(f"every shape here is a straight\nline to within {spread:.1%}",
                            xy=(0.5, 0.88), xycoords="axes fraction",
                            ha="center", va="top", color=FG[style])
            wide.set_ylabel("effect, normalised at mid-range")
            wide.set_ylim(0.0, 2.8)
            wide.legend(frameon=False, loc="upper left")
            fig.tight_layout()
            _save(fig, "angular-signatures", style)


def geometry_esds(data, ref) -> None:
    """What dropping the parameter correlations does to a distance's esd.

    Continues the walkthrough's session into `mccusker_structural`, the
    protocol WP-1072 measured the spread under (it quotes full/diagonal, 0.713
    to 1.152; this axis is the reciprocal), and the reason it has to be *this*
    plan is itself the point: under the walkthrough's own
    `mccusker_default` the only free parameter a cubic distance depends on is
    `a`, the quadratic form has one term, and full and diagonal agree exactly.
    Correlations between coordinates are what the guideline is about.

    Ratio rather than a scatter against the line of equality: the claim is that
    the diagonal-only number lands on *both* sides of the full one, and a ratio
    against 1 is where that is legible.  The esds themselves span a decade and
    would cluster the interesting part of a 1:1 plot into one corner.
    """
    print("geometry-esd")
    result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(2.0, 24.0))
    print(f"  mccusker_structural: Rwp {result.statistics.rwp:.5f}, "
          f"{len(result.geometry.distances)} distances")
    rows = [d for d in result.geometry.distances
            if d.stderr and d.stderr_diagonal]
    bonded = [(d.distance, d.stderr_diagonal / d.stderr) for d in rows if d.bonded]
    contacts = [(d.distance, d.stderr_diagonal / d.stderr) for d in rows if not d.bonded]
    print(f"  {len(rows)} distances with an esd; ratio "
          f"{min(r for _, r in bonded + contacts):.2f}-"
          f"{max(r for _, r in bonded + contacts):.2f}")

    for style in STYLES:
        with _rc(style):
            fig, ax = plt.subplots(figsize=(7.0, 3.4))
            hue = rx.viz.plots.PALETTES[style]
            ax.axhline(1.0, lw=0.8, ls=":", color=FG[style])
            for (points, colour, marker, label) in (
                (bonded, hue["obs"], "o", "bonds"),
                (contacts, hue["calc"], "^", "contacts"),
            ):
                if not points:
                    continue
                ax.plot([d for d, _ in points], [r for _, r in points], marker,
                        ms=4, mfc="none", color=colour, label=label)
            ax.set_xlabel("distance (Å)")
            ax.set_ylabel("esd, diagonal only ÷ full covariance")
            # A categorical scatter is the one case the house style keeps a
            # legend for; the marker shapes carry it in greyscale.
            ax.legend(fontsize=9, frameon=False, loc="lower right")
            fig.tight_layout()
            _save(fig, "geometry-esd", style)


def effective_observations() -> None:
    """The overlap the raw reflection count cannot see.

    The sweep is `tests/test_data_support.py`'s: one LaB6 pattern, Cu Kα,
    15-140°, widened with Lorentzian size broadening alone so the cell, the
    range and the reflection list stay put and M_ind is the only thing that can
    move.  Drawn at more points than the test asserts on, which is the whole
    difference between a figure and an assertion.
    """
    print("effective-observations")
    from rietx.optimize.statistics import count_unique_reflections
    from rietx.optimize.statistics import effective_observations as m_ind
    from tests.test_data_support import _compiled, _lab6

    tt = np.arange(15.0, 140.0, 0.01)
    widths = np.concatenate([np.arange(0.0, 2.0, 0.25), np.arange(2.0, 16.1, 1.0)])
    raw, eff = [], []
    for width in widths:
        structure, instrument = _lab6(radiation="CuKa")
        structure.phases[0].lor_size.value = float(width)
        model, values = _compiled(structure, instrument, tt)
        raw.append(count_unique_reflections(model, values))
        eff.append(m_ind(model, values))
    print(f"  {raw[0]} reflections throughout; {eff[0]:.1f} -> {eff[-1]:.1f} effective")

    for style in STYLES:
        with _rc(style):
            fig, ax = plt.subplots(figsize=(7.0, 3.4))
            hue = rx.viz.plots.PALETTES[style]
            ax.plot(widths, raw, "-", lw=1.6, color=hue["bkg"])
            ax.plot(widths, eff, "-", lw=1.6, color=hue["obs"])
            ax.set_xlabel("Lorentzian size broadening, lor_size (deg)")
            ax.set_ylabel("observations")
            ax.set_ylim(0.0, max(raw) * 1.15)
            for y, text, colour in ((raw[-1], "reflections measured", hue["bkg"]),
                                    (eff[-1], "effective observations", hue["obs"])):
                ax.annotate(text, xy=(widths[-1], y), xytext=(8, 0),
                            textcoords="offset points", fontsize=9, color=colour,
                            va="center", annotation_clip=False)
            ax.set_xlim(widths[0], widths[-1])
            fig.tight_layout()
            # right-margin labels: tight_layout measures axes, not annotations
            fig.subplots_adjust(right=0.70)
            _save(fig, "effective-observations", style)


def restraint_schedule() -> None:
    """Two converged fits of one pattern, and the difference curve's silence.

    `tests/test_restraints.py`'s under-determined P-1 case, run twice with c_w
    the only variable.  The panels share both axes because the point is that
    they look alike: what separates them is the bond length annotated on each,
    which no residual plot shows.
    """
    print("restraint-schedule")
    from tests.test_restraints import _sched_run, schedule_inputs

    pattern, bonds = schedule_inputs()
    runs = []
    for label, (first, second) in (("scheduled: c_w 300 then 1", (300.0, 1.0)),
                                   ("flat: c_w 1 throughout", (1.0, 1.0))):
        _, result = _sched_run(pattern, bonds, first, second)
        # row 0 is the Zr-O1 restraint, the bond that starts 1.9 A too long
        row = result.restraints.rows[0]
        worst = max(abs(r.deviation_over_sigma) for r in result.restraints.rows)
        runs.append((label, result, row.computed, worst))
        print(f"  {label}: Zr-O1 {row.computed:.3f} A (target {row.target:.3f}), "
              f"Rwp {result.statistics.rwp:.4f}, restraint {worst:.0f} sigma")

    for style in STYLES:
        with _rc(style):
            fig, axes = plt.subplots(2, 1, figsize=(7.0, 4.4), sharex=True, sharey=True)
            hue = rx.viz.plots.PALETTES[style]
            for ax, (label, result, distance, worst) in zip(axes, runs, strict=True):
                tt = np.asarray(result.two_theta)
                delta = ((np.asarray(result.y_obs) - np.asarray(result.y_calc))
                         / np.asarray(result.sigma))
                ax.axhspan(-3.0, 3.0, color=hue["band"], alpha=0.12, lw=0)
                ax.plot(tt, delta, "-", lw=0.8, color=hue["diff"])
                ax.annotate(f"{label}\nZr–O1 {distance:.2f} Å, "
                            f"restraint {worst:.0f}σ, Rwp {result.statistics.rwp:.4f}",
                            xy=(0.015, 0.95), xycoords="axes fraction", fontsize=9,
                            color=FG[style], va="top")
            axes[-1].set_xlabel("2θ (deg)")
            axes[0].set_ylim(-6.0, 9.0)
            fig.supylabel("Δ/σ", fontsize=10, color=FG[style])
            fig.tight_layout()
            _save(fig, "restraint-schedule", style)


def _su(value: float, esd: float | None) -> str:
    """One authority for esd notation in this file (issue #166).

    ``rx.format_su``'s last-place digits when the su is **below 1** —
    ``14.37(17)``, the crystallographic convention every neighbour in the manual
    uses — and decimal-in-parentheses at or above 1, where last-place digits
    stop being readable and the manual's wide-esd prose already writes
    ``14.50(1.46)``.
    """
    if esd is None or not (esd > 0.0):
        return f"{value:.2f}"
    if esd < 1.0:
        return rx.format_su(value, esd)
    return f"{value:.2f}({esd:.2f})"


def hump() -> None:
    """A localised background feature, described two ways.

    Drawn from ``tests/test_extra_components.py``'s synthetic hump case, which
    is where the claim is asserted — the same rule the two refinement panels
    follow, and for the same reason: a figure with its own copy of a case can
    disagree with the test that proves the claim.

    Why synthetic rather than the manual's real worked example (11-BM Si SRM
    640c in a Kapton capillary, ``tests/data/11BM_Si640c.xy``): two reasons, and
    the first is the one that matters.  Only a synthetic hump has a **known**
    position and width, so only here can the figure say how close the three
    refined parameters came — on the real pattern the halo's position is itself
    an envelope reading, and a figure drawing an arrow from a fit to another
    estimate would be claiming a truth it does not have.  Second, that fit is
    four minutes over 47 999 channels, and this script's own bargain (see the
    module docstring) is that regenerating a figure stays cheap.  The real
    measurement is a **table**, in ``docs/docs/concepts/parameters.md`` § Humps, where a
    number can carry its own provenance.

    esd notation follows the decision on issue #166: ``rx.format_su``'s
    last-place digits below su = 1, decimal-in-parentheses at or above, where
    last-place digits stop being readable.  It lives in ``_su`` below so the
    crossover has one home rather than one per figure.
    """
    # explicit rather than through ``rx.viz``: this runs *before* the figure
    # that calls ``result.plot`` and imports the subpackage as a side effect
    from rietx.viz.plots import PALETTES
    from tests.test_extra_components import HUMP_TRUTH, fit_hump_case

    print("running the synthetic hump case …")
    flat, _truth = fit_hump_case(with_peak=False)
    peaked, truth = fit_hump_case(with_peak=True)
    got = {row.path.rsplit(".", 1)[1]: row for row in peaked.parameters
           if "extra_components" in row.path}

    print("background-peak")
    for style in STYLES:
        hue = PALETTES[style]
        colours = LINES[style]
        with _rc(style):
            fig, axes = plt.subplots(2, 1, figsize=(WIDTH, 4.6), sharex=True,
                                     gridspec_kw={"height_ratios": [2, 3]})
            tt = np.asarray(peaked.two_theta)
            keep = tt <= 40.0
            flat_bkg = np.asarray(flat.y_background)
            peak_bkg = np.asarray(peaked.y_background)
            axes[0].plot(tt[keep], flat_bkg[keep], "-", lw=1.4,
                         color=colours[0], label="polynomial alone")
            axes[0].plot(tt[keep], peak_bkg[keep], "-", lw=1.4,
                         color=colours[1], label="polynomial + one peak")
            axes[0].set_ylabel("background\n(counts)")
            axes[0].legend(frameon=False, loc="upper right")

            # what the term added, against the feature the data actually holds
            axes[1].plot(tt[keep],
                         (np.asarray(flat.y_obs) - flat_bkg)[keep],
                         "-", lw=0.7, color=hue["obs"],
                         label="observed − the peak-free background")
            axes[1].plot(tt[keep], (peak_bkg - flat_bkg)[keep], "-", lw=1.8,
                         color=colours[1], label="the fitted peak")
            axes[1].axhline(0.0, lw=0.6, color=FG[style])
            axes[1].set_ylim(-160, 260)
            axes[1].set_ylabel("counts")
            axes[1].set_xlabel("2θ (deg)")
            axes[1].set_xlim(float(tt.min()), 40.0)
            axes[1].legend(frameon=False, loc="upper right")
            axes[1].annotate(
                f"2θ₀ {_su(got['position'].value, got['position'].stderr)}°"
                f"  vs {truth['position']:.1f}° true\n"
                f"Γ {_su(got['fwhm'].value, got['fwhm'].stderr)}°"
                f"  vs {HUMP_TRUTH['fwhm']:.1f}° true",
                xy=(0.02, 0.95), xycoords="axes fraction", ha="left",
                va="top", color=FG[style])
            fig.tight_layout()
            _save(fig, "background-peak", style)


def refinement_figures():
    """The 11-BM NAC fit: the first refinement's panel, and the impurity peak.

    Returns the Rietveld result, which `geometry_esds` draws from — one
    refinement, three figures.

    `plot_for_vlm`'s montage is deliberately *not* here.  It is drawn for a
    vision model — high contrast, annotated redundancy, one fixed ground — so
    it has no dark twin and is the wrong figure for a human page.
    """
    print("running examples/nac_11bm.py …")
    sys.path.insert(0, str(REPO_ROOT / "examples"))
    from nac_11bm import WAVELENGTH, run

    data, ref, lebail, result = run()

    print("nac-fit / impurity-peak")
    for style in STYLES:
        # The whole fitted range, not the 2-12° window the figure carried
        # before: a window that stops at the strong low-angle peaks reads as a
        # simulation.  What says "real data" is the weak high-angle half, where
        # the counting statistics show and the difference curve has structure.
        fig = result.plot(style=style, wavelength=WAVELENGTH)
        _save(fig, "nac-fit", style)

        # The CaF2 111 line at 7.52 deg: the Le Bail model does not contain the
        # impurity, so the report flags an unmatched observed peak there.  This
        # is the concrete version of "Le Bail first" in the first refinement.
        hue = rx.viz.plots.PALETTES[style]
        with _rc(style):
            fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.8), sharey=True,
                                     sharex=True)
            for ax, res, name in zip(axes, (lebail, result),
                                     ("Le Bail: CaF₂ not in the model",
                                      "Rietveld: CaF₂ added"), strict=True):
                tt = np.asarray(res.two_theta)
                keep = (tt >= 7.27) & (tt <= 7.70)
                ax.plot(tt[keep], np.asarray(res.y_obs)[keep] / 1e5, ".", ms=3.5,
                        color=hue["obs"])
                ax.plot(tt[keep], np.asarray(res.y_calc)[keep] / 1e5, "-", lw=1.2,
                        color=hue["calc"])
                ax.set_xlabel("2θ (deg)")
                ax.set_title(name, color=FG[style])
            # Two series, so they are labelled directly rather than boxed, in
            # the corner of the panel where neither curve goes.
            for text, colour, dy in (("observed", hue["obs"], 0.0),
                                     ("calculated", hue["calc"], 0.10)):
                axes[1].annotate(text, xy=(0.97, 0.95 - dy), xycoords="axes fraction",
                                 ha="right", va="top", color=colour)
            axes[0].annotate("observed intensity\nthe model cannot place",
                             xy=(7.525, 0.16), xytext=(7.56, 0.62),
                             color=FG[style], va="center",
                             arrowprops={"arrowstyle": "->", "color": FG[style],
                                         "shrinkB": 6})
            axes[0].set_ylabel("intensity (10⁵ arb. units)")
            axes[0].set_xlim(7.27, 7.70)
            fig.tight_layout()
            _save(fig, "impurity-peak", style)
    return data, ref


def pattern_figure(data) -> None:
    """The NAC pattern as read, before any model: `plot_pattern` (WP-1444).

    The same `data` the fit figures are drawn from, so it is the first refinement's
    panel with the model taken out and the two can be read as a pair.  No
    title: in the manual the caption is the title, as for every other figure.
    """
    from nac_11bm import WAVELENGTH

    print("nac-pattern")
    for style in STYLES:
        _save(data.plot(style=style, wavelength=WAVELENGTH), "nac-pattern", style)


if __name__ == "__main__":
    angular_signatures()
    hump()
    data, ref = refinement_figures()
    pattern_figure(data)
    geometry_esds(data, ref)
    effective_observations()
    restraint_schedule()
