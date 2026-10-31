"""Guards on the validation matrix — fast, so they are paid per push.

The matrix (``tests/validation_matrix.py``) is only worth having if it cannot
drift from the suites it describes.  The failure mode it exists to prevent is
specific and has already happened once in this repo: README's validation
section said "eight acceptance suites" while nine were committed, because the
table was maintained by hand and nothing checked it.

So: the registry and the acceptance tree are held in **bijection** by AST
collection (not by import, which a decorator or a module-level fixture could
satisfy without a real test existing), tiers come from a closed vocabulary,
and ``docs/VALIDATION.md`` is asserted byte-identical to its regeneration.
Adding an acceptance test without a matrix row fails here, in ~50 ms, rather
than being noticed a milestone later.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from tests.validation_matrix import (
    CLAIM_TIERS,
    CLAIMS,
    CLOSING_WINDOW_TOL_DEFAULT,
    DATASET_STATES,
    DATASETS,
    DISPERSION_DEFAULT_ON,
    FEATURE_TESTS,
    GAPS,
    INTERMEDIATE_FTOL_DEFAULT,
    REFERENCE_KINDS,
    START_DEPENDENCE_RULE,
    TIERS,
    render_markdown,
    validates,
    verifies,
)

TESTS = pathlib.Path(__file__).resolve().parent
ROOT = TESTS.parent
DATA = TESTS / "data"
SRC = ROOT / "src" / "rietx"


def _collected() -> dict[str, list[str]]:
    """{module stem: [test function names]} over the acceptance suites.

    AST rather than import: a row must correspond to a `def test_*` that
    actually exists in the file, and parsing is also what keeps this guard
    fast enough to live in the non-slow suite.
    """
    out: dict[str, list[str]] = {}
    for path in sorted(TESTS.glob("test_acceptance_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out[path.stem] = [
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
    return out


def test_every_acceptance_test_has_a_matrix_row() -> None:
    """A new acceptance suite cannot land unregistered."""
    registered = {(c.module, c.test) for c in CLAIMS}
    live = {(mod, name) for mod, names in _collected().items() for name in names}

    missing = sorted(live - registered)
    assert not missing, (
        "acceptance tests with no row in tests/validation_matrix.py: "
        f"{missing}.  Add a Claim naming what its tolerance is referenced to "
        "— an unregistered bar is a number nobody can interpret.")


def test_every_matrix_row_names_a_live_test() -> None:
    """And a row cannot outlive the test it describes."""
    registered = {(c.module, c.test) for c in CLAIMS}
    live = {(mod, name) for mod, names in _collected().items() for name in names}

    stale = sorted(registered - live)
    assert not stale, (
        f"matrix rows whose test no longer exists: {stale}.  Delete the row "
        "or fix the name; a matrix describing tests that do not run is worse "
        "than no matrix.")


def test_rows_are_unique() -> None:
    keys = [(c.module, c.test) for c in CLAIMS]
    assert len(keys) == len(set(keys)), "duplicate rows in CLAIMS"


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c.test)
def test_row_tiers_come_from_the_closed_vocabulary(claim) -> None:
    """No suite gets to invent an eighth kind of reference in a docstring."""
    assert claim.tiers, f"{claim.test} names no tier"
    unknown = [t for t in claim.tiers if t not in TIERS]
    assert not unknown, (
        f"{claim.test} names tier(s) {unknown} that are not in TIERS.  Adding "
        "a tier is deliberate: write its rule in validation_matrix.TIERS "
        "first, so the vocabulary stays closed.")
    assert len(set(claim.tiers)) == len(claim.tiers), (
        f"{claim.test} repeats a tier")


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c.test)
def test_every_claiming_row_states_its_reference_value(claim) -> None:
    """`ceiling` alone claims nothing; anything else must say against what."""
    claims_something = any(t in CLAIM_TIERS for t in claim.tiers)
    if claims_something:
        assert claim.reference.strip(), (
            f"{claim.test} carries tier(s) {claim.tiers} but no reference.  A "
            "tolerance without its reference value is not a claim.")
    assert claim.claim.strip(), f"{claim.test} does not say what it claims"
    assert claim.measured.strip(), (
        f"{claim.test} records no measured margin.  Freezing it is how a bar "
        "that quietly drifts toward its tolerance shows up in a diff while "
        "the test is still green.")


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c.test)
def test_row_dataset_resolves(claim) -> None:
    assert claim.dataset in DATASETS, (
        f"{claim.test} names dataset {claim.dataset!r}, which is not in "
        "DATASETS")
    path = DATA / DATASETS[claim.dataset].path
    assert path.exists(), f"tests/data/{DATASETS[claim.dataset].path} is missing"


def test_every_dataset_is_used() -> None:
    used = {c.dataset for c in CLAIMS}
    unused = sorted(set(DATASETS) - used)
    assert not unused, (
        f"datasets registered but claimed by no test: {unused}.  A dataset "
        "nothing asserts against is not validation.")


def test_a_circular_dataset_never_carries_a_certificate_row() -> None:
    """The 11-BM SRM 660a fence, made executable.

    That file's wavelength was calibrated at the beamline against LaB6
    itself, so a refined LaB6 cell reproduces the certificate by
    construction.  It lands 16 ppm away, which is worth recording as
    consistency and is *not* evidence of accuracy.  The absolute anchors are
    SRM 660c and SRM 676a; this guard is what stops a future session from
    quietly promoting a circular number to an anchor.
    """
    for claim in CLAIMS:
        if DATASETS[claim.dataset].role != "consistency":
            continue
        assert "certificate" not in claim.tiers, (
            f"{claim.test} claims the `certificate` tier on dataset "
            f"{claim.dataset!r}, whose agreement with its own standard is "
            "circular (the beamline calibrated lambda against this very "
            "standard).  Use `characterisation` and say so in the reference.")


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c.test)
def test_start_dependence_is_declared(claim) -> None:
    """Width/shape parameters through a sqrt, cone or floor need a sweep.

    Rule 2 of START_DEPENDENCE_RULE.  The Stephens rows are the measured
    reason it exists: over four seeds the coefficients span ~100 % relative
    and the cone violation count goes 15, 12, 0, 0 — a single-start number
    would have called that specimen fine or broken by luck.
    """
    assert claim.starts >= 1
    if claim.module == "test_acceptance_stephens" and "strain" in claim.claim.lower():
        assert claim.starts >= 4, (
            f"{claim.test} quotes strain coefficients from {claim.starts} "
            "start(s); the seed sweep is what makes them interpretable")


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c.test)
def test_named_diagnostic_codes_exist(claim) -> None:
    """A row cannot name a diagnostic the package does not emit."""
    if not claim.diagnostics:
        return
    sources = "\n".join(
        p.read_text(encoding="utf-8") for p in SRC.rglob("*.py"))
    for code in claim.diagnostics:
        bare = code[1:] if code.startswith("!") else code
        assert f'"{bare}"' in sources, (
            f"{claim.test} names diagnostic {bare!r}, which no module in "
            "src/rietx emits")


def test_every_acceptance_suite_declares_its_dispersion_setting() -> None:
    """A suite that pins numbers must not inherit a physics default.

    WP-1001 made ``Source.dispersion`` the package default and measured what
    that costs a tree whose suites rode the old one: 21 tests moved at once,
    including nine bit-identity goldens, and the failures did not distinguish
    "this protocol deliberately excludes dispersion" from "nobody thought
    about it".  Declaring the setting is what makes that distinction
    reviewable — and it is the same rule as adopting another code's protocol,
    which means adopting what it did *not* model as much as what it did.

    A suite may declare it directly or inherit from a builder it imports; both
    show up as the token appearing in the module that owns the protocol, which
    is what this checks.
    """
    undeclared = []
    for path in sorted(TESTS.glob("test_acceptance_*.py")):
        text = path.read_text(encoding="utf-8")
        if "dispersion" not in text:
            undeclared.append(path.name)
    assert not undeclared, (
        f"acceptance suites that never name `dispersion`: {undeclared}.  Set "
        "`instrument.source.dispersion` explicitly (to None to decline it, or "
        "to Dispersion() to apply it) and say in a comment why — riding the "
        "package default means these numbers silently re-baseline the next "
        "time the default moves.")


def test_the_recorded_dispersion_decision_matches_the_live_schema() -> None:
    """The matrix records a decision; this is what keeps it a *fact*.

    Flipping ``Source.dispersion`` back without revisiting the grounds
    written in validation_matrix.DISPERSION_DEFAULT_ON fails here — the
    decision and the code cannot drift apart silently, which is the same
    contract the generated doc has.
    """
    from rietx.schemas.instrument import EmissionLine, Source

    live = Source(lines=[EmissionLine(wavelength=1.5406)]).dispersion is not None
    assert live == DISPERSION_DEFAULT_ON, (
        f"Source.dispersion defaults to {'on' if live else 'off'} but the "
        f"validation matrix records {'on' if DISPERSION_DEFAULT_ON else 'off'}."
        "  If the default is being changed, update DISPERSION_DEFAULT_ON *and* "
        "the grounds above it — the measured trade is recorded there.")


def test_every_acceptance_suite_declares_its_convergence_schedule() -> None:
    """The ``dispersion`` rule one field along (WP-1123).

    ``RefinementPlan.intermediate_ftol`` decides how hard every stage but the
    last is converged, and it moves answers — bounded at 0.02 esd, but a
    certificate comparison is where 0.02 esd is worth stating.  A suite that
    never names it cannot say whether it wanted the shipped schedule or simply
    inherited whatever shipped, which is the distinction that made 21 tests
    ambiguous at once when the dispersion default flipped.
    """
    undeclared = []
    for path in sorted(TESTS.glob("test_acceptance_*.py")):
        if "intermediate_ftol" not in path.read_text(encoding="utf-8"):
            undeclared.append(path.name)
    assert not undeclared, (
        f"acceptance suites that never name `intermediate_ftol`: {undeclared}."
        "  Set it on the plan explicitly — to the shipped value to say these "
        "numbers are what a user's own run produces, or to None to converge "
        "every stage — and say in a comment which and why.")


def test_every_acceptance_suite_declares_its_closing_stage() -> None:
    """The schedule rule one field along (WP-2002).

    ``RefinementPlan.closing_window_tol`` decides whether a plan ends in a
    closing stage at tight windows, and it moves answers by up to an esd.  A
    suite that never names it cannot say whether it wanted the shipped closing
    stage or inherited it.
    """
    undeclared = [path.name for path in sorted(TESTS.glob("test_acceptance_*.py"))
                  if "closing_window_tol" not in path.read_text(encoding="utf-8")]
    assert not undeclared, (
        f"acceptance suites that never name `closing_window_tol`: {undeclared}."
        "  Set it on the plan explicitly — to the shipped value to say these "
        "numbers are what a user's own run produces, or to None for no closing "
        "stage — and say in a comment which and why.")


def test_the_recorded_closing_stage_matches_the_live_plan() -> None:
    """``CLOSING_WINDOW_TOL_DEFAULT``'s record, held to the live default."""
    import rietx as rx

    live = rx.RefinementPlan(stages=[]).closing_window_tol
    assert live == CLOSING_WINDOW_TOL_DEFAULT, (
        f"RefinementPlan.closing_window_tol defaults to {live} but the "
        f"validation matrix records {CLOSING_WINDOW_TOL_DEFAULT}.  If the "
        "default is being changed, update CLOSING_WINDOW_TOL_DEFAULT *and* the "
        "grounds above it.")


