"""The CIF tag registry against what the writers write and what the dictionaries define.

WP-1319 C-a (issue #756 § 1): written ⊆ registry ⊆ dictionary, nothing
deprecated, and the registry's own claims (definition id, purpose, output
kinds) read off the vendored COMCIFS dictionaries and the live writers rather
than trusted.  The written side is measured, never listed: every writer runs on
fixtures that between them reach every tag it can emit, and the output is
parsed back with gemmi.  The registry may not carry a tag no writer emits, so a
row cannot outlive the code that wrote it.

The dictionary side is ``tests/cif_dictionary.py``, because gemmi cannot read a
CIF 2.0 dictionary.  The magCIF private tags and the two
:data:`~rietx.io.cif.registry.KNOWN_VIOLATIONS` are the only exemptions, and
the second set may only shrink.
"""

from __future__ import annotations

from pathlib import Path

import gemmi
import pytest

import rietx as rx
from rietx.crystallography import magcif
from rietx.crystallography.cif import structure_to_cif
from rietx.crystallography.magnetic.operators import identify
from rietx.io.cif.registry import (
    _TAGS,
    KNOWN_VIOLATIONS,
    OUTPUT_KINDS,
    PRIVATE_TAGS,
    TAGS,
)
from rietx.io.exporters import refinement_cif_doc
from tests.cif_dictionary import Dictionaries
from tests.test_exporters import fitted_lab6  # noqa: F401  (a fixture)
from tests.test_magcif import _ALL, _read
from tests.test_operator_list_phase import S3_CHILD_LABEL, S3_CHILD_OPS, _phase

DATA = Path(__file__).parent / "data"

# one worker builds the module's fits and dictionaries once (tests/CLAUDE.md)
pytestmark = pytest.mark.xdist_group("cif-registry")

#: The allow-list as C-a found it.  It may lose members, never gain one.
_FOUND_AT_C_A = {"_pd_proc_intensity_total_su", "_symmetry_space_group_name_H-M"}


@pytest.fixture(scope="module")
def dictionaries() -> Dictionaries:
    return Dictionaries()


def _tags(doc) -> set[str]:
    """Every tag in a gemmi document: single items and loop columns."""
    out: set[str] = set()
    for block in doc:
        for item in block:
            if item.pair is not None:
                out.add(item.pair[0])
            elif item.loop is not None:
                out.update(item.loop.tags)
    return out


def _read_tags(path: Path) -> set[str]:
    return _tags(gemmi.cif.read(str(path)))


def _plain_structures() -> list[rx.Structure]:
    """Structures reaching every tag of the non-magnetic structure block:
    LaB6, NAC with its anisotropic tensors, fluorapatite, and fluorapatite
    with one site in a disorder group and another an ion the X-ray table
    lacks (``Ca+``, written neutral with an ``_atom_type_description``)."""
    out = [rx.Structure.from_cif(str(DATA / name), aniso=True)
           for name in ("cod_1000055.cif", "cod_1000236.cif", "fluorapatite.cif")]
    disordered = rx.Structure.from_cif(str(DATA / "fluorapatite.cif"))
    atoms = disordered.phases[0].atoms
    atoms[0] = atoms[0].model_copy(
        update={"disorder_assembly": "A", "disorder_group": "1"})
    atoms[1] = atoms[1].model_copy(update={"species": "Ca+"})
    return [*out, disordered]


def _bodied_structure() -> rx.Structure:
    """A phase with a rigid body carrying one riding H beside a free atom: the
    site flags a body writes (WP-1810)."""
    from rietx.crystallography.bodies import add_body, place_body_atoms
    from rietx.crystallography.riding import set_riding_lengths

    seed = rx.Atom(label="Li", species="Li", x=rx.Parameter(value=0.6),
                   y=rx.Parameter(value=0.6), z=rx.Parameter(value=0.6))
    phase = rx.Phase(name="m", space_group="P1", cell=rx.Cell.cubic(8.0),
                     atoms=[seed])
    phase = add_body(phase, "oh", ["O1", "H1"], ["O", "H"],
                     [(0.0, 0.0, 0.0), (0.9, 0.0, 0.0)], (0.3, 0.3, 0.3))
    body = set_riding_lengths(phase.rigid_bodies[0], {"H1": "OH"}, "xray")
    return rx.Structure(phases=[place_body_atoms(
        phase.model_copy(update={"rigid_bodies": [body]}))])


