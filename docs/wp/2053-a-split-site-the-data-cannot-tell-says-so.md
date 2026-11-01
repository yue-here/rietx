# WP-2053 — a split site the data cannot tell from one elongated atom says so

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 2053 soft (#1088's WP: the stage compile halves a collapsed split pair, which corrupts this WP's d = 0 arm)
Priority: P3 2026-10-26 — a diagnostic that would say more than the fit does today, with nothing wrong in the numbers; its first task is the maintainer's ruling on the reporter's two questions

## Goal

When a site is a split pair closer than the pattern can resolve, or one atom with a strongly
prolate ADP on a special position, the result says that the data cannot choose between the
two descriptions, with the predicted Δχ² between them and the upper bound on a static split.
The model is never changed.

## Context

Issue #1010 (mustachefeeling, 2026-10-16; revised in its comment of 2026-10-21 after reading
the full texts).

**The silence.** Between two images of one site rietx has two edges: below
`cif.TWIN_DISTANCE` = 0.02 Å the site is merged onto its special position (#765; every route
once WP-1991 lands), and at 0.20 Å or more with occupancies summing to at most 1 it is a split
site (the closest split in the MAGNDATA sweep, `cif.py:327`). In between nothing fires. One
atom on a special position with a strongly prolate U gets no comment either.

**Why a fixed distance cannot decide it.** A pair at ±d/2 and one atom whose U along d is
larger by d²/4 share first and second moments (Bachmann & Schulz 1984). Per reflection of
spacing D along d the site's amplitude ratio differs from 1 by cos x − exp(−x²/2) ≈ −x⁴/12,
x = πd/D (checked in triage). In intensity, d = 0.1 Å gives −2.9 % at D = 0.5 Å and −0.17 %
at D = 1 Å; d = 0.2 Å gives −54 % and −2.9 %. The split's derivative is zero at d = 0 (the
structure factor is even in d), so the (d², U∥) information matrix is singular there and the
Hamilton F test and ΔBIC do not apply.

**The reporter's probe** (main at 05ac4bac, not re-run in triage; no script posted): Pnma
toy, CW neutron 1.5 Å, d_min 0.78 Å, white Poisson noise, three seeds. The two models became
distinguishable at about 0.4·d_min (Δχ² +7.7 to +33.7 at d = 0.30 Å; −6.6 to +2.7 at 0.20 Å).
Inside the split model d/σ(d) is not an identifiability test: an unsplit site returned
d = 0.045 ± 0.015 Å. Two of three seeds at d = 0 were hit by #1088.

**What the literature adds** (from the issue comment; the reporter read the full texts):
two minima invisible to the covariance (Kwei et al. 1993, BaTiO₃), so a profile over d or
several starts; the models are not nested, so Williams-Kloot λ (Prince & Spiegelman, ITC C
8.4) beside a parametric bootstrap; "indistinguishable with Bragg data" as a second verdict
(Keen & Goodwin 2015; Shoemaker et al. 2010); ordinary ADPs never show the absence of
disorder (Senn et al. 2016); report both models and choose neither.

**Already the tree's state.** No occupancy taper in `Refinement`: `gui/symmetry.py::_collisions`
declines TOPAS's `occ_merge`. A solved structure should reach `Refinement` with every atom on
its exact Wyckoff position (for WP-1515's solver).

**Seams.** `solve/cost.py`'s structure-factor quadratic form (`chi2`, `chi2_batch`,
`from_model`) may give the predicted Δχ² for one extra structure-factor evaluation per
candidate site; untested. `optimize.statistics` holds the existing Hamilton test.

**Tier.** The statistic is arithmetic (physics). The verdict bands are new judgement, measured
on one synthetic family: they enter `rietx._audit` at tier 3 naming that family, never at
`unaudited` (CI's `tests/audit_delta.py` fails a new name there; the issue comment proposes
`unaudited`, which the tree refuses). A report finding is of the kind "report the number with
its meaning" (DESIGN § Rules, 1).

**Practice.** None of TOPAS, GSAS-II or FullProf offers a split-versus-ADP report, as recalled
in triage (not checked). FullProf and TOPAS v6 have no built-in anharmonic ADPs (checked by
the reporter); Jana2020 has Gram-Charlier terms to sixth order (Petříček et al. 2023). Add the
row to `docs/practice.md` once checked.

### Inherited

## Non-goals

- Anharmonic (Gram-Charlier) ADPs.
- Choosing or changing the model.
- An occupancy taper (`occ_merge`, FOX's DOC) in `Refinement`.
- The sub-0.02 Å merge (WP-1991) and the stage-compile multiplicity (#1088's WP).

## Tasks

- [ ] The ruling: whether the diagnostic exists and where it lives (report finding at the
  answer, validation on request, or nothing), and whether the opt-in two-model comparison
  is wanted. Record it as `Decided YYYY-MM-DD: …`.
- [ ] Reproduce the reporter's probe as a committed script, with a positive arm (split) and a
  negative arm (single atom), after #1088's fix.
- [ ] The diagnostic as ruled: predicted Δχ² against the moment-matched alternative at the
  current profile, the verdict word, and the 2√(U∥ − U⊥) bound; its audit row at tier 3.
- [ ] If ruled in: the opt-in comparison (two fits, a profile over d, a parametric bootstrap
  with a positive arm, Williams-Kloot λ, bond-valence sums, the alternatives named).
- [ ] Tests: both arms, plus a site outside the zone that stays silent.
- [ ] Skill: the reference row for the new code.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_<this WP's file>.py -q
.venv/bin/python -m pytest tests/test_audit_table.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Bachmann, R. & Schulz, H. (1984). *Acta Cryst.* A40, 668-675.
- Hamilton, W. C. (1965). *Acta Cryst.* 18, 502-510.
- Kwei, G. H. et al. (1993). *J. Phys. Chem.* 97, 2368-2377.
- Prince, E. & Spiegelman, C. H. (2006). *ITC* Vol. C, ch. 8.4.
- Keen, D. A. & Goodwin, A. L. (2015). *Nature* 521, 303-309.
- Senn, M. S. et al. (2016). *Phys. Rev. Lett.* 116, 207602.
- Shoemaker, D. P. et al. (2010). *Phys. Rev. B* 81, 144113.
- Kuhs, W. F. (1992). *Acta Cryst.* A48, 80-98.
- Favre-Nicolin, V. & Černý, R. (2002). *J. Appl. Cryst.* 35, 734-743.
- The full list is in issue #1010 and its comment.

## Handover log

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1010). Checked against
  the tree at c0e32ab29: nothing fires between `TWIN_DISTANCE` (0.02 Å) and the 0.20 Å split
  edge, there are no anharmonic ADPs, `occ_merge` is already declined, and the fourth-order
  formula and its intensity table check. No open WP owns it: WP-1991 owns the merge below
  0.02 Å, WP-1447 owns per-pattern thresholds with no split-site content, and WP-1468 treats
  split sites only for drawing. Next: the maintainer's ruling (first task).
