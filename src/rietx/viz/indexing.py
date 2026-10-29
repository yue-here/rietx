"""Static plots for the indexing pipeline (matplotlib/Agg).

Three pictures, one per stage of what :func:`~rietx.indexing.index_pattern`
does.  Their colours are roles in :data:`rietx.viz.plots.PALETTES`, beside the
Rietveld panel's, and each takes ``style="light"`` or ``"dark"`` as that panel
does (WP-1972):

* :func:`plot_peak_list` — what the search was actually given.  A peak list is an
  *input* that has already thrown most of the pattern away, and every indexing
  failure this package has measured on real data was visible here first (WP-1018's
  spurious Kα2 lines, WP-1039's satellites, the LaB6 tail components).
* :func:`plot_candidates` — the ranked answers as tick rows against the observed
  lines, which is the only view in which "indexes everything and predicts a
  forest" looks like what it is.
* :func:`plot_validation` — the validation fit behind the gate, with **both**
  detector lists marked, because they catch different failures
  (:mod:`rietx.indexing.workflow`).

**Why the tick rows are regenerated rather than retrieved.**  A
:class:`~rietx.schemas.indexing.CellCandidate` carries no hkl assignment and no
predicted-2θ list — deliberately, since a candidate is a *lattice* and the
reflections it implies depend on the range you ask about.  So the ticks come from
:func:`rietx.indexing.fom.predicted_lines`, the same enumeration the figures of
merit are computed on, which is what keeps a picture from disagreeing with the
number printed beside it.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextvars import ContextVar

import numpy as np

from ..schemas.indexing import _MODE_NAMES
from .plots import PALETTES, _palette

# The roles, in PALETTES per ground: ``index_obs`` and ``index_calc`` for
# observed data and the calculated model, ``index_bkg`` and ``index_diff`` for
# the recessive marks.  The two Le Bail detectors are ``unmatched``, the purple
# ``plot_for_vlm`` already gives that exact meaning, and ``absent``, the amber
# this palette uses for "look here".  The two never share a mark because they
# are evidence about opposite things — a wrong metric against an oversized one.

#: Candidate rows on the light ground, in **rank order and never cycled**: rank
#: 1 is always the first colour, so two galleries of the same dataset are
#: comparable.  Past the eighth candidate the rows are drawn in ``index_diff``
#: rather than in a generated hue.  ``PALETTES["dark"]["candidate"]`` is the
#: dark ground's.
CANDIDATE_COLORS = tuple(PALETTES["light"]["candidate"])


def _context(plt, style: str):
    """:func:`rietx.viz.plots._ground_context`: the dark ground, or nothing."""
    from .plots import _ground_context
    return _ground_context(plt, style)


def _pyplot():
    """:func:`rietx.viz.plots._pyplot`: one rule for when Agg is forced."""
    from .plots import _pyplot as pyplot
    return pyplot()


#: Set while :func:`plot_indexing` composes its figures.  It returns a dict,
#: which a notebook prints as text, so a figure detached by ``_handed_back``
#: would never be drawn; left with pyplot, each is drawn once as the cell ends.
_COMPOSING: ContextVar[bool] = ContextVar("_COMPOSING", default=False)


def _figure_class():
    """:func:`rietx.viz.plots._figure_class`: one notebook encoding."""
    from .plots import _figure_class as figure_class
    return figure_class()


def _handed_back(fig, style: str):
    """:func:`rietx.viz.plots._handed_back`: one rule for a notebook's figures.

    A composed figure stays with pyplot but still records its palette, so the
    inline backend's draw at the cell's end carries the dark copy too."""
    if _COMPOSING.get():
        fig._rietx_style = style
        return fig
    from .plots import _handed_back as handed_back
    return handed_back(fig, style)


def _two_theta_of_q(q: np.ndarray, wavelength: float) -> np.ndarray:
    """Q → 2θ, clipped at the Ewald limit rather than raising on it."""
    arg = np.clip(wavelength * np.sqrt(np.maximum(np.asarray(q), 0.0)) / 2.0,
                  -1.0, 1.0)
    return np.degrees(2.0 * np.arcsin(arg))


def plot_peak_list(peaks, data=None, *, path: str | None = None,
                   dpi: int = 150, title: str | None = None, style: str = "light"):
    """The picked lines over the pattern they came from — the search's real input.

    ``data`` is optional: with a
    :class:`~rietx.schemas.pattern.PatternData` the lines are drawn over the
    profile, and without one they are drawn as a stem plot against intensity,
    which is all a position list (``PeakList.from_positions``) actually carries.

    A line carrying a **per-line** quality flag — a failed fit, a position at a
    bound, an unresolved shoulder — is drawn faint, because it is in the list
    without being evidence of the same weight, and those are the lines every
    real-data indexing failure this package has measured turned out to be about.
    ``sigma_assumed`` is deliberately **not** one of them: it is a property of the
    whole list rather than of a line (every entry of a ``from_positions`` list
    carries it), so it belongs in the title, where it says once what it means.

    ``style="dark"`` draws on the dark page's ground in the dark palette, as
    :func:`~rietx.viz.plots.plot_result`'s does.
    """
    from ..schemas.pattern import require_two_theta

    if data is not None:
        require_two_theta(data, "plot_peak_list()")
    hue = _palette(style)
    plt = _pyplot()
    usable = peaks.usable()
    tt = np.array([p.two_theta for p in usable], dtype=np.float64)
    esd = np.array([p.two_theta_esd for p in usable], dtype=np.float64)
    inten = np.array([p.intensity for p in usable], dtype=np.float64)
    flagged = np.array([bool(set(p.flags) - {"sigma_assumed"}) for p in usable],
                       dtype=bool)
    assumed = all("sigma_assumed" in p.flags for p in usable) if usable else False

    # σ is quoted rather than drawn: at a whole-pattern scale 3σ is well under a
    # pixel on any list worth indexing (0.03° against a 70° axis), and a mark the
    # legend promises but the eye cannot find is worse than a number
    median_sigma = float(np.median(esd)) if len(esd) else float("nan")
    with _context(plt, style):
        fig, ax = plt.subplots(figsize=(11, 4.5), dpi=dpi, FigureClass=_figure_class())
        if data is not None:
            x = np.asarray(data.two_theta, dtype=np.float64)
            y = np.asarray(data.intensity, dtype=np.float64)
            ax.plot(x, y, "-", lw=0.7, color=hue["index_obs"], label="pattern",
                    zorder=1)
            top = float(y.max())
        else:
            top = float(inten.max()) if len(inten) else 1.0
            ax.vlines(tt, 0.0, inten, lw=0.9, color=hue["index_obs"],
                      label="peak list", zorder=1)

        base = -0.06 * top
        ax.vlines(tt[~flagged], base - 0.03 * top, base + 0.03 * top, lw=1.1,
                  color=hue["index_calc"], zorder=3,
                  label=f"clean ({int((~flagged).sum())})")
        if flagged.any():
            ax.vlines(tt[flagged], base - 0.03 * top, base + 0.03 * top, lw=1.1,
                      color=hue["index_calc"], alpha=0.30, zorder=3,
                      label=f"flagged ({int(flagged.sum())})")

        ax.axhline(0.0, lw=0.4, color=hue["zero"], zorder=0)
        ax.set_xlabel(r"2$\theta$ (deg)")
        ax.set_ylabel("intensity")
        ax.set_title(title or (
            f"{len(usable)} usable lines, source={peaks.source}, "
            rf"$\lambda$={peaks.wavelength:.5f} Å, "
            rf"median $\sigma$(2$\theta$)={median_sigma:.4f}°"
            + (" (assumed, not measured)" if assumed else "")), fontsize=10)
        ax.legend(loc="upper right", fontsize=8, frameon=False)
        fig.tight_layout()
        if path is not None:
            fig.savefig(path)
    return _handed_back(fig, style)


def plot_candidates(candidates: Sequence, peaks, *, path: str | None = None,
                    n: int = 5, dpi: int = 150, title: str | None = None,
                    q_match=None, style: str = "light"):
    """Ranked candidates as tick rows against the observed lines.

    **The forward and reverse directions are both visible, which is the whole
    point.**  Each row draws every line the candidate lattice predicts in range;
    a tick with an observed line under it is solid and one without is hollow.  So
    a cell that indexes everything by predicting a forest — the measured false
    positive this package ranks a panel to avoid — is the row that is mostly
    hollow, and no figure of merit has to be trusted for a reader to see it.

    **``q_match`` is the window the search matched with, and passing the wrong
    one makes the picture contradict the number printed beside it.**  CLAUDE.md's
    rule — the matching window is an argument separate from the per-line σ —
    applies here for the same reason it applies to :func:`fom.fom_panel`: on a
    pattern with a shift allowance the search asked "is this the same line" in a
    *widened* window, and asking it again in the raw σ answers a different
    question.  Measured on 11-BM NAC, which carries the default 0.05° allowance:
    with ``q_match=None`` this figure labelled a row "224/285 indexed" from the
    candidate's own field and drew **213 of 285 as unindexed** in the same
    legend.  ``None`` means ``peaks.q_esd()``, which is the identity when no
    allowance applies; callers with a result in hand should pass
    :func:`rietx.indexing.engines.match_window`.

    Each candidate is matched on the positions it actually claims
    (:func:`rietx.indexing.engines.scored_positions`), so one carrying a fitted
    shift is not marked down for the correction it declared.  The ticks are
    *drawn* at the uncorrected predicted positions, since the shifts this
    package fits are 0.03-0.07° against a 100°+ axis — sub-pixel, where the
    match is not.

    ``style="dark"`` draws on the dark page's ground, each row in the dark
    ground's colour of its rank.
    """
    from ..indexing.engines import scored_positions
    from ..indexing.fom import MATCH_SIGMA, match_lines, predicted_lines

    hue = _palette(style)
    plt = _pyplot()
    shown = list(candidates)[:n]
    if not shown:
        raise ValueError("plot_candidates needs at least one candidate")

    q_esd = peaks.q_esd() if q_match is None else np.asarray(q_match,
                                                             dtype=np.float64)
    tt_obs = peaks.two_theta()
    inten = peaks.intensity()
    tt_lo = float(peaks.two_theta_min)
    tt_hi = float(peaks.two_theta_max)

    with _context(plt, style):
        fig, (ax, axt) = plt.subplots(
            2, 1, figsize=(11, 2.2 + 0.62 * len(shown)), dpi=dpi,
            FigureClass=_figure_class(), sharex=True,
            gridspec_kw={"height_ratios": [1.5, 0.55 + 0.42 * len(shown)]})

        scale = float(inten.max()) if len(inten) and inten.max() > 0 else 1.0
        ax.vlines(tt_obs, 0.0, inten / scale, lw=0.9, color=hue["index_obs"], zorder=2,
                  label=f"observed ({len(tt_obs)})")
        ax.set_ylabel("rel. intensity")
        ax.set_ylim(0.0, 1.15)

        for row, cand in enumerate(shown):
            colour = (hue["candidate"][row] if row < len(hue["candidate"])
                      else hue["index_diff"])
            _hkl, q_pred = predicted_lines(cand.cell, cand.system, cand.centring,
                                           peaks.wavelength, tt_hi)
            tt_pred = _two_theta_of_q(q_pred, peaks.wavelength)
            # each prediction: is an observed line sitting under it?  Against the
            # positions *this* candidate claims, in the window the search used.
            q_claim, _tt_claim = scored_positions(peaks, cand)
            if len(q_claim) and len(q_pred):
                gap = np.abs(np.asarray(q_pred)[:, None] - q_claim[None, :])
                j = np.argmin(gap, axis=1)
                seen = gap[np.arange(len(q_pred)), j] <= MATCH_SIGMA * np.maximum(
                    q_esd[j], 1e-300)
            else:
                seen = np.zeros(len(q_pred), dtype=bool)
            # drawn over the plotted range, matched over the panel's.  Enumerating
            # from ``tt_lo`` instead put the *boundary* prediction outside the set —
            # and ``PeakList.two_theta_min`` is the first line's own position, so
            # every candidate figure read its first observed line as unindexed.
            inview = tt_pred >= tt_lo
            y = -float(row)
            axt.vlines(tt_pred[seen & inview], y - 0.30, y + 0.30, lw=1.0,
                       color=colour, zorder=3)
            axt.vlines(tt_pred[~seen & inview], y - 0.18, y + 0.18, lw=0.8,
                       color=colour, alpha=0.30, zorder=2)
            # **The share is quoted from the panel, not recomputed here.**  The two
            # enumerate over different ranges on purpose — the panel stops at the
            # last *observed* line (``fom.fom_panel``) while the picture must cover
            # the axis it draws — so recomputing gives a number a few points from
            # ``predicted_seen_fraction`` and prints it in a figure whose whole
            # claim is that it agrees with the panel (measured on NAC: 43 % drawn
            # against the panel's 46 %).  The ticks show the lattice over the range;
            # the number is the one that was ranked on.
            fom_value = getattr(cand, "fom_value", None)
            share = fom_value("predicted_seen_fraction") if fom_value else None
            if share is None:
                share = float(np.mean(seen)) if len(seen) else 0.0
            m20 = fom_value("m20") if fom_value else None
            label = (f"#{row + 1} {cand.system} {cand.centring}  "
                     f"a={cand.cell[0]:.4f} V={cand.volume:.1f} Å³  "
                     f"{cand.n_indexed}/{cand.n_lines} indexed, "
                     f"{share:.0%} of predicted lines seen "
                     f"({int(inview.sum())} drawn)")
            if m20 is not None:
                label += f", M20={m20:.1f}"
            # ``confidence`` defaults to ``"low"`` on an *ungated* candidate, so
            # printing it unconditionally would put a verdict in the picture that
            # nothing had reached.  A gated candidate either says something other
            # than low or carries the caveats that made it low; both are shown.
            conf = getattr(cand, "confidence", None)
            caveats = list(getattr(cand, "confidence_caveats", ()) or ())
            if conf and (conf != "low" or caveats):
                # capped: a candidate can carry six caveats, and a label wider than
                # the axes is a label nobody reads.  The count is kept, so a reader
                # knows there are more rather than being shown a truncated set as
                # though it were the whole one.
                shown_caveats = caveats[:3]
                more = len(caveats) - len(shown_caveats)
                text = ", ".join(shown_caveats) + (f", +{more} more" if more else "")
                label += f"  [{conf}" + (f": {text}]" if caveats else "]")
            axt.text(0.004, y + 0.40, label, fontsize=7.5, color=hue["index_diff"], va="bottom",
                     transform=axt.get_yaxis_transform())

        # observed lines the best candidate does not claim.  ``scored_positions``
        # is duck-typed on ``shift_template``/``shift_coefficient``, which a
        # ``CellCandidate`` carries directly — the previous ``hasattr(best, "fit")``
        # guard was never true on one, so this silently drew every shift-carrying
        # candidate against positions it had not claimed.
        best = shown[0]
        q_claim, _tt_claim = scored_positions(peaks, best)
        _hkl0, q_pred0 = predicted_lines(best.cell, best.system, best.centring,
                                         peaks.wavelength, tt_hi)
        idx, _d = match_lines(q_claim, q_esd, q_pred0, k_sigma=MATCH_SIGMA)
        missed = idx < 0
        if missed.any():
            ax.vlines(tt_obs[missed], 0.0, inten[missed] / scale, lw=1.4,
                      color=hue["unmatched"], zorder=3,
                      label=f"not indexed by #1 ({int(missed.sum())})")
        ax.legend(loc="upper right", fontsize=8, frameon=False)

        axt.set_ylim(-len(shown) + 0.3, 0.95)
        axt.set_yticks([])
        axt.set_xlabel(r"2$\theta$ (deg)")
        axt.set_xlim(tt_lo - 1.0, tt_hi + 1.0)
        ax.set_title(title or ("ranked candidates: solid tick = predicted line with "
                               "an observed line under it, faint = predicted and "
                               "absent"), fontsize=10)
        fig.tight_layout()
        if path is not None:
            fig.savefig(path)
    return _handed_back(fig, style)


def plot_validation(validation, result=None, *, path: str | None = None,
                    dpi: int = 150, title: str | None = None, style: str = "light"):
    """The whole-pattern validation fit, with both detector lists marked.

    ``result`` is the :class:`~rietx.schemas.results.RefinementResult` from
    ``validate_by_lebail(..., with_result=True)``.  Without it only the detector
    positions can be drawn, which is a strictly worse picture and is why the
    opt-in return exists.

    Read it the way :mod:`rietx.indexing.workflow`'s table says to read the
    numbers: Rwp is decisive on a **wrong metric** and silent on an
    **oversized** one, so the amber marks (predicted, nothing there) and the
    purple ones (observed, nothing predicted) are not decoration — they are the
    two failures the fit statistic cannot separate.

    ``style="dark"`` draws on the dark page's ground in the dark palette.
    """
    hue = _palette(style)
    plt = _pyplot()
    absent = np.asarray(validation.predicted_but_absent_two_theta,
                        dtype=np.float64)
    unmatched = np.asarray(validation.unmatched_observed_two_theta,
                           dtype=np.float64)

    if result is None:
        with _context(plt, style):
            fig, ax = plt.subplots(figsize=(11, 3.2), dpi=dpi, FigureClass=_figure_class())
            ax.vlines(absent, 0.0, 1.0, lw=1.0, color=hue["absent"],
                      label=f"predicted but absent ({len(absent)})")
            ax.vlines(unmatched, -1.0, 0.0, lw=1.0, color=hue["unmatched"],
                      label=f"unmatched observed ({len(unmatched)})")
            ax.set_yticks([])
            ax.set_xlabel(r"2$\theta$ (deg)")
            ax.legend(loc="upper right", fontsize=8, frameon=False)
            ax.set_title(title or _validation_title(validation), fontsize=10)
            fig.tight_layout()
            if path is not None:
                fig.savefig(path)
        return _handed_back(fig, style)

    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    y_bkg = np.asarray(result.y_background)
    with _context(plt, style):
        fig, (ax, axd) = plt.subplots(
            2, 1, figsize=(11, 6.4), dpi=dpi, FigureClass=_figure_class(), sharex=True,
            gridspec_kw={"height_ratios": [3, 1]})
        ax.plot(tt, y_obs, ".", ms=2.0, color=hue["index_obs"], label="observed", zorder=2)
        ax.plot(tt, y_calc, "-", lw=1.0, color=hue["index_calc"],
                label=_MODE_NAMES[validation.mode], zorder=3)
        ax.plot(tt, y_bkg, "--", lw=0.8, color=hue["index_bkg"], label="background", zorder=1)

        span = float(y_obs.max() - min(y_obs.min(), 0.0))
        if len(absent):
            ax.vlines(absent, -0.05 * span, 0.02 * span, lw=1.0, color=hue["absent"],
                      zorder=4, label=f"predicted but absent ({len(absent)})")
        if len(unmatched):
            for x in unmatched:
                ax.axvline(x, color=hue["unmatched"], lw=0.8, ls=":", alpha=0.8, zorder=1)
            ax.plot([], [], ls=":", lw=0.8, color=hue["unmatched"],
                    label=f"unmatched observed ({len(unmatched)})")
        ax.set_ylabel("intensity")
        ax.legend(loc="upper right", fontsize=8, frameon=False)
        ax.set_title(title or _validation_title(validation), fontsize=10)

        axd.plot(tt, (y_obs - y_calc) / result.sig(), "-", lw=0.6, color=hue["index_diff"])
        axd.axhspan(-3, 3, color=hue["band"], alpha=0.15, lw=0)
        axd.set_ylabel(r"$\Delta/\sigma$")
        axd.set_xlabel(r"2$\theta$ (deg)")
        fig.tight_layout()
        if path is not None:
            fig.savefig(path)
    return _handed_back(fig, style)


def _window_from_result(result, peaks) -> np.ndarray:
    """The σ(Q) the search matched with, rebuilt from what the result records.

    ``index_pattern`` writes ``shift_allowance_deg`` into ``provenance.notes``
    on every run precisely so a run is reproducible from what it reports; that
    plus the quality report's shift screen feed the same
    :func:`~rietx.indexing.engines.effective_shift_allowance` the search
    read.  So
    a picture drawn from a result matches in the window the candidates were
    selected under — CLAUDE.md's rule that a fitted σ is the wrong matching
    window, honoured with **no spec in hand** (WP-1043: the visual check is
    reachable from a result, not only from the suite that ran the search).
    """
    from ..indexing.engines import SearchSpec, match_window

    notes = getattr(getattr(result, "provenance", None), "notes", None) or {}
    try:
        # results recorded before WP-1045 wrote the key under the old name
        raw = notes.get("shift_allowance_deg", notes.get("sigma_sys_deg", 0.0))
        allowance = float(raw or 0.0)
    except (TypeError, ValueError):
        allowance = 0.0
    return match_window(peaks, SearchSpec(shift_allowance_deg=allowance),
                        getattr(result, "quality", None))


def plot_indexing(result, peaks, *, data=None, instrument=None,
                  candidate: int = 0, n: int = 5, validation=None,
                  path: str | None = None, dpi: int = 150, style: str = "light"):
    """The whole visual check, as a function of (result, pattern) — WP-1043.

    The user's design call made the picture part of the deliverable: one
    ranked list with stats *plus a visual check against the diffraction data*.
    Until this function the check lived only in ``tests/indexing_gallery.py``,
    which owned the composition (window reconstruction, top-candidate refit);
    now the gallery is a consumer of this call, not the owner.

    Returns ``{name: Figure}`` in drawing order, with up to three entries
    matching what the inputs allow:

    * ``"peaks"`` — always: the search's real input (over the profile when
      ``data`` is given).
    * ``"candidates"`` — when the result carries any: the ranked tick rows,
      matched in the **window the search used**, reconstructed from the
      result's own provenance notes (:func:`_window_from_result`).
    * ``"validation"`` — the validation-fit panel for ``candidates[candidate]``.
      Pass ``validation=(LeBailValidation, RefinementResult)`` from
      ``validate_by_lebail(..., with_result=True)`` to draw a fit already in
      hand; or pass ``data`` **and** ``instrument`` to run that fit here; or
      neither, and the stored positions-only panel is drawn when the
      candidate carries one.

    ``path`` is a stem: each figure is saved as ``f"{path}_{name}.png"``.
    Figures are returned open either way, and closing them is the caller's.
    They stay with pyplot even in a notebook, unlike a single figure: the
    dict prints as text, so the inline backend draws each one as the cell
    ends, with its dark copy beside it.  ``style`` draws all three figures, as
    each function's own ``style`` does.
    """
    from ..schemas.pattern import require_two_theta

    _palette(style)  # refused before a validation fit is spent on it
    if data is not None or instrument is not None:
        require_two_theta(data, "plot_indexing()", instrument=instrument)
    token = _COMPOSING.set(True)
    try:
        figures = _compose_indexing(result, peaks, data=data, instrument=instrument,
                                    candidate=candidate, n=n, validation=validation,
                                    dpi=dpi, style=style)
    finally:
        _COMPOSING.reset(token)
    if path is not None:
        # under the style, as each function's own save is: outside it a
        # caller's ``savefig.facecolor`` would frame a dark figure in white
        with _context(_pyplot(), style):
            for name, fig in figures.items():
                fig.savefig(f"{path}_{name}.png")
    return figures


def _compose_indexing(result, peaks, *, data, instrument, candidate, n,
                      validation, dpi, style) -> dict:
    """:func:`plot_indexing`'s figures, in drawing order."""
    figures: dict = {}
    figures["peaks"] = plot_peak_list(peaks, data, dpi=dpi, style=style)

    cands = list(getattr(result, "candidates", ()) or ())
    if cands:
        if not 0 <= candidate < len(cands):
            raise ValueError(f"candidate {candidate} is out of range for "
                             f"{len(cands)} candidate(s)")
        figures["candidates"] = plot_candidates(
            cands, peaks, n=n, dpi=dpi, style=style,
            q_match=_window_from_result(result, peaks))
        chosen = cands[candidate]
        if validation is None and data is not None and instrument is not None:
            from ..indexing.workflow import validate_by_lebail

            validation = validate_by_lebail(chosen, data, instrument,
                                            peaks=peaks, with_result=True)
        if validation is not None:
            val, fit = validation
            figures["validation"] = plot_validation(val, fit, dpi=dpi, style=style)
        elif chosen.lebail is not None:
            # positions only — strictly worse than the fit panel and drawn
            # anyway: the two detector lists are what separate a wrong metric
            # from an oversized one, and they need no refit
            figures["validation"] = plot_validation(chosen.lebail, dpi=dpi, style=style)
    return figures


def _validation_title(validation) -> str:
    return (f"{_MODE_NAMES[validation.mode]} validation of {validation.space_group}: "
            f"Rwp={validation.rwp:.4f}, GoF={validation.gof:.2f}, "
            f"{validation.predicted_but_absent}/{validation.n_reflections} "
            f"predicted but absent, {validation.unmatched_observed} unmatched "
            f"observed  [{validation.status}]")


__all__ = ["CANDIDATE_COLORS", "plot_candidates", "plot_indexing",
           "plot_peak_list", "plot_validation"]
