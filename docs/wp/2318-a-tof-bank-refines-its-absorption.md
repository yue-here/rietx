# WP-2318 — a time-of-flight bank refines its absorption factor

Milestone: unscheduled · Status: ⬜
Track: The specimen is not an angle, and the neutron follow-through
Depends on: #1548
Priority: P3 2026-11-27 — a bank fit can bias Biso and occupancies with nothing to free (a P2 row, a path few fits run); down a rung until PR #1548 merges

## Goal

A time-of-flight bank can refine one sample absorption factor, µR per ångström,
applied at each reflection's own wavelength through rietx's one cylinder
function. It is off by default, and a constant-wavelength fit refuses it.

## Context

Issue #1867 (mustachefeeling) proposes it and carries a WP draft. The reporter
is building it on `feat/tof-absorption-factor`, a branch of their fork cut from
PR #1548's head, and opens the PR only after #1548 merges (their comment,
2026-11-27). The bank itself (`model/forward_tof.py`) arrives with #1548 and is
not on `main` yet.

**Today, at #1548's head `78c27cf36`.**

- `forward_tof._absorption_terms` returns `(a, b)` with µR(λ) = a·λ + b from the
  composition and `geometry.capillary_radius_mm`, frozen at stage compile.
- `CompiledTOFModel.absorption` applies `model.absorption.cylinder_absorption`
  (Rouse et al. 1970) per reflection, at the bank's fixed angle.
- `geometry.mu_r` and `geometry.mu_t` are refused. Nothing is refinable.
- `report/tof.py` emits `SPECIMEN_ABSORPTION_TOF` and
  `ABSORPTION_MU_R_OUT_OF_RANGE`; their help entries, audit rows and the rows in
  `docs/skill/rietx/references/tof.md` say the correction is computed.

**On `main`.** `Geometry.mu_r` is a plain float and never a `Parameter`: at one
wavelength a free µR is exactly a combination of scale and Biso
(`schemas/instrument.py`, `Geometry`'s docstring). A negative `mu_r` is refused,
and `_capillary_fields_need_debye_scherrer` limits it to a capillary. On a bank
the angle is fixed and λ varies, so a free factor is no longer that combination.

**The reported evidence is private.** On a vanadium-normalised bank dataset the
obs/calc ratio of single lines falls towards long d, in the Si standard as much
as in the sample. A black-box TOPAS run with one λ-linear attenuation removed the
trend. Not reproduced here: the data is not held.

**The sign (measured 2026-11-27, `main` at `172ce1c97`).** A vanadium spectrum
left uncorrected for its own absorption puts 1/A_V(λ) into the normalised data,
so the net factor is A_specimen/A_V. With `linear_attenuation_neutron` and
`cylinder_absorption`, radius 0.3 cm for both, a solid V rod (cell 27.6 Å³, 2
atoms) against Si powder at packing 0.6, 2θ = 90°, λ from 0.5 to 3.5 Å: µR_V runs
0.142 to 0.326, µR_Si 0.020 to 0.022, A_Si/A_V 1.22 to 1.62. The slope of
ln(A_Si/A_V) is +0.095 per Å, which this factor reproduces only at about
−0.06 Å⁻¹. The reported *falling* trend has the opposite sign, so that cause does
not produce it. `cylinder_absorption` evaluates at µR = −0.1 (1.188) and refuses
nothing.

### Decisions

- Decided 2026-11-27 (maintainer, approving the triage batch): this is its own PR
  after #1548 merges, one time-of-flight PR open at a time. The reporter chooses
  its order against T-5, the joint fit over several banks (#193). It left
  ROADMAP § v2+ that day.
- Design, answered on #1867 2026-11-27, settled by Claude under DESIGN-RULES
  Rules 4 and 5 and the 2026-11-23 delegation of API naming:
  1. The field is `instrument.geometry.mu_r_per_angstrom`, a refinable
     `Parameter`, default `None` (off). It follows `mu_r`; A_B is one program's
     symbol.
  2. It sits on `Geometry`, beside `mu_r` and `capillary_radius_mm`.
  3. The cylinder function stays Rouse.
  4. Declaring it together with `capillary_radius_mm` raises. Declaring it on a
     constant-wavelength pattern raises.
- Proposed on the thread, settled by Claude under the measurement above, and open
  to the reporter's answer: the field may go negative, and the report says a
  negative value is a net factor and not a specimen's µR. The question put to the
  reporter is which cause applies to their dataset (material in the specimen's
  beam only, or an over-corrected vanadium). Read the thread before Task 1.

**Comment:** https://github.com/yue-here/rietx/issues/1867#issuecomment-7224678689

### Rules this adds

The physics is the cylinder factor above with µ ∝ λ (the 1/v law). A negative
value lies outside Rouse's fitted 0 ≤ µR ≤ 1 and has no stated error, so what the
range diagnostic says about it is new judgement. No default and no automatic
action. No independent measurement of µR on a bank dataset is held, so the topic
ships **not yet validated**.

## Non-goals

- GSAS's Lobanov and alte da Veiga cylinder fit.
- A flat specimen on a bank.
- A joint fit over banks (T-5) and the magnetic term (T-6).
- Reading or reducing vanadium data: raw reduction is out of scope, ruled
  2026-11-16 (ROADMAP § v2+).
- A refinable µR at constant wavelength.

## Tasks

- [ ] The field and its refusals, each raising before any work and naming the fix:
      constant wavelength, the radius declared beside it, and a non-capillary
      specimen. #1548's refusal of `mu_r` on a bank names the new field.
- [ ] `forward_tof`: the factor is read per evaluation, enters the parameter table
      and gets its Jacobian column, with a `tests/test_cross_backend.py` row for
      each backend the bank then supports.
- [ ] Report the value with its esd and µR at both ends of the window; word the
      negative case.
- [ ] Audit row, help entry, `capabilities()` feature, and the manual's
      absorption equation with its source.
- [ ] Tests: off state bit-identical; with a = k the factor equals
      `cylinder_absorption(2θ_bank, k·λ)`; analytic column against central
      differences; a synthetic Si bank recovers a known factor and Biso, and fails
      without the factor; the refusals.
- [ ] Test: free the incident-spectrum coefficients (fixed by default) beside the
      factor and pin what the fit reports, since both are smooth in λ.
- [ ] Cross-code record: the same synthetic bank in TOPAS as a black box, nothing
      read.
- [ ] obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: update the two rows in `references/tof.md` that call the correction
      computed and not refinable, and add the field.

## Acceptance

A synthetic bank with a known factor recovers it and Biso within their esds, the
same bank without the factor shows the long-d misfit, and both misuses raise.

```sh
.venv/bin/python -m pytest tests/test_tof_absorption.py tests/test_cross_backend.py tests/test_help.py tests/test_audit_table.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Rouse, Cooper, York & Chakera (1970), *Acta Cryst.* A26, 682.
- Larson & Von Dreele (2004), LAUR 86-748, GSAS Technical Manual, p. 134, as
  quoted in #1867. The issue's two quotations were **not checked** on 2026-11-27:
  the manual is not held and two online copies could not be read.

## Handover log

- **2026-11-27** — created, from the 2026-11-27 issue triage (issue #1867). A
  bank fit has no way yet to refine an absorption trend in wavelength, and this
  file schedules one after PR #1548. Checked against the tree at `172ce1c97` and
  #1548's head `78c27cf36`: the issue's statements about the code hold; the sign
  measurement is in Context; no open WP owns it: 2146 is the ISIS iparm reader and
  2056 and 2070 are constant-wavelength neutron work. Next: wait for #1548, and
  read the reporter's reply on the sign.
