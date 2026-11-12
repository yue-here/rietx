"""The colour tokens the three browser surfaces share, and the theme (WP-1429).

The GUI, ``rietx watch`` and ``rietx compare`` are three pages a reader has
open at once, and before this module each answered "which colour is the
calculated curve" for itself: the GUI's dark red ``#e56a52``, the watcher's
orange ``#ff9d4d``, and ``compare_app.py``'s own list of ten hues.  One fit in
two colour schemes on two different darks is what a second authority looks
like on a screen.

**Why the values live in Python rather than in ``app.css``.**  The two Python
pages ship inside the wheel and the GUI workspace does not — ``gui/`` is a
build input, and what reaches an installed copy is the committed ``dist/``.  A
value the wheel has to serve therefore cannot live in ``gui/src``.  The
reverse direction is a build step, which this repo already does twice:
``help.py`` generates the manual's vocabulary pages (``docs/reference_pages.py``), and
``gui/dist`` is committed and pinned stale-or-current by a test.  So this
module owns the values and emits the stylesheet, ``gui/src/tokens.css`` is
generated and committed, and ``tests/test_gui_palette.py`` holds the two equal
byte for byte — an edit on either side fails until the other follows.

**What is not here.**  Everything in ``app.css`` that is not a colour: the type
and space scales, the radii, the control registers.  And the *role* half of
:data:`~rietx.viz.plots.PALETTES`, the figure palette — chosen so a figure sits
on the manual's and the landing page's warm dark panel rather than as a
brighter card on it, and a figure for print has different needs from a live
page.

**One thing crossed that line** (WP-1438): :data:`PHASE_COLOURS`, which the
figures import from here.  A role colour follows the page it is drawn on, so it
belongs to the surface; a categorical colour follows the phase, so it belongs to
one list or a phase is three different colours in three pictures of the same
refinement.  The cost was foreseen and paid — every committed manual figure pair
with more than one phase was regenerated in that WP.

**The extra roles a page needs are derived, never declared.**  The watcher wants
a row hover, a selected row, a focus ring, four grip states and six state pills,
and none of them is a new token: they are ``color-mix`` over the chrome
tokens.  A token the GUI never reads would be a declared name with no writer
(root CLAUDE.md), and this file is the one place that temptation arrives.
WP-2200 added three of the site's roles, each because a register reads it and
no mix reproduces it: the accent's text role, a control's border and a hover
ground.

Regenerate the stylesheet with::

    python -m rietx.viz.theme > gui/src/tokens.css
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .._about import STATE_DIR_ENV, STATE_DIR_NAME

#: The three-way choice (WP-1029).  "Follow the system" is a *choice* and not
#: the absence of one, so it is a member rather than a null: a user on a machine
#: that switches at dusk wants the app to switch with it, and a user who has
#: decided wants it to stay decided through that switch.
THEME_CHOICES = ("system", "light", "dark")

#: The glyph each choice wears, and what it promises.  Here rather than in
#: each page for the reason the colours are (WP-1429): three surfaces, one
#: set of values.  The GUI cannot import them — `gui/src` is a build input the
#: wheel does not ship — so `tests/test_gui_palette.py` holds `App.svelte`
#: equal to these instead, the same way it holds `tokens.css` equal to the
#: emitter.
THEME_GLYPHS: dict[str, str] = {
    "system": "\u25d0", "light": "\u2600", "dark": "\u263e",
}
THEME_TITLES: dict[str, str] = {
    "system": "follow the system, and keep following it when it changes",
    "light": "light, whatever the system does",
    "dark": "dark, whatever the system does",
}

#: What a choice resolves to.  ``system`` resolves in the *browser*, through the
#: ``prefers-color-scheme`` block :func:`tokens_css` emits — no server can see
#: the machine the page is open on, and a server that guessed would be a second
#: answer to a question CSS already answers correctly.
THEMES = ("light", "dark")

#: The ``color-scheme`` each palette in :data:`TOKENS` is drawn for, which is
#: what native controls (a ``select`` popup, a scrollbar) follow.  This is the
#: seam a named theme enters by (WP-2200; the maintainer's ruling of
#: 2026-11-09 builds light and dark first and Solarized, Monokai and the rest
#: later): a palette under a new key in :data:`TOKENS` and its scheme here, and
#: :func:`tokens_css` emits its ``data-theme`` block.  Listing it as a choice
#: is the Settings piece's.
SCHEMES: dict[str, str] = {"light": "light", "dark": "dark"}

#: The custom properties, in the order they are emitted.  Every theme declares
#: exactly this set; :func:`tokens_css` asserts it.
#:
#: **The site's palette** since WP-2200 (``docs/landing/src/tokens.css``, the
#: one authority for the landing page and the manual): the maintainer ruled on
#: 2026-11-06 that the site is the reference for the GUI's visual language and
#: that its default theme is consistent with it.  A chrome token takes the
#: site's value for the same job, under the GUI's own name: ``--fg`` is the
#: site's ``--ink``, ``--panel`` its ``--surface``, ``--line`` its ``--rule``,
#: ``--bad`` its ``--danger``.  Three of the site's roles arrived with readers
#: in the same WP and keep the site's job: ``--accent-ink`` (the accent as text
#: and the primary button's fill, since white on the orange accent is 4.22:1),
#: ``--line-strong`` (a control's border) and ``--hover`` (a hover ground).
#: The site's other roles (a second ink, a faint ink, a tinted ground, an info
#: state) wait for a reader: a token nothing reads is a name with no writer.
TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "--fg": "#1c1917",
        "--bg": "#fbfaf8",
        "--panel": "#ffffff",
        "--hover": "#ece7e0",
        "--line": "#e6e0d8",
        "--line-strong": "#d1c9bf",
        "--muted": "#6b6259",
        "--accent": "#c65d0a",
        "--accent-ink": "#a34c06",
        "--ok": "#2a7d2a",
        "--warn": "#7d5f00",
        "--bad": "#b4271f",
        "--plot-obs": "#1c1917",
        "--plot-calc": "#c65d0a",
        "--plot-bkg": "#b5793a",
        "--plot-diff": "#6b6259",
        "--plot-zero": "#cfcfcf",
        "--plot-peak": "#0072b2",
        "--plot-peakfit": "#6f83e6",
        "--plot-candidate": "#1a8f45",
        "--plot-mask": "#1c191714",
        "--lane-l": "0.58",
        "--lane-c": "0.15",
    },
    "dark": {
        "--fg": "#f1ece5",
        "--bg": "#15110d",
        "--panel": "#1d1813",
        "--hover": "#2e2820",
        "--line": "#312a22",
        "--line-strong": "#463d32",
        "--muted": "#a0968a",
        "--accent": "#ff9d4d",
        "--accent-ink": "#ffb679",
        "--ok": "#5fd45f",
        "--warn": "#e3c25b",
        "--bad": "#ff8f86",
        "--plot-obs": "#d2c9bd",
        "--plot-calc": "#ff9d4d",
        "--plot-bkg": "#c99a6a",
        "--plot-diff": "#8f8f8f",
        "--plot-zero": "#4a4a4a",
        "--plot-peak": "#008ad5",
        "--plot-peakfit": "#516494",
        "--plot-candidate": "#4ccf8a",
        "--plot-mask": "#f1ece514",
        "--lane-l": "0.72",
        "--lane-c": "0.15",
    },
}

#: One colour per phase, shared by all three surfaces and by the figures
#: (WP-1438).  Theme-independent on purpose: a phase that changed colour when
#: the reader switched themes would be a second fact about the same row.
#:
#: **Okabe-Ito** (Okabe & Ito 2002; Wong, *Nature Methods* **8**, 441, 2011),
#: which is the categorical standard a scientific figure reaches for, and four
#: of its eight, because the Rietveld plot has already spent the rest.  Measured
#: in OKLab against every curve role and page of both themes on both surfaces
#: (WP-1438): blue landed 0.053 from the difference curve, orange 0.061 from the
#: figures' calculated curve, vermillion 0.065 from the app's.  Since WP-2200 the
#: calculated curve is orange in the app too, and blue is the picked-peak
#: marks'.  What is left is bluish
#: green, reddish purple, sky blue and yellow.  Black is not a member: it is the
#: *single-phase* row's neutral, which is
#: :data:`~rietx.viz.plots.PALETTES`'s ``tick`` and follows the theme.
#:
#: **No four of the eight clear the 0.13 floor against everything**, and they do
#: not have to.  A tick sits in a row of its own below the data, so its identity
#: is carried by position as well as by hue, and the floor is what a mark drawn
#: *over* the data is held to.  What the set is chosen for is the weakest link,
#: which is 0.0637 here — bluish green against the light theme's candidate
#: overlay, a mark from the indexing tab.  Spending vermillion instead would buy
#: 0.001 and put the collision on the *calculated curve*, which is on screen
#: whenever a tick row is.
#:
#: **The order is the page's, not the palette's.**  Which four is the curve
#: measurement's answer; the order is contrast against the page — bluish green
#: 0.390, reddish purple 0.330, sky blue 0.280, yellow 0.191 — because a tick
#: that collides with a curve is still in its own row and a tick nobody can see
#: against the page is not saved by anything.  Four is the ceiling rather than a
#: shortage: past four, rows want labels.
#:
#: What it replaced scored worse on both counts it is held to
#: (``tests/test_gui_palette.py``): the tab10 light list came **0.009** from the
#: figures' own ±3σ band — `#2ca02c` against `#2a9d2a`, two greens that are one
#: colour — the dark list 0.052 from the candidate overlay, and the dark list's
#: closest pair was 0.113, under the floor it asks of everything else.  This set
#: is 0.0637 and 0.184.
PHASE_COLOURS: tuple[str, ...] = ("#009e73", "#cc79a7", "#56b4e9", "#f0e442")

#: :data:`PHASE_COLOURS` as custom properties.  They are declared once, in
#: ``:root``, rather than in each theme block, because they do not vary with the
#: theme — the dark blocks override what changes and nothing else.
PHASE_TOKENS: dict[str, str] = {
    f"--phase-{index}": colour for index, colour in enumerate(PHASE_COLOURS)
}

#: The reasoning, keyed by the token each note precedes.  It travels with the
#: values because a palette is a set of decisions and a bare hex is none of
#: them — the notes came out of ``app.css`` with WP-1429 and are emitted into
#: the generated stylesheet, which is a file people read.
NOTES: dict[str, str] = {
    "--plot-obs": """The pattern plot's curves (WP-1029, redrawn in the site's
