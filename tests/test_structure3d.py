"""WP-1015 — the structure viewer's geometry payload.

Everything asserted here is crystallography that the browser is deliberately not
allowed to do: the symmetry orbit, the rotation each image carries, the
displacement ellipsoid in the representation whose eigenvalues are physical, and
the cell frame.  The client's whole job is ``pos + k·T·v`` over a unit sphere,
so a defect in this module is a picture that is *confidently wrong* — the same
failure mode the FitReport's gates exist for, one dimension up.

Two of these tests exist because a viewer's plausible-looking output hides them:
an image drawn with its parent's tensor looks fine on a cubic cell and is wrong
on every other one, and ``√(negative eigenvalue)`` is a NaN that takes a whole
mesh with it rather than an atom that looks odd.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from rietx.crystallography.adp import principal_values, u_cartesian
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.symmetry import expand_orbit, expand_positions, get_spacegroup
from rietx.gui import structure3d as s3
from rietx.schemas.structure import AnisoU, Atom, Cell, Parameter, Phase, Structure

DATA = Path(__file__).parent / "data"


def _p(value: float) -> dict:
    return {"value": value}


@pytest.fixture(scope="module")
def lab6():
    """Cubic, Pm-3m, one atom on the corner and one on a face-diagonal axis."""
    return structure_from_cif(str(DATA / "cod_1000055.cif"))


@pytest.fixture(scope="module")
def nac():
    """Cubic I2₁3 **with** the file's anisotropic tensors — six sites, six shapes."""
    return structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)


def monoclinic(**atom_kw) -> Structure:
    """P2₁/c, β = 110° — the cheapest cell on which a wrong metric shows.

    Built rather than read: nothing here needs a real refinement, and the
    assertions are about a general position (multiplicity 4) against an
    inversion centre (multiplicity 2) in a cell whose axes are not orthogonal.
    """
    cell = Cell(a=_p(5.0), b=_p(9.0), c=_p(7.0),
                alpha=_p(90.0), beta=_p(110.0), gamma=_p(90.0))
    atoms = [Atom(label="C1", species="C", x=_p(0.12), y=_p(0.23), z=_p(0.34),
                  **atom_kw),
             Atom(label="O1", species="O", x=_p(0.0), y=_p(0.0), z=_p(0.0))]
    return Structure(phases=[Phase(name="mono", space_group="P 1 21/c 1",
                                   cell=cell, atoms=atoms)])


# ----------------------------------------------------------------------
# the orbit and the frame
# ----------------------------------------------------------------------
def test_a_cubic_phase_expands_to_its_multiplicities(lab6):
    payload = s3.build(lab6)
    by_label = {site["label"]: site for site in payload["sites"]}
    assert by_label["La"]["multiplicity"] == 1      # 1a, the cell corner
    assert by_label["B"]["multiplicity"] == 6       # 6f, on the fourfold axes
    assert all(site["special"] for site in payload["sites"])

    # the *drawn* atoms are the orbit plus boundary duplicates, and the two are
    # distinguishable: a count that mixed them would report 8 La in a cell with
    # one, which is exactly the "8 corners" picture told as a structure
    real = [a for a in payload["atoms"] if not a["boundary"]]
    assert len(real) == 7
    assert sum(1 for a in real if a["site"] == 0) == by_label["La"]["multiplicity"]
    # …and with no bonds to complete, the only images are the seven copies that
    # put the corner atom at all eight corners, beside the B that only La's
    # hidden LaB₂₄ polyhedra need, which the client draws with them
    plain = s3.build(lab6, bond_tolerance=0.5)
    assert not plain["bonds"]
    assert sum(a["boundary"] and not a["vertex_only"] for a in plain["atoms"]) == 7
    vertices = {v for p in plain["polyhedra"] for v in p["vertices"]}
    assert all(k in vertices for k, a in enumerate(plain["atoms"]) if a["vertex_only"])


def test_a_monoclinic_phase_expands_and_frames_the_same_way():
    payload = s3.build(monoclinic())
    multiplicity = {site["label"]: site["multiplicity"] for site in payload["sites"]}
    assert multiplicity == {"C1": 4, "O1": 2}       # 4e general, 2a inversion
    assert payload["sites"][0]["special"] is False
    assert payload["sites"][1]["special"] is True

    assert payload["volume"] == pytest.approx(5.0 * 9.0 * 7.0
                                              * math.sin(math.radians(110.0)))
    lattice = np.array(payload["lattice"])
    # the c axis leans: a payload built on a diagonal metric would not
    assert lattice[2][0] == pytest.approx(7.0 * math.cos(math.radians(110.0)))


@pytest.mark.parametrize("structure", [monoclinic(), None])
def test_the_cell_frame_is_twelve_edges_of_the_right_lengths(structure, lab6):
    payload = s3.build(structure if structure is not None else lab6)
    corners = np.array(payload["corners"])
    edges = np.array(payload["edges"])
    assert corners.shape == (8, 3)
    assert edges.shape == (12, 2)
    lengths = np.linalg.norm(corners[edges[:, 0]] - corners[edges[:, 1]], axis=1)
    a, b, c = payload["cell"][:3]
    # four parallel copies of each axis, which is what makes the box a box
    assert sorted(np.round(lengths, 9)) == pytest.approx(
        sorted([a] * 4 + [b] * 4 + [c] * 4))


def test_the_orbit_carries_the_operation_that_produced_each_image():
    """``expand_orbit`` is ``expand_positions`` plus the rotation, one authority."""
    sg = get_spacegroup("P 1 21/c 1")
    xyz = np.array([0.12, 0.23, 0.34])
    orbit = expand_orbit(sg, xyz)
    assert [p.tolist() for p, _ in orbit] == [p.tolist()
                                              for p in expand_positions(sg, xyz)]
    for position, rot in orbit:
        assert np.allclose(np.abs(np.linalg.det(rot)), 1.0)


