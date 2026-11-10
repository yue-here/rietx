"""WP-1210 — the GUI's colours, held apart in OKLab.

Since WP-1429 the values are :data:`rietx.viz.theme.TOKENS` — Python, because
``rietx watch`` and ``rietx compare`` ship inside the wheel and the GUI
workspace does not, and the three pages a reader has open at once must not
answer "which colour is the calculated curve" three ways.  ``gui/src/tokens.css``
is generated from them and committed, and the byte-equality test below holds the
two together, so an edit on either side fails until the other follows.  Every
other assertion here reads the module, which is the authority.

The distance that decides whether two of them are one colour is
:func:`rietx.gui.structure3d._oklab_distance`, which the phase palette already
uses.  So the assertion is here, in Python, rather than in ``plot.test.ts``: a
TypeScript port would be a second answer to "how far apart are these two
colours", and this repo has paid for that shape before.  What the vitest side
asserts is the *plumbing* — that ``curveColors`` reads each property and falls
back per property.

Why it is worth asserting at all: before this WP the peak layer had no colours
of its own, and the two it borrowed were `--plot-diff` and `--plot-calc`
**exactly** on the light theme.  Nothing failed; the picture simply drew the
picked-peak fit and the model in one red.

WP-1217 added the history graph's lanes at the bottom, which are the same
question about a different set: the rail is where two marks of one shape and
one weight mean different things, so following a line is the whole job.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from rietx.gui.structure3d import MIN_SEPARATION, _oklab, _oklab_distance, _oklab_hex
from rietx.viz.plots import PALETTES
from rietx.viz.theme import (
    PHASE_COLOURS,
    PHASE_TOKENS,
    THEME_CHOICES,
    THEME_GLYPHS,
    THEME_TITLES,
    TOKENS,
    tokens_css,
)

ROOT = Path(__file__).resolve().parent.parent
TOKENS_CSS = ROOT / "gui" / "src" / "tokens.css"
PLOT_TS = ROOT / "gui" / "src" / "lib" / "plot.ts"

#: The colours a *curve* is drawn in — the set a reader has to tell apart.
#:
#: `--plot-zero` and `--plot-mask` are deliberately absent: both are chrome (a
#: zero line, a wash over what is not fitted), and neither carries a quantity.
#: The pairs that sit under the floor are named below in :data:`NAMED_PAIRS`.
CURVES = ("--plot-obs", "--plot-calc", "--plot-bkg", "--plot-diff",
          "--plot-peak", "--plot-peakfit", "--plot-candidate")

#: What a *layer's* colour must clear: every other curve, plus the two inks a
#: mark can otherwise be mistaken for.
NEIGHBOURS = (*CURVES, "--muted", "--fg")

#: The colours a layer drawn over the data owns — the peak layer's pair
#: (WP-1210) and the candidate overlay's one (WP-1211).  They are held to more
#: than the curve floor because a layer is drawn *on top of* the curves rather
#: than beside them: separation from the page as well, and from `--accent` and
#: `--bad`, which is the specific mistake WP-1210 was written to undo.
LAYERS = ("--plot-peak", "--plot-peakfit", "--plot-candidate")

#: The pairs the shipped palette misses the floor on, named rather than exempted
#: quietly, each held to the distance it was measured at so it can only improve.
#:
#: All three are the background (WP-2200).  The site's palette draws it dashed in
#: the figures' brown, beside an orange calculated curve and a grey difference,
#: as the design rounds of 2026-11-06 to 11-08 drew it and as `viz/plots.PALETTES`
#: has drawn every figure since.  The dash carries its identity, as the point
#: marks carry the observations'.  A fourth pair fails.
#:
#: The pairs WP-1210 named here (light `--plot-bkg`/`--plot-diff` at 0.129, dark
#: `--plot-obs`/`--plot-diff` at 0.124) cleared the floor under the new palette and
#: left the table, and so did the recessive set that exempted the old grey
#: observations from the background: the observations are drawn in the ink now.
#: `--muted` still draws the masked measured points, which are the same data as
#: `--plot-obs` (WP-1033); what may *not* borrow it is a mark that is not the
#: data, which `test_each_layer_colour_clears_the_floor_against_every_neighbour`
#: holds.
NAMED_PAIRS: dict[str, dict[tuple[str, str], float]] = {
    "light": {("--plot-bkg", "--plot-calc"): 0.064},
    "dark": {("--plot-bkg", "--plot-calc"): 0.092,
             ("--plot-bkg", "--plot-diff"): 0.109},
}


def _block(name: str, css: str) -> dict[str, str]:
    """The custom properties declared in one block of the emitted stylesheet."""
    start = css.index(name)
    depth, end = 0, start
    for index in range(start, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    body = css[start:end]
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", body))


@pytest.fixture(scope="module")
def themes() -> dict[str, dict[str, str]]:
    """The authority itself — `viz/theme.py`, not a file parsed back."""
    return {name: TOKENS[name] for name in ("light", "dark")}


def test_the_committed_stylesheet_is_the_emitters_output():
    """The seam WP-1429 exists to close, and the only test that reads the file.

    `gui/src/tokens.css` is generated and committed for the same reason
    `gui/dist` is: the GUI's build cannot import Python, and the wheel cannot
    ship the GUI's sources.  A generated file nobody regenerates is a second
    authority wearing a comment that says it is not one, so this is what keeps
    the edit where the header says it goes.
    """
    assert TOKENS_CSS.read_text(encoding="utf-8") == tokens_css(), (
        "gui/src/tokens.css is stale - run "
        "`python -m rietx.viz.theme > gui/src/tokens.css` and rebuild the dist")


@pytest.mark.parametrize("name", ["light", "dark"])
def test_every_block_of_the_stylesheet_carries_the_whole_palette(name):
    """The emitter's own structure: three blocks, and the dark one twice.

    The dark palette is declared twice on purpose — the `@media` block paints
    before an app has booted, the attribute block is what an explicit choice
    sets — and before WP-1429 the two were free to drift, which is why
    `app.css` was parsed here at all.  They now come from one dict, so what is
    left to check is that the *emitter* puts every token in every block: a
    comment wrapper or an indent bug that swallowed a declaration would show as
    a missing curve rather than a wrong one.
    """
    css = tokens_css()
    blocks = [":root {"] if name == "light" else [
        ':root:not([data-theme="light"])', ':root[data-theme="dark"]']
    # the phase palette does not follow the theme, so it is declared once, in
    # `:root` with the light set, and the dark blocks override what changes
    # and nothing else (WP-1438)
    expected = dict(TOKENS[name], **PHASE_TOKENS) if name == "light" else TOKENS[name]
    for block in blocks:
        assert _block(block, css) == expected, f"{block} is short"


def test_the_typescript_fallbacks_are_the_light_tokens():
    """`curveColors` reads each property and falls back per property (plot.ts).

    The fallbacks are for a page with no stylesheet — jsdom — so they are a
    copy of the light palette in a second language, which is the shape WP-1429
    removes everywhere it reaches.  It does not reach here: a TypeScript
    literal is what a missing property falls back *to*, and generating a `.ts`
    twin of `tokens.css` would be a second generated file for ten values.  So
    the copy stays and is pinned instead.

    The phase palette's four are the exception that says what the rule is
    about (WP-1438): they do not follow the theme, so *their* fallback is not
    "the light value" — it is the value, and a page with no stylesheet draws a
    phase in the colour every other surface draws it in.
    """
    source = PLOT_TS.read_text(encoding="utf-8")
    fallbacks = dict(re.findall(r'pick\("(--[\w-]+)",\s*"(#[0-9a-fA-F]{6,8})"\)',
                                source))
    assert fallbacks, "no `pick(token, fallback)` calls found in plot.ts"
    expected = dict(TOKENS["light"], **PHASE_TOKENS)
    assert fallbacks == {key: expected[key] for key in fallbacks}
    assert set(PHASE_TOKENS) <= set(fallbacks), "the phase tokens are not read"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_layer_has_its_own_colours_in_both_themes(themes, theme):
    """Not `--accent`/`--bad`, which are chrome and collide with two curves."""
    palette = themes[theme]
    for token in LAYERS:
        assert token in palette, f"{token} is missing from the {theme} theme"
        for chrome in ("--accent", "--bad"):
            assert palette[token] != palette[chrome]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_each_layer_colour_clears_the_floor_against_every_neighbour(themes, theme):
    """The phase palette's floor, applied to the plot's own set.

    Both directions matter and one of them is the reason this test exists: the
    fitted curve has to be separable from `--plot-calc` (the report), and the
    markers from everything a marker sits on.  The candidate overlay joins it
    for a sharper version of the same reason — it is drawn over the peak
    markers, on the tab that owns both, to answer which picked lines a cell
    accounts for.
    """
    palette = themes[theme]
    for token in LAYERS:
        mine = _oklab(palette[token])
        for other in NEIGHBOURS:
            if other == token:
                continue
            gap = _oklab_distance(mine, _oklab(palette[other]))
            assert gap >= MIN_SEPARATION, (
                f"{theme}: {token} {palette[token]} is {gap:.3f} from "
                f"{other} {palette[other]} — under the {MIN_SEPARATION} floor")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_chromatic_curve_pair_clears_it_too(themes, theme):
    """The floor holds across the whole curve set, the named pairs apart.

    Which is the assertion that would have failed the day the peak layer was
    written: `--accent` against `--plot-diff` was 0.000.
    """
    palette = themes[theme]
    known = NAMED_PAIRS[theme]
    for one in CURVES:
        for two in CURVES:
            if one >= two:
                continue
            gap = _oklab_distance(_oklab(palette[one]), _oklab(palette[two]))
            floor = known.get((one, two), MIN_SEPARATION)
            assert gap >= floor, (
                f"{theme}: {one} and {two} are {gap:.3f} apart")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_named_pairs_are_still_the_only_ones(themes, theme):
    """An exemption that outlives its reason is a lie about the palette."""
    palette = themes[theme]
    under = {
        (one, two)
        for one in CURVES for two in CURVES
        if one < two
        and _oklab_distance(_oklab(palette[one]), _oklab(palette[two])) < MIN_SEPARATION
    }
    assert under == set(NAMED_PAIRS[theme]), (
        f"{theme}: the pairs under the floor have changed — {sorted(under)}")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_layer_colour_reads_against_its_own_page(themes, theme):
    """A colour that clears every curve can still be invisible on the surface."""
    palette = themes[theme]
    page = _oklab(palette["--bg"])
    for token in LAYERS:
        gap = _oklab_distance(_oklab(palette[token]), page)
        assert gap >= 0.30, f"{theme}: {token} is {gap:.3f} from the page"


# --- the history graph's lanes (WP-1217) -----------------------------------
#
# Half a palette in each place, on purpose: `lib/history.ts` owns the hue
# *rotation* and `viz/theme.py` owns the lightness and chroma a rail is read
# at, so a lane's ink is `oklch(var(--lane-l) var(--lane-c) <hue>)` and neither
# file holds a colour.  What decides whether the rotation is fine enough is a
# distance, and this is the file that has one.

HISTORY_TS = ROOT / "gui" / "src" / "lib" / "history.ts"


def _lanes(name: str) -> list[tuple[float, float, float]]:
    """The lane inks of one theme, as OKLab — through sRGB, as a screen shows them."""
    lightness = float(TOKENS[name]["--lane-l"])
    chroma = float(TOKENS[name]["--lane-c"])
    source = HISTORY_TS.read_text(encoding="utf-8")
    hues = [float(h) for h in re.search(
        r"LANE_HUES\s*=\s*\[([^\]]+)\]", source).group(1).split(",")]
    return [_oklab(_oklab_hex((lightness,
                               chroma * math.cos(math.radians(hue)),
                               chroma * math.sin(math.radians(hue)))))
            for hue in hues]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_pair_of_lanes_clears_the_floor(themes, theme):
    """Two lanes 72° apart at this chroma; a sixth lane at 60° would not.

    The rail is the one place in this app where two marks of the same shape and
    the same weight mean different things, so following a line across ten rows
    is the whole job and the hues have to be nameable apart.  Hue-only at
    constant L and C puts a pair 2·C·sin(Δh/2) apart before the sRGB gamut has
    its say, which is why the measurement goes through the hex a browser will
    actually paint.
    """
    lanes = _lanes(theme)
    assert len(lanes) == 5
    for i, one in enumerate(lanes):
        for two in lanes[i + 1:]:
            gap = _oklab_distance(one, two)
            assert gap >= MIN_SEPARATION, f"{theme}: two lanes are {gap:.3f} apart"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_lane_reads_against_the_panel_it_is_drawn_on(themes, theme):
    """`--panel`, not `--bg`: the graph sits inside a panel's surface."""
    surface = _oklab(themes[theme]["--panel"])
    for index, lane in enumerate(_lanes(theme)):
        gap = _oklab_distance(lane, surface)
        assert gap >= 0.30, f"{theme}: lane {index} is {gap:.3f} from the panel"


