# WP-1455 — a TOPAS TCHZ profile reads in

Milestone: unscheduled · Status: 🔄 2026-11-17 — claimed by @mustachefeeling
Track: Coming from another code
Depends on: — (1433 soft: the `.inp` grammar the reader still refuses)
Priority: P3 2026-09-24 — a hand translation works; it cost an agent six source reads, and nothing checks the letters

## Goal

An instrument profile stated in TOPAS's `TCHZ_Peak_Type` form becomes an
`Instrument` without a hand translation, `Z` term included. So does the
goniometer radius, if the file's `Rs` is that radius. Each profile
parameter's help entry names its TOPAS equivalent.

## Context

**The evidence.** A 2026-09-24 transcript review read an agent session on a
private synchrotron in-situ series: `in-situ series 1` in the private
`yue-here/rietx-corpus-map`. Quote only what the runs did (CONTRIBUTING,
WP-1450). The instrument file came in TOPAS form: `prm` lines for U, V, W, Z,
X and Y, a zero shift, an axial term, and two radii (`Rp`, `Rs`). rietx has
no reader for it.

The agent spent six tool calls grepping the source for the width convention
and for what happens to a negative variance. `help_for` gave
Γ_G² = U·tan²θ + V·tanθ + W, but not how a Z term folds in. The file's own
W + Z is negative, so Γ_G² < 0 at low angle. `RESOLUTION_NOT_POSITIVE` fired
on the first fit, where U, V and W were free, and that finding was correct.
The agent then replaced them with (0, 0, 10⁻⁶) for the rest of the session,
reasoning that TOPAS clamps the negative variance to about zero. Nobody has
checked that.

`CAPILLARY_OFFSET_UNAVAILABLE` asked for a goniometer radius on 48 of 48
patterns of each final chain, and the agent never set one. TOPAS's `Rs` is
the secondary radius, which is probably the number that finding wants. Verify
the meaning before reading it in.

**The translation.** Take TOPAS's TCHZ Gaussian FWHM² as
U·tan²θ + V·tanθ + W + Z/cos²θ. Then Z/cos²θ = Z + Z·tan²θ, so Z folds
exactly into U + Z and W + Z, and rietx needs no new parameter. rietx's own
1/cos²θ Gaussian term is the per-phase sample size `P` (`gauss_size`,
`docs/manual/profiles.md` eq `prof-caglioti-g`), which is λ-scaled across
histograms (WP-1131). It is the wrong home for an instrument term.

For the Lorentzian, rietx's X is the 1/cosθ term and Y the tanθ term
(`help_for("instrument.profile.x")`). TOPAS appears to name them the other
way round, and the agent's translation swapped the letters to keep the
physics. **Every letter and unit here is to be measured against TOPAS's own
output, never adopted from its prose** (root CLAUDE.md, comparing against
another code).

**The seams.** `src/rietx/io/instrument_profile.py` holds the instrument-file
readers: GSAS-I `.prm` (`read_gsas_prm`) and GSAS-II `.instprm`. The TOPAS
`.inp` reader (`src/rietx/io/projects/topas.py`, `read_topas_inp`) builds a
`Structure` only. Its docstring says `to_structure` never builds an
`Instrument`, and the emission profile and geometry stay on `TopasModel`.
How to add a format, and what a reader may repair:
`src/rietx/io/CLAUDE.md`.

**Scope question.** A TOPAS profile arrives two ways. One is a
`TCHZ_Peak_Type(…)` macro call in an `.inp`. The other is a bare fragment of
named `prm` lines, which is what this session had. The fragment has no fixed
grammar, since the names are the user's. So the first cut is probably the
macro, with the fragment left to the caller and the help entries.

### Inherited

**From the 2026-09-25 review of a second session on the same series.** A
second agent session read the same instrument file and made the same
translation. It folded Z into U and W, set the file's 1/cosθ Lorentzian term
as rietx X and dropped the tanθ one as about zero. It replaced the Gaussian
terms with (0, 0, 10⁻⁶), because the folded variance is non-positive below
2θ ≈ 62°, which covers the whole fitted range. It got there with one
`help_for` call over the profile paths, against the first session's six source
reads. It also took `Rs` as the goniometer radius. `CAPILLARY_OFFSET_UNAVAILABLE`
then fired on 0 of 48 final results, against 48 of 48 in the first session.
That is consistent with the guess about `Rs` above, and it does not verify it.
Two sessions have now zeroed the Gaussian by hand, so what TOPAS does with a
negative variance is still the open question.

