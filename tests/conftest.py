"""Suite-wide hygiene and the fixtures that share an expensive refinement.

Six things live here, in the order they have to happen:

1. **Headless matplotlib.**  Every test refinement writes obs/calc/diff PNGs
   (CLAUDE.md's Tests convention), so ``MPLBACKEND=Agg`` is set before anything
   can import pyplot and pick an interactive backend.  ``RIETX_TELEMETRY=0``
   goes beside it and for a stricter reason: since WP-1403 a plain ``fit()``
   records itself into ``.rietx/runs`` under the working directory, so a suite
   that did not decline would grow a run directory per fit — thousands of them,
   in whatever directory pytest was launched from.  ``setdefault``, so a
   session deliberately measuring the recorder can still switch it back on
   from outside.  ``test_telemetry.py`` re-enables it per test through
   ``runs.set_enabled``, which is the seam that exists for it, and a meta-test
   there asserts that a plain fit under this environment creates nothing.
2. **A jax persistent compile cache.**  The backend files are jit-compile
   bound, not arithmetic bound; jax keys its on-disk cache by a content hash of
   the computation, so it is safe to share across processes (and across xdist
   workers).  A miss costs exactly what today's run costs.  ``rm -rf
   tests/.jax_cache`` is a clean reset.
3. **Figure autoclose.**  ``result.plot()`` hands back a live figure; most
   plotting tests never close theirs.  The autouse fixture below closes them
   *only* if pyplot was imported, so the ~700 tests that never plot do not pay
   an import.

4. **The ``--dist loadgroup`` guard.**  A parallel run that does not honour the
   ``xdist_group`` marks refits the shared fixtures and mis-measures every
   wall-clock budget, both without failing, so ``pytest_configure`` refuses it
   rather than leaving it to be noticed in a ``--durations`` list.
5. **The ``--jax-cases`` selection, and its guard.**  CI's jax job runs only
   the cases that reach jax, read off their code (``tests/jax_cases.py``,
   WP-2019).  It runs after ``-m``'s own deselection and before the shard
   split.  Wherever jax does not import, a case that skips for want of jax
   while the selection does not hold it fails instead, and so does a module
   skipped at import for it: every leg but the jax job lacks jax, so such a
   case would run on no per-push leg, and a skip is how that would look.
6. **The ``--shard K/N`` selection.**  A CI fast leg runs as N jobs, because
   its two-core runner gives no more workers to add (WP-1547).  Each job keeps
   shard K of the collected files, split by recorded seconds with every file
   and every ``xdist_group`` whole (``tests/shards.py``).  It runs after
   ``-m``'s own deselection, so the split is of the tier being run.

Shared expensive results (``sample1_results``, ``srm660c_baseline``,
``cr2wo6_nuclear``, ``lamno3_nuclear``) are
session-scoped: they exist because several acceptance modules were re-deriving
the *identical* fit.  A consumer must carry the matching
``@pytest.mark.xdist_group`` or a second xdist worker silently recomputes the
whole fixture — see each fixture's docstring for the group name.  The mark is
what pins a consumer to its fixture's worker; the guard above is what makes
sure the marks are being read at all.

The builders those fixtures call stay in their own modules on purpose:
``tests/test_compare_ui.py`` asserts the comparison UI's standards against
their locations field by field, so moving or renaming one breaks that check.
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("JAX_COMPILATION_CACHE_DIR",
                      str(Path(__file__).parent / ".jax_cache"))
# The compiled kernels split their rows across threads (WP-1115).  Under
# ``-n auto`` the suite is already parallel one rank up, so a second layer only
# oversubscribes: N workers × 8 threads on N cores is slower than N × 1, and it
# makes every wall-clock budget in the suite a function of the worker count.
# One thread per worker, unless the run says otherwise.
if os.environ.get("PYTEST_XDIST_WORKER"):
    # `_about` imports nothing, so naming the variable through it costs no
    # import of the package this must run before (CLAUDE.md § Conventions)
    from rietx._about import COMPILED_THREADS_ENV

    os.environ.setdefault(COMPILED_THREADS_ENV, "1")


@pytest.fixture(autouse=True)
def _spglib_error_mode_is_not_a_shared_global():
    """Put back the error mode an imported oracle changes under everyone's feet.

    ``spgrep/__init__.py`` (0.7.0) sets ``spglib.error.OLD_ERROR_HANDLING =
    False`` when it is imported, and it is imported *inside* the oracle tests of
    ``tests/test_magnetic_irreps.py``.  From that point on, in that xdist
    worker, spglib **raises** where it used to return ``None``, so
    ``crystallography.magnetic.operators.identify()`` — which reads the
    ``None`` — leaks a ``SpglibError`` instead of the ``ValueError`` it
    documents.  Tests in two other files then fail or pass according to how
    ``-n auto`` happened to deal them: measured 2026-09-06, three failures on
    worker gw4 and none anywhere else, and green in every serial run.

    Restoring the flag per test is the suite-wide half of the fix; the other
    half is that a caller should catch both (see
    ``magnetic.isotropy.IDENTIFY_REFUSALS``, ``wyckoff.SPGLIB_REFUSALS`` and
    ``indexing.reduce.SPGLIB_REFUSALS``).

    It **sets** spglib's own default rather than preserving whatever it finds
    (Yue's review of #389).  The two are not the same: a collection-time import
    of spgrep — a conftest, a module-scope import in a test file, a plugin —
    happens before any fixture runs, so "restore what I found" would preserve
    the broken mode for the whole worker and every test would run in the state
    this fixture exists to prevent.  ``True`` is what spglib itself defaults to,
    so a test that says nothing about the mode gets spglib's documented one; a
    test that wants the other mode sets it and is restored here.
    """
    import spglib.error

    before = spglib.error.OLD_ERROR_HANDLING
    spglib.error.OLD_ERROR_HANDLING = True
    yield
    spglib.error.OLD_ERROR_HANDLING = before


#: The one ``--dist`` that honours ``@pytest.mark.xdist_group``.  ``load``
#: distributes by test and ``loadscope``/``loadfile`` by scope and file, so all
#: three deal a group's members to whichever worker is free.
REQUIRED_DIST = "loadgroup"


def pytest_configure(config: pytest.Config) -> None:
    """Refuse a parallel run that would silently ignore the ``xdist_group`` marks.

    ``-n`` on its own leaves xdist at ``--dist load``, and the marks then do
    nothing.  Two things break, both of them quietly:

    * a shared session fixture (``sample1_results``, ``srm660c_baseline``, and
      every module-scoped refinement pinned the same way) is rebuilt by each
      worker that draws one of its consumers, so the sharing costs more than it
      saved — the failure this file's own docstring describes;
    * every wall-clock budget in the suite becomes a function of how the tests
      happened to be dealt, which is what turns a runaway guard into a load
      sensor (``tests/CLAUDE.md`` § Budgets in tests).

    Neither shows up as a failure — the run is green, merely slower and
    measuring something else — and the check CLAUDE.md offers for it is a human
    reading a ``--durations`` list for a setup that appears twice.  That is a
    guard that goes quiet, so the invariant is enforced here instead.  Serial
    runs (no ``-n``, or ``-n 0``) are unaffected.  ``-n 1`` is refused with the
    rest: one worker cannot split a group, but the mode is still the one that
    ignores the marks, and ``-n 0`` is how to ask for a serial run.
    """
    n = getattr(config.option, "numprocesses", None)
    if not n:  # None (no -n) or 0 (-n 0, explicitly serial)
        return
    dist = getattr(config.option, "dist", REQUIRED_DIST)
    if dist != REQUIRED_DIST:
        raise pytest.UsageError(
            f"-n {n} with --dist {dist} ignores the xdist_group marks: shared "
            "fixtures refit on every worker that needs one, and the suite's "
            "wall-clock budgets start measuring machine load instead of what "
            f"they assert. Both are silent. Pass --dist {REQUIRED_DIST} "
            "(CLAUDE.md § Commands), or -n 0 to run serially."
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--shard", metavar="K/N", default=None,
        help="run shard K of N: whole files, xdist groups kept together, "
             "split by tests/shard_times.json (tests/shards.py)")
    parser.addoption(
        "--jax-cases", action="store_true", default=False,
        help="run only the cases that reach jax (tests/jax_cases.py)")


#: Why a marked case on this worker did not join its group, set where it is found.
_UNGROUPED = pytest.StashKey[str]()


def _refuse_ungrouped(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Fail every case whose ``loadgroup`` did not take, the guard above one rank down.

    ``pytest_configure`` checks the flag, and the flag is not the mechanism.
    xdist groups a case by appending ``@<group>`` to its node id inside its own
    ``pytest_collection_modifyitems``, through a private attribute, and pytest
    9.2.0 moved the id to another (pytest-xdist#1386, fixed on xdist's main
    after 3.8.0).  Under that pair every mark was ignored, the run stayed green
    but for the tests sharing a module's server, and the shared fixtures
    refitted per worker.  This hook runs after xdist's, so a marked case still
    lacking the suffix is the mechanism failing.  The case fails at setup
    (``pytest_runtest_setup`` below), because a ``UsageError`` raised on a
    worker reaches the controller as an INTERNALERROR without its message.
    """
    if not (hasattr(config, "workerinput") and config.getvalue("loadgroup")):
        return
    import xdist

    reason = (f"--dist {REQUIRED_DIST} did not group this case: pytest "
              f"{pytest.__version__} with pytest-xdist {xdist.__version__} drops "
              "the xdist_group marks (pytest-xdist#1386). Install a pair that "
              "groups; pyproject's [dev] pin names one.")
    for item in items:
        if any(True for _ in item.iter_markers("xdist_group")) and "@" not in item.nodeid:
            item.stash[_UNGROUPED] = reason


def pytest_runtest_setup(item: pytest.Item) -> None:
    reason = item.stash.get(_UNGROUPED, None)
    if reason is not None:
        pytest.fail(reason, pytrace=False)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep the cases that reach jax, then shard K's files, after every other
    selection has run.

    Under xdist the controller collects nothing: each worker collects, runs
    this hook and reports its list, and xdist refuses a run whose workers
    disagree.  So both selections are functions of the items alone.
    ``jax_cases.reaches`` reads each case's code, and ``shards.assign`` breaks
    every tie by name, never by collection order or a clock.
    """
    _refuse_ungrouped(config, items)
    if getattr(config.option, "jax_cases", False):
        from tests import jax_cases

        kept: list[pytest.Item] = []
        dropped: list[pytest.Item] = []
        for item in items:
            (kept if jax_cases.reaches(item) else dropped).append(item)
        if dropped:
            config.hook.pytest_deselected(items=dropped)
        items[:] = kept
    spec = getattr(config.option, "shard", None)
    if spec is None:
        return
    from tests import shards

    try:
        k, n = shards.parse(spec)
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from None
    files: list[str] = []
    pairs: list[tuple[str, str | None]] = []
    for item in items:
        try:
            file = item.path.relative_to(config.rootpath).as_posix()
        except ValueError:
            file = item.path.as_posix()
        files.append(file)
        # xdist names an item with several marks after all of them joined
        # ("g_h"); merging each name's files here is the safe superset
        names = [m.args[0] if m.args else m.kwargs.get("name", "default")
                 for m in item.iter_markers("xdist_group")]
        pairs += [(file, str(name)) for name in names] or [(file, None)]
    mine, _ = shards.assign(shards.units(pairs), shards.recorded_seconds(), n)[k - 1]
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item, file in zip(items, files, strict=True):
        (selected if file in mine else deselected).append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = selected


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector: pytest.Collector):
    """Fail a module skipped at import for want of jax that the selection
    cannot reach; leave out one ``--jax-cases`` does not select; and report
    the rest from shard 1 alone.

    A module-level ``importorskip`` skips the file before it has an item, so
    neither selection above can place it.  Rule (c) of ``tests/jax_cases.py``
    reads the module itself, which is how the guard and ``--jax-cases`` judge
    it.  Under ``--shard``, every shard used to report its skip, and on CI's
    first sharded run the py3.14 leg's two shards summed to eight more than
    the unsharded count: jax, torch and six browser files (WP-1547).  A leg's
    passed+skipped must sum to the unsharded total, because that total is how
    a module that never ran gets seen (tests/CLAUDE.md § Quoting numbers).
    """
    report = yield
    if not (report.skipped and isinstance(collector, pytest.Module)):
        return report
    from tests import jax_cases

    config = collector.config
    failure = jax_cases.guard(report.longrepr,
                              lambda: jax_cases.module_reaches(collector.path), collector)
    if failure is not None:
        report.outcome = "failed"
        report.longrepr = failure
        return report
    if getattr(config.option, "jax_cases", False) \
            and not jax_cases.module_reaches(collector.path):
        report.outcome = "passed"   # outside the selection, like a deselected case
        report.longrepr = None
        return report
    spec = getattr(config.option, "shard", None)
    if spec is not None:
        from tests import shards

        try:
            k, _ = shards.parse(spec)
        except ValueError:
            return report   # pytest_collection_modifyitems raises the usage error
        if k != 1:
            report.outcome = "passed"
            report.longrepr = None
    return report


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Fail a case that skips for want of jax where the selection cannot reach it.

    Only where jax does not import, since that is where such a case skips.
    The jax job runs ``--jax-cases`` alone and every other leg lacks jax, so a
    case ``tests/jax_cases.py`` cannot see would run on no per-push leg, and
    its skip would say so to nobody.  An xfail is left alone.
    """
    report = yield
    if not report.skipped or hasattr(report, "wasxfail"):
        return report
    from tests import jax_cases

    failure = jax_cases.guard(report.longrepr, lambda: jax_cases.reaches(item), item)
    if failure is not None:
        report.outcome = "failed"
        report.longrepr = failure
    return report


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    if "matplotlib.pyplot" in sys.modules:
        import matplotlib.pyplot as plt

        plt.close("all")


@pytest.fixture(scope="session")
def sample1_results():
    """The eight IUCr round-robin sample-1 mixtures (cpd-1a..h), fitted once
    under the v0.3 QPA protocol.

    ``test_acceptance_sequential``'s unchained baseline was an exact
    re-derivation of this — same phases, instrument, ``seed_scales`` and
    ``qpa_plan()`` — so the two suites share one set of fits.  History
    recording and the per-sample plots come from the QPA suite's ``_fit``;
    history is record-only and changes no value.

    **Consumers must carry** ``@pytest.mark.xdist_group("qpa-sample1")``, or a
    second worker recomputes all eight refinements.
    """
    from tests.test_acceptance_qpa_roundrobin import (
        SAMPLE1,
        _fit,
        _require_data,
        corundum_phase,
        fluorite_phase,
        qpa_plan,
        zincite_phase,
    )

    _require_data()
    out = {}
    for sample in SAMPLE1:
        _, result = _fit(sample, [corundum_phase(), zincite_phase(),
                                  fluorite_phase()], plan=qpa_plan())
        out[sample] = result
    return out


@pytest.fixture(scope="session")
def cr2wo6_nuclear():
    """The Cr₂WO₆ nuclear-only fits at 150 K and 4 K, fitted once.

    Two suites refined these two files from the same trirutile start under
    the same six stages: WP-1327's moment acceptance
    (``test_acceptance_magnetic``), which seeds its moment fits from them, and
    WP-1326's satellite arm (``test_satellites_acceptance``), which reads
    ``report().satellites`` off them.  WP-1418's ``solve_magnetic`` acceptance
    (``test_magnetic_solve_acceptance``) solves both.  The 4 K fit starts from
    the 150 K one.

    Both ``ref`` objects are live (``report()`` works); do not ``fit()`` them
    again, and copy a model before editing it.

    **Consumers must carry** ``@pytest.mark.xdist_group("magnetic-cr2wo6")``.
    """
    import rietx as rx
    from tests.test_acceptance_magnetic import (
        DATA,
        NUCLEAR_STAGES,
        _fit,
        _instrument,
        _trirutile,
    )

    d4 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_4K.dat")
    d150 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_150K.dat")
    # the nuclear references the magnetic solve starts from, at the declared
    # stages alone (WP-2002): ended in a closing stage, the 150 K reference moves
    # enough that class 3's pair, which a correlation near its threshold folds,
    # no longer folds (moduli 0.514 and 0.131 with esds 0.69 and 2.79)
    ref150, nuc150 = _fit(_trirutile(), _instrument(), d150, NUCLEAR_STAGES,
                          closing_window_tol=None)
    ref4, nuc4 = _fit(ref150.structure.model_copy(deep=True),
                      ref150.instrument.model_copy(deep=True), d4, NUCLEAR_STAGES,
                      closing_window_tol=None)
    return {"d4": d4, "d150": d150, "ref150": ref150, "nuc150": nuc150,
            "ref4": ref4, "nuc4": nuc4}


@pytest.fixture(scope="session")
def lamno3_nuclear():
    """The LaMnO₃ 50 K nuclear-only fit, fitted once.

    WP-1327's moment acceptance (``test_acceptance_magnetic_lamno3``) seeds
    its two moment fits from it, and WP-1418's ``solve_magnetic`` acceptance
    (``test_magnetic_solve_acceptance``) solves it.  ``data`` carries the
    contaminant exclusion the fit was made with.

    ``ref`` is live (``report()`` works); do not ``fit()`` it again, and copy
    a model before editing it.

    **Consumers must carry** ``@pytest.mark.xdist_group("magnetic-lamno3")``.
    """
    import rietx as rx
    from rietx.crystallography.cif import structure_from_cif
    from tests.test_acceptance_magnetic_lamno3 import (
        CONTAMINANT,
        DATA,
        NUCLEAR_STAGES,
        _fit,
        _instrument,
    )

    data = rx.read_pattern(DATA / "gsas2_bt1_lamno3_50K.gsas")
    data = data.model_copy(update={"excluded_regions": [CONTAMINANT]})
    ref, nuc = _fit(structure_from_cif(DATA / "gsas2_bt1_lamno3.cif"),
                    _instrument(), data, NUCLEAR_STAGES)
    return {"data": data, "ref": ref, "nuc": nuc}


@pytest.fixture(scope="session")
def srm660c_baseline():
    """``(data, ref, result)`` for the NIST SRM 660c protocol, fitted once.

    Three suites were running this identical refinement — the acceptance
    itself, the dispersion-off half of ``test_acceptance_dispersion``'s
    ``srm660c_pair``, and the numpy reference of the jax end-to-end test.  All
    three built it from ``build_srm_inputs()`` + ``_nist_calibrated_plan()``,
    the second and third with ``history=False``, which records nothing and
    changes no value.

    ``ref`` is live: it still holds the compiled model, so ``ref.report()``
    works and ``ref.branch().run_stage(...)`` can warm-extend the plan with a
    further stage.  Do not ``fit()`` it again — branch first.

    **Consumers must carry** ``@pytest.mark.xdist_group("srm660c")``.
    """
    import rietx as rx
    from tests.test_acceptance_srm660c import (
        _nist_calibrated_plan,
        build_srm_inputs,
    )

    data, structure, instrument = build_srm_inputs()
    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, plan=_nist_calibrated_plan())
    return data, ref, result
