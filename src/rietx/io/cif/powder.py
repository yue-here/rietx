"""The pdCIF pattern block of a refinement CIF (WP-1933 C-d, issue #756 § 2.2).

**Every measured point, and the fit's choice among them.**  The profile loop
carries the whole measured grid, as the Acta E notes (2014 § 3.3.7) ask of a
deposited powder pattern, and ``_pd_proc_ls_weight`` says which points the fit
used: the weight it gave a fitted point, 1/σ², and 0 on every other.  A point
outside the fit has no calculated value, so its ``_pd_calc_intensity_total`` and
``_pd_proc_intensity_bkg_calc`` are ``.`` (inapplicable).  Where the caller
hands no pattern, only the fitted points are written.

**The grid as measured.**  ``_pd_meas_2theta_scan``, because nothing here
corrects the angles.  ``_pd_proc_2theta_corrected`` is reserved for a grid a
zero or displacement correction has moved (ITC Vol. G ch. 4.2, p. 267), and the
fit models those corrections in the peak positions instead.

**Intensities, and where their su comes from.**  A pattern whose file stated σ
writes ``_pd_meas_intensity_total`` with that σ in parentheses.  A pattern
without one writes ``_pd_meas_counts_total`` when every value is a whole count,
since a count carries no su by definition (ch. 4.2, p. 263), and
``_pd_meas_intensity_total`` with no su otherwise.  The σ the fit weighted by can
differ from the file's: a measured background widens it
(``model.forward.compile_model``).  So the weights state the fit's σ and the
parentheses state the file's.

``_pd_proc_d_spacing`` is the measured 2θ at the primary wavelength, with no
zero or displacement correction, the same grid as ``_pd_meas_2theta_scan``.

The loop is written at eight significant figures.  The number rule's shortest
``repr`` grew a refinement CIF 1.5-1.7× here with digits of float noise
(WP-1319), and a measured intensity carries its su in parentheses anyway.

References
----------
- Toby, B. H. (2006), *International Tables for Crystallography* Vol. G,
  ch. 3.3 (pp. 124-129, the block layout and the d-spacing recommendation) and
  ch. 4.2 (pp. 263-267, the pattern items).
- COMCIFS ``cif_pd.dic`` 2.5.0: every item's name and contents.
- IUCr (2014), *Notes for Authors*, Acta Cryst. E, § 3.3.7: deposit every
  measured point.
"""

from __future__ import annotations

import numpy as np

from .numbers import number, text


def _g(x: float) -> str:
    return f"{x:.8g}"


def _fitted(result, pattern) -> np.ndarray:
    """Which of ``pattern``'s points the fit used, as a boolean mask.

    The fitted grid is a subset of the measured one, taken unchanged by
    ``compile_model``.  So each fitted 2θ is found in the measured grid by
    value, and a pattern that is not the one fitted is refused.
    """
    tt = np.asarray(pattern.two_theta, dtype=np.float64)
    fit = np.asarray(result.two_theta, dtype=np.float64)
    at = np.searchsorted(tt, fit)
    if (fit.size > tt.size or np.any(at >= tt.size)
            or not np.array_equal(tt[np.minimum(at, tt.size - 1)], fit)):
        raise ValueError(
            "the pattern handed to the refinement CIF is not the one this "
            f"result was fitted to: {fit.size} fitted points are not all "
            f"among its {tt.size} measured ones")
    mask = np.zeros(tt.size, dtype=bool)
    mask[at] = True
    return mask


def _runs(tt: np.ndarray, mask: np.ndarray) -> list[tuple[float, float, int]]:
    """The unfitted stretches of the grid, as (first 2θ, last 2θ, points)."""
    out = []
    start = None
    for i, fitted in enumerate([*mask.tolist(), True]):
        if not fitted and start is None:
            start = i
        elif fitted and start is not None:
            out.append((float(tt[start]), float(tt[i - 1]), i - start))
            start = None
    return out