# ----------------------------------------------------------------------
# WP-1438 — the phase palette, which is categorical rather than a role
# ----------------------------------------------------------------------

#: How close a phase colour comes to a *curve* colour, on the worst of the four
#: surfaces (two themes × the tokens and the figure palette).
#:
#: It is under :data:`MIN_SEPARATION` and that is the decision rather than an
#: oversight: a tick sits in a row of its own below the data, so its identity is
#: carried by position as well as by hue, and the floor is what a mark drawn
#: *over* the data is held to.  No four of Okabe-Ito's eight clear 0.13 against
#: everything, so what the set is chosen for is this number (measured 0.0637, and
#: the constant is the floor it may not fall below) and what it is for is the
#: other direction — it may not get worse.  The two lists this one
#: replaced scored **0.009** (tab10's green against the figures' own ±3σ band,
#: which is the same colour) and 0.052.
PHASE_CURVE_WEAKEST = 0.063

#: The roles a tick is drawn near on the figure surface, whose curve colours are
#: not the tokens' (matplotlib orange against the GUI's red, and a green band).
FIGURE_ROLES = ("obs", "calc", "bkg", "diff", "band")


def _phase_distances() -> list[tuple[float, str]]:
    """Every phase colour against every curve role, on every surface."""
    out = []
    for index, colour in enumerate(PHASE_COLOURS):
        lab = _oklab(colour)
        for theme in ("light", "dark"):
            for token in CURVES:
                out.append((_oklab_distance(lab, _oklab(TOKENS[theme][token])),
                            f"phase {index} {colour} vs {theme} {token}"))
            for role in FIGURE_ROLES:
                out.append((_oklab_distance(lab, _oklab(PALETTES[theme][role])),
                            f"phase {index} {colour} vs {theme} figure {role}"))
    return sorted(out)


