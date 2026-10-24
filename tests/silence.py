"""The test of silence: for a warning code, a fixture where it must fire and one
where it must stay silent (WP-2037).

The mechanical ground of the generality rule asks this of every flag: "a known
truth (an injected misfit, a weighed impurity), and the flag fires where the
fault is and stays silent where it is not" (``docs/milestones/generality.md``
§ The rule).  A warning costs its reader attention each time it prints, so one
that fires where nothing is wrong spends that attention for nothing, and one
that stopped firing at all is green everywhere.  ``SILENCE`` is where each
code's pair lives, and ``tests/test_silence.py`` runs every pair.  Rust's
``#[expect]`` is the form.

Two halves, and only one of them fails.  A code whose row in
``rietx._audit.ROWS`` declares ``response="warning"`` must have a pair, so an
audit (WP-2004 to 2007) that gives a code that response adds its pair in the
same change.  Every other code some raise site passes ``level="warning"`` is
*listed*, never failed: ``python -m tests.silence`` prints the ones still
without a pair, read off ``docs/reference_pages.diagnostic_index``, the walk
``tests/test_audit_table.py`` holds the response column to.

**Adding a pair.**  Write two functions of no arguments that call the
*narrowest* function raising the code (a reader, a guard check, a diagnostics
builder, never a whole fit where a smaller call reaches the same branch) and
return what it returns: a list of ``Diagnostic`` or ``GuardFinding``, whose
``.code`` the test reads.  ``fires`` builds the fault; ``silent`` builds the
nearest state without it, and may return the findings of several such states,
since silence is asserted on all of them at once.  Take the fixtures from the
test that already pins the code where one exists, imported inside the function
so this module stays cheap to import, and name it in ``source``.  Keep a pair
under about 2 s: the fast tier grows by its tail (``tests/CLAUDE.md`` § Budgets
in tests).  A guard finding is passed through ``refine._guard_diagnostics``, so
the code tested is the one the reader sees.

**A pair verifies; it does not validate.**  Each fixture is built from the
code's own condition, so it shows the branch fires and stays quiet as
written.  The mechanical ground's families (real data with a known truth)
are a separate test, and a pair whose fixtures sit far from the threshold
says nothing about the threshold.
"""

from __future__ import annotations

import dataclasses
import functools
import importlib.util
import pathlib
import sys
import tempfile
from collections.abc import Callable, Iterable

ROOT = pathlib.Path(__file__).resolve().parent.parent


@dataclasses.dataclass(frozen=True)
class Pair:
    """One code's two fixtures, and the test or module they were taken from."""

    fires: Callable[[], Iterable]
    silent: Callable[[], Iterable]
    source: str


def codes(found: Iterable) -> set[str]:
    """The codes among ``Diagnostic``s or ``GuardFinding``s."""
    return {f.code for f in found}


# --------------------------------------------------------------- the CIF reader


def _read_cif(text: str) -> list:
    """``structure_from_cif``'s diagnostics for a CIF given as text."""
    from rietx.crystallography.cif import structure_from_cif

    found: list = []
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "s.cif"
        path.write_text(text, encoding="utf-8")
        structure_from_cif(path, diagnostics=found)
    return found


def _snap_fires() -> list:
    """The 6e oxygen of a corundum-type oxide 2e-4 off its position, with the
    file's own multiplicity 6 beside it: the reader moves it there and says so
    (``cif.py``'s ``_snap_to_stated_multiplicity``)."""
    from tests.test_cif_stated_columns import FE, MULT, O_ROUNDED, _cif

    return _read_cif(_cif([FE, O_ROUNDED], {MULT: ["4", "6"]}))


def _snap_silent() -> list:
    """The same site printed on its position, and the bundled fluorapatite,
    whose Ca1 at 0.3333333333 is the file's own rounding of 1/3 (WP-2037's
    snap floor, ``cif.CIF_PRINTED_ROUNDING``)."""
    from tests.test_cif_stated_columns import FE, MULT, O_EXACT, _cif

    return (_read_cif(_cif([FE, O_EXACT], {MULT: ["4", "6"]}))
            + _read_cif((ROOT / "tests" / "data" / "fluorapatite.cif")
                        .read_text(encoding="utf-8")))


def _multiplicity_fires() -> list:
    """A file stating multiplicity 6 for a site nowhere near a 6e position."""
    from tests.test_cif_stated_columns import FE, MULT, O_FAR, _cif

    return _read_cif(_cif([FE, O_FAR], {MULT: ["4", "6"]}))


def _multiplicity_silent() -> list:
    """The same general site, stated as the 12 it is."""
    from tests.test_cif_stated_columns import FE, MULT, O_FAR, _cif

    return _read_cif(_cif([FE, O_FAR], {MULT: ["4", "12"]}))


def _twins_fires() -> list:
    """P6₃/mmc's 6h site (x, 2x, ¼) printed 1e-3 off, beyond the snap."""
    from tests.test_cif_sites_coincide import _HEX

    return _read_cif(_HEX.format(x="0.828", y="0.657"))