# ----------------------------------------------------------------------
# the ellipsoids
# ----------------------------------------------------------------------
def test_an_isotropic_site_is_a_sphere_of_the_equivalent_radius():
    """U_cart = Uiso·I exactly — the closed form the module takes, checked
    against the general path it deliberately does not take."""
    structure = monoclinic()
    biso = structure.phases[0].atoms[0].biso.value
    uiso = biso / (8.0 * math.pi ** 2)
    payload = s3.build(structure)
    drawn = next(a for a in payload["atoms"] if a["site"] == 0)
    assert drawn["rms"] == pytest.approx([math.sqrt(uiso)] * 3)
    assert np.allclose(drawn["ellipsoid"], math.sqrt(uiso) * np.eye(3))

    # …and the general path, through the metric, lands on the same sphere
    from rietx.crystallography.adp import isotropic_u6

    cell = structure.phases[0].cell.lengths_angles()
    assert np.allclose(u_cartesian(isotropic_u6(uiso, cell), cell), uiso * np.eye(3))


def test_an_anisotropic_sites_axes_are_the_principal_values(nac):
    """The semi-axes the payload draws are √(eigenvalues of U_cart), for every
    site, and ``T·Tᵀ`` reconstructs the tensor the eigen-decomposition came from."""
    payload = s3.build(nac)
    phase = nac.phases[0]
    cell = phase.cell.lengths_angles()
    checked = 0
    for site in payload["sites"]:
        atom = phase.atoms[site["index"]]
        assert site["aniso"] is True
        want = np.sqrt(np.clip(principal_values(atom.aniso.values(), cell), 0.0, None))
        first = next(a for a in payload["atoms"] if a["site"] == site["index"])
        assert first["rms"] == pytest.approx(want.tolist())
        transform = np.array(first["ellipsoid"])
        assert np.allclose(transform @ transform.T,
                           u_cartesian(atom.aniso.values(), cell))
        checked += 1
    assert checked == 6


def test_every_symmetry_image_rotates_its_tensor_and_keeps_its_size(nac):
    """The invariant that separates a rotated tensor from a copied one.

    A rotation preserves eigenvalues, so every image of a site has the *same*
    semi-axis lengths — and the orientations must nonetheless differ, or the
    images were drawn with the parent's tensor.  That defect is invisible on a
    cubic-site sphere and wrong on every anisotropic one.
    """
    payload = s3.build(nac)
    seen_rotation = False
    for site in payload["sites"]:
        images = [a for a in payload["atoms"]
                  if a["site"] == site["index"] and not a["boundary"]]
        assert len(images) == site["multiplicity"]
        rms = np.array([a["rms"] for a in images])
        assert np.allclose(rms, rms[0])
        transforms = np.array([a["ellipsoid"] for a in images])
        if not np.allclose(transforms, transforms[0]):
            seen_rotation = True
        for transform in transforms:
            covariance = transform @ transform.T
            assert np.allclose(covariance, covariance.T)
    assert seen_rotation, "no image was rotated; the tensors were copied"


def _turned(vectors: np.ndarray, pair: list[int], angle: float) -> np.ndarray:
    """``vectors`` as another LAPACK may return them: ``pair`` turned by
    ``angle`` within its plane, and every column's sign flipped."""
    out = -np.array(vectors)
    i, j = pair
    c, s = math.cos(angle), math.sin(angle)
    out[:, i], out[:, j] = c * out[:, i] + s * out[:, j], c * out[:, j] - s * out[:, i]
    return out


def test_a_uniaxial_sites_free_axes_are_the_same_whatever_eigh_returned(nac):
    """The client draws a principal ellipse round each of T's columns (D6), and
    on a site uniaxial by symmetry two of them are free. A Mac and an x86
    runner chose them differently for NAC's Na1, an X against a + (WP-1462's
    gate). This test plays every other solver: turned and flipped, the axes
    must come back as one answer, and still reproduce U."""
    phase = nac.phases[0]
    cell = phase.cell.lengths_angles()
    basis = s3.cartesian_basis(*cell)
    na = next(atom for atom in phase.atoms if atom.label == "Na1")
    u = u_cartesian(na.aniso.values(), cell)
    values, vectors = np.linalg.eigh(u)
    # oblate on the threefold axis: the short axis is the lone one
    assert values[2] - values[1] < 1e-12 * values[2] < values[1] - values[0]

    want = s3._pin_axes(values, vectors, basis)
    for angle in (0.3, 1.1, 2.9):
        assert np.allclose(s3._pin_axes(values, _turned(vectors, [1, 2], angle), basis),
                           want, rtol=0, atol=1e-12)
    assert np.allclose(want @ np.diag(values) @ want.T, u, rtol=0, atol=1e-15)
    # the first free axis is a's shadow on the plane (a, b and c tie on [111])
    lone, a = want[:, 0], basis[:, 0] / np.linalg.norm(basis[:, 0])
    shadow = a - (a @ lone) * lone
    assert np.allclose(want[:, 1], shadow / np.linalg.norm(shadow), rtol=0, atol=1e-12)
    assert np.allclose(want.T @ want, np.eye(3), rtol=0, atol=1e-12)


def test_a_spherical_tensors_axes_are_the_lattice_orthonormalised():
    """Three equal values leave every axis free, so a sphere takes a, then b's
    part normal to a, then their cross product."""
    basis = s3.cartesian_basis(5.0, 6.0, 7.0, 90.0, 104.0, 90.0)
    values = np.full(3, 0.02)
    rng = np.random.default_rng(1462)
    answers = [s3._pin_axes(values, np.linalg.qr(rng.normal(size=(3, 3)))[0], basis)
               for _ in range(3)]
    for answer in answers:
        assert np.allclose(answer, answers[0], rtol=0, atol=1e-12)
    a = basis[:, 0] / np.linalg.norm(basis[:, 0])
    assert np.allclose(answers[0][:, 0], a, rtol=0, atol=1e-12)
    assert np.allclose(answers[0].T @ answers[0], np.eye(3), rtol=0, atol=1e-12)


def test_a_distinct_axis_only_ever_flips_to_face_one_way(nac):
    """A lone axis is free only in its sign: flipped, it comes back as it was."""
    phase = nac.phases[0]
    cell = phase.cell.lengths_angles()
    basis = s3.cartesian_basis(*cell)
    f1 = next(atom for atom in phase.atoms if atom.label == "F1")
    values, vectors = np.linalg.eigh(u_cartesian(f1.aniso.values(), cell))
    assert np.allclose(s3._pin_axes(values, -vectors, basis),
                       s3._pin_axes(values, vectors, basis), rtol=0, atol=0)
    assert np.allclose(np.abs(s3._pin_axes(values, vectors, basis)), np.abs(vectors),
                       rtol=0, atol=0)


