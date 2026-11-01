"""Measure every numbered equation against the column it is typeset in (WP-1408).

    uv pip install --python .venv/bin/python playwright     # once, see below
    .venv/bin/python docs/docs/check_equations.py

`make_screenshots.py`'s rule applied to a *measurement* rather than a picture.
The manual's equation numbers are placed by CSS and their equations by MathJax
in the browser, so how wide an equation is, and whether it collides with its own
number, is not a fact any source file holds. This script is the one authority
for how that was measured; it prints a row per labelled equation and exits
non-zero when one does not fit.

**playwright is deliberately not a dependency.** It is not in `[dev]`, only this
script and `make_screenshots.py` want it, and the docs build never runs either.
The chromium it drives is resolved by `make_screenshots.chromium_path()` — the
cached build on a machine that has run a browser pass before, or
`PLAYWRIGHT_CHROMIUM`.

**What the numbers mean.** Sphinx's `basic.css` floats the equation number
and reserves no space for it, so a wide equation is typeset *under* its own
number (WP-1408 measured it under the old theme, WP-1986 again under
pydata-sphinx-theme: six equations, by up to 191 px). `_static/custom.css` lays
a numbered equation out as a two-cell grid, which makes the collision
impossible and turns the remaining question into a width: does the typeset
math fit the cell the grid gives it? So each row carries

* `ink` — the `mjx-math` box, the equation's actual typeset width;
* `cell` — the client width of the `mjx-container` it sits in;
* `clear` — the gap from the ink's right edge to the number's left edge;
* `over` — how far the ink overflows the cell, i.e. how far it scrolls.

A failing row is fixed by **reflowing the equation** (`aligned`, `split`, or
naming a sub-expression once), never by narrowing the number's column: the
reader reads the equation, and a horizontal scrollbar in the middle of a
derivation is a defect with a scrollbar on it.

Measured at two viewport widths because the failure is width-dependent. The
theme shows the page's own contents in a right-hand column at the wider one,
so its text column is the narrower of the two (about 645 px against 720 px).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TREE = Path(__file__).resolve().parent
# `make_screenshots.py` sits beside this script since the GUI pages moved
# (WP-1986).  The insert keeps the import working when this file is loaded by
# path rather than run as a script.
sys.path.insert(0, str(TREE))

from make_screenshots import chromium_path  # noqa: E402  (after the path insert)

#: Where the measurement is taken.  Two widths, and two text columns, see the
#: module docstring.
VIEWPORTS = ({"width": 1440, "height": 1000}, {"width": 1100, "height": 1000})

#: The narrowest gap from an equation to its own number that counts as clear.
#: Not a design constant: a number small enough that only a real collision
#: course trips it, and large enough that a font substitution on another
#: machine does not.
MIN_CLEARANCE_PX = 8

#: Only a row with *less* clearance than this is printed; a passing row with
#: more is silent.  The interesting end of the list is the tight one — a wide
#: equation is a narrow gap — and printing every equation on every page buries
#: it.
REPORT_BELOW_CLEARANCE_PX = 60

#: Read off each `div.math` that carries a number.  Written as one expression
#: so a page is walked once; `mjx-math` rather than `mjx-container` is the ink,
#: because the container is a full-width block whichever way the equation is
#: aligned inside it.
_PROBE = """() => {
  const rows = [];
  for (const div of document.querySelectorAll('div.math')) {
    const eqno = div.querySelector('span.eqno');
    const box = div.querySelector('mjx-container');
    const ink = div.querySelector('mjx-container > mjx-math');
    if (!eqno || !box || !ink) continue;
    const a = ink.getBoundingClientRect(), b = eqno.getBoundingClientRect();
    rows.push({
      id: (div.closest('[id^="equation-"]') || div).id || div.id,
      // childNodes[0], not textContent: the `¶` permalink is a child of the
      // number's own span and would be read as part of it.
      number: (eqno.childNodes[0].textContent || '').trim(),
      ink: Math.round(a.width),
      cell: Math.round(box.clientWidth),
      clear: Math.round(b.left - a.right),
      over: Math.max(0, box.scrollWidth - box.clientWidth),
    });
  }
  return rows;
}"""


def build(out: Path) -> None:
    """A `-W` build of the manual into `out`, the same one the suite makes."""
    subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "-q", "-E", "-b", "html",
         str(TREE), str(out)],
        check=True,
    )


def pages(out: Path) -> list[Path]:
    """Built pages that carry at least one numbered equation.

    Derived from the output rather than listed: a chapter added to the Theory tab is
    measured without anyone editing this file, and a page with no equation
    costs nothing to skip.
    """
    return sorted(p for p in out.rglob("*.html") if 'class="eqno"' in p.read_text(encoding="utf-8"))


def measure(out: Path) -> int:
    from playwright.sync_api import sync_playwright

    executable = chromium_path()
    print(f"chromium: {executable or 'playwright default'}")
    targets = pages(out)
    print(f"{len(targets)} page(s) with numbered equations\n")

    failures: list[str] = []
    with sync_playwright() as play:
        browser = play.chromium.launch(executable_path=executable or None)
        try:
            for viewport in VIEWPORTS:
                context = browser.new_context(viewport=viewport)
                try:
                    page = context.new_page()
                    print(f"—— viewport {viewport['width']} px " + "—" * 28)
                    print(f"{'equation':<34} {'no.':>8} {'ink':>6} "
                          f"{'cell':>6} {'clear':>6} {'over':>5}")
                    total = 0
                    for target in targets:
                        page.goto(target.as_uri())
                        # MathJax typesets after load; there is no event for
                        # "done", so wait for the first container and then for
                        # the layout to settle.
                        page.wait_for_selector("mjx-container", timeout=60_000)
                        page.wait_for_timeout(1_500)
                        for row in page.evaluate(_PROBE):
                            total += 1
                            bad = row["clear"] < MIN_CLEARANCE_PX or row["over"] > 0
                            if not bad and row["clear"] > REPORT_BELOW_CLEARANCE_PX:
                                continue
                            mark = "FAIL" if bad else "    "
                            # The path, not the name: two tabs each have an index.html.
                            name = (f"{target.relative_to(out).as_posix()}:"
                                    f"{row['id'].removeprefix('equation-')}")
                            print(f"{mark} {name:<29} {row['number']:>8} {row['ink']:>6} "
                                  f"{row['cell']:>6} {row['clear']:>6} {row['over']:>5}")
                            if bad:
                                failures.append(
                                    f"{viewport['width']} px  {name} {row['number']}: "
                                    f"ink {row['ink']} px in a {row['cell']} px cell, "
                                    f"clearance {row['clear']} px, overflow {row['over']} px")
                    print(f"     {total} numbered equations measured\n")
                finally:
                    context.close()
        finally:
            browser.close()

    if failures:
        print("equations that do not fit their column:")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"every numbered equation clears its number by ≥ {MIN_CLEARANCE_PX} px "
          "and fits its cell.")
    return 0


def main() -> int:
    # Before the build, not inside `measure`: a full `-E` sphinx run is a
    # minute, and paying it to arrive at an ImportError is the one failure this
    # script can see coming.
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        print("playwright is not installed — see this module's docstring.", file=sys.stderr)
        return 2

    work = Path(tempfile.mkdtemp(prefix="rietx-equations-"))
    try:
        build(work / "html")
        return measure(work / "html")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
