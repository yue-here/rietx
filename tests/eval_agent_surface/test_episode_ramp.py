"""E-RAMP rebuilds the episode the 2026-08-26 baseline was given.

The round compares its E-RAMP cells with that run's economics, and that
comparison is only worth making if the agents were handed the same patterns.
So the generator is asserted against the preserved copy byte for byte, and that
assertion skips — rather than passing — where the copy is not on this machine.
CI never has the copy, so its digest is asserted too, on every machine.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.eval_agent_surface.episodes import ramp

# The preserved run, outside the repo and maintainer-local (PROTOCOL.md
# § The episodes).  Its absence costs this file one assertion and nothing else.
BASELINE = Path.home() / "rietx-agent-runs" / "2026-08-26-insitu-ramp" / "data"

# `_digest` of the preserved copy's 68 patterns and host.cif, read from the copy
# itself.  It moves only if the registered baseline does, never to follow the
# generator.
BASELINE_SHA256 = "31a1dad0db549361dcd68abfce21492e1901fcd6bdf9453c1e860a657046bff7"


def _digest(directory: Path) -> str:
    """One sha256 over every file's name, length and bytes, in name order."""
    h = hashlib.sha256()
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        data = path.read_bytes()
        h.update(f"{path.name}\0{len(data)}\0".encode())
        h.update(data)
    return h.hexdigest()


@pytest.fixture(scope="module")
def episode(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("e-ramp")
    ramp.write_workspace(out)
    return out


def test_the_workspace_holds_patterns_and_the_host_and_nothing_else(tmp_path):
    written = ramp.write_workspace(tmp_path, 3)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(p.name for p in written)
    assert (tmp_path / "host.cif").exists()
    assert len([p for p in tmp_path.iterdir() if p.suffix == ".xye"]) == 3
    # nothing that says what was done to them
    assert not [p for p in tmp_path.iterdir() if p.suffix in {".py", ".json", ".md"}]


def test_a_pattern_is_three_columns_with_the_fallback_sigma(tmp_path):
    ramp.write_workspace(tmp_path, 1)
    lines = (tmp_path / "ramp_00_25C.xye").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(ramp.GRID)
    x, y, s = (float(v) for v in lines[0].split())
    assert x == pytest.approx(ramp.GRID[0])
    assert s == pytest.approx(max(y, 1.0) ** 0.5, rel=1e-6)


def test_the_truth_steps_where_the_episode_says_it_does():
    """A first-order step at 430 °C, and a second phase only above it."""
    assert ramp.a_of_T(430.0) < ramp.a_of_T(431.0)
    assert ramp.a_of_T(431.0) - ramp.a_of_T(430.0) > 0.015  # the step, not the ramp
    assert ramp.w_of_T(430.0) == 0.0
    assert ramp.w_of_T(520.0) == pytest.approx(1.0)
    assert ramp.a_of_T(720.0) / ramp.a_of_T(25.0) - 1 == pytest.approx(0.008, abs=5e-4)


@pytest.mark.xdist_group("episode-ramp")
def test_the_episode_has_the_baselines_digest(episode):
    assert _digest(episode) == BASELINE_SHA256, (
        "E-RAMP no longer rebuilds the baseline's workspace, so the round's "
        "comparison with that run's economics is void until the generator is "
        "repaired.  Changing the registered baseline instead is the "
        "maintainer's call"
    )


@pytest.mark.xdist_group("episode-ramp")
@pytest.mark.skipif(not BASELINE.is_dir(), reason="the preserved 2026-08-26 run is maintainer-local")
def test_the_episode_is_the_baselines_data_byte_for_byte(episode):
    assert _digest(BASELINE) == BASELINE_SHA256, "the preserved copy has changed"
    ours = {p.name: p.read_bytes() for p in episode.iterdir()}
    theirs = {p.name: p.read_bytes() for p in BASELINE.iterdir()}
    assert sorted(ours) == sorted(theirs)
    differing = [name for name, data in ours.items() if theirs[name] != data]
    assert not differing, (
        "E-RAMP no longer rebuilds the baseline's workspace: the seed, the grid "
        "or the order of the RNG's draws has moved, and the round's comparison "
        f"with that run's economics is void for {len(differing)} patterns"
    )
