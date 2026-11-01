# WP-2037: before and after, worked on FAP

Every **before** block marked *measured* is verbatim output of `main` (5d64a86) on 2026-10-23,
from the skill's worked default on FAP (`examples/skill_worked_default.py`, Cu Kα
Bragg-Brentano, `mccusker_structural`). Every **after** block is a mock-up of the
WP's four clauses; the numbers in it are the measured ones, the layout is proposed.
Only the `diagnostics:` section of each summary is shown; the stage, report, protocol
and agreement lines around it do not change.

The four measured diagnostics, for reference:

| code | level | where | bears on |
|---|---|---|---|
| `SITE_SNAPPED_TO_SPECIAL_POSITION` | warning | `phases.0.atoms.0` | nothing: the shift is 3.3e-11, the CIF's own rounding |
| `FLOOR_HIT` | warning | `phases.0.extinction` | an ADP or scale read from this fit |
| `RESOLUTION_UNCONSTRAINED` | warning | `instrument.profile.u`, `.v`, `.w` | a width, size or strain |
| `PATTERN_UNDERSAMPLED` | warning | none | any intensity-derived number |

Under the WP: the first goes silent at tier 1 (snap floor from the file's
precision); the second is a warning under `structure`; the third under `microstructure`
and `calibration`; the fourth declares scope `qpa, structure` in its audit row, having
no `where`.

---

## 1. `ref.summary()` with no deliverable

**Before** (measured, 3 829 characters in all; this section is 1 433 of them):

```
  diagnostics: 4 unresolved
    warning[SITE_SNAPPED_TO_SPECIAL_POSITION]: 1 site(s) in phase 'fluorapatite' lie within 0.0001 of a special position of 'P 63/m' and were expanded there: Ca1 (3.3e-11 → multiplicity 4). The largest shift is 3.33e-11 in fractional coordinates.
      at: phases.0.atoms.0
      help: Check these multiplicities against the source file.
    warning[FLOOR_HIT]: phases.0.extinction refined to its floor (ρ=+0.057).
      at: phases.0.extinction
      help: Quote an upper limit instead of a value, or remove the parameter if its phase or term is unsupported. For a displacement parameter, check absorption, species and occupancy.
    warning[RESOLUTION_UNCONSTRAINED]: U, V, W refined on a predominantly Lorentzian pattern (Γ_L exceeds Γ_G at 4133 of 5753 fitted points; the Gaussian carries 45% of the width).
      at: instrument.profile.u, instrument.profile.v, instrument.profile.w
      help: Calibrate on a standard with lab_calibrate (certified cell held fixed) and save_instrument_profile, then load_instrument_profile before this fit. Until then, do not quote the widths, or any size or strain read from them.
    warning[PATTERN_UNDERSAMPLED]: The median fitted peak spans 4.6 steps across its FWHM (76 peaks), below the 5 the guidelines ask for.
      help: Re-collect at a step near FWHM/5 if the intensities must be quotable.
```

Four rows the skill tells the agent to act on. One is rounding. One voids a claim the
worked default never makes. The header says "unresolved" about all four.

**After** (mock-up):

```
  diagnostics: 3 rows, 0 error; no deliverable given, so none is printed in full
    FLOOR_HIT at phases.0.extinction: warning under structure
    RESOLUTION_UNCONSTRAINED at instrument.profile.u, .v, .w: warning under microstructure, calibration
    PATTERN_UNDERSAMPLED: warning under qpa, structure
    pass deliverable= for the rows that decide your purpose; every row is in result.diagnostics
```

The last line is the reading rule. It lives in the output, so the skill's § 4 can drop
"act on each `d.suggestion`" and say only: *declare your purpose with `deliverable=`
and act on the warnings printed under it.*

---

## 2. `ref.summary(deliverable="structure")`

**Before** (measured): the same four rows as § 1, in full, followed by the
`deliverable: structure` block. 4 114 characters.

**After** (mock-up):

```
  diagnostics under structure: 2 warnings, 0 errors, 1 info
    warning[FLOOR_HIT]: phases.0.extinction refined to its floor (ρ=+0.057).
      at: phases.0.extinction
      help: Quote an upper limit instead of a value, or remove the parameter if its phase or term is unsupported. For a displacement parameter, check absorption, species and occupancy.
    warning[PATTERN_UNDERSAMPLED]: The median fitted peak spans 4.6 steps across its FWHM (76 peaks), below the 5 the guidelines ask for.
      help: Re-collect at a step near FWHM/5 if the intensities must be quotable.
    info: RESOLUTION_UNCONSTRAINED at instrument.profile.u, .v, .w (warning under microstructure, calibration)
```

