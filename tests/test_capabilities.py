"""WP-1007 — capabilities(), structured guard findings, and the missing exports.

Two kinds of test here, and the second is the interesting one:

* **Registry meta-tests.** Every member of every live registry must appear in its
  arm of ``capabilities()`` (the WP-0602 pattern — a restated literal union went
  stale two days after the torch backend landed). These fail when someone adds a
  backend, solver, plan, mode, anode or reader format and forgets the arm.
* **A byte-for-byte pin on the guard strings.** ``GuardReport`` used to hold
  formatted text and now holds :class:`GuardFinding` objects; the rendered form
  is a published surface (the diagnostics' messages are built from it), so the
  expected strings below are literals copied from the pre-change output, not
  re-derived from the code that produces them.
"""

from __future__ import annotations

import json
from importlib.metadata import version
from typing import get_args

import numpy as np
import pytest

import rietx as rx
from rietx.backend.api import BACKEND_NAMES, EXPERIMENTAL_BACKENDS
from rietx.background.diagnostics import _KBETA
from rietx.capabilities import capabilities
from rietx.io.readers import PATTERN_FORMATS
from rietx.optimize.least_squares import SOLVERS
from rietx.refine import _guard_diagnostics
from rietx.schemas.common import Mode
from rietx.schemas.instrument import _RADIATIONS
from rietx.strategy.staged import PLAN_INFO, PLAN_PRESETS, GuardFinding, GuardReport


@pytest.fixture(scope="module")
def caps():
    return capabilities()


# --------------------------------------------------------- registry arms
def test_every_backend_appears_with_its_flags(caps):
    assert [b.name for b in caps.backends] == list(BACKEND_NAMES)
    by_name = {b.name: b for b in caps.backends}
    assert by_name["numpy"].available and not by_name["numpy"].experimental
    assert by_name["numpy"].requires is None
    for name in EXPERIMENTAL_BACKENDS:
        assert by_name[name].experimental, f"{name} is registered experimental"
    # availability is a property of *this* machine, not of the registry — the
    # question a backend menu needs answered and the registry cannot answer
    assert by_name["jax"].requires == "jax"
    assert isinstance(by_name["jax"].available, bool)
    # the Apple-GPU row is the only one that is not fp64 throughout
    assert by_name["torch-mps"].dtype == "float64/jacobian:float32"


def test_every_solver_mode_and_plan_appears(caps):
    assert caps.solvers == list(SOLVERS)
    assert caps.modes == list(get_args(Mode))
    assert {p.name for p in caps.plans} == set(PLAN_PRESETS)
    # the four facts come from PLAN_INFO, not restated here
    for plan in caps.plans:
        info = PLAN_INFO[plan.name]
        assert (plan.title, plan.description, plan.when_to_use) == \
               (info.title, info.description, info.when_to_use)
        assert plan.modes == list(info.modes)
    # modes is plural for a reason: profile_only is both a Le Bail plan and a
    # no-structure Rietveld one, so a one-plan-one-mode arm would be wrong
    assert len(PLAN_INFO["profile_only"].modes) == 2


def test_every_search_preset_appears_with_its_ceiling(caps):
    """WP-1042: the search_presets arm quotes the live registry, never a
    restatement — same meta-test as plans, one registry over."""
    from rietx.indexing.engines import (
        DEFAULT_SEARCH_PRESET,
        SEARCH_PRESET_INFO,
        SEARCH_PRESETS,
    )

    assert {p.name for p in caps.search_presets} == set(SEARCH_PRESETS)
    for cap in caps.search_presets:
        info = SEARCH_PRESET_INFO[cap.name]
        assert (cap.title, cap.description, cap.when_to_use) == \
               (info.title, info.description, info.when_to_use)
        assert cap.total_budget_seconds == SEARCH_PRESETS[cap.name]
        assert cap.typical_seconds == info.typical_seconds
        assert cap.default == (cap.name == DEFAULT_SEARCH_PRESET)
    # exactly one default, and it is the one index_pattern resolves
    assert sum(p.default for p in caps.search_presets) == 1


def test_the_indexing_control_vocabularies_quote_the_live_registries(caps):
    """WP-1045: the GUI form's checkboxes and selects read these arms, so a
    registered engine (or system, centring, template) missing from them is an
    engine a human cannot ask for — the same meta-test as plans and presets,
    over the four vocabularies the control surface renders."""
    from rietx.indexing.engines import (
        CENTRINGS,
        SYSTEM_ORDER,
        engine_descriptions,
    )
    from rietx.schemas.indexing import SHIFT_TEMPLATES

    assert {e.name for e in caps.indexing_engines} == \
        set(engine_descriptions())
    for cap in caps.indexing_engines:
        assert cap.description == engine_descriptions()[cap.name]
    assert caps.crystal_systems == list(SYSTEM_ORDER)  # order IS information
    assert caps.centrings == {s: list(v) for s, v in CENTRINGS.items()}
    assert caps.shift_templates == list(SHIFT_TEMPLATES)