def test_two_phases_are_never_one_colour():
    """The floor applies here in full: two tick rows are two of the same mark.

    This is what the shipped dark list failed — `#6fb1ff` and `#c9a6ff` were
    0.113 apart while every other pair in the app was held to 0.13.
    """
    for i, one in enumerate(PHASE_COLOURS):
        for j, two in enumerate(PHASE_COLOURS[i + 1:], start=i + 1):
            gap = _oklab_distance(_oklab(one), _oklab(two))
            assert gap >= MIN_SEPARATION, (
                f"phases {i} and {j} ({one}, {two}) are {gap:.3f} apart")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_phase_reads_against_every_page_it_is_drawn_on(theme):
    """Four surfaces, and the figure's warm ground is not the app's `--bg`.

    Yellow is the member this is for: it is the safest of the four against the
    curves and the weakest against a white page, which is why it is spent last.
    """
    for index, colour in enumerate(PHASE_COLOURS):
        lab = _oklab(colour)
        for name, page in (("--bg", TOKENS[theme]["--bg"]),
                           ("--panel", TOKENS[theme]["--panel"]),
                           ("figure ground", PALETTES[theme]["ground"])):
            gap = _oklab_distance(lab, _oklab(page))
            assert gap >= MIN_SEPARATION, (
                f"{theme}: phase {index} {colour} is {gap:.3f} from {name}")


