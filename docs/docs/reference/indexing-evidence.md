# Indexing evidence and the route to a phase

This page gives the evidence view of an indexing result, `IndexingEvidence` with one `CandidateEvidence` per candidate and each caveat's kind as a `CaveatEvidence`, the figures `plot_indexing` draws from a result, and how a candidate cell becomes a phase to refine and to screen for its extinction symbol.

The result these views are built from, and the confidence gate they feed, are in [The indexing search and its result](indexing.md).

:::{admonition} Provisional
:class: warning
Indexing is still being measured against real data, so every name on this page may change in a 1.x release: the types in `rietx.schemas.indexing`, the helpers under `rietx.indexing` and `rietx.viz.plot_indexing`.
A change is announced in the release notes, and the data contracts a consumer parses do not move with it.
{ref}`provisional-by-declaration` gives the promise in full.
:::

## The evidence view

The confidence gate exists for unattended use, where a program that cannot weigh evidence must never be handed one cell.
A consumer that can weigh evidence wants the inputs to that judgement instead, and `IndexingResult.evidence` returns them in one place, as an `IndexingEvidence`.
Everything in it is a projection of fields the result already carries, computed on each call, so the two can never disagree.

```python
import rietx as rx
from rietx.schemas.common import Provenance

candidate = rx.CellCandidate(
    cell=(4.157, 4.157, 4.157, 90.0, 90.0, 90.0),
    cell_esd=(1e-4, 1e-4, 1e-4, 0.0, 0.0, 0.0),
    system="cubic", volume=71.84,
    found_by=["dichotomy", "svd", "trial_error"],
    confidence="low",
    confidence_caveats=["not_validated", "geometric_ambiguity"])
result = rx.IndexingResult(
    candidates=[candidate], engines_run=["dichotomy", "svd", "trial_error"],
    provenance=Provenance(package_version="0", created_utc="2026-10-22T00:00:00Z"))

evidence = result.evidence()
row = evidence.candidates[0]
assert [(c.name, c.kind) for c in row.caveats] == [
    ("not_validated", "capping"), ("geometric_ambiguity", "refuting")]
assert row.validated is False and row.lebail_rwp is None
```

| Field | Holds |
|---|---|
| `IndexingEvidence.candidates` | one `CandidateEvidence` per candidate, in rank order |
| `IndexingEvidence.systems_searched`, `IndexingEvidence.search_complete` | what the search entered, and per system whether it was exhausted |
| `IndexingEvidence.systems_supported` | the systems the peak list supports at all; empty when the result carries no quality report |
| `IndexingEvidence.n_usable_lines` | the usable lines the answer is about |
| `IndexingEvidence.fom_ranked` | the panel members that ranked the candidates, read off the first candidate carrying a panel |
| `IndexingEvidence.fom_undefined` | the members the list was too short for, name to reason |
| `IndexingEvidence.validated` | whether a pattern was supplied, so validation could run at all |

| Field | Holds |
|---|---|
| `CandidateEvidence.index` | the position in `IndexingResult.candidates`, the address other calls take |
| `CandidateEvidence.cell`, `CandidateEvidence.cell_esd`, `CandidateEvidence.system`, `CandidateEvidence.centring`, `CandidateEvidence.volume` | the lattice |
| `CandidateEvidence.confidence` | the grade |
| `CandidateEvidence.caveats` | every caveat with its kind |
| `CandidateEvidence.found_by` | the finders that reached it |
| `CandidateEvidence.n_indexed`, `CandidateEvidence.n_lines` | its coverage |
| `CandidateEvidence.fom` | the panel members that ranked it, name to value |
| `CandidateEvidence.validated` | whether a validation fit ran on this candidate, which `IndexingEvidence.validated` does not say |
| `CandidateEvidence.lebail_status`, `CandidateEvidence.lebail_rwp` | that fit's status and Rwp; `None` when it did not run |
| `CandidateEvidence.predicted_but_absent`, `CandidateEvidence.unmatched_observed` | that fit's two counts; `None` when it did not run |
| `CandidateEvidence.ambiguity_partners` | how many ambiguity partners it has |

