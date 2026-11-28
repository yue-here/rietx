"""WP-1420's repro reads the two chains' disagreement from ``direction_gaps``.

``tests/repro_1420.py`` counted ``SEQUENTIAL_PATH_DEPENDENT`` on the
subgroup's cell after WP-2003 removed the code, so its column read 0 on every
chain, including series whose two directions end ~30 esd apart (draw 20260904
at 0.15: forward ``++++``, backward ``----``).  ``cell_gap_esd`` reads the
largest \\|gap_esd\\| on ``phases.1.cell.*`` at or after the onset instead.
The rows here are built by hand so the reader is pinned without a chain.
"""
from __future__ import annotations

from types import SimpleNamespace

from rietx.schemas.sequential import DirectionGap
from tests.repro_1420 import ONSET, cell_gap_esd


def _row(path: str, index: int, gap_esd: float | None) -> DirectionGap:
    return DirectionGap(path=path, label=f"p{index:03d}", index=index,
                        forward=1.0, backward=1.0, gap=0.0, gap_esd=gap_esd,
                        forward_rung="warm", backward_rung="warm")


def test_a_disagreement_on_the_subgroup_cell_is_read():
    """Positive arm: a signed gap on the subgroup's cell is read as its size."""
    rows = [_row("phases.1.cell.a", ONSET + 1, -31.7),
            _row("phases.1.cell.c", ONSET + 2, 12.0)]
    assert cell_gap_esd(SimpleNamespace(direction_gaps=rows)) == 31.7


def test_rows_off_the_subgroup_cell_or_before_onset_are_not_read():
    """Negative arm: the parent's cell, the subgroup's scale, the absent
    patterns and an esd-less row each carry a large gap that must not leak."""
    rows = [_row("phases.0.cell.a", ONSET + 1, 50.0),
            _row("phases.1.scale", ONSET + 1, 99.0),
            _row("phases.1.cell.a", ONSET - 1, 40.0),
            _row("phases.1.cell.c", ONSET + 1, None),
            _row("phases.1.cell.a", ONSET + 3, 0.004)]
    assert cell_gap_esd(SimpleNamespace(direction_gaps=rows)) == 0.004


def test_a_forward_only_run_has_no_gap():
    """No ``direction_gaps`` (forward only) or no esd anywhere reads ``None``,
    never 0, which would read as an agreement."""
    assert cell_gap_esd(SimpleNamespace(direction_gaps=None)) is None
    rows = [_row("phases.1.cell.a", ONSET + 1, None)]
    assert cell_gap_esd(SimpleNamespace(direction_gaps=rows)) is None