def _twins_silent() -> list:
    """0.1 Å off the position: a real general site, left where it is."""
    from tests.test_cif_sites_coincide import _HEX

    return _read_cif(_HEX.format(x="0.828", y="0.676"))


def _listed_twice_fires() -> list:
    """Rock salt with the Ni orbit listed a second time as an image of the first."""
    from tests.test_cif_sites_coincide import _ROCKSALT

    return _read_cif(_ROCKSALT.format(extra="Ni2 Ni 0.5 0.5 0.0001 1\n"))


def _listed_twice_silent() -> list:
    """The same two rows as a refined split, occupancies 0.523 + 0.481."""
    from tests.test_cif_sites_coincide import _ROCKSALT

    return _read_cif(_ROCKSALT.replace("Ni1 Ni 0 0 0 1", "Ni1 Ni 0 0 0 0.523")
                     .format(extra="Ni2 Ni 0.5 0.5 0.0001 0.481\n"))


# --------------------------------------------------- the instrument-file readers


def _read_prm(text: str, **options) -> list:
    from rietx.io.instrument_profile import read_gsas_prm

    found: list = []
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "sets.prm"
        path.write_text(text, encoding="utf-8")
        read_gsas_prm(path, diagnostics=found, **options)
    return found


def _profile_set_fires() -> list:
    """A bank offering two type-3 profile sets, read without naming one."""
    from tests.test_gsas_prm import _SET3, _prcf_set, _prm

    return _read_prm(_prm() + _prcf_set(2, 3, _SET3))


def _profile_set_silent() -> list:
    """The same file with the set the default would pick named by the caller."""
    from tests.test_gsas_prm import _SET3, _prcf_set, _prm

    return _read_prm(_prm() + _prcf_set(2, 3, _SET3), profile_set=1)


def _instprm_geometry_fires() -> list:
    """The HB2A neutron ``.instprm``, which states no ``Diff-type``."""
    from rietx.io.instrument_profile import read_gsas2_instprm
    from tests.test_gsas2_instprm import HB2A

    found: list = []
    read_gsas2_instprm(HB2A, diagnostics=found)
    return found


def _instprm_geometry_silent() -> list:
    """A file that states its geometry, ``Diff-type:Bragg-Brentano``."""
    from rietx.io.instrument_profile import read_gsas2_instprm

    found: list = []
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "bb.instprm"
        path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                        "Type:PXC\nLam:1.5405\nDiff-type:Bragg-Brentano\n"
                        "Gonio. radius:217.5\n", encoding="utf-8")
        read_gsas2_instprm(path, diagnostics=found)
    return found


# ------------------------------------------------------- the data-support check


def _sampled_diagnostics(step: float, w: float) -> list:
    """``refine._data_support_diagnostics`` on a LaB6 pattern collected at
    ``step`` with Caglioti W = ``w``, compiled and never fitted: the sampling
    measure is model-free, read off the observed channels alone."""
    from rietx.model.forward import compile_model
    from rietx.refine import _data_support_diagnostics
    from tests.test_data_support import _lab6, _sampled

    structure, instrument = _lab6()
    model = compile_model(structure, instrument, _sampled(step, w), mode="rietveld")
    return _data_support_diagnostics(None, model)


def _undersampled_fires() -> list:
    """3.2 nominal steps per FWHM, under the five McCusker et al. (1999) ask."""
    return _sampled_diagnostics(0.005, 2.5e-4)


def _undersampled_silent() -> list:
    """7.9 steps, inside the band, and 31.6, above it: the band's upper end
    costs beam time and is never flagged."""
    return _sampled_diagnostics(0.002, 2.5e-4) + _sampled_diagnostics(0.002, 4.0e-3)


# ------------------------------------------------------------------- the guards


def _guard(**fields) -> list:
    """The diagnostics a ``GuardReport`` holding ``fields`` renders to."""
    from rietx.refine import _guard_diagnostics
    from rietx.strategy.staged import GuardReport

    return _guard_diagnostics(GuardReport(**fields))


def _floor_findings(theta: float, lo: float, *, cos: float, active: int | None) -> list:
    """``bound_findings`` for one width, ``instrument.profile.y`` in [lo, 1],
    solved to ``theta``.  ``active`` is the LM driver's exact active set (−1 the
    lower limit, 0 none), and ``None`` the conjunction TRF falls back to."""
    import numpy as np

    from rietx.strategy.staged import bound_findings

    return bound_findings(
        (np.array([lo]), np.array([1.0])), ["instrument.profile.y"], np.array([theta]),
        cos=np.array([cos]), esd=np.array([0.07]),
        active=None if active is None else np.array([active], dtype=np.int8))


def _floor_fires() -> list:
    """A width the default driver holds on its floor of 0 (WP-1929)."""
    return _guard(at_bounds=_floor_findings(0.0, 0.0, cos=0.03, active=-1))


