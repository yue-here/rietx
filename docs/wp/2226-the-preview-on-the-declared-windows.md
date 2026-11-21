# WP-2226 — The preview on the declared windows

Milestone: unscheduled · Status: 🔄 2026-11-21 — claimed by @yue-here
Track: A long run is not one fit
Depends on: 2222 (the closing stage off by default)
Priority: P3 2026-11-19 — a visible shift of up to 0.13 % of the strongest peak when a preview starts from a default fit; nothing is wrong with the fit

## Goal

A GUI preview that starts from the last fit draws the curve that fit
measured. At the fit's own values the residual pane and the Rwp header do not
move when the preview opens.

## Context

**Why it moved.** The GUI preview (`gui/preview.py`, WP-2125 and WP-2128)
compiles at `compile_model`'s windows, which drop 1e-3 of each peak's area
(`CLOSING_WINDOW_TOL`). Until WP-2222 a default fit ended on a closing stage at
the same windows, so the preview at the fit's values reproduced the fit to
1e-9. Since WP-2222 a default fit ends on the declared stages' 2 % windows
(`forward.WINDOW_AREA_TOL`). The preview then differs from the fit by the
tails: up to 0.13 % of the strongest peak on the fluorapatite example (26
counts on 20 310), and the Rwp header in its third digit. Yue accepted that
shift on 2026-11-19 (WP-2222 § Context, ruling 3) and asked for this
follow-up.

**Why the preview was not moved to 2 % in WP-2222.** Its three branches
(frozen, rewindowed, recompiled) test whether a frozen window is still big
enough, and the thresholds were measured at 1e-3 windows. At 2 % the same
estimates missed by up to 1.3 σ, against the 1e-9 the tests ask of a
rewindowed or recompiled answer.

**What to decide first.** Either the preview compiles at the window the last
fit's last stage ran at (`StageResult.window_area_tol`, which every stage
records), or it stays at 1e-3 and the curves route draws at 1e-3 too. The
first keeps the fit's numbers on screen. The second keeps the preview's
accuracy where it was measured. Both are a reader-output change and go to
Yue before merge.

## Tasks

- [ ] Measure the preview's three branches at 2 % windows on `fap` and `nac`
      (the `tests/test_gui_preview.py` cases), and the shift at the base
      values under each option above.
- [ ] Bring the choice to Yue with those numbers.
- [ ] Implement it, and restore exact agreement at the base values in
      `test_the_residuals_are_the_curves_route_s_at_the_last_fit` and
      `test_at_the_base_values_the_answer_is_frozen_and_the_last_fit`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_preview.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## Handover log

- **2026-11-19** — filed by WP-2222's session after Yue accepted the shift
  and asked for a follow-up.