Two rows to act on, both about what a structure quotes. The third is one line, and it
says where it would matter.

---

## 3. `ref.summary(deliverable="cell")`

**Before** (measured):

```
ValueError: unknown deliverable 'cell'; one of 'phase_id', 'qpa', 'structure', 'series'
```

**After** (mock-up). No warning touches a cell path, so every row is `info` here:

```
  diagnostics under cell: 0 warnings, 0 errors, 3 info
    info: FLOOR_HIT at phases.0.extinction (warning under structure)
    info: RESOLUTION_UNCONSTRAINED at instrument.profile.u, .v, .w (warning under microstructure, calibration)
    info: PATTERN_UNDERSAMPLED (warning under qpa, structure)
  deliverable: cell
    phases.0.cell.a = 9.36713(5) Å, c = 6.88453(6) Å
    exchangeability: 2 row(s)
      instrument.geometry.sample_displacement ~ phases.0.cell.a, phases.0.cell.c, instrument.zero_shift (R²=1.00)
      instrument.geometry.sample_transparency ~ phases.0.cell.a, phases.0.cell.c, instrument.zero_shift (R²=0.98)
```

The exchange rows are the ones that decide a cell on this instrument, and they are
already computed. The cell values are illustrative; the deliverable block for `cell` is
new work in `_deliverable_lines`.

---

## 4. `ref.summary(deliverable="microstructure")`

**After** (mock-up):

```
  diagnostics under microstructure: 1 warning, 0 errors, 2 info
    warning[RESOLUTION_UNCONSTRAINED]: U, V, W refined on a predominantly Lorentzian pattern (Γ_L exceeds Γ_G at 4133 of 5753 fitted points; the Gaussian carries 45% of the width).
      at: instrument.profile.u, instrument.profile.v, instrument.profile.w
      help: Calibrate on a standard with lab_calibrate (certified cell held fixed) and save_instrument_profile, then load_instrument_profile before this fit. Until then, do not quote the widths, or any size or strain read from them.
    info: FLOOR_HIT at phases.0.extinction (warning under structure)
    info: PATTERN_UNDERSAMPLED (warning under qpa, structure)
  deliverable: microstructure
    size: not quotable (RESOLUTION_UNCONSTRAINED)
```

The same code that was one line under `structure` is the whole story here.

---

## 5. A demotion: `SEQUENTIAL_DISCONTINUITY` (clause 1)

WP-2003 will demote the discontinuity test (5× median and 3σ, tier 3). Two shapes.

**Before** (as § Demotion rules it today; not yet on `main`): the code becomes an `info`
record with no threshold that fires on every series run and lists every step, largest
first. On a 68-pattern ramp, `SeriesResult.summary()` would print:

```
  diagnostics: 1 unresolved
    info[SEQUENTIAL_STEP_SIZES]: Largest steps along the chain, in esds: phases.0.cell.a 4.1σ at 23→24, 2.9σ at 51→52, 2.2σ at 11→12, ... (68 steps listed)
      help: A step may be a transition, a sample shift or a wrong model; only the sample history can say which.
```

Every series carries this row, and the skill says to act on it.

**After** (mock-up): the statistic is a field, the help is keyed to the field, and no
diagnostic fires.

```python
>>> series.steps                      # SeriesResult.steps: list[Step], largest first
[Step(path='phases.0.cell.a', at=(23, 24), size_esd=4.1), Step(path=..., size_esd=2.9), ...]
>>> rx.explain("SeriesResult.steps")
steps: every parameter's change between consecutive patterns, in esds of the later
fit, largest first. A step may be a transition, a sample shift or a wrong model, and
only the sample history can say which; rietx enforces no threshold on it.
```

and the series summary carries one line in its trajectory block, not its diagnostics:

```
  trajectory: 68 patterns, largest step phases.0.cell.a 4.1σ at 23→24 (series.steps)
```

The GUI's series panel plots `series.steps` beside the trajectory. The number is in
three places and is a message in none.

---

## 6. The caller sets the response (clause 4)