def test_no_phase_colour_comes_closer_to_a_curve_than_the_recorded_number():
    """The one distance below the floor, pinned so it can only improve.

    Named rather than exempted quietly, the way `NAMED_PAIRS` names its
    pairs: the nearest neighbour is bluish green against the light candidate
    overlay, and a retune that brought a phase closer to a curve than this would be
    undoing what the set was chosen for.
    """
    worst, where = _phase_distances()[0]
    assert worst >= PHASE_CURVE_WEAKEST, f"{where} is {worst:.3f}"


def test_the_order_spends_the_most_legible_first():
    """Which four is the curve measurement's answer; the order is the page's.

    A tick that collides with a curve is still in a row of its own; a tick
    nobody can see against the page is not saved by anything.  So the set is
    ordered by its worst contrast against a page, and a reordering that put a
    weaker colour in the slot every two-phase pattern uses fails here.
    """
    def page_gap(colour: str) -> float:
        lab = _oklab(colour)
        return min(_oklab_distance(lab, _oklab(page))
                   for theme in ("light", "dark")
                   for page in (TOKENS[theme]["--bg"], TOKENS[theme]["--panel"],
                                PALETTES[theme]["ground"]))

    gaps = [page_gap(colour) for colour in PHASE_COLOURS]
    assert gaps == sorted(gaps, reverse=True), (
        "the phase order is not by page contrast: "
        + ", ".join(f"{c} {g:.3f}" for c, g in zip(PHASE_COLOURS, gaps)))