palette by WP-2200): observed points in the ink, the calculated curve in the
accent, the background dashed in the figures' brown, the difference in the
muted grey, as the design rounds drew them and as rietx's own figures do
(`viz/plots.PALETTES`).  The brown sits under the 0.13 OKLab floor from the
orange curve (0.065 light, 0.092 dark) and from the dark difference grey
(0.110): the dash carries its identity, as the point marks carry the
observations', and `tests/test_gui_palette.py` names the three pairs and holds
each to its measured distance.""",
    "--plot-peak": """The picked-peak layer (WP-1210, recoloured by WP-2200).
The marks take Okabe-Ito blue, the complement of the orange fits, which the
maintainer chose in the design rounds of 2026-11-08 (`#0072b2`).  Its dark
twin there was `#56b4e9`, which is `--phase-2` exactly, so the dark marks take
the same hue lifted for the dark ground, the nearest blue that clears 0.13 from
every curve and every phase.  One hue and two tones, because the layer is one
thing: the markers take the stronger contrast against the page in either theme
and the fitted curve sits a step in, dashed.  The fit cannot take the accent as
the prototype drew it, because it shares the pane with the calculated curve.""",
    "--plot-candidate": """An indexing candidate's predicted lines (WP-1211) —
the last of the free hue space the note above measured, spent rather than
borrowed.  It could not take the peak layer's: these two layers are up at the
same time, on the same tab, and the whole question the picture answers is which
of the picked lines a cell accounts for.  Nor the model's tick colour, which
was plotly's own per-phase cycle when this was written and is `--phase-N` in
this file since WP-1438 — measured against it at 0.0637 in OKLab, the weakest
link that palette is chosen for and the reason its order is what it is.""",
    "--plot-mask": """What is *not* being fitted (WP-1033): a wash,
