# WP-2227 — how a Refine ran: the options, drawn

Pictures for the three questions in `../2227-the-gui-shows-how-a-refine-ran.md`. Each
whole-window picture is the rebuilt page at `/next`, 1440 × 900, one device pixel per CSS pixel,
on the `fap` example. The page is the R4 branch's build (WP-2231, `49bacf929`). Each option is
drawn over the real page by editing its DOM in a scratch probe; nothing in `gui/src` changed.
A dashed magenta box marks the part an option changes. The box is not part of any design.
Every whole-window picture comes in light and dark. A `-crop-light` file zooms on the boxed
part.

The numbers are real fits of `fap`, except one. A one-stage re-fit lands at Rwp 9.25 %, the same
as the staged fit. The staged run that frees atom positions ends at 9.23 %. The fallback's
discarded Rwp of 45.21 % is illustrative, since no real fit has triggered the fallback.

## The three states

- **one**: Refine on a converged model ran one stage.
- **released**: the plan gained a seventh stage freeing atom positions, which the last fit held,
  so Refine ran in stages.
- **fallback**: the one-stage re-fit was rejected, so the plan ran in stages from the same start.

## The pictures

Today's behaviour, for reference:

- `ladder-blank-one-*.png`: what the Plan tab shows today after a one-stage re-fit. Every
  stage's Rwp is blank. This is why today's GUI always runs in stages.
- `status-today-*.png`: the status bar during a real one-stage re-fit. It reads
  `warm_refit (1/1)`, the internal stage name.

Question 1 (where) with question 2 (the ladder after one stage), in the Plan tab:

- `ladder-row-one-*.png`: one row stands in for the plan. A block after the stages, drawn
  like the closing stage, reads "One stage", "Free Everything above, at once", 20 free and
  Rwp 9.25 %. The stage rows keep their counts and leave Rwp blank.
- `ladder-span-one-*.png`: the plan's rows with one Rwp spanning them. A bracket joins the six
  stages' Rwp slots, with Rwp 9.25 % and "all six at once" at its middle.
- `ladder-row-released-*.png`: a staged run, with the chip of what the last fit held marked by
  an accent ring and dot. Its tooltip names it. This is question 3's "mark it" option.
- `ladder-row-fallback-*.png`: a staged run, with the discarded one-stage try as a greyed block
  above stage 1: "One stage, discarded", its Rwp struck through, and "Diverged, so the plan ran
  in stages from the same start".

Question 1, beside Rwp on the Pattern graph's title line (the Parameters tab is in front, to
show the feedback needs no Plan tab):

- `title-one-*.png`: "One stage: the model had converged".
- `title-released-named-*.png`: "In stages: Atom position shift was held". Question 3's "name
  it" option.
- `title-released-unnamed-*.png`: "In stages". Question 3's "do not name it" option.
- `title-fallback-*.png`: "In stages: the one-stage re-fit diverged".

Question 1, in the Console:

- `console-all-*.png`: the Console after three Refines, one per state. After each
  `ref.fit(...)` line, a comment carries the plan line that `Refinement.summary()` prints. The
  first two are the real lines from these fits; the third is WP-2224's fallback text.