A pipeline that cannot tolerate undersampled data, and an expert who has decided the
extinction floor is the expected state for this specimen:

```python
>>> print(ref.summary(deliverable="structure",
...                   levels={"PATTERN_UNDERSAMPLED": "deny", "FLOOR_HIT": "allow"}))
  diagnostics under structure: 0 warnings, 1 error, 2 info (1 level set by caller)
    error[PATTERN_UNDERSAMPLED]: The median fitted peak spans 4.6 steps across its FWHM (76 peaks), below the 5 the guidelines ask for.
      help: Re-collect at a step near FWHM/5 if the intensities must be quotable.
    info: FLOOR_HIT at phases.0.extinction (allowed by caller)
    info: RESOLUTION_UNCONSTRAINED at instrument.profile.u, .v, .w (warning under microstructure, calibration)
```

The same map in `rx.settings` applies to every summary and to `result.usable`, which
then reads a caller's `deny` as an error. The audited default is untouched; the audit
row for the override is `caller`, no tier.

---

## 7. A batch of 200 fits (the aggregate)

A pipeline agent fitting a tray of related specimens, nobody reading any one summary:

```python
>>> rx.diagnostics_summary(results, deliverable="qpa")
diagnostics over 200 fits under qpa
  fits with an error:     3   (result.usable False)
  fits with a warning:   41
  warnings per fit:     0.26 median 0, max 4
  by code (firing rate, response under qpa):
    PATTERN_UNDERSAMPLED          200/200  warning   <- fires on every fit: check the suite, not the code
    PHASE_UNCONSTRAINED            38/200  warning
    HIGH_CORRELATION               22/200  info
    FLOOR_HIT                      17/200  info
    BOUND_HIT                       3/200  error
```

The first row is the triage: a code firing on every fit in a batch tells the pipeline
nothing about any one fit and tells the maintainer the batch shares the fault (one
instrument, one step size). The same function, run over the acceptance suites in CI,
is the WP's suite metric. The arrow is a prompt to look, not a verdict on the code.

---

## 8. The audit table (clause 2's two tables)

**Before** (`rietx._audit`, today):

```python
Row("RESOLUTION_UNCONSTRAINED", "code"),                     # tier unaudited
Row("PATTERN_UNDERSAMPLED", "code"),
```

**After** (mock-up). One response column per code; scope only where the code carries
no `where`:

```python
Row("RESOLUTION_UNCONSTRAINED", "code", tier=2, response="warning",
    responds="do not quote a width, size or strain from this fit; calibrate first",
    evidence="...", grounds="..."),
Row("PATTERN_UNDERSAMPLED", "code", tier=2, response="warning", scope=("qpa", "structure"),
    responds="do not quote an intensity-derived number; re-collect at FWHM/5",
    evidence="McCusker 1999 §3, five to ten steps per FWHM", grounds="..."),
```

and the purpose table, once:

```python
PURPOSES = {
    "cell":           Purpose(depends=("phases.*.cell.*", "instrument.zero_shift",
                                       "instrument.geometry.sample_*"),
                              why="position corrections exchange with the cell (report.identifiability)"),
    "qpa":            Purpose(depends=("phases.*.scale", "phases.*.atoms.*.occ", "phases.*.atoms.*.biso",
                                       "phases.*.texture.*", "instrument.background.*",
                                       "instrument.geometry.mu_*"),
                              why="scale, Biso and absorption are one group (skill §3); background absorbs scale (WP-1055)"),
    "microstructure": Purpose(depends=("instrument.profile.*", "phases.*.lor_*", "phases.*.gauss_*",
                                       "phases.*.microstrain.*"),
                              why="sample broadening is read against the instrument's (WP-1131)"),
    ...
}
```

A meta-test fails a `warning` row whose `responds` sentence names no result number or
plan outcome, a code with no `where` at any raise site and no `scope`, and a purpose
whose globs match no live path.

---

## 9. The skill's § 4 sentence

**Before** (`docs/skill/rietx/SKILL.md`):

> `print(result)` shows per-stage status, the diagnostics, provenance, and the
> agreement indices last. Act on each `d.suggestion`, then grep its code.

**After**:

> Declare your purpose with `ref.summary(deliverable=…)` and act on the warnings it
> prints under that purpose. `result.diagnostics` holds every row.

The rest of the rule now lives in the summary's own last line (§ 1), where no skill
upgrade can leave it stale.