def test_the_payload_draws_the_same_ellipsoids_whatever_eigh_returned(nac, monkeypatch):
    """The tests above hold ``_pin_axes`` to one answer; this one holds the
    payload to it. Every image of every NAC site is built again under an
    ``eigh`` that flips every column and turns every equal pair, which is what
    another LAPACK may do. Four of the six sites have such a pair."""
    want = [atom["ellipsoid"] for atom in s3.build(nac)["atoms"]]
    eigh = np.linalg.eigh

    def other_lapack(u):
        values, vectors = eigh(u)
        close = np.diff(values) < 1e-12 * np.abs(values).max()
        pair = [int(np.argmax(close)), int(np.argmax(close)) + 1] if close.any() else None
        return values, (_turned(vectors, pair, 0.7) if pair else -vectors)

    monkeypatch.setattr(np.linalg, "eigh", other_lapack)
    got = [atom["ellipsoid"] for atom in s3.build(nac)["atoms"]]
    assert np.allclose(got, want, rtol=0, atol=1e-12)


def test_an_images_rings_are_the_image_of_its_sites_rings(nac):
    """Each image's T is the site's pinned T turned by that image's Cartesian
    rotation, so equivalent atoms wear equivalent rings. Pinned image by image,
    NAC's images drew their free rings up to 60° from the site's, turned."""
    payload = s3.build(nac)
    phase = nac.phases[0]
    basis = s3.cartesian_basis(*phase.cell.lengths_angles())
    turns = [basis @ (np.array(op.rot, dtype=float) / op.DEN) @ np.linalg.inv(basis)
             for op in get_spacegroup(phase.space_group).operations()]
    for site in payload["sites"]:
        images = [np.array(a["ellipsoid"]) for a in payload["atoms"] if a["site"] == site["index"]]
        own = images[0]
        for image in images:
            assert any(np.allclose(image, turn @ own, rtol=0, atol=1e-12) for turn in turns)


def test_a_non_positive_definite_tensor_is_flagged_and_never_nan():
    """The ``ADP_NOT_POSITIVE_DEFINITE`` case, as geometry.

    A negative eigenvalue is not a large number, it is an impossible ellipsoid,
    and ``√(negative)`` is a NaN that loses the whole mesh rather than one atom.
    The semi-axis is drawn at **zero** instead — visibly flat, and the payload
    says so rather than leaving the shape to be interpreted.
    """
    bad = AnisoU.from_values([0.02, 0.02, -0.01, 0.0, 0.0, 0.0])
    structure = monoclinic(aniso=bad)
    payload = s3.build(structure)
    site = payload["sites"][0]
    assert site["npd"] is True
    assert "not positive definite" in payload["note"]

    for atom in payload["atoms"]:
        assert np.isfinite(atom["ellipsoid"]).all()
        assert np.isfinite(atom["rms"]).all()
    flagged = [a for a in payload["atoms"] if a["site"] == 0]
    assert all(a["npd"] for a in flagged)
    assert all(min(a["rms"]) == 0.0 for a in flagged)   # collapsed, not imaginary

    # the healthy site in the same structure is untouched
    assert payload["sites"][1]["npd"] is False


def test_the_probability_levels_are_the_ortep_numbers():
    assert s3.probability_scale(0.50) == pytest.approx(1.5382, abs=5e-5)
    assert s3.probability_scale(0.90) == pytest.approx(2.5003, abs=5e-5)
    levels = s3.build(monoclinic())["probability_levels"]
    assert set(levels) == {f"{p:g}" for p in s3.PROBABILITY_LEVELS}
    assert levels["0.5"] == pytest.approx(s3.probability_scale(0.5))
    with pytest.raises(ValueError):
        s3.probability_scale(1.0)


# ----------------------------------------------------------------------
# bonds
# ----------------------------------------------------------------------
def test_a_bond_that_leaves_the_cell_is_drawn_leaving_it(lab6):
    """Segments over the 27 nearest translations, not pairs inside the box.

    The B₆ octahedra of LaB6 are joined along the axes by B–B contacts that
    cross the cell faces; a viewer that only bonded atoms drawn inside would
    show six isolated octahedra and no framework.
    """
    payload = s3.build(lab6, bond_tolerance=1.05)
    assert payload["bonds"], "no B-B contact was found at all"
    # …and they are the real ones: B-B in LaB6 is 1.68 Å between octahedra and
    # 1.75 Å within one, and nothing else is that close
    assert {round(b["d"], 3) for b in payload["bonds"]} == {1.681, 1.752}
    corners = np.array(payload["corners"])
    lo, hi = corners.min(axis=0) - 1e-9, corners.max(axis=0) + 1e-9
    outside = [b for b in payload["bonds"]
               if np.any(np.array(b["b"]) < lo) or np.any(np.array(b["b"]) > hi)]
    assert outside, "every bond stayed inside the box; the translations did nothing"


def test_the_bond_threshold_is_a_control_and_the_payload_says_which(lab6):
    """A radius-sum slack is a drawing threshold, so it is reported, not implied.

    At 1.15 the La–B contact at 3.058 Å is inside 1.15·(2.07 + 0.84) and every
    lanthanum shows its 24-fold coordination; at 1.05 it is outside and only the
    boron framework survives.  Neither is wrong — which is the argument for the
    knob, and for echoing back the value the picture was drawn at.
    """
    loose = s3.build(lab6, bond_tolerance=1.15)
    tight = s3.build(lab6, bond_tolerance=1.05)
    assert loose["bond_tolerance"] == 1.15 and tight["bond_tolerance"] == 1.05
    assert len(loose["bonds"]) > len(tight["bonds"])
    assert 3.058 == pytest.approx(max(b["d"] for b in loose["bonds"]), abs=1e-3)
    assert 1.752 == pytest.approx(max(b["d"] for b in tight["bonds"]), abs=1e-3)