def test_the_recorded_convergence_schedule_matches_the_live_plan() -> None:
    """What keeps the record above a fact rather than a memory.

    Moving the default without revisiting the measured trade written beside
    ``INTERMEDIATE_FTOL_DEFAULT`` fails here.
    """
    import rietx as rx

    live = rx.RefinementPlan(stages=[]).intermediate_ftol
    assert live == INTERMEDIATE_FTOL_DEFAULT, (
        f"RefinementPlan.intermediate_ftol defaults to {live} but the "
        f"validation matrix records {INTERMEDIATE_FTOL_DEFAULT}.  If the "
        "default is being changed, update INTERMEDIATE_FTOL_DEFAULT *and* the "
        "grounds above it — the measured trade is recorded there.")


def test_tier_rules_are_written() -> None:
    for name, rule in TIERS.items():
        assert len(rule) > 120, (
            f"tier {name!r} has no written rule.  The vocabulary is only "
            "useful if each entry says what qualifies.")


def test_gaps_are_recorded_with_what_would_close_them() -> None:
    assert len(GAPS) >= 5
    for title, body in GAPS:
        assert title.strip() and len(body) > 80, (
            f"gap {title!r} does not say what would close it.  A matrix that "
            "lists only what passed is marketing.")


def test_start_dependence_rule_has_three_parts() -> None:
    assert START_DEPENDENCE_RULE == 3


