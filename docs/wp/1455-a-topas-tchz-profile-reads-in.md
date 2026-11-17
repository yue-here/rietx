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

### The measurement and the two reviews (folded from Inherited, 2026-11-17)

- **The second review (2026-09-25)** read the same instrument file and made the
  same translation in one `help_for` call: Z folded into U and W, the file's
  1/cosθ Lorentzian term as rietx X, the tanθ one dropped as about zero, and
  `Rs` taken as the goniometer radius, after which
  `CAPILLARY_OFFSET_UNAVAILABLE` fired on 0 of 48 results against 48 of 48 in
  the first session. Both sessions zeroed the Gaussian by hand because the
  folded W + Z was negative, so **what TOPAS does with a negative Gaussian
  variance is still unmeasured**; the reader refuses it (Tasks, item 4).
- **The letters are measured** (issue #732, 2026-10-08): a black-box TOPAS 6
  run of our own `case_nacl_xray` written with `TCHZ_Peak_Type`, every value
  distinct and fixed, `iters 0`. By position the six value slots act as (U, V,
  W, Z, X, Y) in the formula's letters: Γ_G² += v1·tan²θ + v2·tanθ + v3 +
  v4/cos²θ, Γ_L += v5·tanθ + v6/cosθ, each factor 1. Rewritten as `pv_fwhm`/
  `pv_lor` equations under that reading, TOPAS reproduces its own TCHZ Y_calc
  to 2.5e-9 and 1.1e-7; the Technical Reference's printed signature
  `(u, uv, v, vv, w, wv, x, xv, y, yv, z, zv)` by position misses by 0.69 and
  0.091. TOPAS 6 refuses the ten-argument form. A reader maps by position,
  never by the file's names (`pkx` in some tutorial inputs, `pkz` in others).
  The run's inputs and outputs are this WP's fixtures
  (`tests/data/topas_tchz_nacl_xray_run1[01]*`, README rows); the report is in
  the maintainer-local planning tree.
- **#732's reader half is this WP; its writer half is WP-1911.** #815 writes
  the profile as `peak_type pv` with `pv_fwhm`/`pv_lor` equations, so this
  reader does not read back what rietx writes; it reads the macro, which is
  what users bring. Reading the writer's equations back is left to WP-1911's
  round trip.

## Non-goals

- Fundamental parameters beyond one radius (`Rp`, TOPAS's full axial model).
  FPA is fenced to v2.
- Writing TOPAS profiles out.

## Tasks

- [x] Measure the letters and units against TOPAS's own output. Archive
      file 8 in the private corpus map is a TCHZ `.inp`; cite it by number
      (WP-1450). Where the archive holds no TOPAS output, say so and measure
      against the published TCHZ definition instead.
      *Done 2026-11-17 against TOPAS 6's own output, a better bar than either:
      the #732 black-box runs of our own synthetic case (Context, the
      measurement), committed as fixtures with README rows. Archive file 8 was
      not needed: its own TOPAS output would measure the same slots on private
      numbers, and a synthetic input can be shipped.*
- [x] Verify what `Rs` means against the TOPAS Technical Reference, and read
      it into `goniometer_radius_mm` if it is that radius.
      *Done: the v6 TR (2015) names `Rs` the secondary radius (§ 2.11, p. 15;
      keyword `[Rp #] [Rs #]`, p. 139, default 217.5 mm) and divides a
      specimen displacement by it (`th2_offset = -2 Rad (c) Cos(Th) / Rs;`,
      p. 144), which is what `goniometer_radius_mm` does. Read from `Rs`,
      `Radius(r)` and `Radius(r, r)` into `TopasModel.secondary_radii`; one
      value is the radius, two different ones are refused by `to_instrument`.
      `Radius(a, b)` with a ≠ b is not read: its printed order is
      `(rp, rs)`, but the TCHZ macro's printed order proved wrong, and no run
      measures this one (`TopasModel.radius_unordered`). The old reader took
      `Radius`'s first argument, which is `Rp` by the printed order.*
- [x] Help entries: each `instrument.profile.*` entry names its TOPAS and
      GSAS-II equivalent, and U and W say how a Z term folds into them.
      `tests/test_help.py` crosses the vocabulary both ways.
      *Done: the TCHZ slot by position and the GSAS-II letter with its unit
      factor (`instprm_factor`), pinned against `TCHZ_SLOT_TERMS` by
      `test_topas_tchz.py::test_each_profile_entry_names_its_topas_and_gsas2_equivalent`.*
- [x] Read `TCHZ_Peak_Type(…)` from an `.inp` into an `Instrument`, beside
      the GSAS readers or through `read_topas_inp`. Decide which, and write it
      here.
      *Decided: through `read_topas_inp`, which already parses the file's
      symbols, blocks and phases. It records every call on `TopasModel.tchz`
      (`TopasTCHZ`: args, six values by position, refine flags, owning phase)
      and judges nothing, so a structure import never fails on a profile;
      `rietx.io.projects.topas.to_instrument(model, instrument, *, phase=None)`
      maps and refuses, beside `to_structure`. The caller's `instrument`
      supplies the source and geometry kind (as `TopasModel.geometry` already
      advises); the five profile terms come back `vary=False`. Refused by
      name: no call, a call without twelve arguments, a slot that does not
      resolve, differing calls without `phase=`, W = v3 + v4 < 0 or X < 0
      (the GSAS-II reader's rule; TOPAS's behaviour is unmeasured), a
      Lorentzian negative below 180°, two secondary radii. Reads the macro
      only: the writer's `pv_fwhm`/`pv_lor` equations stay WP-1911's.*
- [x] Tests: a synthetic `.inp` with a nonzero Z round-trips to the same
      Γ_G(θ) to 1e-12 across 5-150°. The Z fold is algebra, so this tolerance
      is exactness, not a measured spread.
      *Done: `tests/test_topas_tchz.py`. Γ_G and Γ_L to 1e-12 over 2901
      angles, Z dropped misses by > 1e-3; and against TOPAS's own Y_calc,
      runs 10 and 11 at 2.1e-3 and 2.5e-3 with the signature-order arm at
      0.41 and 0.087, and run 10's slots against run 11 missing.*
- [x] Skill: one line in `references/api.md`'s reader list, generated.
      *Done in `api-io.md`, where the readers moved: one sentence in the
      instrument-files row and `to_instrument`'s generated entry (+571 B).*

## Acceptance

A TCHZ `.inp` reads to an `Instrument` whose Γ_G and Γ_L match the bar task
1 established: TOPAS's own output where the archive holds one, the published
definition otherwise. The WP says which bar was used.

```sh
.venv/bin/python -m pytest tests/test_help.py tests/test_projects_topas.py tests/test_topas_tchz.py -q
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
