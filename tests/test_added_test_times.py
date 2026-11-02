"""The handover's report on added tests (``tests/added_test_times.py``, WP-1506)."""

from tests.added_test_times import added_tests, per_file, times

DIFF = """\
diff --git a/tests/test_a.py b/tests/test_a.py
@@ -10,0 +11,4 @@
+def test_new(x):
+    pass
+def helper():
+    pass
diff --git a/src/rietx/x.py b/src/rietx/x.py
@@ -1,0 +2 @@
+def test_in_the_package():
diff --git a/tests/sub/test_b.py b/tests/sub/test_b.py
@@ -3,0 +4,2 @@
+    async def test_method(self):
+diff --git a/tests/test_c.py b/tests/test_c.py
diff --git a/tests/test_d.py b/tests/test_d.py
@@ -5 +4,0 @@
-def test_removed():
@@ -9 +9 @@
-def test_resigned(a):
+def test_resigned(a, b):
"""


def test_a_def_counts_only_when_added_under_tests_and_not_also_removed():
    assert added_tests(DIFF) == {("tests.test_a", "test_new"),
                                 ("tests.sub.test_b", "test_method")}


def test_cases_sum_by_function_and_a_class_member_matches_its_module(tmp_path):
    """``@grp`` is the suffix xdist's loadgroup appends to a grouped test.
    A skipped case is no cost, so it adds no seconds."""
    junit = tmp_path / "junit.xml"
    junit.write_text(
        "<testsuites><testsuite>"
        '<testcase classname="tests.test_a" name="test_new[1]" time="1.5"/>'
        '<testcase classname="tests.test_a" name="test_new[2]" time="2.0"/>'
        '<testcase classname="tests.test_a" name="test_new[3]" time="0.01">'
        '<skipped message="not this leg"/></testcase>'
        '<testcase classname="tests.test_a" name="test_newer" time="9"/>'
        '<testcase classname="tests.test_ab" name="test_new" time="7"/>'
        '<testcase classname="tests.sub.test_b.TestK" name="test_method" time="0.25"/>'
        '<testcase classname="tests.sub.test_b.TestK" name="test_method@grp" time="0.5"/>'
        "</testsuite></testsuites>", encoding="utf-8")
    assert times(str(junit), added_tests(DIFF)) == {
        ("tests.test_a", "test_new"): [1.5, 2.0],
        ("tests.sub.test_b", "test_method"): [0.25, 0.5]}


def test_a_directory_reads_every_shard_of_a_leg(tmp_path):
    """A CI leg runs as several shards, so an added test is in one file of them."""
    for shard, case in (("1", '<testcase classname="tests.test_a" name="test_new" time="3"/>'),
                        ("2", '<testcase classname="tests.sub.test_b" name="test_method" time="4"/>')):
        (tmp_path / f"junit-py3.14-{shard}").mkdir()
        (tmp_path / f"junit-py3.14-{shard}" / "junit.xml").write_text(
            f"<testsuites><testsuite>{case}</testsuite></testsuites>", encoding="utf-8")
    assert times(str(tmp_path), added_tests(DIFF)) == {
        ("tests.test_a", "test_new"): [3.0],
        ("tests.sub.test_b", "test_method"): [4.0]}


def test_a_file_totals_its_added_tests_so_many_short_ones_show_as_one_long():
    """Twelve one-minute tests in one file were never read as twelve minutes."""
    rows = {("tests.test_a", "test_one"): [1.5, 2.0],
            ("tests.test_a", "test_two"): [4.0],
            ("tests.sub.test_b", "test_method"): [0.25]}
    assert per_file(rows) == {"tests.test_a": (7.5, 2), "tests.sub.test_b": (0.25, 1)}
