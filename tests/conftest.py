"""Suite-wide hygiene and the fixtures that share an expensive refinement.

Four things live here, in the order they have to happen:

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

Shared expensive results (``sample1_results``, ``srm660c_baseline``) are
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
    ``magnetic.isotropy.IDENTIFY_REFUSALS``).
    """
    import spglib.error

    before = spglib.error.OLD_ERROR_HANDLING
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
