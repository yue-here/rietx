"""The peak editor's cross-group marks follow the edit (WP-2030, task 9).

``duplicate_line`` and the two ghost marks are judged against a line that may
sit in *another* group: a copy's better-measured owner, a ghost's parent.  The
editor refits one group and used to re-mark only that group's components, so
moving or deleting the owner left the copy marked unusable, and moving a line
onto another group's component never marked the worse of the two.

Interpretation table, written before the tests were (each arm can fail):

| arm | must read if the marks follow | reading if they are stale |
|---|---|---|
| the owner moves away | the copy in the other group is unmarked | still ``duplicate_line``: a real line withheld from the search |
| the owner's group is deleted | the copy is unmarked | the same |
| a line moves onto another group's worse component | that component is marked | both usable: one line offered twice |
| an unrelated group is refitted after a user cleared a copy's mark | the mark stays cleared | the mark is back: the editor overruled the person |
| a ghost's parent moves away | the ghost is unmarked | still ``ghost_kbeta`` |

Synthetic data only: Gaussian lines on a flat background, Poisson noise.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.gui.peaks import _spliced
from rietx.indexing.pick import flag_duplicate_lines, pick_peaks_with_state

LAM = 1.5406
LAM_KB = 1.392234
POSITIONS = [14.0, 19.0, 23.5, 28.0, 33.0, 38.5, 44.0, 49.0, 54.5, 60.0]


def _pattern(kbeta: float = 0.0) -> rx.PatternData:
    """Ten lines 4.5-6° apart, each with a Kβ image at ``kbeta`` of its height."""
    tt = np.round(np.arange(10.0, 70.0, 0.01), 3)
    sig = 0.08 / 2.3548
    y = np.full_like(tt, 2000.0)
    for p in POSITIONS:
        y += 3000.0 * np.exp(-0.5 * ((tt - p) / sig) ** 2)
        if kbeta:
            g = 2 * np.degrees(np.arcsin(LAM_KB / LAM * np.sin(np.radians(p / 2))))
            y += kbeta * 3000.0 * np.exp(-0.5 * ((tt - g) / sig) ** 2)
    obs = np.random.default_rng(5).poisson(y).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))


@pytest.fixture(scope="module")
def picked():
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    pl, det, _ = pick_peaks_with_state(_pattern(), ins)
    return pl, det, ins


def _at(pl, two_theta):
    return min(pl.peaks, key=lambda p: abs(p.two_theta - two_theta))


def _with_copy(pl, of: float, into: float, esd_factor: float):
    """``pl`` plus a component of the group at ``into`` sitting on the line at
    ``of``, its position esd ``esd_factor`` times that line's."""
    owner, host = _at(pl, of), _at(pl, into)
    assert owner.group != host.group
    copy = owner.model_copy(update={
        "group": host.group, "flags": [],
        "two_theta_esd": owner.two_theta_esd * esd_factor,
        "two_theta_esd_fit": None})
    out = pl.model_copy(update={"peaks": sorted(
        [p.model_copy() for p in pl.peaks] + [copy],
        key=lambda p: p.two_theta)})
    return out, copy


def _moved(pl, group, by):
    return [p.model_copy(update={"two_theta": p.two_theta + by})
            for p in pl.peaks if p.group == group]


def _flagged(pl, mark):
    return [round(p.two_theta, 3) for p in pl.peaks if mark in p.flags]


def test_a_copy_is_unmarked_when_its_owner_moves_away(picked):
    pl, det, ins = picked
    pl, copy = _with_copy(pl, of=33.0, into=38.5, esd_factor=3.0)
    flag_duplicate_lines(pl.peaks)
    assert _flagged(pl, "duplicate_line") == [round(copy.two_theta, 3)]
    owner = next(p for p in pl.peaks if p is not copy
                 and abs(p.two_theta - copy.two_theta) < 1e-9)
    out = _spliced(pl, owner.group, _moved(pl, owner.group, 1.5), det,
                   ins.source.lines, source=ins.source)
    assert _flagged(out, "duplicate_line") == []


def test_a_copy_is_unmarked_when_its_owners_group_is_deleted(picked):
    pl, det, ins = picked
    pl, copy = _with_copy(pl, of=33.0, into=38.5, esd_factor=3.0)
    flag_duplicate_lines(pl.peaks)
    owner_group = _at(pl, 33.0).group
    if owner_group == copy.group:      # _at found the copy itself
        owner_group = next(p.group for p in pl.peaks if p is not copy
                           and abs(p.two_theta - copy.two_theta) < 1e-9)
    out = _spliced(pl, owner_group, [], det, ins.source.lines,
                   source=ins.source)
    assert _flagged(out, "duplicate_line") == []
    assert any(p.two_theta == copy.two_theta for p in out.peaks)


def test_a_line_moved_onto_a_worse_component_marks_that_component(picked):
    pl, det, ins = picked
    # the copy sits alone at 30.5° first; the 33° line is then moved onto it,
    # better measured, so the copy is now the one physical line's second fit
    pl, copy = _with_copy(pl, of=33.0, into=38.5, esd_factor=3.0)
    copy.two_theta = 30.5
    pl = pl.model_copy(update={"peaks": sorted(pl.peaks,
                                                key=lambda p: p.two_theta)})
    flag_duplicate_lines(pl.peaks)
    assert _flagged(pl, "duplicate_line") == []
    g = next(p.group for p in pl.peaks
             if p is not copy and abs(p.two_theta - 33.0) < 0.05)
    out = _spliced(pl, g, _moved(pl, g, 30.5 - _at_group(pl, g)), det,
                   ins.source.lines, source=ins.source)
    assert _flagged(out, "duplicate_line") == [30.5]
    marked = next(p for p in out.peaks if "duplicate_line" in p.flags)
    assert marked.group == copy.group