def _floor_silent() -> list:
    """The same width at 0 that no limit held: the driver's set empty, and
    under the conjunction a residual pulling it back inside.  And a width the
    driver holds on a lower limit of 1e-6, which a caller could widen: that
    is ``BOUND_HIT``, not a floor."""
    return _guard(at_bounds=(_floor_findings(0.0, 0.0, cos=0.03, active=0)
                             + _floor_findings(0.0, 0.0, cos=-0.03, active=None)
                             + _floor_findings(1e-6, 1e-6, cos=0.03, active=-1)))


def _resolution_findings(*, x: float, w: float, free: bool) -> list:
    """``check_resolution_supported`` on a compiled LaB6 model, never fitted,
    with Lorentzian X = ``x`` and Gaussian W = ``w``, and U, V, W freed in the
    table where ``free``."""
    import numpy as np

    from rietx import Instrument, PatternData
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.strategy.staged import GAUSSIAN_RESOLUTION_PATHS, check_resolution_supported
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    instrument = Instrument.debye_scherrer(wavelength=0.4139)
    instrument.profile.x.value, instrument.profile.w.value = x, w
    tt = np.arange(3.0, 24.0, 0.01)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    if free:
        table.set_vary(list(GAUSSIAN_RESOLUTION_PATHS), True)
    return check_resolution_supported(table, model)


def _resolution_fires() -> list:
    """U, V, W freed on a predominantly Lorentzian pattern (Γ_L > Γ_G at every
    fitted point), McCusker et al. (1999) § Synchrotron's failure."""
    return _guard(unsupported_resolution=_resolution_findings(x=0.05, w=1e-4, free=True))


def _resolution_silent() -> list:
    """The same pattern with U, V, W held, which is the paper's remedy, and
    U, V, W freed where the Gaussian dominates."""
    return _guard(unsupported_resolution=(
        _resolution_findings(x=0.05, w=1e-4, free=False)
        + _resolution_findings(x=0.001, w=1e-3, free=True)))


SILENCE: dict[str, Pair] = {
    "CIF_SITE_LISTED_TWICE": Pair(
        _listed_twice_fires, _listed_twice_silent, "tests/test_cif_sites_coincide.py"),
    "CIF_SITE_MULTIPLICITY_DISAGREES": Pair(
        _multiplicity_fires, _multiplicity_silent, "tests/test_cif_stated_columns.py"),
    "CIF_SITE_TWINS_MERGED": Pair(
        _twins_fires, _twins_silent, "tests/test_cif_sites_coincide.py"),
    "FLOOR_HIT": Pair(
        _floor_fires, _floor_silent, "tests/test_bound_hit_at_convergence.py"),
    "GSAS2_INSTPRM_GEOMETRY_ASSUMED": Pair(
        _instprm_geometry_fires, _instprm_geometry_silent, "tests/test_gsas2_instprm.py"),
    "GSAS_PRM_PROFILE_SET_DEFAULTED": Pair(
        _profile_set_fires, _profile_set_silent, "tests/test_gsas_prm.py"),
    "PATTERN_UNDERSAMPLED": Pair(
        _undersampled_fires, _undersampled_silent, "tests/test_data_support.py"),
    "RESOLUTION_UNCONSTRAINED": Pair(
        _resolution_fires, _resolution_silent,
        "strategy.staged.check_resolution_supported (no test pinned it before)"),
    "SITE_SNAPPED_TO_SPECIAL_POSITION": Pair(
        _snap_fires, _snap_silent, "tests/test_cif_stated_columns.py"),
}


# ------------------------------------------------------------- the listed half


@functools.cache
def _raised() -> dict[str, dict[str, set]]:
    """Every code's raise sites, ``docs/reference_pages.diagnostic_index``."""
    spec = importlib.util.spec_from_file_location(
        "_reference_pages", ROOT / "docs" / "reference_pages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.diagnostic_index()


def declared_warnings() -> list[str]:
    """The codes whose audit row declares ``response="warning"`` or ``"error"``:
    each must have a pair, and ``tests/test_silence.py`` fails one that has
    none.  An error is included because a false one costs more: it turns
    ``usable`` false, which the package itself reads (``solve/cost.py``)."""
    from rietx import _audit

    return sorted(row.name for row in _audit.ROWS
                  if row.kind == "code" and row.response in ("warning", "error"))


def warning_codes() -> list[str]:
    """Every code a raise site passes ``level="warning"``, with the declared
    ones beside them."""
    raised = {code for code, sites in _raised().items() if "warning" in sites["levels"]}
    return sorted(raised | set(declared_warnings()))


def missing() -> list[str]:
    """The warning codes with no pair yet.  Listed, never failed, until an
    audit gives the code its response."""
    return sorted(set(warning_codes()) - SILENCE.keys())


def main() -> int:
    gone, total = missing(), len(warning_codes())
    print(f"{len(gone)} of {total} warning codes have no silence pair in "
          f"tests/silence.py's SILENCE ({total - len(gone)} have one).")
    for code in gone:
        print(f"  {code}  ({', '.join(sorted(_raised().get(code, {}).get('files', ())))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
