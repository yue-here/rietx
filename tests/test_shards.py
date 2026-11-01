"""The CI shard split (``tests/shards.py``, ``conftest``'s ``--shard``, WP-1547).

Every xdist worker computes its shard for itself, and xdist refuses a run whose
workers collected different lists.  So the split must be a function of the
files and groups alone, and most rows here pin that.  One end-to-end row checks
that a real ``--collect-only`` at each shard splits the unsharded list exactly.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import shards
from tests.conftest import pytest_collection_modifyitems, pytest_make_collect_report

ROOT = Path(__file__).resolve().parents[1]

#: Two files in group ``g``, a third in ``g`` and ``h``, which pulls in ``e``.
PAIRS = [("a.py", "g"), ("a.py", None), ("b.py", "g"), ("c.py", None),
         ("d.py", "h"), ("e.py", "h"), ("d.py", "g"), ("f.py", None)]
SECONDS = {"a.py": 5.0, "b.py": 1.0, "c.py": 4.0, "d.py": 2.0, "e.py": 3.0, "f.py": 6.0}


def _shard_files(pairs, seconds, n):
    return [files for files, _ in shards.assign(shards.units(pairs), seconds, n)]


def test_groups_merge_files_transitively_and_a_lone_file_is_its_own_unit():
    assert sorted(map(sorted, shards.units(PAIRS))) == [
        ["a.py", "b.py", "d.py", "e.py"], ["c.py"], ["f.py"]]


@pytest.mark.parametrize("n", [1, 2, 3, 5])
def test_every_file_lands_in_exactly_one_shard(n):
    """More shards than units leaves the extra shards empty, never a file twice."""
    out = _shard_files(PAIRS, SECONDS, n)
    assert len(out) == n
    assert sorted(f for files in out for f in files) == sorted(SECONDS)


@pytest.mark.parametrize("n", [2, 3])
def test_a_group_spanning_files_stays_on_one_shard(n):
    (home,) = [files for files in _shard_files(PAIRS, SECONDS, n) if "a.py" in files]
    assert {"a.py", "b.py", "d.py", "e.py"} <= home


def test_the_answer_does_not_depend_on_the_order_items_were_collected():
    """Ties included: three equal units, so placement rests on the tie-break."""
    pairs = PAIRS + [("x.py", None), ("y.py", None), ("z.py", None)]
    seconds = SECONDS | {"x.py": 2.5, "y.py": 2.5, "z.py": 2.5}
    want = _shard_files(pairs, seconds, 3)
    rng = random.Random(1547)
    for _ in range(20):
        shuffled = pairs[:]
        rng.shuffle(shuffled)
        assert _shard_files(shuffled, dict(reversed(seconds.items())), 3) == want


def test_the_largest_shard_is_within_one_unit_of_an_even_split():
    """Graham's bound for any list schedule, which LPT is."""
    rng = random.Random(7)
    for _ in range(50):
        seconds = {f"t{i}.py": rng.expovariate(0.05) for i in range(rng.randint(3, 60))}
        pairs = [(f, None) for f in seconds]
        n = rng.randint(2, 4)
        loads = [load for _, load in shards.assign(shards.units(pairs), seconds, n)]
        assert sum(loads) == pytest.approx(sum(seconds.values()))
        assert max(loads) <= sum(seconds.values()) / n + max(seconds.values()) + 1e-9


def test_a_file_the_record_lacks_weighs_the_median_recorded_file():
    """The median of 1, 2 and 9 is 2, so the new file balances the two small ones."""
    out = shards.assign(shards.units([("a.py", None), ("b.py", None), ("c.py", None),
                                      ("new.py", None)]),
                        {"a.py": 1.0, "b.py": 2.0, "c.py": 9.0}, 2)
    assert out == [(frozenset({"c.py"}), 9.0), (frozenset({"a.py", "b.py", "new.py"}), 5.0)]


@pytest.mark.parametrize("spec", ["0/2", "3/2", "1/0", "2", "1/2/3", "a/b", "-1/2", ""])
def test_a_malformed_or_out_of_range_shard_is_a_usage_error(spec):
    config = SimpleNamespace(option=SimpleNamespace(shard=spec))
    with pytest.raises(pytest.UsageError, match="--shard"):
        pytest_collection_modifyitems(config, [])


@pytest.mark.parametrize(("spec", "reported"), [(None, True), ("1/2", True), ("2/2", False)])
def test_a_module_skipped_at_import_is_reported_by_shard_one_alone(spec, reported):
    """Such a module has no item to place, and each shard counted its skip
    until the second shard learned to drop it: eight extra on CI's py3.14."""
    module = object.__new__(pytest.Module)
    module.config = SimpleNamespace(option=SimpleNamespace(shard=spec))
    report = pytest.CollectReport("tests/test_x.py", "skipped",
                                  ("tests/test_x.py", 1, "Skipped: no torch"), [])
    wrapper = pytest_make_collect_report(module)
    next(wrapper)
    with pytest.raises(StopIteration) as done:
        wrapper.send(report)
    assert done.value.value.skipped is reported


def test_no_shard_option_leaves_the_collection_alone():
    items = [object(), object()]
    pytest_collection_modifyitems(SimpleNamespace(option=SimpleNamespace(shard=None)), items)
    assert len(items) == 2