def test_the_generated_doc_is_committed_and_current() -> None:
    """docs/VALIDATION.md is output, not a hand-maintained table.

    The same executable-doc design as the theory manual (WP-0604): if the
    registry moves and the doc does not, the fast suite fails here rather
    than the two diverging silently for a milestone.
    """
    doc = ROOT / "docs" / "VALIDATION.md"
    assert doc.exists(), (
        "docs/VALIDATION.md is missing; regenerate with "
        "`.venv/bin/python -m tests.validation_matrix`")
    assert doc.read_text(encoding="utf-8") == render_markdown(), (
        "docs/VALIDATION.md has drifted from tests/validation_matrix.py.  "
        "Regenerate it: `.venv/bin/python -m tests.validation_matrix`  "
        "(the doc is generated output — edit the registry, not the doc).")


# ---------------------------------------------------------------------------
# The feature registry and its join (WP-2010).  ``rietx.features`` names every
# feature once; these hold it to the help vocabulary and the Theory headings,
# both ways, and to the claims and tests that verify and validate it.
# ---------------------------------------------------------------------------

THEORY = ROOT / "docs" / "docs" / "theory"


def _theory_headings() -> list[str]:
    """Every H2 and H3 of the Theory tab, ``"<page> § <heading text>"``.

    Fenced blocks are skipped, so a ``## `` inside a code example is not a
    heading; ``index.md`` and ``references.md`` hold no topic.
    """
    out: list[str] = []
    for page in sorted(THEORY.glob("*.md")):
        if page.name in ("index.md", "references.md"):
            continue
        fence = False
        for line in page.read_text(encoding="utf-8").splitlines():
            if line.startswith("```"):
                fence = not fence
                continue
            if fence:
                continue
            for marks in ("## ", "### "):
                if line.startswith(marks):
                    out.append(f"{page.stem} § {line[len(marks):].strip()}")
    return out