def test_one_list_serves_every_surface():
    """The figure palette's phase entry is this module's list, not a copy.

    Both themes, because a phase's colour is a fact about the phase: the same
    refinement drawn in the GUI, in `rietx watch` and in the manual's figure
    names its phases the same way or the three pictures are not of one fit.
    """
    for theme in ("light", "dark"):
        assert PALETTES[theme]["phase"] == list(PHASE_COLOURS)
    assert list(PHASE_TOKENS.values()) == list(PHASE_COLOURS)


#: The indexing figures' roles (WP-1972), each drawn on its own ground only.
INDEXING_ROLES = ("index_obs", "index_calc", "index_bkg", "index_diff",
                  "absent", "unmatched")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_indexing_colour_reads_against_its_figure_ground(theme):
    """The light hues were chosen for a white page and the dark ones derived
    from them, so both are measured.  The weakest is the light amber, 0.218
    from white, and on the dark ground the background grey, 0.42."""
    hue = PALETTES[theme]
    ground = _oklab(hue["ground"])
    for role in INDEXING_ROLES:
        gap = _oklab_distance(_oklab(hue[role]), ground)
        assert gap >= MIN_SEPARATION, f"{theme}: {role} {hue[role]} is {gap:.3f}"
    for rank, colour in enumerate(hue["candidate"], start=1):
        gap = _oklab_distance(_oklab(colour), ground)
        assert gap >= MIN_SEPARATION, f"{theme}: rank {rank} {colour} is {gap:.3f}"


