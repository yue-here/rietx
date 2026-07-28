"""The ``pxrdref`` command-line entry point.

Deliberately tiny: the package is API-first, and the CLI exists for the few
things that are genuinely terminal-shaped — watching a running refinement,
rendering a result file, and launching the settings-comparison UI.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: pxrdref <command> [...]\n\n"
              "commands:\n"
              "  watch <dir> [--port N] [--open]   live viewer for a LiveSession directory\n"
              "  html <result.json> <out.html>     render a saved RefinementResult to HTML\n"
              "  compare [--data DIR] [--port N] [--open]\n"
              "                                    browser UI comparing refinement\n"
              "                                    settings on the bundled standards")
        return 0

    command, rest = argv[0], argv[1:]
    if command == "watch":
        from .watch import main as watch_main

        watch_main(rest)
        return 0
    if command == "compare":
        from .compare_app import main as compare_main

        return compare_main(rest)
    if command == "html":
        if len(rest) != 2:
            print("usage: pxrdref html <result.json> <out.html>", file=sys.stderr)
            return 2
        from .schemas.results import RefinementResult
        from .viz.html import write_html

        with open(rest[0], encoding="utf-8") as fh:
            result = RefinementResult.model_validate_json(fh.read())
        write_html(result, rest[1])
        print(f"wrote {rest[1]}")
        return 0

    print(f"pxrdref: unknown command {command!r} (try --help)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