def _constant_step(tt: np.ndarray) -> float | None:
    """The grid's step when every step agrees to 1e-6 of it, else ``None``."""
    if tt.size < 2:
        return None
    steps = np.diff(tt)
    step = float(np.median(steps))
    if step > 0.0 and np.all(np.abs(steps - step) <= 1e-6 * step):
        return step
    return None


def _refuse_non_finite(tag: str, column) -> None:
    """The number rule names the first non-finite value and refuses it."""
    values = np.asarray(column, dtype=np.float64)
    bad = np.flatnonzero(~np.isfinite(values))
    if bad.size:
        number(tag, values[bad[0]], where=f"point {bad[0]}")


def pattern_items(result, wavelength: float, pattern=None
                  ) -> tuple[list[tuple[str, str]], list[str], list[list[str]]]:
    """The pattern block's pairs, its loop's tags and the loop's rows.

    ``pattern`` is the :class:`~rietx.schemas.pattern.PatternData` the fit was
    given, every measured point included; ``None`` writes the fitted points
    alone.  ``wavelength`` is the primary line's, for the d-spacing.  Every
    value is formatted before the caller sets one, so a refusal leaves the block
    unwritten.  The module docstring says what each item states.
    """
    fit_tt = np.asarray(result.two_theta, dtype=np.float64)
    n_fit = fit_tt.size
    if pattern is None:
        tt, y = fit_tt, np.asarray(result.y_obs, dtype=np.float64)
        file_sigma = None
        mask = np.ones(n_fit, dtype=bool)
    else:
        tt = np.asarray(pattern.two_theta, dtype=np.float64)
        y = np.asarray(pattern.intensity, dtype=np.float64)
        file_sigma = (None if pattern.sigma is None
                      else np.asarray(pattern.sigma, dtype=np.float64))
        mask = _fitted(result, pattern)

    # the σ the fit weighted by: RefinementResult.sig() is the one authority
    # (a pre-v0.2 result carries none and gets the fit's own fallback)
    sig = result.sig()
    calc = np.asarray(result.y_calc, dtype=np.float64)
    bkg = np.asarray(result.y_background or [0.0] * n_fit, dtype=np.float64)
    weight = np.zeros(tt.size)
    weight[mask] = 1.0 / sig ** 2

    if file_sigma is not None:
        y_tag = "_pd_meas_intensity_total"
    elif np.all(y >= 0.0) and np.array_equal(y, np.round(y)):
        y_tag = "_pd_meas_counts_total"
    else:
        y_tag = "_pd_meas_intensity_total"
    for tag, column in (("_pd_meas_2theta_scan", tt), (y_tag, y),
                        ("_pd_proc_ls_weight", weight),
                        ("_pd_calc_intensity_total", calc),
                        ("_pd_proc_intensity_bkg_calc", bkg)):
        _refuse_non_finite(tag, column)

    with np.errstate(divide="ignore"):
        d = wavelength / (2.0 * np.sin(np.radians(tt) / 2.0))
    tags = ["_pd_meas_2theta_scan", y_tag, "_pd_proc_ls_weight",
            "_pd_proc_d_spacing", "_pd_calc_intensity_total",
            "_pd_proc_intensity_bkg_calc"]
    rows = []
    k = 0                                    # index into the fitted arrays
    for i in range(tt.size):
        if file_sigma is not None:
            yi = number(y_tag, y[i], file_sigma[i], where=f"point {i}")
        elif y_tag == "_pd_meas_counts_total":
            yi = str(int(y[i]))
        else:
            yi = _g(y[i])
        di = _g(d[i]) if tt[i] > 0.0 else "."
        if mask[i]:
            rows.append([_g(tt[i]), yi, _g(weight[i]), di, _g(calc[k]), _g(bkg[k])])
            k += 1
        else:
            rows.append([_g(tt[i]), yi, "0", di, ".", "."])

    pairs = [
        ("_pd_meas_number_of_points", str(tt.size)),
        ("_pd_meas_2theta_range_min", number("_pd_meas_2theta_range_min", tt[0])),
        ("_pd_meas_2theta_range_max", number("_pd_meas_2theta_range_max", tt[-1])),
    ]
    step = _constant_step(tt)
    if step is not None:
        pairs.append(("_pd_meas_2theta_range_inc", _g(step)))
    pairs += [
        ("_pd_proc_number_of_points", str(n_fit)),
        ("_pd_proc_2theta_range_min", number("_pd_proc_2theta_range_min", fit_tt[0])),
        ("_pd_proc_2theta_range_max", number("_pd_proc_2theta_range_max", fit_tt[-1])),
    ]
    runs = _runs(tt, mask)
    if runs:
        clauses = [f"2theta {_g(lo)} to {_g(hi)} deg ({n} point{'s' if n > 1 else ''})"
                   for lo, hi, n in runs]
        # text() wraps it in lines checkCIF reads (PLAT802)
        pairs.append(("_pd_proc_info_excluded_regions", text(
            "_pd_proc_info_excluded_regions",
            "Not fitted, weight 0 in the profile loop: " + "; ".join(clauses))))
    return pairs, tags, rows