def test_the_gui_names_the_reflection_in_the_strip_and_not_in_a_box():
    """Which reflection a tick is goes in the strip under the plot (WP-1438).

    What this owns is the *wiring*: `plot.test.ts` owns the row's text and
    `tests/test_gui_server.py` owns the payload, and nothing between them
    would notice the readout ceasing to read `tick_hkl` at all. The plot draws
    no box of its own, since WP-1213 deleted plotly's on a report that it
    covered the data; `App.test.ts` holds the chart to that.
    """
    gui = Path(__file__).resolve().parents[1] / "gui" / "src"
    readout = (gui / "lib" / "plot.ts").read_text(encoding="utf-8")
    start = readout.index("for (const [phase, ticks] of")
    row = readout[start:readout.index("\n  }", start)]
    assert "tick_hkl" in row, "the strip's tick row reads no indices"
    assert "formatHkl" in row, "the label is not the shared one"
    # and the fallback, for a result reopened from a history that predates it
    assert "?.[j]" in row and "length === 3" in row, (
        "a result carrying no indices must keep the row it had rather than "
        "printing the word undefined")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_single_phase_neutral_is_not_a_member_of_the_set(theme):
    """A single row takes the neutral, which follows the theme and is a role.

    Okabe-Ito's eighth colour is black, and it is exactly what a light page's
    single-phase row draws in — but as `tick`, the role, which is the warm
    off-white on a dark ground.  A member of a categorical set cannot do that:
    it would change colour with the theme.
    """
    assert PALETTES[theme]["tick"] not in PHASE_COLOURS


# ----------------------------------------------------------------------
# the theme control, on two pages (WP-1438)
# ----------------------------------------------------------------------
APP_SVELTE = Path(__file__).resolve().parents[1] / "gui" / "src" / "App.svelte"


def _declared(source: str, name: str) -> dict[str, str]:
    """The `Record<ThemeChoice, string>` literal `name` holds, as a dict.

    Parsed rather than imported: `gui/src` is a build input the wheel does not
    ship, so there is no importing it from here — the same reason
    `tokens.css` is generated and byte-compared rather than read.
    """
    start = source.index(f"const {name}")
    body = source[source.index("{", start) + 1:source.index("}", start)]
    return {m.group(1): m.group(2) for m in
            re.finditer(r'(\w+)\s*:\s*"((?:[^"\\]|\\.)*)"', body)}


def test_the_watcher_and_the_gui_offer_the_same_three_themes():
    """One set of values for three surfaces is WP-1429's rule, and a glyph is
    a value (WP-1438).

    The watcher draws its control from `viz/theme.py` over the wire. The GUI
    cannot import that module, so this holds its literals equal to it
    instead — an edit on either side fails until the other follows, which is
    exactly what `tokens.css` is held to.
    """
    source = APP_SVELTE.read_text(encoding="utf-8")
    glyphs = _declared(source, "GLYPH")
    titles = _declared(source, "THEME_TITLE")
    assert glyphs == THEME_GLYPHS
    assert titles == THEME_TITLES
    assert set(THEME_GLYPHS) == set(THEME_TITLES) == set(THEME_CHOICES)


def _contrast(a: str, b: str) -> float:
    """The WCAG 2.2 contrast ratio of two opaque `#rrggbb` colours."""
    def luminance(value: str) -> float:
        parts = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
               for c in parts]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


APP_CSS = ROOT / "gui" / "src" / "app.css"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_filled_controls_ink_legibly_on_their_fill(theme):
    """The primary and an engaged toggle are filled in the accent's text role.

    White on the orange accent is **4.22:1**, under WCAG AA, which is why the
    maintainer's ruling of 2026-11-06 fills the one primary in `--accent-ink`
    (5.84:1 with white).  The ink is `--panel`, never a literal white: on the
    dark theme the fill is a light orange, and `--panel` is the near-black there
    (WP-1438 found the literal on its way into the watcher's control).
    """
    fill, ink = TOKENS[theme]["--accent-ink"], TOKENS[theme]["--panel"]
    assert _contrast(fill, ink) >= 4.5, (
        f"{theme}: --panel on --accent-ink is {_contrast(fill, ink):.2f}:1")
    css = APP_CSS.read_text(encoding="utf-8")
    for block in ("button {", "button.on {"):
        start = css.index("\n" + block)
        rule = css[start:css.index("}", start)]
        assert "background: var(--accent-ink)" in rule, f"{block} is not filled in --accent-ink"
        assert "color: var(--panel)" in rule, f"{block} does not ink in --panel"
        assert "#fff" not in rule, f"{block} inks white on its fill"


