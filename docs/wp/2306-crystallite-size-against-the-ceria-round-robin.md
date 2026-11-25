# WP-2306 — Crystallite size, validated against the IUCr ceria size-strain round robin

Milestone: unscheduled · Status: ⬜
Track: The fit has no reference
Depends on: 2010 (the feature registry and the `reference_kind` join, PR #1266)
Priority: P3 2026-11-23 — a validation row over published data; changes no number a user gets, but gives the size side of microstructure its first independent referent

## Goal

The validation matrix carries a row per usable instrument of the IUCr CPD size-strain round
robin (Balzar et al. 2004): the instrument profile fitted on the annealed ceria standard, the
broadened ceria fitted with that profile held, and rietx's crystallite size compared with the
paper's published spread for the same quantity. The row states what it does not validate:
strain.

## Context

**Source.** Issue #1724 (2026-11-20, @mustachefeeling), filed after the maintainer's answer 5
on #1051 ("file issues for references that lift a feature"). WP-2010's task list names this
follow-up ("the ceria round robin as a microstructure measurement"), and its Non-goals call it
the first one. Under #1051's Rule 2, a published measurement by other laboratories on the same
specimen is an independent measurement, so a `prediction` claim against it with
`reference_kind = "independent_measurement"` validates (WP-2010's `validates()`, landing in
PR #1266). WP-2072 is the same shape for the SRM 660c cell and is the model to copy.

**The reference.** Balzar, D. et al. (2004), *J. Appl. Cryst.* **37**, 911-924,
doi:10.1107/S0021889804022551. Specimen S1 is nanocrystalline CeO₂ (hydrated ceria heated at
923 K for 45 h); S2 is commercial ceria annealed at 1573 K for 3 h, the instrumental standard.
Both were measured on several instruments. The paper certifies nothing: its numbers are
participants' results and their spread. The reporter's reading (not re-derived in triage):
volume-weighted size D_V of 223(5) to 232(19) Å across instruments and area-weighted D_A of
167(3) to 174(12) Å from the lognormal fit (Table 2); an average real diameter of 191(5) Å
(spheres, strain neglected); isotropic broadening ("very small if nonexistent anisotropy");
a size-profile Gaussian-to-Lorentzian integral-breadth ratio of 0.704 to 1.01 from Rietveld
(Table 4); a strain-free Rietveld average of 226(9) Å (the paper's eq. 20); and, as a negative
control, Gaussian size broadening misread as strain when only the Lorentzian size term is
refined (226 Å becomes 390 Å).

**The data, as the page lists it** (https://mysite.du.edu/~balzar/s-s_rr.htm, read
2026-11-23). Each pair is a "sh" (sharp, S2) and a "br" (broadened, S1) pattern:

| files | laboratory | formats on the page |
|---|---|---|
| `lebailsh`/`lebailbr` | Le Mans, lab Cu Kα₁/Kα₂, P = 0.8 | .xy, .gs, .dbw |
| `langfsh1-3`/`langfbr1-3` | Birmingham, lab, incident-beam monochromator, three ranges | .xy, .gs, .dbw |
| `stephsh`/`stephbr` | the NSLS synchrotron set (by name) | .xy |
| `massonsh`/`massonbr` | the ESRF synchrotron set (by name) | .xy |
| `hewsh`/`hewbr` | a CW neutron set (by name; the page says which) | .xy, .gs, .dbw |
| `tobysh`/`tobybr` | a CW neutron set (by name; the page says which) | .gs only |
| `daymsh`/`daymbr` | the TOF set (by name) | .gs only |

The instrument for each file was inferred from the participant's name and is to be confirmed
from the page's own text before a row is written. The `.xy` files carry 2θ, counts and an esd
where one was measured. **Neutron TOF is fenced** (ROADMAP § v2+), so the TOF pair is out of
scope, which leaves at most six instruments. A `.gs`-only set needs `read_pattern` to read
that GSAS file; check it does before counting the row.

**Data status.** The page states no licence or terms (checked 2026-11-23: no "licence",
"copyright", "terms" or "permission" in its text). OpenAlex lists the article as hybrid open
access, which covers the paper and not the files. The tree's precedent is `tests/data/qarr/*.prn`,
the IUCr CPD QPA round-robin patterns: in `tests/data/`, never in the wheel, and for that
reason never an example project (WP-1204). Whether the same holds for these files is a
licensing call and is the maintainer's (root CLAUDE.md § Licensing). Until it is made, the
work can run against a local copy in the maintainer's local-only data root, with the test a
`slow` opt-in that skips by name where the files are absent.

**What rietx reports, and the comparison it needs.** The instrument ⊕ sample split is in
place (root CLAUDE.md § Conventions): Gaussian variances add, Lorentzian FWHMs add, and the
phase's `gauss_size` and `lor_size` are the size terms. `model/microstructure.py` reports
each mechanism's Gaussian and Lorentzian reading **separately**, through Scherrer on the
**FWHM** with `caglioti.SCHERRER_K` = 0.9, and deliberately never combines them, since a
combined number is a function of two correlated columns. The paper's Rietveld sizes are
volume-weighted domain sizes from the integral breadth of the size Voigt. So the comparison
needs one derived number from both columns, with its esd through the covariance
(`model/geometry.py`'s J·Cov·Jᵀ; root CLAUDE.md, the WP-1072 invariant), and it needs the
paper's definition of each published number matched to that quantity first: column length
against sphere diameter, integral breadth against FWHM, and which K.

**The tier of what this adds.** No new heuristic in the package. The bar is a published
spread, quoted from the paper and never tuned (Rule 2's referent). A test-side helper that
combines the two size readings is not a package surface; if it becomes one, it needs its
`help.py` entry, its Theory equation and its `_audit` row.

### Inherited

None yet.

## Non-goals

- Strain. The paper reports strain as small and method-dependent, so a strain number from it
  is a spread across methods and validates nothing. The negative control (Gaussian size read
  as strain) is in scope because it is a size claim.
- Anisotropic size. WP-2061 owns hkl-dependent size and cites this data set as its isotropic
  control; this WP gives it that control and adds no anisotropic model.
- Neutron TOF (fenced, ROADMAP § v2+).
- A new package output for a combined size. Decide it in its own WP if the test helper earns
  a public twin.

## Tasks

- [ ] The maintainer's call on the data: vendor the files into `tests/data/` beside
      `qarr/*.prn`, or keep them local with a `slow` opt-in. Ask the page's author first if
      the session prefers a stated licence.
- [ ] Read Balzar et al. (2004) through the paper-reader skill and settle, per published
      number, which quantity it is (D_V, D_A, average diameter; integral breadth or FWHM;
      K). Pick the one rietx's two size columns can be converted to, and write the
      conversion with its source line.
- [ ] Confirm each file's instrument from the page, and that `read_pattern` reads each
      `.xy` (esd column) and the `.gs`-only CW neutron set. Record the polarisation P the
      page gives per X-ray set.
- [ ] Per instrument: fit S2 for the instrument profile (`lab_calibrate`-style, cell free,
      since S2 has no certificate), `save_instrument_profile`, then fit S1 with
      `load_instrument_profile` and both size terms free. Mirror the paper's protocol where
      it states one (transparency and displacement on the flat-plate sets).
- [ ] The comparison: the combined size with its esd through the covariance, against the
      published spread for the same quantity, the spread stated as a spread and not as an
      esd. Both size widths non-zero. The isotropy check reports no hkl-dependent width.
- [ ] The negative control: the S1 fit with only `lor_size` free inflates the strain or the
      size the way the paper reports, and the test pins the direction, never the landing.
- [ ] The validation-matrix claim per instrument, `reference_kind = "independent_measurement"`,
      once PR #1266 lands; the rows state that the patterns were not used in development
      and that strain is not validated.
- [ ] Tests (acceptance, `slow`) + obs/calc/diff PNGs to `tests/output/` for every S1 and S2
      fit.
- [ ] Skill: none expected, since the row is a validation record. Check
      `references/judging.md`'s size passage (a coherent domain size from the two 1/cosθ
      terms) against the conversion the second task settles.

## Acceptance

Every usable instrument's S1 size, converted to the paper's quantity, lies inside the paper's
published spread for that quantity, and each matrix row says what it validates and what it
does not.

```sh
.venv/bin/python -m pytest tests/test_acceptance_ceria_round_robin.py -m slow
.venv/bin/python -m ruff check src tests examples
```

## References

- Balzar, D. et al. (2004). Size-strain line-broadening analysis of the ceria round-robin
  sample. *J. Appl. Cryst.* **37**, 911-924. doi:10.1107/S0021889804022551.
- The data page: https://mysite.du.edu/~balzar/s-s_rr.htm.
- WP-2010 (the registry and Rule 2), WP-2072 (the same shape for the SRM 660c cell), WP-2061
  (anisotropic size; this is its isotropic control).

## Handover log

- **2026-11-23** — created, from the 2026-11-23 issue triage (issue #1724). Checked against
  the tree at 711acfc8d: no test, fixture or WP references the round-robin data (no
  `Balzar` or `ceria` match in `tests/`; WP-2010 names it as an unfiled follow-up and WP-2061
  as a future control); `microstructure.py` reports the Gaussian and Lorentzian size readings
  separately on the FWHM with K = 0.9, so the comparison needs the combination and the
  quantity match recorded in Context. The data page was read: it lists seven pairs and states
  no terms. No open WP owns it: WP-2010 asks for it to be filed as its own WP, and WP-2061
  only consumes it. The reporter's published numbers were not re-derived. Next: the
  maintainer's data call, then the paper read.
