# magnetic — the magnetic structure

**Opened 2026-09-18 as v1.6**, the same day v1.5 shipped, and renamed on
2026-10-03 (WP-1540). A milestone is now named and a release is numbered,
so this one ships in whichever release is cut after its acceptance is met.
[`../ROADMAP.md`](../ROADMAP.md) § magnetic carries the prose, and the WP
index lists the rows. Issue threads #286 and #426 quote it as v1.6.

Narrative about the WPs below goes to the record of the release in flight,
[v1.11](v1.11.md) today, as for every other WP (protocol rule 5).

## Scope

The magnetic scattering track: seven WPs, 1326 to 1329, 1343, 1418 and 1419.
Each WP file states its own context and baseline; nothing is restated here.

The track answers a question the package refuses today. Three readers decline
a magnetic structure with one sentence, and the unexplained-intensity report
names a magnetic contribution as a cause it cannot test. The rungs run from
the hypothesis test that needs no moment (1326, a satellite is a position),
through the moment itself (1327) and its interchange (1328), series (1329)
and its price in peak width (1343), to determination rather than statement
(1418) and a nuclear superstructure refined on mode amplitudes (1419).

Most of it has a working reference implementation on the `mustachefeeling`
fork, measured on data this repository does not hold. Issues #256, #257, #277,
#286 and #293 are the design threads, and the decisions taken in them are
recorded in the WP files rather than in the threads.

**Not in scope, and the fence says so.** Neutron time-of-flight stays at v2+
(§ v2+, issue #193), as do incommensurate structures, polarised neutrons and
magnetic X-rays (1327's non-goals). The fork's integration branch carries a
TOF chain merged into the magnetic one; it is split back out rather than
landed here, and the ruling is 1419's `### Inherited`. Magnetic structures
left the v2+ fence on 2026-09-02 by a decision recorded in DESIGN.md, and a
second item leaves it the same way or not at all.

## The order

Moved from ROADMAP on 2026-10-03 (WP-1540), verbatim.

**The order, set in #286 on 2026-09-16 and 2026-09-18.** 1418's M-6 and M-7
first, having no forward-model contact; then 1327's verb, one PR; M-9 with
1418; then 1419 alone, because the decision it carries — the full child group
for reflection generation, multiplicity and the metric, the ε-reduced
stabiliser only for orbit expansion of the mode field — gets decided properly
in a PR that is about it and waved through in one that is not. Refined in
#286 on 2026-09-25: PR #448 (the operation-list phase) and the k ≠ 0
supercell follow 1327's model. Then 1326, which needs neither; 1328 once #448
is in, so it opens complete; then 1343 and 1329. M-9 waits for the supercell
and 1328. Every magnetic
row in the agent skill, diagnostic codes included, goes in
`references/magnetic.md`, and the merge result of the whole set is measured
once before the first PR is cut.

## Acceptance

**These rows are written at the open**, which is what protocol rule 6 asks
for: a row written after the fact cannot fail. Each names a state a later
session can check without asking what was intended.

They are stated at the level `../ROADMAP.md` and the WP files already commit
to. The session that opens each WP sharpens its own row here, because a bar
set by someone who has not read the WP is a bar set too low.

- **A satellite is answered without a moment** (1326). A pattern whose
  nuclear model leaves intensity at G ± k gets the candidate propagation
  vectors and a stated hypothesis test, with no moment anywhere in the model,
  and a k = 0 case says so rather than ranking.
- **An unsupported moment is held, not bounded** (1327). A moment the powder
  cannot see is held for the stage under 1301's rule, `StageResult.held`
  records it, and the report says what the powder cannot separate rather than
  returning a confident wrong singleton.
- **The stored form is the operator list** (1327). A magnetic or child group
  is the operations it has; a Hermann-Mauguin symbol beside them is a label
  and must generate them exactly, or it is refused. A phase whose symbol does
  not generate its own operations gets the wrong absences and converges
  anyway, which is the whole safety property.
- **Two lists, and each consumer names which it reads** (1419). The full
  child group drives reflection generation, multiplicity and the cell metric;
  the sign-consistent stabiliser drives orbit expansion of the mode field
  alone. The fork's sweep is why this is a row: the metric is safe on 32 of
  32 pairs because the dropped operations are translation-coset partners, and
  reflection generation is not — the unique count doubles on the 15 pairs
  where the reduction bites, harmless in Rietveld and wrong in Le Bail and
  Pawley, where the extras would take free intensities.
- **A mode amplitude is absolute, and it has a seed** (1419). χ² is an even
  function of the amplitude vector at a zone-boundary k, so A = 0 is a local
  *maximum* and the gradient there is exactly zero. The amplitude is absolute
  in the ADP and Stephens pattern rather than a coordinate-DOF offset, a seed
  rule in `Stage.strain_seed`'s shape starts it off the parent, and an
  acceptance case starts *at* the parent and converges.
- **The tested quantity is A_τ, not its components** (1419). The per-irrep
  total carries an esd from its own covariance block, the way
  `model/geometry.py` propagates J·Cov·Jᵀ. The components are an arbitrary
  basis's coordinates, so testing each of them asks a question the basis
  chose; the printed sign is a domain convention and says so.
- **A magnetic file opens and writes back** (1328). magCIF in and out, and
  the three readers that refuse a magnetic structure stop refusing.
- **The moment's trajectory is a measurement, not an ordering artefact**
  (1329). A ramp through an onset runs `direction="both"` and flags what the
  two chains disagree on, as every series does.
- **A broad magnetic peak is not paid for by a low moment** (1343). The
  magnetic width has its own term, and the record says what declaring it
  changes — never an Rwp comparison as the evidence.
- **The determination abstains where the powder cannot separate** (1418).
  LaMnO₃ 50 K ranks A-type first of four with its powder-equivalence class
  listed; Cr₂WO₆ 150 K abstains with the k = 0 sentence; every shipped
  fixture is bit-identical with no magnetic model declared.
- **The skill's magnetic rows are in `references/magnetic.md`** (every WP).
  Diagnostic codes included, so `diagnostics.md`'s remaining headroom never
  has to absorb them, and the merge result of the whole set is measured once
  before the first PR is cut rather than at the sixth merge.