def test_the_record_reads_shares_of_python_legs_and_reads_past_the_jax_job(tmp_path):
    """Two Python legs at different runner speeds give one numpy profile.

    ``py3.12`` runs twice as slow and comes as two shards, which sum.  A skip
    costs nothing, a test class belongs to its module, and a module skipped at
    import (no classname) is not a file the record can place.  The jax job runs
    ``--jax-cases`` unsharded since WP-2019, so its seconds place nothing."""
    def write(job, cases):
        (tmp_path / job).mkdir()
        body = "".join(
            f'<testcase classname="{cn}" name="t" time="{t}">'
            + ('<skipped message="no"/>' if skip else "") + "</testcase>"
            for cn, t, skip in cases)
        (tmp_path / job / "junit.xml").write_text(
            f"<testsuites><testsuite>{body}</testsuite></testsuites>", encoding="utf-8")

    write("junit-py3.11", [("tests.test_a", 3, False), ("tests.test_b.TestK", 1, False),
                           ("tests.test_b", 9, True), ("", 0, True)])
    write("junit-py3.12-1", [("tests.test_a", 6, False)])
    write("junit-py3.12-2", [("tests.test_b", 2, False)])
    write("junit-jax", [("tests.sub.test_c", 7.04, False), ("tests.test_a", 1, True)])
    out = shards.record(tmp_path, "run 1")
    # both legs give a 3/4 share to test_a; the median leg total is (4 + 8)/2
    assert out == {"source": "run 1",
                   "numpy": {"tests/test_a.py": 4.5, "tests/test_b.py": 1.5}}


def test_a_file_one_leg_skips_weighs_what_the_leg_running_it_spent(tmp_path):
    """The documentation executes on the newest leg alone (WP-2019), so its
    file weighs its share there: a median over two legs would halve it."""
    for job, docs in (("junit-py3.11", True), ("junit-py3.14", False)):
        (tmp_path / job).mkdir()
        (tmp_path / job / "junit.xml").write_text(
            '<testsuites><testsuite><testcase classname="tests.test_a" name="t" time="6"/>'
            '<testcase classname="tests.test_docs" name="t" time="4">'
            + ('<skipped message="RIETX_DOCS=skip"/>' if docs else "")
            + "</testcase></testsuite></testsuites>", encoding="utf-8")
    out = shards.record(tmp_path, "run 1")
    # both legs ran test_a in 6 s, so they share a clock and docs keeps its 4 s
    assert out["numpy"] == {"tests/test_a.py": 6.0, "tests/test_docs.py": 4.0}


def test_a_file_one_leg_runs_only_part_of_neither_halves_it_nor_sets_the_clock(tmp_path):
    """Every file executing the documentation also holds cases that run on
    every leg (``test_examples``' walkthroughs, ``test_manual``'s text checks),
    so "ran it at all" cannot tell its legs apart.  The leg that ran more of it
    weighs it, and it is no part of either leg's clock."""
    for job, docs in (("junit-py3.11", False), ("junit-py3.14", True)):
        (tmp_path / job).mkdir()
        (tmp_path / job / "junit.xml").write_text(
            '<testsuites><testsuite><testcase classname="tests.test_a" name="t" time="6"/>'
            '<testcase classname="tests.test_docs" name="walk" time="1"/>'
            '<testcase classname="tests.test_docs" name="guide" time="9">'
            + ("" if docs else '<skipped message="RIETX_DOCS=skip"/>')
            + "</testcase></testsuite></testsuites>", encoding="utf-8")
    out = shards.record(tmp_path, "run 1")
    # the clock is test_a alone, 6 s on each leg, so docs keeps the 10 s it cost
    assert out["numpy"] == {"tests/test_a.py": 6.0, "tests/test_docs.py": 10.0}


def test_a_leg_missing_a_shard_another_leg_has_is_refused(tmp_path):
    """A timed-out shard uploads nothing, and its files would weigh zero."""
    for job in ("junit-py3.11-1", "junit-py3.11-2", "junit-py3.14-1"):
        (tmp_path / job).mkdir()
        (tmp_path / job / "junit.xml").write_text(
            '<testsuites><testsuite><testcase classname="tests.test_a" name="t" time="1"/>'
            "</testsuite></testsuites>", encoding="utf-8")
    with pytest.raises(SystemExit, match=r"py3\.14.*\[2\]"):
        shards.record(tmp_path, "run 1")


def test_the_committed_record_covers_most_of_the_suite():
    """A file the record lacks costs balance and never a test, so nothing goes
    red when the record goes stale.  An empty or garbled profile would be the
    same silence across every file, and this row is the one that sees it.  It
    holds one profile: the jax job no longer shards, so a second would be a
    name nothing reads (WP-2019)."""
    record = json.loads(shards.RECORD.read_text(encoding="utf-8"))
    files = {p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").rglob("test_*.py")}
    assert set(record) == {"source", "numpy"}
    assert record["source"]
    seconds = shards.recorded_seconds()
    assert all(f.startswith("tests/") and f.endswith(".py") and s >= 0
               for f, s in seconds.items())
    assert len(files & seconds.keys()) > len(files) / 2


def _collected(*extra):
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", *extra,
         "tests/test_suite_config.py", "tests/test_added_test_times.py"],
        cwd=ROOT, capture_output=True, encoding="utf-8")
    assert proc.returncode == pytest.ExitCode.OK, (proc.stdout + proc.stderr)[-2000:]
    return {line for line in proc.stdout.splitlines() if "::" in line}


def test_a_real_collection_splits_into_disjoint_shards_that_cover_it():
    """End-to-end, so the option, the hook's order and the path keys are real."""
    whole = _collected()
    one, two = _collected("--shard", "1/2"), _collected("--shard", "2/2")
    assert one and two
    assert not one & two
    assert one | two == whole
