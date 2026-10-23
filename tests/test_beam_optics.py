"""WP-1445 — a source declares what its beam can carry, and the ghost screen reads it.

The screen looks for Kβ and W Lα images of the strongest lines.  Whether such an
image *can* be in the beam is a fact about the instrument, so it is declared
(``Source.kbeta``) rather than inferred from the wavelength, which called a
neutron pattern at 1.5404 Å a copper tube.  ``None`` is undeclared and the screen
runs exactly as before, so every case below is a pair: the declared source skips,
and the same peaks under an undeclared one are flagged.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.background.diagnostics import (
    _KBETA,
    _W_LA1,
    contamination_flags_from_peaks,
    diagnose,
    ghost_searches,
)
from rietx.io.formats.base import METADATA_KEYS
from rietx.schemas.instrument import Source

DATA = Path(__file__).parent / "data"
LAM = 1.5405929
RATIO = 0.14  # an unfiltered tube's Kβ/Kα (Hölzer et al. 1997 Table VI)


def _peaks_with_ghosts(lam_ghost: float) -> tuple[np.ndarray, np.ndarray]:
    """Ten strong parents, and a line at each one's image of ``lam_ghost``."""
    parents = np.array([21.0, 27.5, 33.0, 38.0, 43.5, 49.0, 54.0, 60.0, 66.0, 72.0])
    stol = np.sin(np.radians(parents / 2.0))
    ghosts = 2.0 * np.degrees(np.arcsin(stol * lam_ghost / LAM))
    tt = np.concatenate([parents, ghosts])
    intensity = np.concatenate([np.linspace(1000.0, 600.0, len(parents)),
                                RATIO * np.linspace(1000.0, 600.0, len(parents))])
    order = np.argsort(tt)
    return tt[order], intensity[order]


def _kinds(lam_ghost: float, source: object | None) -> set[str]:
    tt, intensity = _peaks_with_ghosts(lam_ghost)
    flags = contamination_flags_from_peaks(tt, intensity, None, LAM, source=source)
    return {f.kind for f in flags}


def _neutron() -> object:
    return rx.Instrument.constant_wavelength_neutron(1.5404).source


def test_an_undeclared_source_still_finds_the_kbeta_ghosts():
    # the control every skip below is read against
    assert _kinds(_KBETA["CuKa"], None) == {"kbeta"}
    assert _kinds(_KBETA["CuKa"], rx.Instrument.bragg_brentano().source) == {"kbeta"}


def test_an_undeclared_source_still_finds_the_tungsten_ghosts():
    assert _kinds(_W_LA1, rx.Instrument.bragg_brentano().source) == {"tungsten_la"}


def test_a_neutron_source_never_runs_either_search():
    assert ghost_searches(_neutron()) == ()
    assert _kinds(_KBETA["CuKa"], _neutron()) == set()
    assert _kinds(_W_LA1, _neutron()) == set()


def test_a_monochromator_skips_both_searches():
    src = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6).source
    assert src.kbeta == "monochromator"
    assert _kinds(_KBETA["CuKa"], src) == set()
    assert _kinds(_W_LA1, src) == set()


def test_a_filter_is_recorded_and_changes_nothing():
    # measured on corundum and zincite (WP-1445): an injected Kβ image is found
    # at 0.14, 0.10, 0.05 and 0.02, so a skip would discard real leaks
    src = rx.Instrument.bragg_brentano().source.model_copy(update={"kbeta": "filter"})
    assert _kinds(_KBETA["CuKa"], src) == {"kbeta"}
    assert _kinds(_W_LA1, src) == {"tungsten_la"}


def test_a_mirror_is_recorded_and_changes_nothing():
    src = rx.Instrument.bragg_brentano().source.model_copy(update={"kbeta": "mirror"})
    assert _kinds(_KBETA["CuKa"], src) == {"kbeta"}
    assert _kinds(_W_LA1, src) == {"tungsten_la"}


def test_one_monochromator_declaration_serves_both_facts():
    src = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6).source
    assert src.kbeta == "monochromator"
    # the polarisation it already set is untouched
    assert src.polarization.value == pytest.approx(1.0 / (1.0 + np.cos(
        np.radians(26.6)) ** 2))


def test_no_declaration_leaves_the_field_empty():
    assert rx.Instrument.bragg_brentano().source.kbeta is None
    assert rx.Instrument.debye_scherrer(0.4128).source.kbeta is None


def test_a_document_without_the_field_loads_and_one_with_it_round_trips():
    src = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6).source
    doc = json.loads(src.model_dump_json())
    assert doc["kbeta"] == "monochromator"
    assert Source.model_validate(doc).kbeta == "monochromator"
    del doc["kbeta"]
    assert Source.model_validate(doc).kbeta is None
    with pytest.raises(ValueError):
        Source.model_validate({**doc, "kbeta": "foil"})