def _partition_errors(vocabulary: list[str], features, not_features) -> list[str]:
    """What breaks the partition: a key claimed twice, unclaimed, or dead.

    ``vocabulary`` is the live set (help keys and Theory headings together);
    each must be claimed by exactly one feature or exempted once, and every
    key a feature or an exemption names must be live.
    """
    owner: dict[str, str] = {}
    errors: list[str] = []
    for name, f in features.items():
        for key in (*f.parameters, *f.instrument_fields, *f.theory):
            if key in owner:
                errors.append(f"{key!r} is claimed by {owner[key]} and {name}")
            owner[key] = name
    for key in not_features:
        if key in owner:
            errors.append(f"{key!r} is claimed by {owner[key]} and exempted")
        owner[key] = "NOT_FEATURES"
    live = set(vocabulary)
    errors += [f"{key!r} is claimed by no feature and not exempted"
               for key in vocabulary if key not in owner]
    errors += [f"{key!r} ({who}) names nothing on the tree"
               for key, who in owner.items() if key not in live]
    return errors


def _vocabulary() -> list[str]:
    from rietx.help import INSTRUMENT_FIELD_HELP, PARAMETER_HELP

    return [*PARAMETER_HELP, *INSTRUMENT_FIELD_HELP, *_theory_headings()]


def test_the_features_partition_the_help_vocabulary_and_the_theory_headings() -> None:
    """Both ways: a new family or heading no feature claims fails by name,
    and so does a key the registry names that the tree no longer has."""
    from rietx.features import FEATURES, NOT_FEATURES

    errors = _partition_errors(_vocabulary(), FEATURES, NOT_FEATURES)
    assert not errors, (
        "the feature registry does not partition the help vocabulary and the "
        "Theory headings:\n  " + "\n  ".join(errors) + "\nA new help family "
        "or Theory heading joins a feature in src/rietx/features.py (or "
        "NOT_FEATURES with its reason); a renamed one is renamed there too.")


def test_the_partition_check_names_a_new_family_and_a_dead_key() -> None:
    """The positive arm: the check above can fail, and says which key."""
    from dataclasses import replace

    from rietx.features import FEATURES, NOT_FEATURES

    vocabulary = [*_vocabulary(), "phases.*.throwaway_family"]
    errors = _partition_errors(vocabulary, FEATURES, NOT_FEATURES)
    assert errors == ["'phases.*.throwaway_family' is claimed by no feature "
                      "and not exempted"]
    feats = dict(FEATURES)
    feats["qpa"] = replace(feats["qpa"], theory=(*feats["qpa"].theory,
                                                 "corrections § Gone"))
    errors = _partition_errors(_vocabulary(), feats, NOT_FEATURES)
    assert errors == ["'corrections § Gone' (qpa) names nothing on the tree"]


def test_a_feature_with_no_theory_heading_declares_why() -> None:
    """The four featureless topics: a heading or a declared exception, not
    both and not neither."""
    from rietx.features import FEATURES

    for name, f in FEATURES.items():
        assert bool(f.theory) != bool(f.no_theory.strip()), (
            f"{name}: give it Theory headings or a no_theory reason, never "
            "both or neither")
    assert sorted(n for n, f in FEATURES.items() if f.no_theory) == [
        "extinction_symbols", "joint_refinement", "peak_picking_and_fitting",
        "tof_profile"]


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c.test)
def test_a_claim_names_registered_features(claim) -> None:
    from rietx.features import FEATURES

    unknown = [f for f in claim.features if f not in FEATURES]
    assert not unknown, (
        f"{claim.test} names feature(s) {unknown} that rietx.features does "
        "not register")
    assert len(set(claim.features)) == len(claim.features)