def test_a_metal_metal_contact_is_a_lattice_distance_unless_the_phase_is_an_alloy(lab6):
    """The rule that keeps a large cation from bonding to its own cell edges.

    gemmi's covalent radius for lanthanum is 2.07 Å against a = 4.158 Å, so a
    plain radius-sum rule draws all twelve cell edges as La–La sticks and the
    boron framework vanishes into a cage.  Suppressed because LaB6 contains a
    non-metal; in a phase that does not, the metal–metal contact is the only
    bond there is and the suppression lifts by itself.
    """
    payload = s3.build(lab6, bond_tolerance=1.3)
    assert payload["bond_metals"] is False
    a = payload["cell"][0]
    assert all(b["d"] < a for b in payload["bonds"])   # no bond is a cell edge

    assert s3.bonds_between_metals(["Fe"]) is True     # bcc iron: bond them
    assert s3.bonds_between_metals(["Ni", "Al"]) is True
    assert s3.bonds_between_metals(["La", "B"]) is False
    assert s3.bonds_between_metals(["Na", "Ca", "Al", "F"]) is False


def test_an_atom_is_never_bonded_to_its_own_boundary_duplicate(lab6):
    """The corner atom is drawn eight times; a zero-length stick between two of
    those copies would be a bond to itself."""
    payload = s3.build(lab6, bond_tolerance=1.15)
    assert all(b["d"] >= s3.BOND_MIN for b in payload["bonds"])


# ----------------------------------------------------------------------
# species, colours, radii
# ----------------------------------------------------------------------
@pytest.mark.parametrize(("species", "element"), [
    ("La", "La"), ("La3+", "La"), ("O2-", "O"), ("o", "O"), ("FE", "Fe"),
    ("D", "D"), ("Xx", "X"), ("", "X"),
])
def test_a_species_resolves_to_its_element(species, element):
    """Charge is a scattering detail; radius and colour are the element's.

    gemmi's own ``Element("O2-")`` answers ``X``, which is why the charge comes
    off here first — an oxygen drawn in the unknown-element grey is a viewer
    quietly disagreeing with the parameter table about what the atom is.
    """
    assert s3.element_symbol(species) == element


def test_colours_are_cpk_where_the_convention_names_one_and_derived_elsewhere():
    assert s3.element_color("O") == s3._CPK["O"]
    assert s3.element_color("C") == s3._CPK["C"]
    # nothing names lanthanum, so it is derived — stable, and not the fallback grey
    derived = s3.element_color("La")
    assert derived == s3.element_color("La")
    assert derived.startswith("#") and len(derived) == 7
    assert derived != s3.element_color("Ce")
    # WP-1029: it was `#909090`, which is *exactly* titanium's entry — so an
    # unparseable species was drawn as titanium and a picture of a typo looked
    # like a picture of a structure
    assert s3.element_color("X") == s3.UNKNOWN_COLOR
    assert s3.UNKNOWN_COLOR not in s3._CPK.values()


def test_colours_are_separated_within_the_phase_being_drawn():
    """WP-1029: distinguishability is a property of the *set*, not of the table.

    The three pairs a user reported are the fixture, with the distances that
    made them collisions measured rather than asserted as "too close".
    """
    for one, two, before in [("F", "Ca", 0.070), ("Si", "Cl", 0.078),
                             ("Na", "La", 0.099)]:
        alone = s3._oklab_distance(s3._oklab(s3.element_color(one)),
                                   s3._oklab(s3.element_color(two)))
        assert alone == pytest.approx(before, abs=5e-4)
        assert alone < s3.MIN_SEPARATION            # …which is why they collide

        palette = s3.phase_palette([one, two])
        together = s3._oklab_distance(s3._oklab(palette[one]),
                                      s3._oklab(palette[two]))
        assert together >= s3.MIN_SEPARATION

    # a chosen colour outranks a derived one when something must move: Na keeps
    # its purple and lanthanum, whose hue was chosen for nobody, is what shifts
    palette = s3.phase_palette(["Na", "La"])
    assert palette["Na"] == s3._CPK["Na"]
    assert palette["La"] != s3.element_color("La")

    # anchors never move, whatever else is in the phase
    for element, colour in s3.phase_palette(["O", "N", "C", "S", "F", "Cl"]).items():
        assert colour == s3.element_color(element)

    # and the palette is a function of the phase, not of when it was asked for
    assert s3.phase_palette(["Na", "Ca", "Al", "F"]) == s3.phase_palette(["F", "Al", "Ca", "Na"])


@pytest.mark.parametrize("cif", sorted(p.name for p in DATA.glob("*.cif")))
def test_every_bundled_phase_is_drawn_in_colours_that_can_be_told_apart(cif):
    """The bar the WP set: no two species of one real phase within MIN_SEPARATION.

    Collected from ``tests/data`` rather than from a hand-written element list,
    because the collision that prompted this — F against Ca, both in NAC — was
    found by *looking at* a structure and not by reading the table.  A CIF added
    to the data directory is covered without anyone remembering to add it.
    """
    try:
        structure = structure_from_cif(str(DATA / cif))
    except (RuntimeError, ValueError) as exc:   # a pdCIF, not a structure CIF
        # WP-1328 gave the reader `io/CLAUDE.md`'s refusal shape — a
        # ValueError naming the file — where gemmi's bare `RuntimeError`
        # used to escape, so this skip matches on the *sentence* rather than
        # on the class: any other ValueError here is a structure CIF this
        # test must not pass over in silence.
        if "single data block expected" not in str(exc):
            raise
        pytest.skip(f"{cif} is not a single-block structure file: {exc}")
    payload = s3.build(structure, phase=0)
    colours = {site["element"]: site["color"] for site in payload["sites"]}
    labs = {element: s3._oklab(colour) for element, colour in colours.items()}
    elements = sorted(labs)
    for i, one in enumerate(elements):
        for two in elements[i + 1:]:
            gap = s3._oklab_distance(labs[one], labs[two])
            assert gap >= s3.MIN_SEPARATION, f"{cif}: {one} {colours[one]} vs {two} {colours[two]}"


