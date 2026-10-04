# WP-1515 — Scoping structure solution: which routes, which corpus, how many milestones

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: — (1514 soft, the rigid bodies direct space needs; 1511 and 1513 soft, the verified cell and the contact census a search reads)
Priority: P2 2026-09-28 — a scoping WP: the track's aim, a structure out, waits on its route decision

## Goal

A queued milestone draft, or two, for solving a structure from a verified
cell. The draft decides which routes the package takes (direct space,
charge flipping, completion by difference Fourier), what corpus proves
each, and what a solution run looks like to an agent driving it: its inputs,
its anytime answer, and the evidence beside every candidate. This WP builds
nothing.

## Context

**Unfenced 2026-09-28.** "Structure solution from an indexed cell" sat in
ROADMAP § v2+ beside charge flipping (#198) and difference Fourier maps
(#197). The grounds are in DESIGN.md § Locked decisions, *Structure fence
revised*. The same day this WP was re-scoped from an implementation WP to a
scoping one, because it measured at milestone size or larger.

**Why it is milestone-sized.** The closest precedent is indexing: 30 WPs
numbered 1018–1049, 23 of them on engines, candidates and extinction.
Solution has the same parts: engines, a cost, a candidate list that must
never be a confident singleton, an acceptance corpus, an anytime answer on
the event ladder, a GUI panel and a skill shape. It also depends on 1514's
milestone.

**The routes.** The source run used direct space, which suits molecular and
metal-organic structures with known fragments. An inorganic unknown usually
goes through charge flipping on extracted intensities (#198). Any route ends
in completion by difference Fourier maps (#197). The track's aim covers both
classes of structure. So this scoping decides whether #197 and #198 leave
the fence with direct space, and in what order. The input they need already
exists: Le Bail extraction (`lebail_update`), and Pawley intensities with
their overlap flags (`PAWLEY_OVERLAP_UNRESOLVED`).

**What the source run measured.** `solution case 1` (private corpus map
§ 5; WP-1510 has the source).
- **Engine.** Parallel tempering with six replicas, temperatures geometric
  from 3 to 300 in χ² units, and neighbour swaps every 50 steps. One
  compiled `Refinement` was held for the run, with `predict()` per
  evaluation: 20-35 ms each. An earlier multistart calling `fit()` per trial
  took 10-20 s a trial.
- **Cost.** χ² plus a clash penalty plus a soft coordination prior built
  from what the person knew. Annealing on the profile alone reached a low χ²
  with chemically absurd coordination, so the prior was necessary.
- **Evidence.** Four independent runs from random starts converged on one
  chemistry class, their Rwp within 2 % of each other. Transplanting the
  analogue structure's coordinates did worse than a blind start.
- **Wall clock.** Batches ran 30-80 min each. Six Monitor watches expired
  with no events, and the person had to ask to see the leader.
- **The host.** The agent proposed GSAS-II and the person approved it. Its
  notes recorded an earlier pyobjcryst pipeline with untrustworthy results
  (a stale cached cost, a clash term the least-squares step ignored). It
  built on rietx's `predict()` instead. An agent with a fast evaluate path
  in the package it is already driving stays in that package.

**The cost function is the first measured choice.** The run used the full
profile χ² through `predict()`. DASH fits correlated integrated intensities
from a Pawley extraction, which is far cheaper per evaluation. Measure both
on one case.

**The corpus is the first gate.** That is indexing's lesson: its
low-symmetry real-data corpus is still fenced, and every scoreboard says
"high-symmetry" out loud. Candidate sources: the SDPD round robins; public
powder data deposited with published structures (pdCIF supplements); and
patterns simulated from COD entries. The COD search API finds structures by
formula, and some of its entries are wrong, so look at each before citing
it.

**The agent surface.** The person's knowledge goes in as declared data:
contents and Z, fragments, expected coordination, and contacts they rule
out. The answer is anytime, with a ceiling, in the shape WP-1042 gave
indexing. Progress streams on the event ladder so `rietx watch` draws the
leader. The answer is distinct solutions, ranked, with agreement across
seeds beside each. The winner is handed to a Rietveld plan. WP-1517 measures
the whole surface with real agents.

### Inherited

- **2026-10-03, from [1902](1902-the-solve-cost-as-a-quadratic-form.md),
  closed: WP-1904 is reserved.** Decided 2026-10-02 on issue #562: the
  Wyckoff-class enumeration claims WP-1904, a separate module
  (`crystallography/site_classes.py`, beside `wyckoff.py`, outside `solve/`)
  with its own acceptance across all 564 gemmi settings. Its file is written
  when its PR lands, or sooner if the reporter wants the number on record. Do
  not take 1904 for anything else.

- **2026-09-30, from the issue triage (issue #562, and its prototype
  comment): the reporter's scoping proposal for this WP.** Thirteen chunks
  S0-S9, six of them touching no v1.6 file. The design rests on one cost
  object, χ²(I) = χ²_Pawley,min + (I − I_P)ᵀM(I − I_P) with M = ΩᵀWΩ (1.8e-16
  on NAC), a ranked list with evidence and no `.structure`, and #197/#198
  leaving the fence with direct space in the order map, direct space, charge
  flipping. The comment reports a blind prototype on a private corpus of 23
  inorganic patterns (counts only, nothing about a specimen): 17 right, 15
  graded `high`, none of those wrong. It proposes amendments (a) to (g): a
  sparse-plus-low-rank M, Wyckoff-class enumeration from the start, a
  mandatory prior-off control arm, rival-margin and blind-contrast grade
  edits, S4 restated as incremental-move throughput, an adaptive ladder, and
  extraction seeding in the entry point. **The blind-contrast threshold is
  proposed, not validated, not coded**, and the Kabova et al. (2025)
  thresholds were taken from a summary, so neither is a constant yet.
  *Checked at `e3e6486a`*: `structure_factor.py`, `events.py` and
  `schemas/indexing.py` line numbers are on `4de25284` and `5ac3fc03` and
  were not re-measured. Eight questions are open, and the reporter asks in
  the comment whether S0 may open as the first PR. Those are the
  maintainer's. **Decided 2026-09-30:** the route is map, then direct space, then charge
  flipping, as one milestone (v1.9, block 19xx); #197 and #198 leave the fence
  (DESIGN.md § Structure fence revised, edited today; maximum-entropy maps stay
  fenced). Filed: WP-1901 (the map) and WP-1902 (the cost, doublet spike first).
  **Adversarial review the same day** (against `e3e6486a`): the χ² identity
  holds to 4e-16 about S0's own least-squares answer and only 1e-7 about fitted
  Pawley intensities and 2.4e-2 about Le Bail ones, so the floor is S0's own
  solve; the proposed identity test is tautological and the failing test is
  Ω·I against Rietveld `evaluate`; Le Bail and Pawley apply no per-line Lp, which
  a lab doublet needs (−0.6 % to +1.4 % over 20-130°), and NAC, single-line,
  hides it, so a FAP spike comes first. S2b and S7a are *not* free of v1.6 files
  (a new answer type or `Capabilities` field moves `SCHEMA_VERSION`, contested by
  WP-1343 and PR #522); S7b's constant is `PROJECT_FORMAT_VERSION`, not SCHEMA;
  `solve_engines`/`solve_presets` are registry arms, not `features` booleans, and
  the grade thresholds need a seventh versioned contract like
  `indexing_thresholds_version`. The Kabova et al. (2025) 5× bar is "worthy of
  close inspection", not a pass bar, and RMSD₁₅ < 0.35 Å compares with a
  DFT-D-optimised structure for molecular organics, never with deposited
  coordinates. The prototype's thresholds were tuned on about six negatives in a
  private corpus nobody can rerun, and "15 high, none wrong" is in-sample (rule
  of three: up to about 20 % false-high at 95 %), so grades ship provisional,
  under a versioned contract, validated on a public held-out set frozen first.
  The Wyckoff-class enumeration must reuse `symmetry.site_orbit` and
  `wyckoff.site_constraints` (a second orbit authority is the risk) and compile
  per assignment; it comes before S2a. Defer: S4 as a general kernel, S6a/b until
  a public case defeats direct space, S7b and S9. ATTRIBUTION.md needs rows for
  DASH (MIT), FOX (GPL-2), GALLOP (GPL-3), Superflip (no redistribution; clean
  room means never opening the package), TOPAS TR § 10.23, Kabova and Earl &
  Deem, plus README rows for COD (CC0) and IUCrData (CC-BY). Corpus files "at
  test time only" imply network fetches in the suite; the precedent is that
  no grant means not vendored. DASH is MIT (this file's References say
  commercial and are stale). Companion: #561,
  under WP-1514. Private-corpus figures stay out of the public tree unless
  the corpus is cited by number (root CLAUDE.md § Licensing).

## What the scoping decides

1. The routes and their order.
2. The cost function or functions, by measurement.
3. The engines. Parallel tempering first, and a second only after a
   measurement says the first falls short.
4. The corpus.
5. The answer type and its evidence.
6. The vocabulary of priors.
7. How many milestones, and their placement against 1514's.

## Non-goals

- Building any of it. A throwaway spike to measure the cost function is
  allowed, and nothing from it merges.
- Rigid bodies themselves (1514).

## Tasks

- [ ] Prior art with licences, searching the maintainer-local paper corpus
      first (root CLAUDE.md § Roadmap; its location is in the
      maintainer's memory).
- [ ] Measure the two cost functions on one public case: time per
      evaluation, and whether each finds the published structure.
- [ ] The corpus, with provenance for `tests/data/README.md`.
- [ ] The route decision for #197 and #198, and the fence line in ROADMAP
      that records it.
- [ ] The milestone draft or drafts: WP files, a ROADMAP section with the
      rows' order, and a DESIGN.md entry if a locked decision moves. **Open
      the milestone's WPs in the next unused number block, checked against
      `origin/main` and the open PRs on the day you file.** A sibling
      scoping may be filing at the same time.
- [ ] The maintainer's decision recorded here. This WP closes on it.

## Acceptance

The draft's WP files exist and are self-contained, ROADMAP carries the
queued section and the fence line for #197 and #198, and the index is
regenerated. The maintainer's route decision is recorded in this file.

```sh
python3 .claude/hooks/wp_index.py
.venv/bin/python -m pytest tests/test_docs_consistency.py -n auto --dist loadgroup
```

## References

Verify each citation before quoting it in code.

- Earl, D. J. & Deem, M. W. (2005). *Phys. Chem. Chem. Phys.* 7,
  3910–3916. Parallel tempering.
- David, W. I. F. et al. (2006). *J. Appl. Cryst.* 39, 910–915. DASH
  (commercial; papers only).
- Coelho, A. A. (2000). *J. Appl. Cryst.* 33, 899–908. TOPAS whole-profile
  annealing (closed; papers only).
- Favre-Nicolin, V. & Černý, R. (2002). *J. Appl. Cryst.* 35, 734–743. FOX
  (licence unverified).
- Oszlányi, G. & Sütő, A. (2004). *Acta Cryst.* A60, 134–141. Charge
  flipping.
- Palatinus, L. & Chapuis, G. (2007). *J. Appl. Cryst.* 40, 786–790.
  Superflip (licence unverified).
- Baerlocher, Ch., McCusker, L. B. & Palatinus, L. (2007). *Z. Kristallogr.*
  222, 47–53. Charge flipping on powder data.

## Handover log

- **2026-09-28** — created as an implementation WP and re-scoped the same
  day into this scoping WP, after indexing's size and the route question put
  it at milestone size or larger. Nothing started.