def test_every_anode_appears_with_its_lines_and_kbeta(caps):
    assert {a.name for a in caps.anodes} == set(_RADIATIONS)
    by_name = {a.name: a for a in caps.anodes}
    for name, lines in _RADIATIONS.items():
        assert by_name[name].wavelengths == list(lines)
    # a Kα1-only entry has one line, and its Kβ is the parent anode's
    assert by_name["CuKa"].kalpha1_only is False
    assert len(by_name["CuKa"].wavelengths) == 2
    assert by_name["CuKa1"].kalpha1_only is True
    assert by_name["CuKa1"].wavelengths == [by_name["CuKa"].wavelengths[0]]
    assert by_name["CuKa1"].kbeta == by_name["CuKa"].kbeta == _KBETA["CuKa"]


def test_every_source_kind_in_the_union_appears_as_a_radiation(caps):
    """The registry here is the ``Instrument.source`` union itself.

    A source kind reachable by ``model_validate`` and absent from the arm is a
    radiation a client cannot discover — the same failure as an unlisted plan,
    one vocabulary over, and the reason ``_source_classes`` reads the annotation
    instead of restating it.
    """
    union = get_args(rx.Instrument.model_fields["source"].annotation)
    live = {get_args(cls.model_fields["kind"].annotation)[0] for cls in union}
    assert {r.kind for r in caps.radiations} == live
    assert live >= {"xray_cw", "neutron_cw"}, "both radiations must be reachable"


def test_each_radiation_reports_what_actually_differs(caps):
    """Derived predicates, so each flag flips with its own feature (WP-1037).

    Checked against the *classes* rather than against expected literals: a
    hand-written ``True`` here would be a second opinion that agreed with itself
    while the field it describes was renamed away.
    """
    from rietx.schemas.instrument import NeutronSource, Source

    by_kind = {r.kind: r for r in caps.radiations}
    for cls, kind in ((Source, "xray_cw"), (NeutronSource, "neutron_cw")):
        arm = by_kind[kind]
        assert arm.anomalous_dispersion == ("dispersion" in cls.model_fields)
        assert arm.polarization_refinable == ("polarization" in cls.model_fields)
        # harmonic support is *not* "has a harmonics field" — both classes do,
        # and only one accepts a value.  The class attribute is the one
        # authority, and ``check_harmonics`` reads the same one.
        assert arm.harmonic_contamination == cls.harmonics_supported

    # and the two disagree, which is the whole reason the arm exists
    assert by_kind["xray_cw"].anomalous_dispersion
    assert not by_kind["neutron_cw"].anomalous_dispersion
    assert by_kind["xray_cw"].harmonic_contamination is False
    assert by_kind["neutron_cw"].harmonic_contamination is True
    # unbounded on both, for different reasons: an X-ray source declares its own
    # line list, and a neutron source can grow one at λ/n.  A source whose
    # spectrum is one wavelength and can be nothing else would report 1 — there
    # is no such class any more, which is what harmonics changed here
    assert by_kind["neutron_cw"].max_emission_lines is None
    assert by_kind["xray_cw"].max_emission_lines is None
    # every entry is documented rather than defaulting to its own discriminator
    assert all(r.title != r.kind and r.scatterer != "undocumented"
               for r in caps.radiations)


def test_the_anode_arm_says_nothing_about_a_neutron_source(caps):
    """``anodes`` is a sub-vocabulary of one radiation, which is why both arms
    exist: a client reading ``anodes`` alone would conclude this build does
    X-rays only."""
    assert all(a.wavelengths for a in caps.anodes)
    assert "neutron_cw" not in {a.name for a in caps.anodes}