def _pattern_with_kbeta_ghosts() -> rx.PatternData:
    """Ten strong lines and an unfiltered tube's Kβ image of each, as counts."""
    tt = np.arange(15.0, 80.0, 0.01)
    parents = np.array([21.0, 27.5, 33.0, 38.0, 43.5, 49.0, 54.0, 60.0, 66.0, 72.0])
    amp = np.linspace(20000.0, 12000.0, len(parents))
    ghosts = 2.0 * np.degrees(np.arcsin(
        np.sin(np.radians(parents / 2.0)) * _KBETA["CuKa"] / LAM))
    y = np.full_like(tt, 50.0)
    for centre, a in [*zip(parents, amp), *zip(ghosts, RATIO * amp)]:
        y += a * np.exp(-0.5 * ((tt - centre) / 0.04) ** 2)
    counts = np.random.default_rng(0).poisson(y).astype(float)
    return rx.PatternData(two_theta=tt, intensity=counts)


def test_diagnose_reads_the_declared_source():
    # the control: undeclared flags the images, the declared sources do not
    data = _pattern_with_kbeta_ghosts()
    undeclared = diagnose(data, wavelength=LAM)
    assert undeclared.contamination
    assert undeclared.contamination_searches == ["kbeta", "tungsten_la"]
    # and a skip is recorded as one, so the empty list does not read as clean
    neutron = diagnose(data, wavelength=LAM, source=_neutron())
    assert neutron.contamination == [] and neutron.contamination_searches == []
    mono = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6).source
    behind_mono = diagnose(data, wavelength=LAM, source=mono)
    assert behind_mono.contamination == [] and behind_mono.contamination_searches == []
    assert diagnose(data, wavelength=0.4139).contamination_searches == [], "no anode"


def test_the_xrdml_reader_names_the_optics_a_file_lists():
    powder = rx.read_pattern(DATA / "panalytical_powder.xrdml")
    both = rx.read_pattern(DATA / "panalytical_attenuator.xrdml")
    assert powder.metadata["beam_optics"] == "xRayMirror"
    assert both.metadata["beam_optics"] == "xRayMirror,monochromator"
    assert "beam_optics" in METADATA_KEYS


def test_a_file_listing_no_optics_records_none(tmp_path):
    text = (DATA / "panalytical_powder.xrdml").read_text(encoding="utf-8")
    start = text.index("<xRayMirror")
    end = text.index("</xRayMirror>") + len("</xRayMirror>")
    bare = tmp_path / "bare.xrdml"
    bare.write_text(text[:start] + text[end:], encoding="utf-8")
    assert "beam_optics" not in rx.read_pattern(bare).metadata


# ---------------------------------------------------------------------------
# WP-1539 — the file's optics reach the instrument the wizard builds
# ---------------------------------------------------------------------------
def test_the_reader_says_which_side_of_the_sample_an_optic_sits():
    both = rx.read_pattern(DATA / "panalytical_attenuator.xrdml")
    # this file's hybrid monochromator is before the sample
    assert "monochromator" in both.metadata["beam_optics"]
    assert "diffracted_beam_optics" not in both.metadata
    assert "diffracted_beam_optics" in METADATA_KEYS


def test_only_a_monochromator_after_the_sample_maps_to_kbeta():
    from rietx.gui.imports import kbeta_from_metadata

    # a mirror and a monochromator, both before the sample: undeclared, since
    # "mirror" would name the optic that is not deciding Kβ
    incident = rx.read_pattern(DATA / "panalytical_attenuator.xrdml").metadata
    assert kbeta_from_metadata(incident) is None
    mirror = rx.read_pattern(DATA / "panalytical_powder.xrdml").metadata
    assert kbeta_from_metadata(mirror) == "mirror"  # recorded, acts on nothing
    assert kbeta_from_metadata({"beam_optics": "monochromator"}) is None
    assert kbeta_from_metadata({"beam_optics": "monochromator,filter"}) is None
    assert kbeta_from_metadata({"beam_optics": "monochromator",
                                "diffracted_beam_optics": "monochromator"}) == "monochromator"
    assert kbeta_from_metadata({"beam_optics": "filter"}) == "filter"
    assert kbeta_from_metadata({}) is None
    assert kbeta_from_metadata(None) is None


def test_the_preset_builder_sets_kbeta_from_the_file_and_the_constructor_outranks_it():
    from rietx.gui.imports import instrument_from_preset

    spec = {"preset": "bragg_brentano", "radiation": "CuKa",
            "goniometer_radius_mm": 240.0}
    assert instrument_from_preset(spec).source.kbeta is None  # the control
    got = instrument_from_preset({**spec, "kbeta": "monochromator"})
    assert got.source.kbeta == "monochromator"
    own = instrument_from_preset({**spec, "kbeta": "filter",
                                  "monochromator_two_theta": 26.6})
    assert own.source.kbeta == "monochromator"


def test_the_preset_builder_refuses_an_unknown_kbeta_by_name():
    from rietx.gui.imports import UploadRefused, instrument_from_preset

    with pytest.raises(UploadRefused) as caught:
        instrument_from_preset({"preset": "bragg_brentano", "radiation": "CuKa",
                                "goniometer_radius_mm": 240.0, "kbeta": "bogus"})
    assert caught.value.where == ["instrument.kbeta"]