def test_every_feature_is_verified_by_a_claim_or_a_named_test() -> None:
    """A feature ships verified or does not ship (DESIGN.md § Rules, 2)."""
    from rietx.features import FEATURES

    verified = {f for c in CLAIMS if verifies(c) for f in c.features}
    bare = sorted(f for f in FEATURES
                  if f not in verified and f not in FEATURE_TESTS)
    assert not bare, (
        f"features no claim and no named test verifies: {bare}.  Name the "
        "test that checks each against a formula, a published table, another "
        "code or a known answer in validation_matrix.FEATURE_TESTS, write one, "
        "or fence the feature until one exists.")
    assert set(FEATURE_TESTS) <= set(FEATURES), (
        f"FEATURE_TESTS names features the registry lacks: "
        f"{sorted(set(FEATURE_TESTS) - set(FEATURES))}")


def test_every_test_a_feature_names_exists() -> None:
    """By AST, as the claims are: the name must be a ``def test_*``."""
    missing = []
    for feature, tests in FEATURE_TESTS.items():
        for node_id in tests:
            module, name = node_id.split("::")
            path = TESTS / module
            if not path.exists():
                missing.append(f"{feature}: {node_id} (no file)")
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names = {n.name for n in ast.walk(tree)
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if name not in names:
                missing.append(f"{feature}: {node_id}")
    assert not missing, f"FEATURE_TESTS names tests that do not exist: {missing}"


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c.test)
def test_every_prediction_names_its_reference_values_kind(claim) -> None:
    """The kind decides whether the row verifies or validates (WP-2010)."""
    if "prediction" in claim.tiers:
        assert claim.reference_kind in REFERENCE_KINDS, (
            f"{claim.test} is a prediction and names reference_kind "
            f"{claim.reference_kind!r}; use one of {sorted(REFERENCE_KINDS)}")
    else:
        assert not claim.reference_kind, (
            f"{claim.test} names a reference_kind but is not a prediction")


def test_the_predictions_that_verify_rather_than_validate() -> None:
    """The retier of 2026-10-31 by rule, enumerated so a change shows here.

    Yue's ruling on #1051 counted 6 or 7 of the 9 ``prediction`` rows; the rule
    gives 8: his seven (two capillary identities, three Nd₂Ru₂O₇
    joint-wavelength rows, Si 640c against XND, the v0.3 microabsorption table)
    and the bethanechol zeroshift row, whose prediction is checked against the
    package's own collinearity statistic.  The ninth, the dispersion fractions
    against the weighed compositions, validates.
    """
    verifying = {c.test for c in CLAIMS
                 if "prediction" in c.tiers and not validates(c)}
    assert verifying == {
        "test_capillary_absorption_is_an_exact_reparameterisation",
        "test_the_absorption_shift_is_independent_of_dispersion",
        "test_the_refined_wavelength_is_the_solo_cell_disagreement",
        "test_swapping_which_wavelength_is_held_measures_the_same_ratio",
        "test_the_neutron_widths_leave_one_esd_at_every_start",
        "test_the_symmetric_window_recovers_xnd_to_sub_ppm",
        "test_the_microabsorption_shape_was_mostly_dispersion",
        "test_the_2004_zeroshift_hypothesis_cannot_be_tested_on_these_data",
    }
    validating = {c.test for c in CLAIMS
                  if "prediction" in c.tiers and validates(c)}
    assert validating == {"test_sample1_fractions_beat_the_dispersion_free_fit"}


def test_the_registry_bit_is_the_matrix_derivation() -> None:
    """``Feature.independently_measured`` is a copy the report reads at run
    time; this is what keeps it the matrix's answer."""
    from rietx.features import FEATURES

    validated = {f for c in CLAIMS if validates(c) for f in c.features}
    wrong = sorted(n for n, f in FEATURES.items()
                   if f.independently_measured != (n in validated))
    assert not wrong, (
        f"rietx.features disagrees with the matrix on {wrong}: set "
        "independently_measured to whether a validating claim names it")
    assert len(validated) == 11


def test_every_dataset_state_is_one_of_rule_twos_three() -> None:
    for key, ds in DATASETS.items():
        assert ds.state in DATASET_STATES, f"{key}: state {ds.state!r}"