def test_the_payload_carries_the_paths_the_parameter_table_owns(lab6):
    """A click on an atom must reach the row that already exists for it."""
    payload = s3.build(lab6, phase=0)
    assert [site["path"] for site in payload["sites"]] == [
        "phases.0.atoms.0", "phases.0.atoms.1"]
    assert payload["phases"] == [lab6.phases[0].name]


def test_the_ball_radius_is_quoted_and_leaves_room_for_a_stick(lab6):
    """The drawing constants are the payload's, not the client's own opinion.

    ``ball_fraction`` is echoed rather than assumed because the caption under the
    picture states it, and a client that hard-coded it would eventually state a
    number the balls were not drawn at.  Bounded on both sides: balls of a
    *bonded* pair cannot merge (their contact is at 0.4·(r_i+r_j), well inside
    the 1.15 cutoff), and even hydrogen keeps a ball wider than the 0.08 Å stick
    the client draws — or the smallest atom there is would be a lump on a rod.
    """
    payload = s3.build(lab6, phase=0)
    assert payload["ball_fraction"] == s3.BALL_FRACTION
    assert s3.BALL_FRACTION < payload["bond_tolerance"]
    assert s3.BALL_FRACTION * s3.element_radius("H") > 0.08


def test_a_phase_that_is_not_there_is_an_index_error(lab6):
    with pytest.raises(IndexError):
        s3.build(lab6, phase=3)


def test_a_cell_larger_than_the_viewer_draws_says_so(nac):
    payload = s3.build(nac, max_atoms=20)
    assert len(payload["atoms"]) == 20
    assert "trimmed to 20" in payload["note"]


def test_every_bond_ends_on_an_atom_that_is_drawn(lab6):
    """Found by looking at the picture, not at the payload.

    A bond to a translated image is *correct* and reads as broken — the eye sees
    a stick going into empty space — so each out-of-cell endpoint gets its atom
    drawn.  Exactly one level: completing those atoms' bonds in turn would be
    the packing diagram this WP declines to build.
    """
    payload = s3.build(lab6, bond_tolerance=1.05)
    drawn = {tuple(round(v, 6) for v in atom["pos"]) for atom in payload["atoms"]}
    for bond in payload["bonds"]:
        assert tuple(round(v, 6) for v in bond["a"]) in drawn
        assert tuple(round(v, 6) for v in bond["b"]) in drawn

    # they are images, so they do not enter the multiplicity count…
    real = [a for a in payload["atoms"] if not a["boundary"]]
    assert len(real) == sum(s["multiplicity"] for s in payload["sites"])
    # …and each carries its source's tensor unchanged, a translation being a
    # translation, with the fractional coordinate that says which image it is
    outside = [a for a in payload["atoms"] if a["boundary"] and min(a["frac"]) < 0]
    assert outside
    for atom in outside:
        assert all(math.isfinite(v) for v in atom["frac"])
        source = next(a for a in real if a["site"] == atom["site"])
        assert atom["rms"] == source["rms"]

    # the cap counts them: a cell that fills up says so rather than truncating
    small = s3.build(lab6, bond_tolerance=1.15, max_atoms=20)
    assert len(small["atoms"]) == 20
    assert "end in mid-air" in small["note"]


# ----------------------------------------------------------------------
# coordination polyhedra (WP-1466)
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def fap():
    """Hexagonal P6₃/m: PO₄ tetrahedra, and two Ca sites with no clear gap."""
    return structure_from_cif(str(DATA / "fluorapatite.cif"))


def brucite() -> Structure:
    """Mg(OH)₂, P-3m1, from textbook coordinates: MgO₆ with H 2.68 Å from Mg."""
    cell = Cell(a=_p(3.147), b=_p(3.147), c=_p(4.770),
                alpha=_p(90.0), beta=_p(90.0), gamma=_p(120.0))
    atoms = [Atom(label="Mg1", species="Mg", x=_p(0.0), y=_p(0.0), z=_p(0.0)),
             Atom(label="O1", species="O", x=_p(1 / 3), y=_p(2 / 3), z=_p(0.2203)),
             Atom(label="H1", species="H", x=_p(1 / 3), y=_p(2 / 3), z=_p(0.4130))]
    return Structure(phases=[Phase(name="brucite", space_group="P -3 m 1",
                                   cell=cell, atoms=atoms)])


#: a tetrahedron's four corners at 1.6 Å, the Si–O distance
TETRAHEDRON = [1.6 * np.array(v) / math.sqrt(3.0)
               for v in ((1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1))]


def cluster(centre, ligands, side: float = 12.0) -> Structure:
    """``(species, occ)`` pairs at the centre and ``(species, offset Å, occ)``
    around it, alone in a P1 cell of ``side`` Å.

    Built rather than read, because each test needs one shell with one defect
    in it: at 12 Å the nearest translated ligand is 8.8 Å from the centre,
    beyond the window of a centre whose ligands sit at 2.1 Å or less
    (:data:`~rietx.gui.structure3d.SHELL_REACH`).
    """
    cell = Cell(a=_p(side), b=_p(side), c=_p(side),
                alpha=_p(90.0), beta=_p(90.0), gamma=_p(90.0))
    atoms = [Atom(label=f"{species}0{k}", species=species, x=_p(0.5), y=_p(0.5),
                  z=_p(0.5), occ=_p(occ)) for k, (species, occ) in enumerate(centre)]
    for k, (species, offset, occ) in enumerate(ligands):
        x, y, z = 0.5 + np.asarray(offset, dtype=float) / side
        atoms.append(Atom(label=f"{species}{k + 1}", species=species,
                          x=_p(x), y=_p(y), z=_p(z), occ=_p(occ)))
    return Structure(phases=[Phase(name="cluster", space_group="P 1",
                                   cell=cell, atoms=atoms)])


def _drawn(payload: dict) -> dict:
    """``{(site label, coordination, drawn by default): count}``."""
    out: dict = {}
    for p in payload["polyhedra"]:
        key = (payload["sites"][p["site"]]["label"], p["coordination"],
               p["drawn_by_default"])
        out[key] = out.get(key, 0) + 1
    return out