deliberately not a sixth curve colour.  It marks absence from the residual
rather than a quantity, so it carries no hue anything else could be confused
with, and it is weak enough that the recessive grey observations stay readable
through it.""",
    "--lane-l": """The history graph's lanes (WP-1217).  Not a palette but half
of one: the hues are `gui/src/lib/history.ts`'s `LANE_HUES`, rotated there, and
what lives here is the lightness and chroma each theme reads a rail at — so a
lane's ink is `oklch(var(--lane-l) var(--lane-c) <hue>)` and no module learns a
colour.  The chroma is what the 72° spacing is measured against
(`tests/test_gui_palette.py`); the lightness is the panel's, not the plot's,
because a rail is drawn on `--panel` and has to read there.""",
}

#: The route both Python pages link, and what it is served as — one spelling,
#: because two servers linking two different paths to one stylesheet is the
#: duplication this module exists to remove.  ``viz/chart.py`` is the
#: precedent for serving an asset out of the installed package; the difference
#: is that this one is *rendered*, the GUI's committed copy being the generated
#: side rather than the source.
CSS_ROUTE = "/tokens.css"
CSS_CONTENT_TYPE = "text/css; charset=utf-8"

#: What the emitted stylesheet opens with.  It names the generator, because the
#: one thing a reader of a generated file needs is where to make the edit.
_HEADER = """\
/* Generated by `python -m rietx.viz.theme` — edit `src/rietx/viz/theme.py`.

   The colour tokens of all three browser surfaces this package ships: this
   app, `rietx watch` and `rietx compare` (WP-1429).  The values live in Python
   because the two Python pages ship inside the wheel and this workspace does
   not, and `tests/test_gui_palette.py` fails while this file and the emitter
   disagree.

   `app.css` keeps everything that is not a colour — the type and space scales,
   the radii and the nine control registers — and imports this file.

   The dark palette is declared twice, on purpose: the `@media` block is what
   paints correctly before an app has booted and while nobody has chosen, and
   the attribute block is what an explicit choice sets — which has to beat the
   system in *both* directions, and one media query cannot say that. */
