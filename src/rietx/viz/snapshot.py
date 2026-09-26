"""The numbers behind a stage's picture, written where a viewer can draw them.

Until WP-1402 a live view was a *page*: ``LiveSession`` built a plotly figure
after every stage and wrote it self-contained, the whole of plotly.js inlined
afresh each time. That cost the fit several megabytes of serialisation on its
own thread per stage, cost the reader their zoom whenever the page reloaded,
and made recording a run impossible on an install without plotly, because
building the figure was how the view was stored.

This module writes the numbers instead. The fit pays a decimation and a small
JSON write; the viewer draws it with the chart module the package vendors and
redraws in place; and nothing here imports a plotting library. ``viz/live.py`` is a
shim over it, and WP-1403's recorder will be a second caller.

**It is a picture's data, not a record.** The curves are decimated to a screen's
worth of points and rounded to :data:`SIGNIFICANT_DIGITS`, both of which are
invisible at any zoom a browser can show and neither of which belongs in
anything anyone measures from. ``RefinementResult`` is the record, and
``rietx html`` still writes the self-contained emailable page on demand.

Three conventions this file must not get wrong, each with a WP behind it:

* **Δ/σ is what the fit minimised**, so ``delta`` is always it, divided by the
  σ the ``CompiledModel`` stored — a lookup, never a re-derivation (WP-1029).
  ``weighted`` reports whether that σ was *measured* and changes only what a
  viewer may call the axis.
* **Ticks carry every emission line's positions**, not just the primary, or a
  reader flags each Kα2 peak as an unindexed impurity.
* **A tick cap is reported, never silent** — ``n_total`` rides beside every
  capped list, the way ``MAX_CANDIDATE_TICKS`` does it in ``gui/session.py``,
  because a silent cap reads as coverage.

**One is written every stage, and that is a decision rather than the absence of
one** (WP-1438, answering the question WP-1413 left the maintainer). Measured
there: 8.30 / 6.54 / 10.56 ms a stage on ``nac`` / ``cpd-2`` / ``trigger``, so
50 / 59 / 84 ms of a whole fit and 1.233× / 1.049× / 1.031× of its wall clock.
Only ``nac`` is over the 5 % budget and it is a 0.354 s fit, where the whole
charge is 50 ms — a *ratio* is the wrong test on a fit that short, because what
a person could notice is the absolute number, and thinning would cost the live
view its redraws on precisely the fits somebody is watching. If that number
ever moves, the throttle is by **time** and never by count, which is what a
logger does when it needs one (TensorBoard's ``flush_secs``): a stage boundary
is the natural thing to write on, and how often it comes is the fit's business.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from ..crystallography.symmetry import reflection_label_row
from .compare import decimation_index

#: The file a run's viewer reads. Flat in a ``LiveSession`` directory, beside
#: ``events.jsonl`` and ``status.json``.
SNAPSHOT_FILE = "snapshot.json"

#: Bumped when a reader would get a field wrong without knowing. Adding a field
#: is not that: a viewer ignores what it does not know, the way
#: ``EventRecord.data`` is an open dict.
SCHEMA_VERSION = 1

#: The decimation budget. Not a point count: :func:`decimation_index` makes
#: ``max_points // 2`` buckets and keeps each one's min **and** max of every
#: curve it is given, so the drawn count lands between this and a small
#: multiple of it depending on how much the curves disagree about where their
#: extremes are. That is why ``n_drawn`` is a reported field.
#:
#: 4000 is the budget every other window in this package uses
#: (``viz/compare.py``, ``gui/session.py``), and agreeing with them matters
#: more than the number does: a reader flipping between the watcher and the
#: GUI must not see two different pictures of one fit.
MAX_POINTS = 4000

#: Ticks kept per phase. A cap because a large cell over a wide range can hand
#: a browser a hundred thousand of them, and 2000 is ``MAX_CANDIDATE_TICKS``.
MAX_TICKS_PER_PHASE = 2000

#: Significant digits kept on every curve. Six is three more than a 4000-pixel
#: screen can resolve, and it is most of what keeps the payload small.
SIGNIFICANT_DIGITS = 6

#: Decimals kept on 2θ. A pattern step is 0.001-0.01°, so five is two more than
#: the axis has.
TWO_THETA_DECIMALS = 5


def _round_significant(values: np.ndarray, digits: int) -> np.ndarray:
    """Round to ``digits`` significant figures, vectorised.

    Significant and not decimal, because a diffraction pattern's intensities
    span four or five orders of magnitude and a fixed number of decimals is
    either wasteful at the top or destructive at the bottom.
    """
    out = np.asarray(values, dtype=np.float64).copy()
    finite = np.isfinite(out) & (out != 0.0)
    if not finite.any():
        return out
    scale = 10.0 ** (digits - 1 - np.floor(np.log10(np.abs(out[finite]))))
    out[finite] = np.round(out[finite] * scale) / scale
    return out


def _json_list(values: np.ndarray) -> list:
    """A float list JSON can hold, with non-finite values as ``None``.

    ``json.dumps`` writes a bare ``NaN``, which is not JSON and which
    ``JSON.parse`` refuses — so one non-finite point would cost a viewer the
    whole curve. ``null`` is what the chart draws as a gap, which is the right
    picture of a point that has no value.

    The per-element branch runs only when there is something to branch on.
    ``tolist`` is one C call and the comprehension is 6000 python iterations a
    curve, which measured 5-9 ms of an 18 ms snapshot before this check was
    here — and a finite curve is what every stage of every fit produces.
    """
    values = np.asarray(values, dtype=np.float64)
    if np.isfinite(values).all():
        return values.tolist()
    return [None if not np.isfinite(v) else float(v) for v in values]


def stage_ticks(model, values: dict, *,
                max_per_phase: int = MAX_TICKS_PER_PHASE) -> dict[str, dict]:
    """Reflection positions per phase, every emission line's, capped out loud.

    Where a tick goes is ``viz/live.py``'s answer, moved rather than
    rewritten: a second way of placing one would be a second answer to where a
    peak is. Only the filtering and sorting changed, from a python generator
    over every position to numpy.

    ``hkl`` rides beside ``two_theta``, index for index (WP-1438), and is
    carried through the *same* filter, sort and thinning rather than
    recomputed against them — a tick and its Miller index that were derived
    separately could come apart, and the reader would never know which of the
    two was lying.
    """
    ticks: dict[str, dict] = {}
    for ip, cp in enumerate(model.phases):
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        rows = [cp.reflections.two_theta(cell, lam)
                + values["instrument.zero_shift"]
                for lam in model.line_wavelengths]
        pos = np.concatenate(rows) if rows else np.zeros(0)
        # one reflection list per emission line, in the same order each time,
        # so the index list is that list tiled: a Kα2 image is the same hkl
        # (H, m), not H: a satellite is labelled by its order (WP-1326)
        hkl = (np.tile(cp.reflections.hklm, (len(rows), 1)) if rows
               else np.zeros((0, 4), dtype=np.int64))
        # filtered and sorted in numpy, not in a generator: the cap below
        # exists because a large cell over a wide range reaches a hundred
        # thousand positions, and walking those in python is the cost this
        # module was written to stop paying
        keep = np.isfinite(pos)
        pos, hkl = pos[keep], hkl[keep]
        order = np.argsort(pos, kind="stable")
        pos, hkl = pos[order], hkl[order]
        n_total = int(pos.size)
        if n_total > max_per_phase:
            # evenly through the sorted list, so the cap thins the pattern
            # rather than truncating it at some 2θ the reader never chose
            idx = np.unique(np.linspace(0, n_total - 1, max_per_phase)
                            .round().astype(np.int64))
            pos, hkl = pos[idx], hkl[idx]
        ticks[f"phase {ip}"] = {
            # at most ``max_per_phase`` of them reach python
            "two_theta": [round(float(p), TWO_THETA_DECIMALS) for p in pos],
            "hkl": [reflection_label_row(r) for r in hkl],
            "n_total": n_total,
        }
    return ticks


def build_snapshot(model, table, outcome, stage_name: str, *,
                   max_points: int = MAX_POINTS,
                   digits: int = SIGNIFICANT_DIGITS) -> dict:
    """The payload, from one stage's frozen model and its solved θ.

    Every field's writer, because a field whose writer nobody named is how a
    default becomes a lie (WP-1076):

    ``schema``/``written``     here;
    ``stage``                  the caller's stage name;
    ``weighted``               ``CompiledModel.sigma_measured``, which
                               ``compile_model`` set from ``data.sigma is not
                               None``;
    ``statistics``             ``optimize.statistics.compute_statistics`` over
                               this stage's own arrays;
    ``two_theta``/``y_obs``    ``CompiledModel.tt``/``.y_obs``, the in-range
                               points ``compile_model`` masked to;
    ``y_calc``                 ``model.evaluate`` at the decoded θ;
    ``y_bkg``                  ``model.background`` at the same θ;
    ``delta``                  Δ divided by ``CompiledModel.sigma``;
    ``ticks``                  :func:`stage_ticks`, whose rows carry
                               ``two_theta``, the matching ``hkl`` and the
                               uncapped ``n_total``;
    ``n_points``/``n_drawn``   the mask's count and the decimation's.
    """
    from ..optimize.statistics import compute_statistics

    values = table.decode(outcome.theta)
    tt = np.asarray(model.tt, dtype=np.float64)
    y_obs = np.asarray(model.y_obs, dtype=np.float64)
    y_calc = np.asarray(model.evaluate(values), dtype=np.float64)
    y_bkg = np.asarray(model.background(values), dtype=np.float64)
    sigma = np.asarray(model.sigma, dtype=np.float64)
    # Δ/σ either way: it is what the fit minimised whether or not the file
    # carried an esd column, and σ here is the one the model stored (WP-1029)
    delta = (y_obs - y_calc) / sigma

    stats = compute_statistics(y_obs, y_calc, sigma,
                               n_free=len(table.free_paths), y_background=y_bkg)

    # One index set for every curve, from the one authority on which points
    # survive — never striding, which drops peak tops (viz/compare.py).  The
    # three curves handed to it are the GUI's and the comparison UI's, not
    # these four: the background is smooth, so adding it to the index would
    # buy nothing it is not already exactly representable at, and would cost
    # a quarter more points in every payload.
    idx = decimation_index(tt, [y_obs, y_calc, delta], max_points)

    return {
        "schema": SCHEMA_VERSION,
        "written": time.time(),
        "stage": stage_name,
        "weighted": model.sigma_measured,
        "statistics": {
            "rwp": float(stats.rwp), "gof": float(stats.gof),
            "chi2": float(stats.chi2), "rp": float(stats.rp),
            "n_free": int(stats.n_free_parameters),
        },
        "n_points": int(len(tt)),
        "n_drawn": int(len(idx)),
        "two_theta": [round(float(v), TWO_THETA_DECIMALS) for v in tt[idx]],
        "y_obs": _json_list(_round_significant(y_obs[idx], digits)),
        "y_calc": _json_list(_round_significant(y_calc[idx], digits)),
        "y_bkg": _json_list(_round_significant(y_bkg[idx], digits)),
        "delta": _json_list(_round_significant(delta[idx], digits)),
        "ticks": stage_ticks(model, values),
    }


def write_snapshot(directory: str | Path, model, table, outcome,
                   stage_name: str, **kwargs) -> dict:
    """Write one stage's snapshot into ``directory``, atomically.

    Written to a temporary name and renamed, because a viewer polls this file
    and a partial read is a broken plot rather than an old one.

    Returns the payload, so a caller wanting the same stage's numbers for a
    second file writes them from this rather than recomputing them. That is
    what keeps ``LiveSession``'s ``status.json`` from being a second answer to
    what the Rwp was.
    """
    directory = Path(directory)
    payload = build_snapshot(model, table, outcome, stage_name, **kwargs)
    tmp = directory / (SNAPSHOT_FILE + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(directory / SNAPSHOT_FILE)
    return payload