def test_every_reader_format_appears_in_dispatch_order(caps):
    assert [r.name for r in caps.reader_formats] == [f.name for f in PATTERN_FORMATS]
    by_name = {r.name: r for r in caps.reader_formats}
    # the arm states what read_pattern actually sniffs, sourced from the registry
    assert "BANK" in by_name["gsas"].sniff
    assert ".cif" in by_name["pdcif"].extensions
    # and it names the reader keyword a caller has to supply *and* record
    assert by_name["pdcif"].options == ["block"]
    assert by_name["xy"].options == []
    # a binary format's sniff has to say what it *refuses* too, since two of the
    # four Bruker RAW versions are recognised in order to be declined and a
    # client choosing what to offer an upload dialog reads this arm (WP-1047)
    assert "RAW4.00" in by_name["bruker_raw"].sniff
    assert by_name["bruker_raw"].options == ["scan"]
    assert PATTERN_FORMATS[0].name == "bruker_raw"       # magic bytes go first
    # every reader that can hold several measurements offers the same keyword,
    # which is what makes ``scan`` a vocabulary rather than one format's quirk
    assert {r.name for r in caps.reader_formats if "scan" in r.options} == {
        "bruker_raw", "rasx", "brml", "ras", "uxd", "xrdml"}


def test_the_reader_option_allowlist_is_exactly_what_the_formats_take(caps):
    """``READER_OPTIONS`` and ⋃ ``fmt.options`` are one vocabulary, two halves.

    The split is what lets ``reader_options_for`` tell a **typo** (no format has
    ever heard of it — a caller error, raises) from an option this particular
    file's format does not take (normal; a UI carries a value across a change of
    file, so it is dropped and reported).  That distinction is only sound while
    the two halves agree, and nothing else would notice if one grew alone.
    """
    from rietx.io.readers import READER_OPTIONS

    union = {o for fmt in PATTERN_FORMATS for o in fmt.options}
    assert set(READER_OPTIONS) == union
    # and the arm quotes the allowlist, so a client renders every control
    assert [o.name for o in caps.reader_options] == sorted(READER_OPTIONS)
    assert all(o.kind in ("str", "int") and o.help for o in caps.reader_options)


def test_every_versioned_contract_is_a_live_value(caps):
    """Six of them since WP-1003 — and the count is why they live in the arm.

    A contract named only in prose is a contract someone forgets to add; this
    test fails on a ``*_version`` field whose value is not the constant it
    claims to quote, and the field list below is checked against the model, so
    a seventh contract cannot arrive unnoticed either.  The sixth is the
    proof: ``INDEXING_THRESHOLDS_VERSION`` rode on every ``IndexingResult``
    for four WPs before the WP-1003 review noticed the arm did not quote it.
    """
    from rietx.gui.textdoc import FORMAT_VERSION as TEXTDOC_FORMAT_VERSION
    from rietx.history.events import EVENT_SCHEMA_VERSION
    from rietx.report.schemas import THRESHOLDS_VERSION
    from rietx.schemas.common import SCHEMA_VERSION
    from rietx.schemas.indexing import INDEXING_THRESHOLDS_VERSION
    from rietx.schemas.project import PROJECT_FORMAT_VERSION

    live = {
        "schema_version": SCHEMA_VERSION,
        "report_thresholds_version": THRESHOLDS_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "project_format_version": PROJECT_FORMAT_VERSION,
        "textdoc_format_version": TEXTDOC_FORMAT_VERSION,
        "indexing_thresholds_version": INDEXING_THRESHOLDS_VERSION,
    }
    declared = {name for name in type(caps).model_fields
                if name.endswith("_version") and name != "package_version"}
    assert declared == set(live), "a versioned contract is missing from the arm"
    for name, constant in live.items():
        assert getattr(caps, name) == constant
    assert caps.package_version and caps.package_version[0].isdigit()


def test_the_installed_distribution_resolves_under_the_name_we_ask_for(caps):
    """The one failure mode `caps.package_version[0].isdigit()` cannot see.

    Asking ``importlib.metadata.version`` for a name no distribution carries —
    a rename that missed ``pyproject.toml``, or a package directory renamed
    ahead of its reinstall — is a *successful* lookup of nothing: it raises
    ``PackageNotFoundError``, ``refine`` falls back, and ``0.0.0+dev`` is
    stamped into every result's provenance, every history header and every
    project.  The assertion above passes on it, because ``"0"`` is a digit, and
    an audit for a stale name cannot catch it either, because nothing stale is
    left behind (WP-1062).
    """
    from rietx._about import DIST_NAME
    from rietx.refine import _DEV_VERSION, _VERSION

    assert version(DIST_NAME), f"no installed distribution named {DIST_NAME!r}"
    assert _VERSION != _DEV_VERSION
    assert caps.package_version == _VERSION