"""


def _declarations(theme: str, *, notes: bool) -> list[str]:
    """One theme's custom properties, as indented CSS lines."""
    out: list[str] = []
    for token, value in TOKENS[theme].items():
        if notes and token in NOTES:
            body = " ".join(NOTES[token].split())
            out.append(_wrap_comment(body))
        out.append(f"  {token}: {value};")
    return out


def _phase_declarations() -> list[str]:
    """The phase palette, declared once because it does not follow the theme."""
    note = ("One colour per phase, both themes: four of Okabe-Ito's eight. "
            "Orange and vermillion are out because the calculated curves have "
            "spent them, blue because the picked-peak marks have, and black "
            "is the single-phase "
            "row's neutral rather than a member. `viz/theme.py` carries the "
            "measurement and the order.")
    return [_wrap_comment(note)] + [f"  {token}: {value};"
                                    for token, value in PHASE_TOKENS.items()]


def _wrap_comment(text: str, width: int = 76) -> str:
    """A CSS comment wrapped at `width`, indented two spaces and continued four."""
    words, lines, line = text.split(), [], "  /* "
    for word in words:
        if len(line) + len(word) + 1 > width and line.strip() not in ("/*",):
            lines.append(line.rstrip())
            line = "     " + word + " "
        else:
            line += word + " "
    lines.append(line.rstrip() + " */")
    return "\n".join(lines)


def tokens_css() -> str:
    """The stylesheet every surface links — three blocks and a header.

    ``color-scheme`` travels with the theme and is not decoration: it is what
    makes the native controls a page does *not* style — ``select`` popups,
    checkboxes, scrollbars, the caret — follow an explicit choice.  Without it,
    choosing light on a dark system leaves a page of dark dropdowns.  The GUI
    sets it inline as well (``lib/theme.ts``), which wins and agrees; the two
    Python pages have no such code and take it from here.

    Every palette past ``light`` gets a ``data-theme`` block of its own, in
    :data:`TOKENS`' order, with the scheme :data:`SCHEMES` gives it: that is
    the seam a named theme enters by (WP-2200).  ``light`` is ``:root`` itself,
    so its attribute block carries the scheme alone.
    """
    if set(TOKENS) != set(SCHEMES):
        raise ValueError("every palette needs a colour scheme: "
                         f"{sorted(set(TOKENS) ^ set(SCHEMES))}")
    for name in TOKENS:
        if set(TOKENS[name]) != set(TOKENS["light"]):
            raise ValueError(f"{name} declares different tokens from light: "
                             f"{sorted(set(TOKENS[name]) ^ set(TOKENS['light']))}")
    light = "\n".join(_declarations("light", notes=True) + _phase_declarations())
    dark = "\n".join(_declarations("dark", notes=False))
    dark_indented = "\n".join("  " + line if line.strip() else line
                              for line in dark.splitlines())
    blocks = "".join(
        f"\n:root[data-theme=\"{name}\"] {{\n  color-scheme: {SCHEMES[name]};\n"
        + "\n".join(_declarations(name, notes=False)) + "\n}\n"
        for name in TOKENS if name != "light")
    return (
        f"{_HEADER}"
        f":root {{\n  color-scheme: light dark;\n{light}\n}}\n"
        f"\n@media (prefers-color-scheme: dark) {{\n"
        f"  :root:not([data-theme=\"light\"]) {{\n{dark_indented}\n  }}\n}}\n"
        f"\n:root[data-theme=\"light\"] {{\n  color-scheme: light;\n}}\n"
        f"{blocks}"
    )


