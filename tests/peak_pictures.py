"""obs/calc/diff pictures of what ``pick_peaks`` fitted, for the picker's tests.

``tests/CLAUDE.md``'s standing rule asks every test refinement for obs/calc/diff
PNGs in ``tests/output/``, and the picker's own suites (``test_peak_fdr.py``,
``test_peak_resolvability.py``, ``test_peak_bounds.py``) drew none: WP-1968's
last open task.  A flag (``weak_line``, ``unresolved_split``, ``width_capped``,
``position_at_bound``) is a judgement about a component the picture can show,
so each flag gets its own tick row under the true lines.

The *calc* is the picker's own fit, never a refit: each group's fitted profile
(:func:`rietx.indexing.peakfit.group_profile`, the peak editor's drawing call)
over the frozen envelope, so the picture cannot disagree with the list.  The
*diff* is (obs − calc)/σ, the weighting the groups were fitted under; outside
every group window the calc is the envelope alone.
"""

from __future__ import annotations

import pathlib

import numpy as np

OUTPUT = pathlib.Path(__file__).parent / "output"

#: the flags drawn as their own tick rows, in this order; any other flag a
#: component carries joins the "other flags" row
FLAG_ROWS = ("weak_line", "unresolved_split", "width_capped", "position_at_bound")


def draw_pick(stem: str, data, instrument, peaks, det, fits, *, truth=None,
              title: str = "", zoom: tuple[float, float] | None = None) -> pathlib.Path:
    """Write ``tests/output/peaks_<stem>.png`` and return its path.

    ``peaks, det, fits`` are :func:`rietx.indexing.pick.pick_peaks_with_state`'s
    answer; ``truth`` the true line positions, when the test knows them.
    ``zoom`` restricts the drawn range (the fit is evaluated whole either way).
    """
    from rietx.indexing.peakfit import group_profile
    from rietx.viz.plots import _pyplot

    plt = _pyplot()
    tt, y, sig, env = det.two_theta, det.intensity, det.sigma, det.envelope
    calc = np.array(env, dtype=np.float64, copy=True)
    for group, fit in zip(det.groups, fits):
        calc[group.i0:group.i1] = env[group.i0:group.i1] + group_profile(
            det, group, instrument, fit)
    keep = np.ones(len(tt), dtype=bool) if zoom is None else (
        (tt >= zoom[0]) & (tt <= zoom[1]))

    rows: list[tuple[str, np.ndarray]] = []
    if truth is not None:
        rows.append(("true lines", np.asarray(truth, dtype=np.float64)))
    clean = [p.two_theta for p in peaks.usable()
             if not set(p.flags) & set(FLAG_ROWS)]
    rows.append((f"usable, unflagged ({len(clean)})", np.array(clean)))
    for flag in FLAG_ROWS:
        at = [p.two_theta for p in peaks.peaks if flag in p.flags]
        if at:
            rows.append((f"{flag} ({len(at)})", np.array(at)))
    other = [p.two_theta for p in peaks.peaks
             if set(p.flags) - set(FLAG_ROWS) - {"sigma_assumed"}
             and not set(p.flags) & set(FLAG_ROWS)]
    if other:
        rows.append((f"other flags ({len(other)})", np.array(other)))

    fig, (ax, axd, axt) = plt.subplots(
        3, 1, sharex=True, figsize=(11, 6.5),
        gridspec_kw={"height_ratios": [4, 1.3, 0.35 * len(rows) + 0.4]})
    ax.plot(tt[keep], y[keep], ".", ms=1.6, color="0.15", label="observed")
    ax.plot(tt[keep], calc[keep], "-", lw=0.8, color="tab:orange",
            label="picker's fit")
    ax.plot(tt[keep], env[keep], "--", lw=0.7, color="tab:brown",
            label="envelope")
    ax.set_yscale("log")
    ax.set_ylabel("counts")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ax.set_title(title or stem, fontsize=9)
    axd.plot(tt[keep], ((y - calc) / sig)[keep], "-", lw=0.5, color="0.4")
    axd.axhline(0.0, lw=0.5, color="0.7")
    axd.set_ylabel("(obs − calc)/σ", fontsize=8)
    lo, hi = (tt[keep].min(), tt[keep].max())
    for i, (label, pos) in enumerate(rows):
        pos = pos[(pos >= lo) & (pos <= hi)]
        axt.vlines(pos, i + 0.1, i + 0.9, lw=0.9,
                   color="0.2" if i == 0 and truth is not None else f"C{i}")
        axt.text(1.005, 1.0 - (i + 0.5) / len(rows), label, transform=axt.transAxes,
                 fontsize=7, va="center")
    axt.set_ylim(len(rows), 0)
    axt.set_yticks([])
    axt.set_xlabel("2θ (°)")
    fig.subplots_adjust(right=0.82, hspace=0.08)
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / f"peaks_{stem}.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
