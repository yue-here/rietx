# Cases

## Case 1

A series refinement chains N patterns by warm start. Each pattern's entry already carries its goodness of fit (GoF). Proposal: add one line to the series printout naming the patterns whose GoF sits furthest above the median of the accepted patterns. Grounds: two silent misfits in a measured series went unnoticed, and a ranked line would surface them.

- **A.** Add the ranked line naming the worst-GoF patterns.
- **B.** No line. The per-pattern GoF is already reported; the reader inspects it.

## Case 2

In a series, one diagnostic code (say a parameter hitting its bound) fires on many patterns. Proposal: one series-level line counting it, e.g. 'BOUND_HIT in 42 of 68 patterns'.

- **A.** Keep the count line: no single pattern's output shows the count.
- **B.** Drop it: each pattern's own diagnostics already show the code.

## Case 3

Extinction correction is opt-in, and a user may not know it exists. Proposal: a diagnostic EXTINCTION_UNDECLARED that fires when a score test on the residual exceeds 25 (a threshold borrowed from another context), validated on one synthetic dataset family; it is confounded with preferred orientation and Biso. A follow-up would add the same kind of warning for Stephens strain, anisotropic ADPs, surface roughness and absorption.

- **A.** Ship the warning only, without the siblings, until it is validated on more families.
- **B.** No warning. Make the correction findable by documentation: the plan description, the help entry, the manual, and one concise row in the agent skill.
- **C.** Ship the warning at info level with its caveats stated, and the sibling warnings after it.

## Case 4

A warm-started series fit can land in a wrong basin. Proposal: when a warm fit's GoF exceeds 1.25x its seed pattern's GoF, automatically rerun it with the cautious staged plan. The rerun can only lower chi-squared, and a ratio in one row of hundreds is easy to miss.

- **A.** Record the ratio as a field on every pattern; no automatic rerun.
- **B.** Rerun automatically at the 1.25 threshold and record that it did.

## Case 5

A structure file gives a bare space-group symbol for a group with two origin choices (e.g. F d -3 m) and does not say which origin. The reader must pick one.

- **A.** Count bare symbols in public structure databases by source and default to the origin the majority of files mean, recording the count.
- **B.** Refuse to read the file until the caller states the origin.
- **C.** Keep origin choice 1 (the conventional first setting) and emit a warning quoting what each origin would imply for this file.

## Case 6

A pattern file holds several scans (ranges). The caller reads it with no scan= argument, from the Python API or from the GUI.

- **A.** Read scan 0 and warn, listing the other scans.
- **B.** Concatenate the scans into one pattern (one other program does this).
- **C.** Refuse, listing the scans; the GUI gets a scan picker.

## Case 7

After a converged fit, the user changes the plan and frees a parameter that was held. Proposal: run a single-stage refit, since the model is already converged, which is faster than the staged plan.

- **A.** Treat a newly freed parameter as a cold start: run the staged plan, and show the user whether a run was staged or single.
- **B.** Run the single-stage refit; the converged model is a good start.

## Case 8

The GUI is being rebuilt. A new Text tab lets the user edit the whole model as text. Each sibling panel has a '?' help box explaining the selected item. Should the Text tab have one?

- **A.** Yes, a help box like the sibling panels.
- **B.** No, keep the new panel simple; help lives in the manual.

## Case 9

In the new Text tab, an edit to the whole text buffer is held as one pending edit. Sibling panels show a live plot preview of a pending edit before it is applied.

- **A.** No preview; the text edit applies when committed, keeping the tab simple.
- **B.** Show a plot preview for the pending text edit, as siblings do.

## Case 10

Parametric refinement: a parameter follows an equation across a series (a cell against temperature, say). An earlier work package settled on a closed vocabulary of basis functions. What is the scope of the equations users can use?

- **A.** A closed vocabulary of named forms (linear, polynomial, Arrhenius, ...), with a general expression language a non-goal, following the earlier closed-basis decision.
- **B.** Users write their own equations in a small expression language; beginner presets later if needed.

## Case 11

Parametric refinement and TOPAS, whose expert users write parametric macros. How should rietx relate to TOPAS here?

- **A.** Build robust parametric machinery on rietx's own terms; an agent ports a TOPAS input that does not import.
- **B.** Build a TOPAS parametric-input reader as milestone work, choose which equations to support by how often each occurs in a TOPAS archive, and accept on agreement with TOPAS output.

## Case 12

Dark-theme GUI plot: choosing the colour of the 'last fit' curve from candidates. Candidate (d) #7f8f94 sits 0.023 apart in OKLab from the difference curve's colour, which is close. The difference curve is drawn in its own strip below the pattern; the two curves never cross or touch.

- **A.** Keep (d) as a candidate: the two never touch, so they cannot be confused.
- **B.** Drop (d): it is too close to the difference curve's colour.

## Case 13

A phase whose refined scale is under 3 sigma of its esd: the data cannot see it, and its cell and atoms wander while Rwp does not move.

- **A.** Automatically hold that phase's structural parameters for the stage, keep its scale free, and record the hold.
- **B.** Leave everything free; report the scale's significance and let the caller decide.

## Case 14

Esds. rietx multiplies esds by the Berar-Lelann factor, which accounts for serially correlated residuals; its esds come out 6-9x GSAS-II's on the same fit.

- **A.** Keep the inflation and report the textbook esd beside it.
- **B.** Drop the inflation and report the textbook esd, matching GSAS-II and common practice.