def _lab_variant(result, ref):
    """(result, structure, instrument) for the items a lab fit reaches."""
    from rietx.schemas.results import AbsorptionCorrection

    structure = ref.fitted_structure.model_copy(deep=True)
    structure.phases[0].extinction = 0.0  # opt-in since WP-1944
    structure.phases[0].extinction.vary = True
    instrument = ref.fitted_instrument.model_copy(deep=True)
    instrument.source = rx.Instrument.bragg_brentano().source
    absorbed = result.model_copy(update={
        "geometry": None,
        "absorption": AbsorptionCorrection(
            method="rouse_cylinder", mu_r=0.3, mu_r_source="given",
            wavelength=instrument.source.primary_wavelength,
            equivalent_delta_biso=0.01)})
    return absorbed, structure, instrument


@pytest.fixture(scope="module")
def written(fitted_lab6, tmp_path_factory) -> dict[str, set[str]]:  # noqa: F811
    """The tags each output kind writes, measured on its writer's output."""
    tmp = tmp_path_factory.mktemp("cif_registry")
    ref, result, _data = fitted_lab6
    instrument = ref.fitted_instrument
    # the fit's own CIF reaches the R factors and the geometry loops; the same
    # result with no geometry carries every other structure through the writer
    # (its geometry rows name LaB6's sites, so they stay on LaB6)
    no_geometry = result.model_copy(update={"geometry": None})
    plain = _plain_structures()
    listed = rx.Structure(phases=[_phase(S3_CHILD_LABEL, list(S3_CHILD_OPS),
                                         (14.0, 6.0, 8.0, 90.0, 97.0, 90.0))])

    out = {kind: set() for kind in OUTPUT_KINDS}
    for structure in [*plain, listed, _bodied_structure()]:
        structure_to_cif(structure, tmp / "s.cif")
        out["structure"] |= _read_tags(tmp / "s.cif")
        out["refinement"] |= _tags(refinement_cif_doc(no_geometry, structure,
                                                      instrument))
    ref.write_cif(tmp / "r.cif")
    out["refinement"] |= _read_tags(tmp / "r.cif")
    # a pattern stating σ, with one measured point past the fitted range: the
    # intensity spelling that carries an su, and the excluded-regions item
    step = result.two_theta[-1] - result.two_theta[-2]
    measured = rx.PatternData(
        two_theta=[*result.two_theta, result.two_theta[-1] + step],
        intensity=[*result.y_obs, result.y_obs[-1]],
        sigma=[*result.sigma, result.sigma[-1]])
    out["refinement"] |= _tags(refinement_cif_doc(no_geometry, ref.fitted_structure,
                                                  instrument, pattern=measured))
    # a Cu doublet, an applied absorption and a refined extinction: the
    # wavelength loop and the items 11-BM LaB6 never needs
    out["refinement"] |= _tags(refinement_cif_doc(*_lab_variant(result, ref)))
    # a time-of-flight bank: its calibration in words, in place of a
    # wavelength, on a result carrying no angular curve
    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, two_theta_bank_deg=90.0)
    out["refinement"] |= _tags(refinement_cif_doc(
        no_geometry.model_copy(update={"two_theta": None}), ref.fitted_structure,
        bank))
    # a Le Bail result: its scaffold sites are marked as dummies
    out["refinement"] |= _tags(refinement_cif_doc(
        no_geometry.model_copy(update={"mode": "lebail"}), ref.fitted_structure,
        instrument))
    # GSAS-II's phase CIF refuses a group stated only as a list, so the
    # operator-list phase is not offered to it
    for structure in plain:
        rx.write_gsas2_phase_cif(structure, tmp / "g.cif")
        out["gsas2"] |= _read_tags(tmp / "g.cif")

    # magnetic: the four magCIF fixtures, plus LaMnO3 stating its OG number,
    # through both writers that carry a magnetic phase; the kind is what they
    # add to the structure and refinement blocks
    magnetic = [_read(tmp, key) for key in _ALL]
    og = identify(magnetic[0].phases[0].magnetic_symmetry.group()).og_number
    magnetic.append(_read(tmp, "LaMnO3",
                          extra=f"_space_group_magn.number_OG {og}\n"))
    for structure in magnetic:
        structure_to_cif(structure, tmp / "m.cif")
        out["magnetic"] |= _read_tags(tmp / "m.cif")
        out["magnetic"] |= _tags(refinement_cif_doc(no_geometry, structure,
                                                    instrument))
    out["magnetic"] -= out["structure"] | out["refinement"]
    return out


def dictionary_violations(tags, dictionaries: Dictionaries) -> dict[str, str]:
    """Each tag the dictionaries do not define, or define only as deprecated,
    with the reason.  Private tags are exempt."""
    found = {}
    for tag in sorted(set(tags) - PRIVATE_TAGS):
        hit = dictionaries.lookup(tag)
        if hit is None:
            found[tag] = "defined in no dictionary"
        elif hit.deprecated:
            found[tag] = f"a deprecated spelling of {hit.definition_id}"
    return found