`CaveatEvidence` is the piece `CellCandidate.confidence_caveats` withholds.
`CaveatEvidence.name` is the caveat and `CaveatEvidence.kind` is `"refuting"` or `"capping"`.
That split lives in a package constant, `rietx.schemas.indexing.INDEX_REFUTING_CAVEATS`, which a JSON consumer cannot see.
A reader told `predicted_but_absent` and `not_validated` in the same breath needs to know that the first argues against the cell while the second only says a question was never asked.
A `geometric_ambiguity` caveat beside `CandidateEvidence.ambiguity_partners` of 0 means the ambiguity walk never reached the candidate ([The confidence gate](indexing.md#the-confidence-gate)).

Read `CandidateEvidence.lebail_rwp` beside the two counts rather than scoring on it.
The three together let a reader notice a detector failing: on the magnetite pair recorded in the type's docstring, before indexing thresholds 1.12 the correct cell read `predicted_but_absent` 2 and its wrong rival 0, which is backwards, while Rwp read 0.25 against 0.79.
A reader given all three could see that, and the gate, reading one number, could not.
That argues for showing Rwp, never for ranking on it.

The result's own dump keeps the same shape: `IndexingResult` carries no top-level `cell` key, and the evidence view is the companion to dump beside it ([Answers as JSON](programs.md#answers-as-json)).
The streamed per-system shortlists `index_pattern` sends on its event stream use the same `CandidateEvidence` shape.

## Drawing the result

`rietx.viz.plot_indexing` draws the ranked candidates as tick rows against the peak list, and a validation-fit panel for one candidate.
It takes the result and the `PeakList` the search ran on.

<!-- api-doc: no-exec — it needs a result from a real search -->
```python
from rietx.viz import plot_indexing

figures = plot_indexing(result, peaks, data=data, instrument=ins, candidate=0)
```

It returns a dict of figures, in drawing order:

- `"peaks"`, always: the peak list, drawn over the profile when `data` is given;
- `"candidates"`, when the result has any: up to `n` (default 5) ranked candidates as tick rows, matched in the window the search used;
- `"validation"`: the validation-fit panel for `candidates[candidate]`.

For the validation panel, pass `validation=` a pair from `rietx.indexing.validate_by_lebail` with `with_result=True` to draw a fit already in hand, or `data` and `instrument` to run that fit, or neither to draw the stored positions-only panel when the candidate carries one.
`path=` saves each figure as `{path}_{name}.png`, and `style="dark"` draws all three dark.
A wrong cell that scores well usually looks wrong at once, which is why the picture is part of the answer.

## From a candidate to a phase

A candidate is a lattice, and a refinement needs a `Structure`.
`rietx.indexing.structure_from_candidate` builds the single-phase model the whole-pattern validation itself uses.

<!-- api-doc: no-exec — it needs a candidate from a real search -->
```python
import rietx as rx
from rietx.indexing import structure_from_candidate

candidate = result.best_or_none()       # or one you chose after reading the evidence
phase = structure_from_candidate(candidate)
lebail = rx.refine(data, phase, ins, mode="lebail", plan="profile_only")
```

| Argument | Default | Does |
|---|---|---|
| `candidate` | | the `CellCandidate` |
| `space_group` | `None` | the space-group symbol; `None` takes `CellCandidate.lattice_group` |
| `name` | `"candidate"` | the phase's name |

Two things about the model are load-bearing.
The one dummy atom is mandatory, because a phase cannot have an empty atom list and a candidate cell has no structure yet.
In Le Bail and Pawley mode every atom path is force-fixed, so it contributes nothing and the parameter table shows it `mode_fixed` rather than editable ([Held rows](parameter-table.md#held-rows)).
And the space group defaults to the absence-free lattice group, for the reason `CellCandidate.lattice_group` exists: a plausible-looking space group would hide the reflections whose absence has not been established.
The six cell numbers go in as the candidate refined them.

The GUI's `Adopt` button builds the same scaffold ([The GUI panel by panel](gui-guide.md#indexing)).

### The extinction symbol

Once a lattice is established, which reflections are systematically absent is the next question.
`determine_extinction_symbol` takes the pattern, a `CellCandidate` and the instrument, and answers with ranked classes, each carrying a list of space groups, because the extinction symbol and not the space group is what a powder measures.
[The extinction symbol](extinction.md) gives what it takes, returns and refuses.

### The way back from a refinement

A refinement's report can send you here.
When Layer 2 finds peak offsets beyond the linearisation radius across most of the misfitting regions, it suggests `reindex_or_recheck_cell`, and the move that suggestion asks for is an indexing search: pick the peaks and index the same pattern ([The fit report](report.md#layer-2)).