@pytest.mark.parametrize(("center", "element", "ligand"), [
    ("P", "O", True), ("Al", "F", True), ("Ca", "F", True),
    ("P", "Ca", False),          # a metal is never a ligand
    ("O", "O", False),           # nor the centre's own element
    ("Mg", "H", False),          # nor hydrogen, which a hydroxide's cation reaches
    ("Mg", "D", False),
])
def test_a_ligand_is_a_non_metal_of_another_element_other_than_hydrogen(center, element,
                                                                        ligand):
    assert s3.is_ligand(center, element) is ligand


def test_the_shell_ends_at_the_largest_gap_of_the_whole_sequence():
    """P3, as Brunner & Schwarzenbach (1971) judge a gap: the quotient of the
    two distances bounding it, the largest anywhere in the sequence."""
    # fluorapatite's P: four O, then Ca at 3.12 Å
    n, gap = s3.shell_gap([1.52, 1.52, 1.55, 1.58, 3.12, 3.59])
    assert (n, gap) == (4, pytest.approx(3.12 / 1.58))
    # LaB6's La: 24 B at one distance, then the next B 1.45 times further
    n, gap = s3.shell_gap([3.058] * 24 + [4.43, 4.43])
    assert (n, gap) == (24, pytest.approx(4.43 / 3.058))
    # one ligand or none is a shell with no gap
    assert s3.shell_gap([2.0]) == (1, 1.0)
    assert s3.shell_gap([]) == (0, 1.0)


def test_the_window_reaches_three_times_the_shortest_distance(lab6):
    """P3: CsCl's Cs has 8 Cl at 3.56 Å and the next at 6.8 Å, past the 6 Å
    the images first reach, so the orbit grows to the 10.7 Å window."""
    a = 4.115
    cell = Cell(a=_p(a), b=_p(a), c=_p(a), alpha=_p(90.0), beta=_p(90.0), gamma=_p(90.0))
    cscl = Structure(phases=[Phase(name="CsCl", space_group="P m -3 m", cell=cell, atoms=[
        Atom(label="Cs", species="Cs", x=_p(0.0), y=_p(0.0), z=_p(0.0)),
        Atom(label="Cl", species="Cl", x=_p(0.5), y=_p(0.5), z=_p(0.5))])])
    (p, *_) = s3.build(cscl)["polyhedra"]
    assert p["coordination"] == 8
    # the next Cl is at a·√11/2, so the gap is √11/√3
    assert p["gap"] == pytest.approx(math.sqrt(11 / 3))
    # LaB6's La: 24 B at one distance, a hidden shell of 24
    assert {q["coordination"] for q in s3.build(lab6)["polyhedra"]} == {24}


def test_the_default_picture_draws_tetrahedra_and_octahedra(lab6, nac, fap):
    """P5 on WP-1462's three phases: PO₄ and AlF₆ drawn, the larger shells hidden.

    Fluorapatite's Ca sites are CaO₉ and CaO₆F, and LaB6's La has 24 B at one
    distance, a shell too large to draw by default.
    """
    assert _drawn(s3.build(lab6)) == {("La", 24, False): 8}
    assert _drawn(s3.build(nac)) == {("Al1", 6, True): 8, ("Ca1", 8, False): 18,
                                     ("Na1", 7, False): 8}
    assert _drawn(s3.build(fap)) == {("P3", 4, True): 6, ("Ca1", 9, False): 4,
                                     ("Ca2", 7, False): 6}


def test_a_split_partner_makes_no_cation(fap):
    """P10: hydroxyfluorapatite's OH oxygen, 0.43 Å from a half-occupied F, is
    one channel position split two ways, so the F does not make it a cation.

    Above :data:`~rietx.gui.structure3d.BOND_MIN`, it had: the O left every Ca
    shell and lost its Ca sticks.
    """
    c = 6.8859
    phase = fap.phases[0]
    (fluorine,) = [a for a in phase.atoms if a.species == "F"]
    fluorine.occ = Parameter(value=0.5)
    phase.atoms.append(Atom(label="O8", species="O", x=_p(0.0), y=_p(0.0),
                            z=_p(0.25 - 0.43 / c), occ=_p(0.25)))
    payload = s3.build(fap)
    elements = [payload["sites"][a["site"]]["element"] for a in payload["atoms"]]
    oxygen = {k for k, a in enumerate(payload["atoms"])
              if payload["sites"][a["site"]]["label"] == "O8"}
    pairs = {tuple(sorted((elements[b["i"]], elements[b["j"]])))
             for b in payload["bonds"] if b["i"] in oxygen or b["j"] in oxygen}
    # the O keeps its Ca, and no stick joins the split positions
    assert pairs == {("Ca", "O")}


def test_no_stick_joins_two_non_metals_closer_than_the_split_floor():
    """P10 on the measured phases: high cristobalite's split O positions,
    0.45-0.90 Å apart, drew O–O sticks until the floor."""
    for row in MEASURED:
        payload = s3.build(measured(row))
        pairs = []
        for b in payload["bonds"]:
            i, j = (payload["sites"][payload["atoms"][k]["site"]] for k in (b["i"], b["j"]))
            pairs.append((i["element"], j["element"]))
            if not (i["metal"] or j["metal"]):
                assert b["d"] >= s3.SPLIT_FLOOR * (i["radius"] + j["radius"]), row["name"]
        # read without the constant, which a broken floor would carry with it
        if row["name"].startswith("high cristobalite"):
            assert ("O", "O") not in pairs


def test_the_split_floor_spares_a_metal_oxo_bond():
    """P10 holds only between non-metals: uranyl's U=O is 0.67 of the radius sum."""
    payload = s3.build(cluster([("U", 1.0)], [("O", (1.76, 0, 0), 1.0),
                                              ("O", (-1.76, 0, 0), 1.0)]))
    assert sorted(round(b["d"], 2) for b in payload["bonds"]) == [1.76, 1.76]


