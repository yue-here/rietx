"""``RIETX_DOCS=skip`` reaches every execution of the documentation (WP-2019).

``tests/documentation.py`` says why the switch exists.  These rows say that it
works where it is meant to: one end-to-end run with the switch set, over a case
from each of the three executions and a reader of the shared build, in which
every case skips with the module's reason and none runs.  A site that stopped
reading the switch would run here and fail the row, rather than quietly costing
every leg its seconds again.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests import documentation

ROOT = Path(__file__).resolve().parent.parent

#: One case per execution, and one reader of the shared manual build.
SITES = (
    "tests/test_examples.py::test_every_guide_script_prints_what_its_page_quotes",
    "tests/test_tutorials.py::test_tutorial_executes_clean",
    "tests/test_manual.py::test_manual_builds_warning_free",
    "tests/test_help.py::test_every_anchor_resolves_in_the_built_manual",
)


def test_the_switch_skips_on_its_one_value_and_runs_on_any_other(monkeypatch):
    monkeypatch.setenv(documentation.ENV, documentation.SKIP)
    with pytest.raises(pytest.skip.Exception, match=re.escape(documentation.REASON)):
        documentation.skip_here()
    for value in ("run", ""):
        monkeypatch.setenv(documentation.ENV, value)
        documentation.skip_here()
    monkeypatch.delenv(documentation.ENV)
    assert not documentation.skipped()


def test_every_site_skips_under_the_switch_and_none_runs(tmp_path):
    junit = tmp_path / "junit.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", f"--junitxml={junit}",
         *SITES],
        cwd=ROOT, capture_output=True, encoding="utf-8",
        env={**os.environ, documentation.ENV: documentation.SKIP},
        timeout=600,  # a runaway guard: collection alone is seconds
    )
    assert proc.returncode == pytest.ExitCode.OK, (proc.stdout + proc.stderr)[-3000:]
    cases = list(ET.parse(junit).iter("testcase"))
    ran = [c.get("name") for c in cases if c.find("skipped") is None]
    assert not ran, f"ran under {documentation.ENV}={documentation.SKIP}: {ran}"
    reasons = {c.find("skipped").get("message", "") for c in cases}
    assert all(documentation.REASON in r for r in reasons), reasons
    files = {c.get("classname") for c in cases}
    for site in SITES:
        module = site.split("::")[0].removesuffix(".py").replace("/", ".")
        assert module in files, f"{site} collected nothing to skip: {sorted(files)}"
