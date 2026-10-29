"""The ``rietx`` command-line entry point.

Deliberately tiny: the package is API-first, and the CLI exists for the few
things that are genuinely terminal-shaped — watching a running refinement,
summarising an event log after the fact, rendering a result file, launching the settings-comparison UI, and asking "what
is the cell of this pattern I just collected?".

``rietx index`` prints the **candidate list**, never one cell, and carries the
verdict in its exit status (0 when a cell reached the confidence gate, 1 when the
result abstains).  The API has no ``.cell`` and the CLI must not invent one — an
exit code is the one channel a shell pipeline can branch on without parsing.
"""

from __future__ import annotations

import sys


def _utf8_output() -> None:
    """Pin this CLI's own output to UTF-8, whatever the console code page is.

    The prose this package prints carries ``Å``, ``θ``, ``°`` and ``Kα``, and
    ``skill --print`` emits a whole UTF-8 document.  A Windows *console* has
    been UTF-8 since PEP 528, but a captured **pipe** falls back to the ANSI
    code page, and cp1252 cannot encode ``α``: on the nightly's Windows runner
    both ``rietx skill --print`` and ``rietx index --help`` exited 1 with
    ``UnicodeEncodeError`` (run 33251188429).

    ``examples/`` met the same wall in WP-1003 and pinned the pipe from the
    *test* side, on the argument that a reader runs those scripts interactively
    and only the capture is cp1252.  That argument does not reach here: the
    documented purpose of ``skill --print`` is to be piped into a harness that
    reads no skills, so for this command the pipe **is** the consumer.  A
    document is handed over whole or not at all, which also rules out
    ``errors="replace"`` — ``K?`` in an instruction an agent will follow is a
    corruption, not a degradation.

    Reconfiguring a stream already UTF-8 is a no-op, and a stream that cannot
    be reconfigured at all (a pytest capture object, a closed stream) is left
    as it is rather than made an error of its own.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: rietx <command> [...]\n\n"
              "commands:\n"
              "  gui [PROJECT.rex] [--scratch] [--port N] [--no-open]\n"
              "                                    the refinement GUI (localhost)\n"
              "  watch [dir] [--port N] [--open] [--read-only]\n"
              "                                    list and watch the runs under a directory\n"
              "  events <events.jsonl | run dir> [--json]\n"
              "                                    summarise an event log, run by run\n"
              "  html <result.json> <out.html>     render a saved RefinementResult to HTML\n"
              "  index <pattern> --wavelength A [...]\n"
              "                                    determine the unit cell of an unknown\n"
              "                                    phase (rietx index --help)\n"
              "  compare [--data DIR] [--port N] [--open]\n"
              "                                    browser UI comparing refinement\n"
              "                                    settings on the bundled standards\n"
              "  skill [--path | --print [SECTION] | --install [DIR]]\n"
              "                                    the agent skill: where it is, its\n"
              "                                    text, or install it into a repo\n"
              "                                    (rietx skill --help)")
        return 0

    command, rest = argv[0], argv[1:]
    if command == "index":
        return _index(rest)
    if command == "skill":
        return _skill(rest)
    if command == "gui":
        from .gui.server import main as gui_main

        return gui_main(rest)
    if command == "watch":
        from .watch import main as watch_main

        watch_main(rest)
        return 0
    if command == "compare":
        from .compare_app import main as compare_main

        return compare_main(rest)
    if command == "events":
        return _events(rest)
    if command == "html":
        if len(rest) != 2:
            print("usage: rietx html <result.json> <out.html>", file=sys.stderr)
            return 2
        from .schemas.results import RefinementResult
        from .viz.html import write_html

        with open(rest[0], encoding="utf-8") as fh:
            result = RefinementResult.model_validate_json(fh.read())
        write_html(result, rest[1])
        print(f"wrote {rest[1]}")
        return 0

    print(f"rietx: unknown command {command!r} (try --help)", file=sys.stderr)
    return 2


def _events(argv: list[str]) -> int:
    """``rietx events`` — an event log after the fact, one run at a time.

    Terminal-shaped for the reason ``html`` is: the run happened somewhere
    else, and the question is asked of the file it left.  Thin over
    :func:`rietx.history.aggregate.summarize_events`, so a CI job can call
    either; ``--json`` is that function's answer, serialised.
    """
    import argparse

    p = argparse.ArgumentParser(
        prog="rietx events",
        description="Summarise an events.jsonl run by run: fits and stages "
                    "counted, wall clock per stage, the termination "
                    "histogram, the most-held paths, first and last Rwp.")
    p.add_argument("log", help="an events.jsonl, or a run directory holding one")
    p.add_argument("--json", action="store_true",
                   help="print the summary as JSON instead of text")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    from .history.aggregate import summarize_events

    try:
        summary = summarize_events(args.log)
    except FileNotFoundError as exc:
        print(f"rietx events: {exc}", file=sys.stderr)
        return 2
    print(summary.model_dump_json(indent=1) if args.json else summary)
    return 0


def _skill(argv: list[str]) -> int:
    """``rietx skill`` — the agent-facing protocol, and how it reaches a repo.

    Terminal-shaped for the same reason ``index`` is: the three questions here
    are asked *about the installation* rather than about a refinement.  Where is
    the skill (so a harness can be pointed at it)?  What does it say (for a
    harness that reads no skills, and takes plain text)?  And put it in this
    repository (so every harness working here finds it).

    ``--install`` prints the `AGENTS.md` / `CLAUDE.md` snippet and never writes
    it: see :mod:`rietx.skill` on why those files stay their owner's.
    """
    import argparse

    from . import skill as skill_module

    p = argparse.ArgumentParser(
        prog="rietx skill",
        description="The rietx agent skill (agentskills.io format): print its "
                    "path, print its text, or install it into a repository.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--path", action="store_true",
                      help="print the skill directory this build carries")
    mode.add_argument("--print", nargs="?", const="SKILL", metavar="SECTION",
                      dest="print_section",
                      help="print the skill as text: the body by default, a "
                           "reference file by name, or 'all' for the tree")
    mode.add_argument("--install", nargs="?", const=".", metavar="DIR",
                      help="install into DIR (default the current directory): "
                           "one copy in .agents/skills/, a link from each "
                           "requested harness's own directory")
    mode.add_argument("--list-agents", action="store_true",
                      help="print the harness table with its sources and dates")
    p.add_argument("--user", action="store_true",
                   help="install for the user (~) rather than into a project")
    p.add_argument("--agent", action="append", default=None, metavar="NAME",
                   help="harness to link for; repeatable (default: "
                        + ", ".join(skill_module.DEFAULT_AGENTS) + ")")
    p.add_argument("--copy", action="store_true",
                   help="copy rather than symlink (always so on Windows)")
    args = p.parse_args(argv)

    if args.list_agents:
        width = max(len(h.name) for h in skill_module.HARNESSES)
        for h in skill_module.HARNESSES:
            print(f"{h.name:<{width}}  {h.project_dir:<18}  {h.user_dir:<24}  "
                  f"{h.label} ({h.verified}) {h.source}")
        return 0

    if args.print_section is not None:
        try:
            print(skill_module.read(args.print_section))
        except KeyError as exc:
            print(f"rietx skill: {exc.args[0]}", file=sys.stderr)
            return 2
        return 0

    if args.install is not None:
        agents = tuple(args.agent) if args.agent else skill_module.DEFAULT_AGENTS
        try:
            written = skill_module.install(args.install, user=args.user,
                                           agents=agents, copy=args.copy)
        except KeyError as exc:
            print(f"rietx skill: {exc.args[0]}", file=sys.stderr)
            return 2
        print(f"skill installed at {written['canonical']}")
        for name in agents:
            target = written[name]
            note = " (already there)" if target == written["canonical"] else ""
            print(f"  {name}: {target}{note}")
        print("\nAdd these two lines to the project's AGENTS.md or CLAUDE.md "
              "(not written for you):\n")
        print(skill_module.instructions_snippet())
        return 0

    # --path, and the bare default: the question a harness asks first
    path = skill_module.skill_path()
    if path is None:
        print("rietx skill: this build carries no skill directory",
              file=sys.stderr)
        return 1
    print(path)
    return 0


def _index(argv: list[str]) -> int:
    """``rietx index`` — terminal-shaped because "what is this cell?" is a
    question you ask about a file you just collected.

    It prints the **candidate list**, never one cell: the API has no ``.cell`` and
    the CLI must not invent one.  The exit code carries the verdict so a shell
    pipeline can branch on it — 0 when ``best_or_none()`` returns a cell, 1 when
    the result abstains — which is the same statement as the diagnostics, in the
    one channel a script can read without parsing.
    """
    import argparse

    p = argparse.ArgumentParser(
        prog="rietx index",
        description="Determine the unit cell of an unknown phase from a powder "
                    "pattern. Prints every candidate with its confidence and the "
                    "reasons it is not higher; exits 1 if no cell reached the gate.")
    # from the registry, because this string was already stale once: it named
    # five extensions and no pdCIF suffix while three readers were registered
    from .io.readers import PATTERN_FORMATS
    p.add_argument("pattern", help="pattern file — " + ", ".join(
        sorted({e for f in PATTERN_FORMATS if f.refuses is None
                for e in f.extensions})) + ", or any two/three-column ASCII")
    p.add_argument("--wavelength", type=float, required=True,
                   help="primary wavelength in Å. A single line: for a lab Kα "
                        "doublet build the Instrument in python "
                        "(Instrument.bragg_brentano(radiation='CuKa')) and call "
                        "index_pattern — peak picking recognises the Kα2 alias of "
                        "each line and a one-line source cannot")
    p.add_argument("--geometry", default="debye_scherrer",
                   choices=("debye_scherrer", "bragg_brentano",
                            "flat_plate_transmission"))
    p.add_argument("--radius", type=float, default=None,
                   help="goniometer radius in mm (required for bragg_brentano)")
    p.add_argument("--systems", default=None,
                   help="comma-separated crystal systems (default: all). A "
                        "restricted search reports what it did not cover rather "
                        "than concluding anything about the specimen")
    p.add_argument("--engines", default=None,
                   help="comma-separated engines (default: all — 'high' "
                        "confidence means every engine that ran agreed)")
    p.add_argument("--max-d", type=float, default=None,
                   help="longest principal d-spacing in Å (default 25); domain "
                        "size is what an exhaustive search pays for")
    p.add_argument("--min-d", type=float, default=None,
                   help="shortest principal d-spacing in Å (default 2)")
    p.add_argument("--budget", type=float, default=None,
                   help="wall-clock seconds per (engine x crystal system) slice "
                        "of the search (default 30 — so an unbounded "
                        "three-engine, seven-system run is up to 3x7x30 s of "
                        "search, before the probe and validation; --ceiling "
                        "prints the arithmetic)")
    p.add_argument("--total-budget", type=float, default=None,
                   help="wall-clock ceiling for the WHOLE run — search, probe "
                        "and validation. The run returns what was reached and "
                        "INDEX_BUDGET_EXHAUSTED names the systems truncated or "
                        "not reached. Overrides the preset's ceiling")
    p.add_argument("--preset", default=None,
                   help="search preset (default 'quick': every engine and "
                        "system under a whole-run ceiling, truncation reported; "
                        "'full': no ceiling, the pre-1.0 behaviour)")
    p.add_argument("--ceiling", action="store_true",
                   help="print the pre-run cost ceiling for these options — "
                        "worst-case arithmetic and the measured typical range — "
                        "and exit without searching")
    p.add_argument("--shift-allowance", type=float, default=None,
                   help="a MEASURED systematic 2θ allowance in degrees — the "
                        "shift's amplitude a window must span, not the residual "
                        "scatter a template leaves; without one the engines "
                        "assume 0.05° and cap confidence, because a cell found "
                        "in a widened window absorbs the shift")
    p.add_argument("--no-validate", action="store_true",
                   help="skip the whole-profile validation fit (caps every "
                        "candidate at medium)")
    p.add_argument("--json", metavar="FILE", default=None,
                   help="write the full IndexingResult as JSON")
    args = p.parse_args(argv)

    from .indexing import SearchSpec, index_pattern
    from .io.readers import read_pattern
    from .schemas.instrument import Geometry, Instrument

    # what the reader repaired or assumed goes to stderr before anything else:
    # a reversed scan or a dropped duplicate changes the numbers below it, and
    # the CLI is one of the two consumers the GUI preview would otherwise leave
    # blind (the other is the API)
    read_notes: list = []
    data = read_pattern(args.pattern, diagnostics=read_notes)
    for note in read_notes:
        print(note, file=sys.stderr)
    instrument = Instrument.debye_scherrer(wavelength=args.wavelength)
    if args.geometry != "debye_scherrer":
        # built rather than assigned: Geometry's validator refuses a
        # bragg_brentano with no radius, and that refusal is the point
        instrument = instrument.model_copy(update={"geometry": Geometry(
            kind=args.geometry, goniometer_radius_mm=args.radius)})
    spec_kw: dict = {}
    if args.systems:
        spec_kw["systems"] = tuple(s.strip() for s in args.systems.split(","))
    for name, value in (("min_d_axis", args.min_d), ("max_d_axis", args.max_d),
                        ("budget_seconds", args.budget),
                        ("total_budget_seconds", args.total_budget),
                        ("shift_allowance_deg", args.shift_allowance)):
        if value is not None:
            spec_kw[name] = value
    spec = SearchSpec(**spec_kw)
    engine_names = (tuple(e.strip() for e in args.engines.split(","))
                    if args.engines else None)

    if args.ceiling:
        _print_ceiling(spec, engine_names, validate=not args.no_validate)
        return 0

    result = index_pattern(data=data, instrument=instrument,
                           spec=spec, preset=args.preset, engines=engine_names,
                           validate=not args.no_validate)
    print(result)
    if args.json:
        from pathlib import Path

        Path(args.json).write_text(result.model_dump_json(indent=2),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0 if result.best_or_none() is not None else 1


def _print_ceiling(spec, engine_names, *, validate: bool) -> None:
    """The pre-run cost answer, printed with its own epistemics: the search and
    probe lines are arithmetic the per-system budgets enforce, the validation
    line is a measured range, and the typical line is why the worst case is not
    an ETA (``engines.estimate_ceiling``)."""
    from .indexing.engines import estimate_ceiling

    est = estimate_ceiling(spec, engines=engine_names, validate=validate)
    lo, hi = est.validation_seconds_each
    t_lo, t_hi = est.typical_seconds
    print(f"worst case: {est.worst_case_seconds:.0f} s   "
          f"(search {est.search_seconds:.0f} + probe {est.probe_seconds:.0f}, "
          "arithmetic on the per-system budgets; "
          f"+ validation {est.validation_calls} fits x {lo:g}-{hi:g} s, "
          "a measured range — the fit's cost is data-dependent)")
    print(f"measured typical: {t_lo:g}-{t_hi:g} s per real dataset "
          "(searches finish their systems early far more often than not)")
    print(f"a --total-budget binds within ~{est.granularity_seconds:g} s "
          "(the longest uninterruptible stretch)")
    if est.unmodelled:
        print(f"NOT modelled: engine(s) {', '.join(est.unmodelled)} — "
              "the worst case above omits their cost")


if __name__ == "__main__":
    raise SystemExit(main())