def write_pattern_block(block, result, wavelength: float, pattern=None) -> None:
    """Set :func:`pattern_items`' pairs and loop on ``block``.

    **Omitted on a time-of-flight fit**, whose ``two_theta`` is ``None``: every
    tag written here is an angular one (``_pd_meas_2theta_scan``), and
    pdCIF's flight-time column is a different tag
    (``_pd_meas_time_of_flight``) with its own calibration items beside it.
    Writing microseconds under the angular tag would produce a file that reads
    back as a scan nobody measured, so the loop is left out and the rest of the
    document — cell, coordinates, agreement indices, geometry — is written as
    usual.  A flight-time pattern loop is a later rung of the time-of-flight
    track (yue-here/rietx issue #193).
    """
    if not result.two_theta:
        return
    pairs, tags, rows = pattern_items(result, wavelength, pattern)
    for tag, value in pairs:
        block.set_pair(tag, value)
    loop = block.init_loop("", tags)
    for row in rows:
        loop.add_row(row)


def write_reflection_loop(block, rows, structure) -> None:
    """The ``_refln`` loop: each reflection once, with its phase, d and F².

    One row per reflection at the primary line, since d and |F|² do not depend
    on the line.  ``_pd_refln_phase_id`` is the phase's 1-based position in the
    file, the id the phase table of the multi-block layout names (issue #756
    § 2.2, WP-1933's C-e).  A satellite of a modulated phase is left out, since
    its index needs four numbers the flat loop has no column for, and so is the
    magnetic share of a split row.  ``_refln_F_squared_calc`` is the
    structure's |F|² in Rietveld mode, and ``.`` on a phase carrying moments,
    whose stored |F|² is the nuclear share alone (``ReflectionRow``).
    """
    kept = [r for r in rows if r.line == 0 and r.satellite_order == 0
            and r.component != "magnetic"]
    if not kept:
        return
    with_f2 = any(r.f_squared is not None for r in kept)
    table = []
    for r in kept:
        row = [str(r.h), str(r.k), str(r.l), str(r.phase_index + 1),
               number("_refln_d_spacing", r.d, where=f"{r.h} {r.k} {r.l}")]
        if with_f2:
            magnetic = structure.phases[r.phase_index].magnetic_symmetry is not None
            row.append("." if r.f_squared is None or magnetic else
                       number("_refln_F_squared_calc", r.f_squared,
                              where=f"{r.h} {r.k} {r.l}"))
        table.append(row)
    loop = block.init_loop("", [
        "_refln_index_h", "_refln_index_k", "_refln_index_l", "_pd_refln_phase_id",
        "_refln_d_spacing", *(["_refln_F_squared_calc"] if with_f2 else [])])
    for row in table:
        loop.add_row(row)
