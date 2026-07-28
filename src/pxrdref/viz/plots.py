"""Static obs/calc/difference plotting (matplotlib/Agg).

This renderer produces the standard Rietveld panel: observed points,
calculated line, difference curve offset below, and per-phase reflection tick
rows.  The interactive plotly viewer is :mod:`pxrdref.viz.html`; the
VLM-readable montage is :func:`plot_for_vlm` here.
"""

from __future__ import annotations

import numpy as np

from ..schemas.results import RefinementResult


def plot_result(result: RefinementResult, *, path: str | None = None,
                two_theta_range: tuple[float, float] | None = None,
                show_background: bool = True, dpi: int = 150):
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError("plotting needs matplotlib: pip install 'pxrd-refine[viz]'") from exc

    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    y_bkg = np.asarray(result.y_background)
    diff = y_obs - y_calc

    fig, ax = plt.subplots(figsize=(10, 6), dpi=dpi)
    ax.plot(tt, y_obs, ".", ms=2.5, color="#1f5fa8", label="observed", zorder=2)
    ax.plot(tt, y_calc, "-", lw=1.0, color="#c23b22", label="calculated", zorder=3)
    if show_background and np.any(y_bkg):
        ax.plot(tt, y_bkg, "--", lw=0.8, color="#7a7a7a", label="background", zorder=1)

    span = float(y_obs.max() - min(y_obs.min(), 0.0))
    offset = -0.12 * span
    ax.plot(tt, diff + offset, "-", lw=0.7, color="#4a4a4a", label="difference", zorder=2)
    ax.axhline(offset, lw=0.4, color="#bbbbbb", zorder=1)

    tick_base = offset - 0.08 * span
    for row, (name, positions) in enumerate(result.ticks.items()):
        yline = tick_base - row * 0.05 * span
        pos = np.asarray(positions)
        if two_theta_range is not None:
            pos = pos[(pos >= two_theta_range[0]) & (pos <= two_theta_range[1])]
        ax.vlines(pos, yline - 0.015 * span, yline + 0.015 * span,
                  lw=0.6, color=f"C{row + 2}", label=f"hkl: {name}")

    if two_theta_range is not None:
        ax.set_xlim(*two_theta_range)
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_ylabel("intensity")
    s = result.statistics
    ax.set_title(f"{result.mode}  Rwp={s.rwp:.4f}  GoF={s.gof:.2f}")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    fig.tight_layout()
    if path is not None:
        fig.savefig(path)
    return fig


def plot_for_vlm(result: RefinementResult, report=None, *,
                 path: str, n_regions: int = 4, dpi: int = 140):
    """Annotated multi-panel montage rendered for what VLMs *can* read.

    VLM benchmarks (CharXiv, ChartMuseum) show frontier models fail precise
    value extraction from dense single-panel plots, so this montage trades
    density for annotated redundancy: a full-pattern overview, a Δ/σ panel
    (model error in noise units — flat ±3 band means done), and the worst-N
    misfit regions auto-zoomed from the FitReport, each titled with its exact
    numbers so the model reads text, not pixels.  Unmatched observed peaks
    are marked explicitly.

    PNG only, high contrast — JPEG's block artifacts shred one-pixel peak
    outlines and difference curves, which is precisely the evidence a VLM is
    asked to judge.
    """
    if not str(path).lower().endswith(".png"):
        raise ValueError("plot_for_vlm writes PNG only (JPEG artifacts destroy "
                         "thin peak/difference lines); pass a .png path")
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError("plotting needs matplotlib: pip install 'pxrd-refine[viz]'") from exc

    if report is None:
        from ..report import build_layer0
        report = build_layer0(result)

    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    sigma = (np.asarray(result.sigma) if result.sigma
             else np.sqrt(np.maximum(y_obs, 1.0)))
    delta = y_obs - y_calc

    regions = sorted(report.regions, key=lambda r: -r.chi2_share)[:n_regions]
    n_cols = max(len(regions), 1)
    fig = plt.figure(figsize=(3.2 * max(n_cols, 3), 8.5), dpi=dpi)
    gs = fig.add_gridspec(3, n_cols, height_ratios=[2.2, 1.0, 1.6], hspace=0.45)

    # -- panel 1: full pattern
    ax = fig.add_subplot(gs[0, :])
    ax.plot(tt, y_obs, ".", ms=1.6, color="#1f5fa8", label="observed")
    ax.plot(tt, y_calc, "-", lw=0.9, color="#c23b22", label="calculated")
    for i, region in enumerate(regions):
        ax.axvspan(region.two_theta_lo, region.two_theta_hi, color="#f2c14e",
                   alpha=0.45, lw=0)
        ax.annotate(f"R{i + 1}", ((region.two_theta_lo + region.two_theta_hi) / 2,
                                  ax.get_ylim()[1] * 0.95),
                    ha="center", fontsize=9, fontweight="bold", color="#8a6d00")
    for u in report.unmatched:
        if u.kind == "unmatched_obs":
            ax.axvline(u.two_theta, color="#7a1fa8", lw=0.8, ls=":", alpha=0.8)
    s = result.statistics
    ax.set_title(f"{result.mode}: Rwp={s.rwp:.4f}, GoF={s.gof:.2f}; "
                 f"shaded = worst regions, dotted = unmatched observed peaks",
                 fontsize=10)
    ax.set_ylabel("intensity")
    ax.legend(loc="upper right", fontsize=8, frameon=False)

    # -- panel 2: Δ/σ across the pattern
    ax = fig.add_subplot(gs[1, :])
    ax.plot(tt, delta / sigma, "-", lw=0.5, color="#333333")
    ax.axhspan(-3, 3, color="#2a9d2a", alpha=0.15, lw=0)
    ax.set_ylabel(r"$\Delta/\sigma$")
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_title(r"model error in noise units (green band = ±3$\sigma$; "
                 "a correct model stays inside)", fontsize=9)

    # -- panels 3..: worst regions zoomed
    for i, region in enumerate(regions):
        axr = fig.add_subplot(gs[2, i])
        pad = 0.1 * (region.two_theta_hi - region.two_theta_lo)
        lo, hi = region.two_theta_lo - pad, region.two_theta_hi + pad
        m = (tt >= lo) & (tt <= hi)
        axr.plot(tt[m], y_obs[m], ".", ms=2.5, color="#1f5fa8")
        axr.plot(tt[m], y_calc[m], "-", lw=1.1, color="#c23b22")
        span = float(y_obs[m].max() - y_obs[m].min()) if np.any(m) else 1.0
        axr.plot(tt[m], delta[m] - 0.15 * span, "-", lw=0.8, color="#4a4a4a")
        axr.set_title(f"R{i + 1}: {region.two_theta_lo:.2f}-"
                      f"{region.two_theta_hi:.2f}°\n"
                      f"local Rwp={region.local_rwp:.3f}, "
                      f"{region.chi2_share:.0%} of χ², "
                      f"max|Δ/σ|={region.max_abs_delta_over_sigma:.0f}",
                      fontsize=8)
        axr.tick_params(labelsize=7)

    fig.savefig(path, format="png")
    return fig