- **2026-10-08, from the issue triage (issue #732, step 3): the reader half
  of a whole TOPAS input.** #732 asks for `read_topas_inp(...).to_instrument()`
  for the parts the writer states, so that an instrument can round-trip
  through a `.inp` as it already does through `.instprm`, `.prm` and the
  profile JSON. This WP's task "Read `TCHZ_Peak_Type(…)` from an `.inp` into
  an `Instrument`" is that reader. The writer half went to WP-1911 with the
  rest of the issue. *Checked against the tree at 5d1f5f67*: `to_structure`
  builds no `Instrument`. `read_gsas_prm`, `read_gsas2_instprm` and
  `load_instrument_profile` each return one. Two facts move the work here:
  - The contributor reports measuring the X ↔ Y letter swap against TOPAS 6
    (#732's "M3"). That is the measurement this WP's first task asks for.
    The run's output is not in the tree, so it is evidence to ask for, not
    a constant to adopt.
  - PR #815 (open) writes the profile as `peak_type pv` with `pv_fwhm` and
    `pv_lor` equations, never as `TCHZ_Peak_Type`. A reader that reads only
    the macro would not read back what rietx writes. The reader task should
    say which forms it reads: the macro (what users bring), the writer's
    equations (what a round trip needs), or both.
  - *2026-10-11, from the issue triage (#732):* the first bullet is
    superseded. The reporter wrote at 07:41 that "M3" was a reading of the
    TCHZ macro and no TOPAS run, so it cannot be an oracle under their
    clean-room rule. At 08:09 they posted a black-box TOPAS 6 run instead:
    `case_nacl_xray` from #815, written with `TCHZ_Peak_Type`, every value
    distinct and fixed, Y_calc at zero cycles, LP canary 18/18. TOPAS 6
    accepts only the 12-argument form, and by position its six value slots
    are (u, v, w, z, x, y): slots 1-3 are Γ_G² += u tan²θ + v tanθ + w,
    slot 4 is Γ_G² += s4/cos²θ (no rietx term; it folds into U and W),
    slot 5 is Γ_L += s5 tanθ (`profile.y`), slot 6 is Γ_L += s6/cosθ
    (`profile.x`), each with factor 1. Rewritten as #815's equations under
    that reading, the runs reproduce TOPAS's Y_calc to 2.5e-9 and 1.1e-7. A
    second run swapping slots 4 and 5 swaps the inferred map. The Technical
    Reference's printed signature, taken by position, misses by 0.69 and
    0.091. So a reader maps by position, never by the file's names, which
    are user labels (`pkx` in some tutorial inputs, `pkz` in others). The
    reporter offers the inputs, outputs with SHA-256, scripts and provenance
    as fixtures, which is this WP's first task. No reply on the thread yet.
    Checked against the tree at 7d9be3cb: no file under `tests/data/`
    mentions TCHZ (the same session's X-ray extinction run is there, as
    `topas_export_nacl_xray_ext20_ycalc.txt` from #839), and `to_structure`
    still builds no `Instrument`.

## Non-goals

- Fundamental parameters beyond one radius (`Rp`, TOPAS's full axial model).
  FPA is fenced to v2.
- Writing TOPAS profiles out.

## Tasks

- [ ] Measure the letters and units against TOPAS's own output. Archive
      file 8 in the private corpus map is a TCHZ `.inp`; cite it by number
      (WP-1450). Where the archive holds no TOPAS output, say so and measure
      against the published TCHZ definition instead.
- [ ] Verify what `Rs` means against the TOPAS Technical Reference, and read
      it into `goniometer_radius_mm` if it is that radius.
- [ ] Help entries: each `instrument.profile.*` entry names its TOPAS and
      GSAS-II equivalent, and U and W say how a Z term folds into them.
      `tests/test_help.py` crosses the vocabulary both ways.
- [ ] Read `TCHZ_Peak_Type(…)` from an `.inp` into an `Instrument`, beside
      the GSAS readers or through `read_topas_inp`. Decide which, and write it
      here.
- [ ] Tests: a synthetic `.inp` with a nonzero Z round-trips to the same
      Γ_G(θ) to 1e-12 across 5-150°. The Z fold is algebra, so this tolerance
      is exactness, not a measured spread.
- [ ] Skill: one line in `references/api.md`'s reader list, generated.

## Acceptance

A TCHZ `.inp` reads to an `Instrument` whose Γ_G and Γ_L match the bar task
1 established: TOPAS's own output where the archive holds one, the published
definition otherwise. The WP says which bar was used.

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_projects_topas.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Thompson, P., Cox, D. E. & Hastings, J. B. (1987). *J. Appl. Cryst.*
  **20**, 79.
- Coelho, A. A. TOPAS-Academic Technical Reference, `TCHZ_Peak_Type` and the
  goniometer radii.
- WP-1118 (the TOPAS reader), WP-1437 (the help formulas' audit), WP-1454
  (the diagnostic flood that hid the radius finding).

## Handover log

- **2026-09-24** — created from the review of an agent session on a private
  series. The readers and the absent TCHZ handling were checked against the
  tree at `2d42303a`. The Z fold is algebra; the TOPAS letters and `Rs` are
  unverified. Next: measure the letters.