def test_dunder_version_is_the_same_string_capabilities_reports(caps):
    """``rietx.__version__`` is the first thing anyone types (WP-1110 item 12).

    It raised ``AttributeError`` until WP-1110, so the only answer to "what am
    I running" was ``capabilities().package_version`` — reachable by a caller
    who already knew ``capabilities()`` existed.  Pinned as the *same object*
    rather than an equal string: a second ``importlib.metadata`` lookup here
    would be a second authority, free to disagree with the version every
    ``Provenance``, ``TreeHeader`` and ``project.json`` was stamped from.
    """
    import rietx
    from rietx.refine import _VERSION

    assert rietx.__version__ is _VERSION
    assert rietx.__version__ == caps.package_version
    assert "__version__" in rietx.__all__


def test_capabilities_survives_json(caps):
    """WP-1008 serves this verbatim, so it has to be JSON all the way down."""
    round_tripped = type(caps).model_validate_json(caps.model_dump_json())
    assert round_tripped == caps
    assert json.loads(caps.model_dump_json())["features"]["indexing"] is True


# ------------------------------------------------------------- features
def test_features_are_derived_not_asserted(caps):
    """A flag must be a predicate over the tree, not a literal.

    And the predicate's *name* must be data, because this test's first version
    was a tautology: it asserted ``features["indexing"] == hasattr(rx, "index")``
    — the very expression the flag computes — so when the export landed as
    ``index_pattern`` (WP-1024) both sides stayed ``False`` together and the
    test kept passing.  The ``is True`` lines below are what break that
    symmetry: they state what the answer *is*, not that the code equals itself.
    """
    assert caps.features["indexing"] is True
    assert caps.features["peak_picking"] is True
    assert caps.features["peak_fitting"] is True
    assert caps.features["cancellation"] is True

    # schema-shaped flags follow the schemas
    assert caps.features["stephens_strain"] == ("microstrain" in rx.Phase.model_fields)
    assert caps.features["anisotropic_adp"] == ("aniso" in rx.Atom.model_fields)

    # the one default whose position changes published numbers (WP-1001)
    assert caps.features["anomalous_dispersion_default_on"] is True

    # the compiled tier (WP-1115), derived from the tier itself rather than
    # from a literal: two flags, because "numba imports here" and "the next
    # residual will use it" are different questions and `RIETX_COMPILED=0`
    # separates them
    from rietx.model import compiled

    assert caps.features["compiled_kernels"] == compiled.available()
    assert caps.features["compiled_kernels_active"] == compiled.enabled()
    assert all(isinstance(v, bool) for v in caps.features.values())


def test_every_surface_flag_names_a_real_export(caps):
    """The WP-1037 meta-test: each flag's export name, checked against an
    authority the flag itself never consults.

    ``_SURFACE_FLAGS`` is the one table both the flags and this test read, so
    the failure mode it closes — flag and test drifting *together* while the
    export is called something else — needs a third party, and ``__all__`` is
    it: a name in the table but absent from ``__all__`` fails here whether or
    not ``hasattr`` happens to find it.
    """
    from rietx.capabilities import _SURFACE_FLAGS

    missing = set(_SURFACE_FLAGS.values()) - set(rx.__all__)
    assert not missing, f"surface flags name exports not in __all__: {missing}"
    # and the table is the source: every one of its flags is served
    assert set(_SURFACE_FLAGS) <= set(caps.features)


def test_the_documented_feature_keys_are_present(caps):
    """Removing a flag is a client-visible change, so make it a loud one."""
    expected = {
        "anisotropic_adp", "preferred_orientation", "stephens_strain",
        "secondary_extinction", "restraints", "surface_roughness",
        "capillary_absorption", "flat_plate_absorption", "anomalous_dispersion",
        "anomalous_dispersion_default_on", "multi_histogram",
        "sequential_series", "project_container", "background_estimation",
        "pattern_diagnostics", "peak_picking", "peak_fitting", "indexing",
        "cancellation", "report_trajectory", "powderline_recipe",
        "compiled_kernels", "compiled_kernels_active",
    }
    assert set(caps.features) == expected


# ------------------------------------------------- the top-level exports
def test_the_pre_fit_calls_are_reachable_from_the_top_level():
    """``auto_background`` and ``diagnose`` are the two calls a client makes
    *before* its first fit, and this module never imported ``background`` at all
    until WP-1007 — so they were the two it had to go digging for."""
    for name in ("auto_background", "diagnose", "capabilities",
                 "PreferredOrientation", "GuardFinding"):
        assert name in rx.__all__, f"{name} missing from __all__"
        assert hasattr(rx, name)

    tt = np.arange(10.0, 60.0, 0.02)
    y = 120.0 + 40.0 * np.exp(-((tt - 30.0) / 0.1) ** 2)
    data = rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist())
    diag = rx.diagnose(data, wavelength=1.5405929)
    assert diag.n_points == len(tt)
    bkg = rx.auto_background(data, diagnostics=diag)
    # held additively or co-refined under a penalty — never subtracted
    assert bkg.kind in {"pspline", "chebyshev", "fixed+chebyshev"}