def with_alpha(colour: str, alpha: float) -> str:
    """``#rrggbb`` at an opacity, as the ``rgba()`` a plotting library takes.

    The Python twin of ``watch-core.mjs``'s ``withAlpha``, and it exists for the
    same job on the other page: a legend that sits *inside* the paper is over
    the data, so its ground has to be part-transparent while still being the
    palette's colour rather than a literal one.

    Anything that is not a six-digit hex comes back unchanged, which is what a
    caller passing an already-translucent colour wants and what the JS side
    does with a value it cannot parse.

    The spacing is not the JS twin's, and that is deliberate: plotly takes
    either, and this spelling is byte for byte the literal it replaced, so no
    saved page's bytes moved when the literal went.
    """
    text = colour.strip()
    if len(text) != 7 or not text.startswith("#"):
        return colour
    try:
        r, g, b = (int(text[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return colour
    return f"rgba({r},{g},{b},{alpha})"


def state_dir(override: str | Path | None = None) -> Path:
    """Where the person's own settings live — the recent list and the theme.

    ``$HOME/.rietx``, moved by ``$RIETX_STATE_DIR``.  **Not** the working
    directory's ``.rietx/``, which is a fit's telemetry and which no env var
    moves (``_about.py`` holds that warning; the two are the same literal and
    no test can catch them being confused).

    One expression, called by :class:`~rietx.gui.session.Session` and by the two
    Python servers, because a theme read from a different directory than the one
    the GUI wrote to is a bug that looks like the choice not sticking.
    """
    if override is not None:
        return Path(override)
    return Path(os.environ.get(STATE_DIR_ENV) or Path.home() / STATE_DIR_NAME)


def theme_choice() -> str:
    """The theme the person chose, from ``settings.json``; ``system`` by default.

    Anything unreadable, missing or hand-mangled is ``"system"``, never an
    error — the same grammar :meth:`~rietx.gui.session.Session.settings` uses,
    and for the same reason: no setting here is worth refusing to start over.

    No directory argument: every caller wants the person's, and a parameter
    nothing passes is a claim with no writer.  A caller that one day wants to
    ask about some other directory adds it then.
    """
    try:
        raw = json.loads((state_dir() / "settings.json")
                         .read_text(encoding="utf-8"))
        value = raw["ui"]["theme"]
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        # `RuntimeError` is `Path.home()` on a machine with no home to find:
        # a page draws in the default theme there, rather than not at all
        return "system"
    return value if value in THEME_CHOICES else "system"


def set_theme_choice(value: str) -> str:
    """Store the person's theme choice, and answer with what is now stored.

    **One home for the fact, and every page that shows it may set it**
    (WP-1438, widening WP-1429).  That WP made the GUI the sole writer because
    it was the only surface with a settings screen, and the consequence was
    measured here: ``settings.json`` held ``light`` on a dark machine, and a
    person running a fit from a script and watching it in a browser had no way
    to change it without opening an application they were not using.  A
    user-level theme is settable from whichever window you are in — VS Code,
    Grafana and Jupyter all work that way — and what must not be duplicated is
    the *fact*, which still lives in one file and is still read through one
    function.

    Anything not in :data:`THEME_CHOICES` is refused with ``ValueError``,
    unlike the read above.  A read is repairing somebody's file and a write is
    performing somebody's verb: a request to be a theme that does not exist
    has no honest interpretation, and storing it would leave the file saying
    something every reader turns back into ``system``.

    The rest of ``settings.json`` is preserved, including keys this module
    knows nothing about: ``ui`` is an open dict the GUI's frontend owns, and
    this write touches one key of it.  A file that cannot be
    read is *replaced*, on the same grounds :func:`theme_choice` returns
    ``system`` for one: the alternative is refusing to record a preference
    because of an unrelated corruption.

    An open GUI does not repaint on this.  It reads the choice at boot and
    polls only a run's events, so a change made here reaches it when it is
    reloaded, where a change made *there* reaches an open watcher on the poll
    it already makes.  Said rather than fixed: adding a settings poll to the
    GUI to close a direction nobody has asked for is scaffolding.
    """
    if value not in THEME_CHOICES:
        raise ValueError(
            f"{value!r} is not a theme; expected one of "
            + ", ".join(repr(c) for c in THEME_CHOICES))
    directory = state_dir()
    path = directory / "settings.json"
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(stored, dict):
            stored = {}
    except (OSError, ValueError):
        stored = {}
    ui = stored.get("ui")
    stored["ui"] = {**ui, "theme": value} if isinstance(ui, dict) \
        else {"theme": value}
    directory.mkdir(parents=True, exist_ok=True)
    # written whole and moved into place: a reader of this file is a page
    # being drawn, and a half-written settings file would draw as `system`
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(stored, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return value


if __name__ == "__main__":  # pragma: no cover - the regeneration command
    print(tokens_css(), end="")