def test_a_non_metal_bonded_to_a_stronger_one_is_a_cation_and_no_ligand():
    """P2: Si bonded to O is a cation, so it is never a corner of Mg's octahedron.

    As in forsterite, the Si sits 2.69 Å from Mg across an edge of MgO₆.
    Counted as a ligand, it would join a shell of seven.
    """
    x, y, z = np.eye(3) * 2.10
    silicon = 2.69 * np.array([1.0, 1.0, 0.0]) / math.sqrt(2.0)
    payload = s3.build(cluster([("Mg", 1.0)], [*[("O", v, 1.0) for v in (x, -x, y, -y, z, -z)],
                                               ("Si", silicon, 1.0)]))
    (only,) = payload["polyhedra"]
    assert only["coordination"] == 6
    assert {payload["sites"][payload["atoms"][v]["site"]]["element"]
            for v in only["vertices"]} == {"O"}


def test_an_anion_is_never_a_centre():
    """P2: an F among six O draws no FO₆, as fluorapatite's F4 nearly did.

    O is a non-metal of another element, so only the centre half of the rule
    turns the shell away.  An O among four SiO₄ groups draws no OSi₄ either,
    as andalusite's OA did: each Si is bonded to an O of its own.
    """
    x, y, z = np.eye(3) * 3.13
    fluorine = cluster([("F", 1.0)], [("O", v, 1.0) for v in (x, -x, y, -y, z, -z)])
    assert s3.build(fluorine)["polyhedra"] == []
    ligands = []
    for corner in TETRAHEDRON:
        outward = corner / np.linalg.norm(corner)
        ligands += [("Si", 3.0 * outward, 1.0), ("O", 4.6 * outward, 1.0)]
    assert s3.build(cluster([("O", 1.0)], ligands))["polyhedra"] == []


def test_a_metal_and_a_cation_share_no_stick():
    """The metal–metal rule widened to metal–cation (WP-1466).

    Forsterite drew 36 Mg–Si sticks at 2.69-2.79 Å, and they crossed the MgO₆
    faces.  Two cationic non-metals keep theirs: a C bonded to O is a cation
    and so is the H on it, and an organic without C–H sticks is no picture.
    """
    def pairs(payload: dict) -> set[frozenset]:
        element = lambda i: payload["sites"][payload["atoms"][i]["site"]]["element"]  # noqa: E731
        return {frozenset((element(b["i"]), element(b["j"]))) for b in payload["bonds"]}

    row = next(r for r in MEASURED if r["name"] == "olivine forsterite")
    forsterite = pairs(s3.build(measured(row)))
    assert frozenset(("Mg", "Si")) not in forsterite
    assert {frozenset(("Mg", "O")), frozenset(("O", "Si"))} <= forsterite

    formate = pairs(s3.build(cluster([("C", 1.0)], [
        ("O", (1.25, 0.0, 0.0), 1.0), ("H", (-0.6, 0.9, 0.0), 1.0),
        # 2.6 Å, inside the radius-sum cutoff of 2.90
        ("Ca", (0.0, 0.0, 2.6), 1.0)])))
    assert {frozenset(("C", "O")), frozenset(("C", "H"))} <= formate
    assert frozenset(("C", "Ca")) not in formate


def test_a_shell_with_no_clear_gap_is_not_a_polyhedron():
    """P4: shells of six O every 1.10 times the last, from 2.0 Å to past the
    6.0 Å window, so no gap reaches 1.15."""
    octahedron = [*np.eye(3), *-np.eye(3)]
    ligands = [("O", v * 2.0 * 1.1 ** k, 1.0) for k in range(13) for v in octahedron]
    payload = s3.build(cluster([("Al", 1.0)], ligands, side=30.0))
    assert payload["polyhedra"] == []


#: WP-1466's measured phase set, written by ``docs/wp/1466-measure/measure.py``
#: with the picture a chemist draws first beside each phase
MEASURED = json.loads((DATA / "polyhedra_phases.json").read_text(encoding="utf-8"))


def measured(row: dict) -> Structure:
    a, b, c, alpha, beta, gamma = row["cell"]
    cell = Cell(a=_p(a), b=_p(b), c=_p(c), alpha=_p(alpha), beta=_p(beta), gamma=_p(gamma))
    atoms = [Atom(label=label, species=species, x=_p(x), y=_p(y), z=_p(z), occ=_p(occ))
             for label, species, x, y, z, occ in row["atoms"]]
    return Structure(phases=[Phase(name=row["name"], space_group=row["space_group"],
                                   symmetry_operations=row["symmetry_operations"],
                                   cell=cell, atoms=atoms)])


@pytest.mark.parametrize("row", MEASURED, ids=[row["name"] for row in MEASURED])
def test_the_default_picture_on_the_measured_phases(row):
    """Acceptance 1: each phase draws what its row expects by default, and no more."""
    drawn: dict[str, set[int]] = {}
    payload = s3.build(measured(row))
    for p in payload["polyhedra"]:
        if p["drawn_by_default"]:
            element = payload["sites"][p["site"]]["element"]
            drawn.setdefault(element, set()).add(p["coordination"])
    assert {e: sorted(v) for e, v in drawn.items()} == row["expected"]
    _every_polyhedron_is_one(payload)


@pytest.mark.parametrize("name", ["nac", "fap", "brucite"])
def test_every_drawn_polyhedron_is_one(name, nac, fap):
    """P4, checked from the payload alone, as a client would draw it."""
    structure = {"nac": nac, "fap": fap, "brucite": brucite()}[name]
    payload = s3.build(structure)
    assert payload["polyhedra"]
    _every_polyhedron_is_one(payload)


def _every_polyhedron_is_one(payload: dict) -> None:
    atoms = payload["atoms"]
    for p in payload["polyhedra"]:
        centre = np.array(atoms[p["center"]]["pos"])
        element = payload["sites"][p["site"]]["element"]
        vertices = np.array([atoms[v]["pos"] for v in p["vertices"]])
        assert len(set(p["vertices"])) == len(vertices) == p["coordination"] >= 4
        assert p["gap"] >= s3.POLYHEDRON_GAP
        for v in p["vertices"]:
            assert s3.is_ligand(element, payload["sites"][atoms[v]["site"]]["element"])
        distance = np.linalg.norm(vertices - centre, axis=1)
        assert p["mean_distance"] == pytest.approx(distance.mean())
        # every ligand at a vertex, and every face wound outward with the
        # whole shell behind it and the centre strictly inside
        assert {v for face in p["faces"] for v in face} == set(range(len(vertices)))
        for face in p["faces"]:
            a, b, c = vertices[face]
            normal = np.cross(b - a, c - a)
            normal /= np.linalg.norm(normal)
            assert ((vertices - a) @ normal <= 1e-9).all()
            assert (centre - a) @ normal < -s3.INSIDE_TOL
        # an edge is a side of some face
        sides = {tuple(sorted((f[i], f[(i + 1) % 3]))) for f in p["faces"] for i in range(3)}
        assert {tuple(e) for e in p["edges"]} <= sides