# ------------------------------------------------------- guard findings
#: (finding, the exact string v0.2–v0.6 put in the GuardReport list).  Literals
#: copied from the pre-change output — re-deriving them from the constructors
#: would test nothing.
RENDERINGS = [
    (GuardFinding.correlation("instrument.zero_shift",
                              "instrument.geometry.sample_displacement", 0.99987),
     "instrument.zero_shift ~ instrument.geometry.sample_displacement (ρ=+1.000)"),
    (GuardFinding.correlation("a", "b", -0.9912), "a ~ b (ρ=-0.991)"),
    (GuardFinding.at_bound("phases.0.atoms.0.biso"), "phases.0.atoms.0.biso"),
    (GuardFinding.background_absorption("phases.0.atoms.1.biso", 0.4612),
     "phases.0.atoms.1.biso (R²=0.46)"),
    (GuardFinding.roughness_absorption(
        "instrument.geometry.surface_roughness.b", 0.9481),
     "instrument.geometry.surface_roughness.b (R²=0.95)"),
    (GuardFinding.nonpositive_adp("phases.0.atoms.0", -1.234e-3),
     "phases.0.atoms.0 (min eigenvalue -1.23e-03 Å²)"),
    (GuardFinding.nonpositive_strain("phases.0.microstrain", 12, 43,
                                     -5.6789e-5, (0, 0, 2)),
     "phases.0.microstrain (12 of 43 reflections, worst σ²(M) -5.68e-05 at (0, 0, 2))"),
]


@pytest.mark.parametrize("finding,expected", RENDERINGS,
                         ids=[f.code for f, _ in RENDERINGS])
def test_rendered_findings_are_unchanged(finding, expected):
    assert str(finding) == expected
    assert finding.message == expected


def test_findings_carry_paths_and_a_number_instead_of_prose():
    rho = GuardFinding.correlation("a", "b", -0.9912)
    assert rho.paths == ("a", "b") and rho.value == pytest.approx(-0.9912)
    bound = GuardFinding.at_bound("x")
    assert bound.paths == ("x",) and bound.value is None  # no number to report
    r2 = GuardFinding.background_absorption("p", 0.46)
    assert r2.code == "BACKGROUND_ABSORPTION" and r2.value == pytest.approx(0.46)


def test_diagnostics_keep_their_messages_and_gain_their_paths():
    """The whole point: identical prose, and ``where`` finally populated.

    ``_guard_diagnostics`` recovered a path with ``msg.split(" ")[0]``, which
    yields nothing usable for a correlation — two paths and no leading one — so
    ``Diagnostic.where`` was **empty** on exactly the finding a GUI most wants to
    make clickable.  Measured before the change on a real degenerate fit:
    ``where == []``.
    """
    report = GuardReport(
        high_correlations=[GuardFinding.correlation(
            "instrument.zero_shift", "instrument.geometry.sample_displacement",
            0.99987)],
        at_bounds=[GuardFinding.at_bound("phases.0.scale")],
        nonpositive_adps=[GuardFinding.nonpositive_adp("phases.0.atoms.0", -1.2e-3)],
    )
    diags = _guard_diagnostics(report)
    assert [d.code for d in diags] == [
        "HIGH_CORRELATION", "BOUND_HIT", "ADP_NOT_POSITIVE_DEFINITE"]

    corr = diags[0]
    assert corr.message == (
        "instrument.zero_shift ~ instrument.geometry.sample_displacement (ρ=+1.000)")
    assert corr.where == ["instrument.zero_shift",
                          "instrument.geometry.sample_displacement"]
    assert diags[1].where == ["phases.0.scale"]
    assert diags[1].message == "phases.0.scale refined to its bound"
    assert diags[2].where == ["phases.0.atoms.0"]
    assert "not positive definite" in diags[2].message

    # every finding reaches a diagnostic, and the codes are one vocabulary
    assert [f.code for f in report.findings()] == [d.code for d in diags]


def test_a_finding_is_immutable_and_hashable():
    """Findings are values: a report can be deduplicated or put in a set."""
    import dataclasses

    a = GuardFinding.correlation("x", "y", 0.99)
    b = GuardFinding.correlation("x", "y", 0.99)
    assert a == b and len({a, b}) == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.value = 0.5
