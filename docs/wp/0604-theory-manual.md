# WP-0604 — Sphinx + MyST theory manual

Milestone: v0.6 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Sphinx + MyST theory manual: numbered equations cross-referenced from
  docstrings (sphinxcontrib-bibtex)

## Context pointers

- The raw material already exists by invariant: every physics function cites
  author/year/journal in its docstring. The manual organises those citations
  into numbered equations; it must not become a second, divergent source of
  the formulas.

## Inherited

From **WP-0508** (flat-plate absorption, landed 2026-07-28) — a section that
is already written, and a worked example of the house rule.

- **The three specimen-absorption geometries are derived in full in
  `model/absorption.py`'s module docstring**, each in three lines from the ITC
  eq. (6.3.3.1) volume average, including the sin θ cancellation that makes a
  *thick* Bragg-Brentano specimen angle-independent. That is manual prose
  already; lift it rather than re-deriving, and keep the convention paragraph
  (A ≤ 1 transmission vs the A\* = 1/A most tables print — an identity test
  cannot tell them apart, only the direction of the θ-dependence can).
- **It is also the cleanest illustration of "validate against the integral, not
  a transcription".** WP-0501's b₂ was printed with two digits transposed in
  the available scan of Rouse (1970); the error is invisible against a
  constant-θ slice of the paper's own table and 0.08 wrong at µR = 1. The
  flat-plate cases are closed-form integrals rather than fits, so
  `tests/test_flat_plate.py` checks them against an adaptive quadrature of the
  defining path-length integral, sharing no constant with the implementation.

From **WP-0305** (Brindley, landed 2026-07-23) — a concrete instance of the
"second, divergent source" risk this stub already names, and a warning about
*which* source to trust. 0305's own WP body wrote the microabsorption fence as
"µR ≲ 0.01–0.1", which **conflated two conventions**: the shipped fence is
`BRINDLEY_MU_R_FENCE = 0.05` in µ·R, derived from µ·D ≤ 0.1 (D = diameter,
R = radius). The handover log corrected it; the WP body was never rewritten.

The general rule that follows: **transcribe formulas and thresholds from the
code and its docstrings, never from WP prose.** WP bodies record what was
planned, handover logs record what shipped, and where they disagree the code is
authoritative. Every physics function cites author/year/journal in its
docstring by invariant, which is what makes the code the better source.

From **WP-0503** (Stephens anisotropic strain, landed 2026-07-27) — the manual
must state *conventions*, not just equations, and this is the worst offender so
far. Three independent labelling choices sit behind the S_HKL of
`crystallography/stephens.py`, and getting any one wrong rescales every
published number:

1. `√(Σ S·monomial)·d²·10⁻⁶` is the **FWHM** of the ΔM/M distribution here, not
   its standard deviation — no √(8 ln 2) appears anywhere;
2. the coefficients are carried in **10⁻¹² Å⁻⁴**, not physical Å⁻⁴ (and that is
   load-bearing numerically, not cosmetic — see the module docstring);
3. they multiply the **literal monomials** h^H k^K l^L, whereas other codes fold
   symmetry multiplicities into their templates (writing the cubic S220 term as
   `3·(h²k² + h²l² + k²l²)`, say), so their printed values differ by small
   integer factors as well.

A manual that reproduces Stephens (1999) equation (1) without all three is
worse than no manual: a reader would transfer literature S values straight in
and get a wrong width law that still refines. The same applies to the
size↔1/cosθ, strain↔tanθ letter conventions already in `profiles/caglioti.py`
(GSAS and FullProf swap X/Y).

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
