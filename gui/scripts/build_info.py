#!/usr/bin/env python3
"""Stamp ``build-info.json`` beside the committed dist — and define the hash once.

The dist under ``src/rietx/gui/static`` is committed so that installing the
wheel never needs node, which creates one hazard: a dist that no longer matches
the sources it was built from.  The guard is a digest of the frontend sources
recorded at build time and re-checked by ``tests/test_gui_dist.py``, which must
run in the ordinary CI path — where there is no node.

So the digest is defined **here, in stdlib Python**, and both sides call it: the
build (``npm run build`` runs this file after vite) and the test (which imports
this file by path).  The WP sketched a JS hasher plus a Python re-implementation;
two implementations of one digest is the duplication this repo keeps paying for
elsewhere, and the only thing the JS version would have bought is not needing
``python3`` on a machine that is building a Python package's frontend.

Nothing time-varying goes in the file.  A build timestamp would make every
rebuild a dist diff, which would destroy the property the digest exists to give:
``git diff --exit-code src/rietx/gui/static`` means "the dist is stale", not
"someone ran the build".

Usage (from the ``gui/`` directory)::

    python3 scripts/build_info.py [--check]
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

#: Files whose content decides whether the dist is current.  ``src/**`` is every
#: source; the four config files are here because a vite or tsconfig change can
#: alter the output without touching a single component.
SOURCE_GLOBS = ("src/**/*",)
SOURCE_FILES = ("package.json", "package-lock.json", "vite.config.ts",
                "tsconfig.json", "index.html", "next.html", "scripts/build_info.py",
                "scripts/vendor.py")

#: Directories outside ``gui/`` whose every file counts. ``scripts/vendor.py``
#: writes the pinned chart library there (WP-1461), so a hand edit of a vendored
#: file, or a pin moved without a build, reads as a stale dist.
OUTSIDE_DIRS = (Path("..") / "src" / "rietx" / "viz" / "static",)

#: Written next to the built assets, and committed with them.
BUILD_INFO = "build-info.json"

DIST_RELATIVE = Path("..") / "src" / "rietx" / "gui" / "static"


def relative(path: Path, gui_dir: Path) -> str:
    """``path`` as the digest names it: POSIX, relative to ``gui/``, ``../`` outside it."""
    return Path(os.path.relpath(path, gui_dir)).as_posix()


def source_files(gui_dir: Path) -> list[Path]:
    """Every file the digest covers, sorted by POSIX-relative path.

    Sorted by *relative* path rather than by absolute, so the digest does not
    depend on where the checkout lives, and ``.test.ts`` files are included: a
    vitest file is a source of the workspace even though it is not bundled, and
    excluding it would let a test-only change look like a stale dist.
    """
    found: set[Path] = set()
    for pattern in SOURCE_GLOBS:
        found.update(p for p in gui_dir.glob(pattern) if p.is_file())
    for name in SOURCE_FILES:
        candidate = gui_dir / name
        if candidate.is_file():
            found.add(candidate)
    for directory in OUTSIDE_DIRS:
        found.update(p for p in (gui_dir / directory).glob("**/*") if p.is_file())
    return sorted(found, key=lambda p: relative(p, gui_dir))


def source_hash(gui_dir: Path) -> tuple[str, int]:
    """``(sha256 hex, file count)`` over the frontend sources.

    Path *and* content go into the digest, separated by NULs, so renaming a file
    changes the hash even when the bytes move unchanged.
    """
    digest = hashlib.sha256()
    files = source_files(gui_dir)
    for path in files:
        digest.update(relative(path, gui_dir).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest(), len(files)


def read(dist_dir: Path) -> dict:
    try:
        return json.loads((dist_dir / BUILD_INFO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write(gui_dir: Path, dist_dir: Path) -> dict:
    digest, count = source_hash(gui_dir)
    info = {
        "source_hash": digest,
        "n_source_files": count,
        "hashed_by": "gui/scripts/build_info.py",
        "note": ("Recomputed by tests/test_gui_dist.py. A mismatch means the "
                 "committed dist is stale: run `npm --prefix gui run build`. "
                 "Deliberately carries no timestamp — a rebuild of unchanged "
                 "sources must produce a byte-identical tree."),
    }
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / BUILD_INFO).write_text(json.dumps(info, indent=2) + "\n",
                                       encoding="utf-8")
    return info


def main(argv: list[str]) -> int:
    gui_dir = Path(__file__).resolve().parent.parent
    dist_dir = (gui_dir / DIST_RELATIVE).resolve()
    if "--check" in argv:
        recorded = read(dist_dir).get("source_hash")
        digest, _ = source_hash(gui_dir)
        if recorded == digest:
            print(f"dist is current ({digest[:12]})")
            return 0
        print(f"dist is STALE: sources hash {digest[:12]}, dist records "
              f"{str(recorded)[:12]}", file=sys.stderr)
        return 1
    info = write(gui_dir, dist_dir)
    print(f"{BUILD_INFO}: {info['n_source_files']} source files, "
          f"{info['source_hash'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
