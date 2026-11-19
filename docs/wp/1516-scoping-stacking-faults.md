# WP-1516 — Scoping stacking faults: DIFFaX files first, a native model when it earns one

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: 1512 (the component any diffuse curve enters as); 1514 and 1515 soft (its milestone is placed after theirs)
Priority: P3 2026-09-28 — a scoping WP whose milestone ranks after 1514's and 1515's: one user so far, and a 40-minute workaround served them

## Goal

Two outcomes. First, the small rung that can land early, filed as its own
WP: DIFFaX input written from a `Structure` and a layer declaration, and its
output read into WP-1512's component. Second, a queued milestone draft for
a native model of faulted layer stacking, its route chosen by measurement.
Or, instead, a recorded decision to keep the native model fenced until a
second user asks. This WP builds nothing.

## Context

**Unfenced 2026-09-28.** "Stacking faults (DIFFaX-style recursion)" sat in
ROADMAP § v2+ with no issue. The grounds are in DESIGN.md § Locked
decisions, *Structure fence revised*. The same day this WP was re-scoped
from an implementation WP to a scoping one: the file-based rung is one WP,
and a native model is milestone-sized physics.

**What the source run did.** `solution case 1` (private corpus map § 5;
WP-1510 has the source). Electron diffraction showed heavy streaking along
the stacking axis, and the person asked for "the quantitative route".

1. **Source and build.** The DIFFaX distribution page now sits behind a
   sign-in wall, and `curl` saved the sign-in page as the `.tar.gz`. That
   was noticed only when `tar` failed. The source came from a 2010 Wayback
   snapshot and was compiled with one ad hoc `gfortran` line.
2. **Layers by hand.** Two layer types from the space-group operators and
   their inversion images. Scattering factors, Biso and wavelength were
   copied by hand into the input text. DIFFaX's own broadening was
   independent of rietx's profile.
3. **Diffuse by difference.** Faulted minus ideal, convolved with a
   hand-written Lorentzian. The difference carried spikes where Bragg peaks
   cancelled imperfectly. The person noticed them as "weird structure" in
   the background, and a 0.3° median filter removed them.
4. **Into the fit.** Through the background slot, with an outer refit loop.
   WP-1512 has the details, and why that slot breaks on today's tree.
5. **Probabilities by grid.** Switch and slip probabilities were scanned on
   grids of about 13 and 9 points. The minimum came from a three-point
   parabola and the esd from Δχ² = 1, against the agent's own Poisson
   weights. None of it went through the parameter table.
6. **The physics it needed.** In-plane translation faults broaden only some
   reflection classes, and 00l rows are immune to any in-plane slip. That is
   why strong streaking came with no powder width anomaly.

It took under 40 minutes from the request to the first joint fit, the build
included.

**Why a native model is milestone-sized.** It needs a layer schema and a
transition matrix; the recursion or a supercell generator; powder averaging
along the streaks; convolution with rietx's own instrument profile; a
separation of Bragg and diffuse parts that removes the spike problem by
construction; probabilities as parameters with esds; and a cost measurement,
since the calculation runs inside every residual evaluation. FAULTS is the
precedent for doing all of this as refinement (Casas-Cabanas et al. 2016).

**Two native routes.**
- The Treacy-Newsam-Deem recursion (1991), implemented from the paper.
- Supercell averaging, TOPAS's approach (Coelho, Evans & Lewis 2016).
  rietx's own Bragg machinery already evaluates a large P1 supercell: the
  source run built a 128-atom one to test an in-plane doubling. This route
  needs a generator and a cost measurement, and no new physics.

**Licences.** GSAS-II's LICENSE describes DIFFaX as "not copyrighted;
distributed with direct permission of M. Treacy". A review subagent read
that; re-read it before relying on it. So DIFFaX is not vendored. Writing
its input and reading its output are I/O. FAULTS ships with FullProf and
TOPAS is closed, so both are papers only (DESIGN.md § Locked decisions).
GSAS-II wraps DIFFaX rather than reimplementing it. DISCUS's licence is
unverified.

### Inherited

From **WP-1512** (closed 2026-11-18 as option A, Yue's ruling): the `Depends on: 1512 (the
component any diffuse curve enters as)` premise above changed. WP-1512 built no component. A
DIFFaX curve, or one from an in-house code, enters through the fixed-background slot
(`BackgroundFixedPlusChebyshev`, stored as c*·D) plus
`ref.tie("instrument.background.scale", "phases.0.scale")`; the manual's blank guide
(`docs/docs/guides/blank.md` § Hold a curve another program computed) has the route and what
the frozen curve costs under a zero shift. Yue also plans an in-house stacking-fault code
(2026-11-18).

## What the scoping decides

1. The DIFFaX I/O WP's scope, filed first.
2. Recursion or supercell averaging, by a measurement on one public case:
   cost per evaluation, and agreement with DIFFaX on the same input.
3. The layer schema, and where the calculation sits relative to the
   frozen-per-stage rule (a probability is continuous; the layer list is
   not).
4. The public corpus: faulted materials with public data and published
   models, such as the DIFFaX and FAULTS papers' own examples.
5. Milestone or fence. If a milestone, its placement after 1514's and
   1515's.

## Non-goals

- Building the native model. A throwaway spike to measure the two routes is
  allowed, and nothing from it merges.
- Turbostratic disorder, and total scattering (#192).
- Modulated structures (superspace, #258), still fenced.

## Tasks

- [ ] File the DIFFaX input/output WP, depending on 1512, before the rest of
      the scoping.
- [ ] Prior art with licences, searching the maintainer-local paper corpus
      first (root CLAUDE.md § Roadmap; its location is in the
      maintainer's memory).
- [ ] Measure the two native routes on one public case.
- [ ] The public corpus, with provenance for `tests/data/README.md`.
- [ ] The milestone draft, or the fence decision in ROADMAP. **Open any
      milestone's WPs in the next unused number block, checked against
      `origin/main` and the open PRs on the day you file.** A sibling
      scoping may be filing at the same time.
- [ ] The maintainer's decision recorded here. This WP closes on it.

## Acceptance

The DIFFaX I/O WP exists. Either the native model's milestone draft exists
(WP files, a queued ROADMAP section, the index regenerated) or ROADMAP's
fence records why it stays there. The maintainer's decision is recorded in
this file.

```sh
python3 .claude/hooks/wp_index.py
.venv/bin/python -m pytest tests/test_docs_consistency.py -n auto --dist loadgroup
```

## References

Verify each citation before quoting it in code.

- Treacy, M. M. J., Newsam, J. M. & Deem, M. W. (1991). *Proc. R. Soc. Lond.
  A* 433, 499–520. DIFFaX.
- Casas-Cabanas, M., Reynaud, M., Rikarte, J., Horbach, P. &
  Rodríguez-Carvajal, J. (2016). *J. Appl. Cryst.* 49, 2259–2269. FAULTS.
- Coelho, A. A., Evans, J. S. O. & Lewis, J. W. (2016). *J. Appl. Cryst.*
  49, 1740–1749. Supercell averaging.

## Handover log

- **2026-09-28** — created as an implementation WP and re-scoped the same
  day into this scoping WP: the file-based rung is one WP, and a native
  model is milestone-sized physics. Nothing started.