#: Every token a panel sets text in, each with the grounds it is set on: the page
#: and the panel for all of them, and the hover ground for the ink a ghost
#: button's label is set in.
TEXT_ON = {ink: ("--bg", "--panel")
           for ink in ("--muted", "--accent-ink", "--ok", "--warn", "--bad")}
TEXT_ON["--fg"] = ("--bg", "--panel", "--hover")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_text_colour_clears_aa_on_every_ground(theme):
    """The site's rule, carried over with its palette (WP-2200): every text
    colour clears 4.5:1 on each ground it is set on, and the accent, which
    marks and sets no running words, clears 3:1 as a mark.

    `gui/STYLE.md` § Colour states it; before this WP only ink on the accent
    fill was measured.  The weakest pair is `--ok` on the light page, 4.95:1.
    A state colour on the hover ground would not clear it (`--ok` is 4.20:1
    there), so a hovered control keeps its label in the ink.
    """
    palette = TOKENS[theme]
    for ink, grounds in TEXT_ON.items():
        for ground in grounds:
            ratio = _contrast(palette[ink], palette[ground])
            assert ratio >= 4.5, f"{theme}: {ink} on {ground} is {ratio:.2f}:1"
    for ground in ("--bg", "--panel"):
        ratio = _contrast(palette["--accent"], palette[ground])
        assert ratio >= 3.0, f"{theme}: --accent on {ground} is {ratio:.2f}:1"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_drawn_plot_colour_clears_3_to_1_on_its_grounds(theme):
    """WCAG 2.1 § 1.4.11 asks 3:1 of a graphic a reader must see (WP-2200).

    The OKLab floor against the page (0.30) does not imply it: the dark peak fit
    first chosen, `#2e5e9a`, cleared every floor at 2.67:1 on `--panel`.  The
    weakest pair is now that curve, `#516494`, at 3.02:1.  The zero line and the
    mask are chrome drawn to recede (:data:`CURVES`' note), so they are exempt.
    """
    palette = TOKENS[theme]
    for role in CURVES:
        for ground in ("--bg", "--panel"):
            ratio = _contrast(palette[role], palette[ground])
            assert ratio >= 3.0, f"{theme}: {role} on {ground} is {ratio:.2f}:1"


#: Every stylesheet that reads these tokens: the GUI's, its panels', and the two
#: Python pages that link the same `/tokens.css` (WP-1429).
STYLESHEETS = (APP_CSS, *sorted((ROOT / "gui" / "src").rglob("*.svelte")),
               ROOT / "src" / "rietx" / "watch" / "static" / "watch.css",
               ROOT / "src" / "rietx" / "compare_app" / "static" / "compare.css")

#: A declaration setting words in the accent, or filling a control with it.
#: `accent-color`, `border-color`, `outline` and a `color-mix` wash are marks.
ACCENT_AS_TEXT_OR_FILL = re.compile(r"(?<![-\w])(color|background)\s*:\s*var\(--accent\)")


def test_no_page_sets_words_in_the_accent_or_fills_a_control_with_it():
    """The two rules above, held on every page the tokens reach (WP-2200).

    The measurements are made on the tokens, so a page that sets text in
    `--accent` or fills a button with it escapes them: the light accent is
    4.05:1 on the page and `--panel` on it 4.22:1, both under AA.  `rietx watch`
    and `rietx compare` did both when the palette moved, and no test read them.
    """
    found = [f"{path.relative_to(ROOT)}: {match.group(0)}"
             for path in STYLESHEETS
             for match in ACCENT_AS_TEXT_OR_FILL.finditer(
                 path.read_text(encoding="utf-8"))]
    assert not found, f"the accent sets words or fills a control: {found}"