def _at_group(pl, g):
    return next(p.two_theta for p in pl.peaks if p.group == g)


def test_a_mark_the_user_cleared_stays_cleared_across_another_groups_edit(
        picked):
    pl, det, ins = picked
    pl, copy = _with_copy(pl, of=33.0, into=38.5, esd_factor=3.0)
    flag_duplicate_lines(pl.peaks)
    copy.flags = []                     # the user says it is a line
    other = _at(pl, 54.5).group
    out = _spliced(pl, other, [p.model_copy() for p in pl.peaks
                               if p.group == other], det,
                   ins.source.lines, source=ins.source)
    assert _flagged(out, "duplicate_line") == []


def test_a_ghost_is_unmarked_when_its_parent_moves_away():
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    pl, det, _ = pick_peaks_with_state(_pattern(kbeta=0.15), ins)
    ghosts = _flagged(pl, "ghost_kbeta")
    assert ghosts, "the Kβ leak was not flagged; the arm tests nothing"
    # the parent of the ghost nearest 44°'s image, in a group of its own
    image = 2 * np.degrees(np.arcsin(LAM_KB / LAM * np.sin(np.radians(22.0))))
    ghost = _at(pl, image)
    assert "ghost_kbeta" in ghost.flags
    parent = _at(pl, 44.0)
    assert parent.group != ghost.group
    out = _spliced(pl, parent.group, _moved(pl, parent.group, 1.5), det,
                   ins.source.lines, source=ins.source)
    assert round(ghost.two_theta, 3) not in _flagged(out, "ghost_kbeta")
    # the joint screen survives the move: the other ghosts keep their marks,
    # so the follow is per peak and not a wipe of the finding
    assert len(_flagged(out, "ghost_kbeta")) == len(ghosts) - 1


def test_a_ghost_mark_the_user_cleared_stays_cleared_across_another_edit():
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    pl, det, _ = pick_peaks_with_state(_pattern(kbeta=0.15), ins)
    image = 2 * np.degrees(np.arcsin(LAM_KB / LAM * np.sin(np.radians(22.0))))
    ghost = _at(pl, image)
    ghost.flags = [f for f in ghost.flags if f != "ghost_kbeta"]
    other = _at(pl, 14.0).group
    out = _spliced(pl, other, [p.model_copy() for p in pl.peaks
                               if p.group == other], det,
                   ins.source.lines, source=ins.source)
    assert "ghost_kbeta" not in ghost.flags
    assert round(ghost.two_theta, 3) not in _flagged(out, "ghost_kbeta")


def test_a_deleted_group_rejudges_ghosts_under_the_declared_source(
        monkeypatch):
    # deleting a group's last component re-judges the cross-group ghost marks,
    # so it must pass the declared beam as a refit does: with no source the
    # Kβ search runs on a monochromated pattern the picker skipped (WP-1445)
    from rietx.gui import peaks as gp
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins = ins.model_copy(update={
        "source": ins.source.model_copy(update={"kbeta": "monochromator"})})
    editor = gp.PeakEditor(_pattern(kbeta=0.15), ins)
    doc = editor.pick()
    assert _flagged(doc.peaks, "ghost_kbeta") == []
    seen = []
    real = gp.flag_ghosts

    def spy(*a, **k):
        seen.append(k.get("source"))
        return real(*a, **k)

    monkeypatch.setattr(gp, "flag_ghosts", spy)
    groups = [p.group for p in doc.peaks.peaks]
    index = next(i for i, g in enumerate(groups) if groups.count(g) == 1)
    out = editor.remove(doc, index)
    assert seen and all(s is ins.source for s in seen)
    assert _flagged(out.peaks, "ghost_kbeta") == []


def test_a_list_picked_without_contamination_marks_gains_none_from_an_edit():
    """``flag_contamination=False`` holds through every edit (WP-2124).

    The pick honoured the option and the editor's refits did not: each one
    re-judged the Kβ and tungsten marks on the components it spliced, and on
    every untouched line a cross-group ghost could reach.
    """
    from rietx.gui import peaks as gp
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    data = _pattern(kbeta=0.15)
    # the control: with the marks on, this pattern's Kβ images are marked
    assert _flagged(gp.PeakEditor(data, ins).pick().peaks, "ghost_kbeta")

    editor = gp.PeakEditor(data, ins, flag_contamination=False)
    doc = editor.pick()
    assert doc.pick_options["flag_contamination"] is False
    assert gp.settings_of(doc) == gp.pick_settings(flag_contamination=False)
    # a whole-pattern list under limits set since says so, and a range keeps
    # its digits
    assert gp.pick_call(doc.pick_options, default_range=(10, 50)) == (
        "session.pick_peaks(shoulders=True, two_theta_range=None, "
        "flag_contamination=False)")
    assert "(12.3456789, 50)" in gp.pick_call(
        {"two_theta_range": [12.3456789, 50]})
    assert _flagged(doc.peaks, "ghost_kbeta") == []
    for g in sorted(doc.groups):
        doc = editor.refit(doc, g)
    assert _flagged(doc.peaks, "ghost_kbeta") == []
    groups = [p.group for p in doc.peaks.peaks]
    index = next(i for i, g in enumerate(groups) if groups.count(g) == 1)
    doc = editor.remove(doc, index)
    assert _flagged(doc.peaks, "ghost_kbeta") == []