def test_a_polyhedron_is_never_cut_off(nac):
    """P7: a vertex outside the cell is drawn, as an image flagged ``boundary``."""
    payload = s3.build(nac)
    atoms = payload["atoms"]
    outside = {v for p in payload["polyhedra"] for v in p["vertices"]
               if min(atoms[v]["frac"]) < -s3.BOUNDARY_TOL
               or max(atoms[v]["frac"]) > 1 + s3.BOUNDARY_TOL}
    assert outside
    assert all(atoms[v]["boundary"] for v in outside)

    # one that would take the drawing past the atom cap is not drawn, and says so
    full = len(payload["polyhedra"])
    small = s3.build(nac, max_atoms=175)
    assert len(small["atoms"]) <= 175
    assert 0 < len(small["polyhedra"]) < full
    assert f"{full - len(small['polyhedra'])} coordination polyhedra not drawn" in small["note"]
    for p in small["polyhedra"]:
        assert max(p["vertices"]) < len(small["atoms"])


def test_the_centres_sticks_give_way_to_its_polyhedron(nac):
    """P6: exactly the sticks between a centre and its own vertices are listed.

    Na is where the bond rule and the gap disagree: 4 sticks, 7 vertices.
    """
    payload = s3.build(nac)
    atoms, bonds = payload["atoms"], payload["bonds"]
    key = lambda pos: tuple(np.round(pos, 6))                      # noqa: E731
    for p in payload["polyhedra"]:
        ends = {frozenset((key(atoms[p["center"]]["pos"]), key(atoms[v]["pos"])))
                for v in p["vertices"]}
        listed = {k for k, b in enumerate(bonds)
                  if frozenset((key(b["a"]), key(b["b"]))) in ends}
        assert set(p["bonds"]) == listed
    na = next(p for p in payload["polyhedra"]
              if payload["sites"][p["site"]]["label"] == "Na1")
    assert (len(na["bonds"]), na["coordination"]) == (4, 7)


def test_hydrogen_never_joins_a_hydroxides_shell():
    """Counted as a ligand, brucite's 6 H at 2.68 Å would cut Mg's gap to 1.28."""
    payload = s3.build(brucite())
    assert _drawn(payload) == {("Mg1", 6, True): 8}
    for p in payload["polyhedra"]:
        assert p["gap"] == pytest.approx(1.80, abs=0.01)
        assert {payload["sites"][payload["atoms"][v]["site"]]["element"]
                for v in p["vertices"]} == {"O"}


def test_a_split_site_draws_no_polyhedron_and_a_full_one_does():
    """P9: one corner of a tetrahedron split 0.3 Å across its bond.

    Both positions are hull vertices and the gap is clear, so only the split
    rule turns the shell away. At full occupancy it is a real five-vertex
    shell and is drawn.
    """
    across = 0.15 * np.array([1.0, -1.0, 0.0]) / math.sqrt(2.0)
    corners = [TETRAHEDRON[0] + across, TETRAHEDRON[0] - across, *TETRAHEDRON[1:]]

    def shell(occ):
        return [("O", v, occ if k < 2 else 1.0) for k, v in enumerate(corners)]

    assert s3.build(cluster([("Si", 1.0)], shell(0.5)))["polyhedra"] == []
    (whole,) = s3.build(cluster([("Si", 1.0)], shell(1.0)))["polyhedra"]
    assert whole["coordination"] == 5


def test_a_mixed_site_counts_once_as_centre_and_as_ligand():
    """P9: Si/Ge on the centre and O/F on one corner give one tetrahedron."""
    ligands = [("O", TETRAHEDRON[0], 0.5), ("F", TETRAHEDRON[0], 0.5),
               *[("O", v, 1.0) for v in TETRAHEDRON[1:]]]
    payload = s3.build(cluster([("Si", 0.5), ("Ge", 0.5)], ligands))
    (only,) = payload["polyhedra"]
    assert payload["sites"][only["site"]]["element"] == "Si"
    assert only["coordination"] == 4


@pytest.mark.parametrize("shape", ["square", "one-sided", "centre on a face"])
def test_a_shell_the_centre_is_not_inside_is_not_a_polyhedron(shape):
    """P4: a planar shell has no hull, and a centre outside or on one is refused."""
    x, y, z = np.eye(3) * 1.95
    ligands = {
        "square": [x, -x, y, -y],
        # three low and one high, all at 1.95 Å and all above the centre
        "one-sided": [1.95 * np.array(v) / np.linalg.norm(v)
                      for v in ((1, 0, 0.3), (-0.5, 0.87, 0.3), (-0.5, -0.87, 0.3), (0, 0, 1))],
        "centre on a face": [x, -x, y, -y, z],
    }[shape]
    payload = s3.build(cluster([("Cu", 1.0)], [("O", v, 1.0) for v in ligands]))
    assert payload["polyhedra"] == []


def test_a_shell_enclosing_one_of_its_own_ligands_is_not_a_polyhedron():
    """P4, Daams & Villars' convex-volume condition: every ligand at a vertex.

    An octahedron at 2.0 Å with a seventh ligand at 1.9 Å on one vertex's
    ray. The gap after all seven is clear and the centre is inside, so only
    the vertex condition turns it away.
    """
    x, y, z = np.eye(3) * 2.0
    octahedron = [x, -x, y, -y, z, -z]
    assert len(s3.build(cluster([("Al", 1.0)], [("F", v, 1.0) for v in octahedron]))
               ["polyhedra"]) == 1
    enclosed = [*octahedron, 0.95 * x]
    payload = s3.build(cluster([("Al", 1.0)], [("F", v, 1.0) for v in enclosed]))
    assert payload["polyhedra"] == []
