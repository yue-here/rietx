# rietx design rules

Why the package exists and the five rules every change answers to. Every session and
subagent loads this file through the root `CLAUDE.md`. The rest of the design record,
and the history of these rules, is [DESIGN.md](DESIGN.md).

## Why this package exists

**rietx exists so that a scientist can trust a Rietveld refinement they did not drive
by hand.** Trust is built four ways. Every result is checked against an independent
measurement where one exists, and where none does the method, its source and its code are
stated plainly. The package decides alone only where every competent refiner would
decide the same way; where the data can rank the alternatives it ranks them, and where
they cannot it reports the number and stops. Every action is recorded. The report says
what was refined, how well, and what to look at next, so an expert can audit and a
non-expert can learn to steer. The API follows current Python practice, and the whole
of powder diffraction is in scope.

*Written 2026-10-18. The founding statement of 2026-07 and what superseded it are in
[DESIGN.md](DESIGN.md) § History.*

## Rules

Five, each a consequence of the paragraph above. Milestones and rulebooks cite them by
number. A sentence that nobody would use to make a choice does not belong here.

1. **Decisions.** Ambiguity comes in three kinds, and the package answers each
   differently.
   - *The data settle it.* Every competent refiner, shown the number, would take the
     same action: the physics, the arithmetic, established practice. The package acts
     and records that it did. The absent-phase hold is the example.
   - *The data can rank it.* The hypotheses are enumerable and the data score them,
     though not always to one winner: indexing, extinction symbols, structure solution,
     a choice of peak shape. The package enumerates, scores each with its evidence, and
     presents the ranking without picking. It picks in two cases only, and returns the
     whole ranking with the pick. In the first, the caller asked for a pick by calling a
     function made for it, such as `best_or_none`, and no default path calls one. In the
     second, the top candidate leads by a margin every competent refiner would accept,
     so taking it is an action of the first kind.
   - *The data cannot settle it.* The explanation depends on facts outside the pattern:
     sample history, a temperature ramp, a beam dump. The package reports the
     statistic with its meaning and stops, because only an agent told those facts can
     weigh them. A series discontinuity is the example.

   The gate on the first kind is unanimity: if a competent refiner who would act
   otherwise can be named, the action moves to the second or third kind. That line is
   drawn by the physics and by practice and does not move as agents improve. Every
   withheld verdict leaves its statistic. Where a rerun is expensive (an hour-long
   search, a 200-pattern batch, a write into a project's history) the package protects
   work already done: it keeps the best attempt, seeds no successor from a diverged
   fit, refuses to overwrite history, and records each. A default reaches a correct
   answer in the fewest calls, since a fit costs seconds and an agent's reasoning costs
   tokens. The provenance audit of every threshold (the physics', the literature's, or
   ours) is [milestones/generality.md](milestones/generality.md) § The rule.

   An input that leaves a choice open is surfaced. It is never settled by which reading
   most files mean. A bare space-group symbol with two origin settings keeps origin 1
   and warns, naming what each setting implies. A file holding several scans, read
   with no `scan=`, is refused and lists its scans. A new case asks which of the two
   forms fits it (ruled 2026-11-21, WP-2006 § Rulings 23).

2. **Verification and validation.** rietx is written by agents, so both are its
   foundation and not a check at the end. The words carry the field's meanings (Roache
   1998; Oberkampf & Roy 2010, chapters 2 and 10 to 13). A check compares a result with
   a *reference value*, and the kind of reference value decides which of the two the
   check is.

   *Verification* asks whether the code computes its model correctly, and it is the
   package's gate: a feature ships verified or does not ship. Its forms: an exact
   identity (a reparameterisation that provably cannot move the fit, a sum that must
   close); an analytic Jacobian against finite differences; a refactor that reproduces
   every number, or its residual and Jacobian to a rounding bound where it only
   regroups arithmetic; two backends agreeing on one residual; and, weakest, two codes
   agreeing on the same data under the same protocol, or a published refinement of the
   same pattern reproduced under its protocol. The last is weakest because its
   reference value is a model's answer and can share the model's error. Under a
   different protocol it verifies nothing and measures only drift. In
   `tests/validation_matrix.py`'s tiers, `identity`, `own_result` and `cross_code`
   verify. `characterisation`, which records the shape of a known error or that a model
   is inadmissible, claims no accuracy and is neither. Every physics function cites its
   source.

   *Validation* asks whether the model matches the specimen, and its reference value is
   an *independent measurement*: a certified cell, a weighed composition (judged against
   the inter-laboratory spread of refinements), a composition from another probe. A
   prediction written down before the measurement validates only against an
   independent measurement; checked against the package's own arithmetic or another
   code, it verifies. So `certificate` and `spread` validate, and `prediction` validates
   where its reference value is an independent measurement. A validation result reports
   the mismatch in the quantity's own units, with the measurement's uncertainty and the
   fit's esd beside it, over a stated domain (the families, laboratories and instruments
   it was measured on), never only a pass; and it says whether the data is development
   data. Where no claim compares a topic with an independent measurement, the equation,
   its source and its code are stated plainly, and the topic is recorded *not yet
   validated* until one does. That state is separate from *provisional*, which rietx
   keeps for an API that may still change (PEP 411's sense). The validation record is
   for the developers. A user chooses a feature by the sample and the data, so the
   record lives in the matrix and its generated page alone. No surface an agent reads
   while choosing carries a validation verdict: `capabilities()`, the help entries, the
   agent skill, the GUI's help (ruled 2026-10-27) and the fit report (ruled 2026-11-01).

   *A dataset is unused, sealed or development data.* Data that nobody who changes the
   package has run is unused. A family is sealed when its first run is on the tree as it
   stood when the work it judges began (a milestone's open, or the commit its acceptance
   row names), and nothing between then and the close is chosen or reworked on it by
   anyone who changes the package. Running it for another purpose, such as a benchmark
   whose results steer no change, leaves the seal intact. It is run again at the close,
   its mismatch against each reference value is reported for both runs, and it is then
   spent. Every other dataset that has been run is development data: data used to choose
   a threshold, a default or a plan, data a change was reworked on until a number came
   back, and data whose results the developers have seen (Oberkampf & Roy pp. 31-32, 44
   and 401). An independent measurement it carries calibrates as much as it validates. A
   test on it still measures, but weakly, and the record says so. Nothing goes from
   development data back to sealed. A pinned number that moves has moved for the right
   reason only if the new value is no further from its reference value than the old;
   that rule tunes the package toward the development data, and only the sealed
   families show whether the tuning generalises.

3. **Feedback teaches.** The report, each diagnostic's explanation and the manual bring
   a non-expert to competent steering, since steering is what the package leaves to
   them. The agent skill does the same for an agent: it makes the API and the feedback
   surface known accurately so the first call is right, and beyond that names only a
   trap or a practice with a source outside rietx's own runs. The vocabulary is
   generated from the live surface, the manual is reachable from inside the package,
   and the skill shrinks as models learn the package. A rule whose only evidence is a
   run on rietx's own test data is the code's overfit in prose form and is cut.

4. **Design tests.** One per kind of change, each with what passes. The mechanisms
   that enforce them are the project `CLAUDE.md` § Invariants.

   *A new output.* An agent can write the next call from it without a rerun. The
   statistic travels with any verdict, and an unmeasured value is `None`, never a
   default that reads as an answer.

   *A new default or automatic action.* Its kind of ambiguity is stated (Rule 1).
   Kind 1 names a dissenting competent refiner or says none exists, and records that
   it fired. Kind 2 ranks with evidence and picks only in Rule 1's two cases. Kind 3
   reports the number and stops. An Rwp comparison is never its evidence.

   *A new topic.* A test that verifies it lands with the code (Rule 2's gate). Where an
   independent measurement exists, it is named before the code is written: the dataset,
   the measured value with its uncertainty, and the mismatch the test will report. Where
   none exists, the topic is recorded not yet validated. Its equation is in the manual
   with its source, and its off state reproduces every earlier number.

   *A new API.* It takes the shape the surface already has: a verb in, a typed result
   out, a raise on failure, documented or deferred with a reason. The signature and
   docstring are enough for a first call to be right. It names its likeliest misuse, and
   a test makes that call. The mistake is removed where Rule 1's first kind allows.
   Otherwise a literal the call cannot honour raises before any work, naming the argument
   and the fix. A pattern the caller passed that matches nothing warns. A pattern skips
   the rows it cannot change without a word when it changed others. The survey behind
   this test is `docs/practice.md` § How an API meets a caller's mistake.

   *A new skill row.* It names a field, a verb, a code, or a trap or practice with a
   source outside rietx's own runs. Anything else is cut.

5. **Choosing a design.** Four tests, and an order for when they disagree.

   *Intent.* A design starts from what its user does with the result: the quantity
   read, the decision it feeds, and how finely that use resolves it. A number is
   chosen from that use, with its source, and never from the mechanism alone.

   *Convention.* A change takes the shape rietx already uses for the same job. One shape
   sets fewer traps for a person or an agent learning the package. A departure names in
   its WP the likely mistake or the wrong number the convention would cause. A convention
   found wrong is changed everywhere in one change. It is never broken in one place. A
   convention that lets a caller's likeliest mistake pass in silence is a convention found
   wrong, because new code copies the code around it.

   *Direction.* A design builds towards the stated direction of its milestone or of the
   project. Cases test it as acceptance rows. A design is not fitted to one case, and
   nothing is built before a case needs it. A milestone's direction is in its record.
   The project's are two, each ruled by the maintainer.
   - *Arithmetic accuracy.* A speed setting (a convergence tolerance, a peak window, a
     quadrature order) keeps its error under about a tenth of each quantity's esd,
     the final shift/esd McCusker et al. (1999) accept, and spends no wait past that.
     The established programs are the cross-check, and rietx is never less accurate
     than them. Where an error compounds (WP-2222: a Pawley series carrying
     intensities, `lab_calibrate`, published guides), the setting follows what the
     compounding needs. A speed change leaves the model as it was. It answers to an
     independent measurement where one exists, and to this bar otherwise. One that
     only regroups arithmetic is verified at fixed parameters, and its goldens re-pin
     in the same change (ruled 2026-11-19 to 11-27; WP-2307, WP-2317 R0).
   - *Structure-free fitting.* Pawley is the structure-free method rietx leads with.
     WP-2062 carries the move to it as the default. Le Bail follows the established
     programs' practice (ruled 2026-11-27, WP-2317; lifts #1434's fence).

   *Practice.* Where a good answer exists, in diffraction or in another field, rietx
   adopts it and spends its effort on the questions practice leaves open. A practice
   yields to the model's accuracy and to the constraints a reused design must meet. The
   survey behind it is `docs/practice.md`.

   *Conflicts.* Intent comes first. The shape of the API follows rietx convention. A name
   or a meaning follows the term the literature and the IUCr dictionaries use. One
   program's keyword is not that term, and rietx takes no alias for one. A number the
   model computes follows accuracy. An arithmetic setting follows *Arithmetic accuracy*
   above.