# ---------------------------------------------------------------------------
# written ⊆ registry, and nothing in the registry that nothing writes
# ---------------------------------------------------------------------------

def test_every_written_tag_is_in_the_registry(written):
    every = set().union(*written.values())
    assert every - set(TAGS) == set(), sorted(every - set(TAGS))


def test_every_registry_tag_is_written_by_some_writer(written):
    every = set().union(*written.values())
    assert set(TAGS) - every == set(), sorted(set(TAGS) - every)


def test_each_row_names_the_output_kinds_that_carry_it(written):
    wrong = {name: (sorted(tag.kinds),
                    sorted(k for k in OUTPUT_KINDS if name in written[k]))
             for name, tag in TAGS.items()
             if tag.kinds != {k for k in OUTPUT_KINDS if name in written[k]}}
    assert wrong == {}


def test_the_magnetic_kind_is_the_magcif_modules_own_vocabulary(written):
    assert written["magnetic"] == set(magcif.WRITTEN_TAGS) | set(magcif.PRIVATE_TAGS)
    assert PRIVATE_TAGS == set(magcif.PRIVATE_TAGS)


def test_the_registry_has_one_row_per_tag():
    assert len(TAGS) == len(_TAGS)
    assert all(tag.kinds and tag.kinds <= set(OUTPUT_KINDS) for tag in _TAGS)


# ---------------------------------------------------------------------------
# registry ⊆ dictionary, nothing deprecated
# ---------------------------------------------------------------------------

def test_every_registry_tag_is_defined_and_current(dictionaries):
    found = dictionary_violations(TAGS, dictionaries)
    assert set(found) - KNOWN_VIOLATIONS == set(), {
        tag: why for tag, why in found.items() if tag not in KNOWN_VIOLATIONS}


def test_every_written_tag_is_defined_and_current(written, dictionaries):
    found = dictionary_violations(set().union(*written.values()), dictionaries)
    assert set(found) - KNOWN_VIOLATIONS == set(), found


def test_each_row_states_the_dictionarys_definition_id_and_purpose(dictionaries):
    """And its ``_type.contents``, which the writer quotes or refuses a value
    by (``io/cif/numbers.text``).  A tag no dictionary defines states its own."""
    wrong = {}
    for name, tag in TAGS.items():
        hit = dictionaries.lookup(name)
        stated = (tag.definition_id, tag.purpose, tag.contents)
        actual = ((None, None, tag.contents) if hit is None else
                  (hit.definition_id, hit.purpose, hit.contents))
        if stated != actual or not tag.contents:
            wrong[name] = (stated, actual)
    assert wrong == {}


def test_a_private_tag_is_one_no_dictionary_defines(dictionaries):
    assert PRIVATE_TAGS <= set(TAGS)
    assert all(dictionaries.lookup(tag) is None for tag in PRIVATE_TAGS)


# ---------------------------------------------------------------------------
# the allow-list only shrinks
# ---------------------------------------------------------------------------

def test_the_known_violations_only_shrink():
    assert KNOWN_VIOLATIONS <= _FOUND_AT_C_A


def test_each_known_violation_is_still_written_and_still_a_violation(
        dictionaries):
    """A fixed tag leaves the list: one kept after its writer stopped, or
    after the dictionary came to define it, would excuse the next one."""
    assert KNOWN_VIOLATIONS <= set(TAGS)
    assert set(dictionary_violations(KNOWN_VIOLATIONS, dictionaries)) == \
        KNOWN_VIOLATIONS


# ---------------------------------------------------------------------------
# the check can fail
# ---------------------------------------------------------------------------

def test_a_planted_undefined_tag_is_reported_by_name(dictionaries):
    found = dictionary_violations(
        {"_cell_length_a", "_cell_flux_capacitance"}, dictionaries)
    assert found == {"_cell_flux_capacitance": "defined in no dictionary"}


def test_a_planted_deprecated_alias_is_reported_with_its_definition(dictionaries):
    found = dictionary_violations({"_atom_site_symmetry_multiplicity"},
                                  dictionaries)
    assert found == {"_atom_site_symmetry_multiplicity":
                     "a deprecated spelling of "
                     "_atom_site.site_symmetry_multiplicity"}


def test_a_replaced_definition_is_deprecated_under_every_spelling(dictionaries):
    """``_definition_replaced`` deprecates the definition itself, so its id
    and its category's items are deprecated with no alias date."""
    assert dictionaries.lookup("_pd_block.id").deprecated
