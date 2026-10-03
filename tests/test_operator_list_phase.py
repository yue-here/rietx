"""A phase that carries its own operator list (Q-17).

The claim under test is that a group **no Hermann-Mauguin symbol names in its
cell** can be stated, stored and compiled like any other,
and that stating one changes nothing for a phase that does not.  Four
properties carry it and each has its own group here:

* **exactly off.**  ``symmetry_operations=None`` is every phase written before
  the field existed, and a phase that declares the operation list of a *named*
  group predicts the identical pattern — pinned on ``predict()`` bit-for-bit,
  not on a tolerance, because the thing that would break it is a reordering of
  the structure-factor sum and a reordering is invisible to a tolerance.
* **the operations are the authority, not the label.**  Orbits, site
  multiplicities, systematic absences, reflection multiplicities and the cell
  ties all come out of the list; measured against the symbol over nine settings
  covering all seven crystal systems' constraint cases.
* **refuses rather than lies.**  A list that is not a group, a plain symbol
  that does not generate the list, and a bracketed label with no list are
  refusals with the reason in them.
* **the 29 unnamable isotropy subgroups.**  Every (group, k) case the all-group
  k-sweep could not name reaches ``candidates`` and comes back with a
  candidate carrying its operator list, and the child of the one real case —
  Ba₂FeSbSe₅'s S3(a,b) in 2a,b,a+c — is *built* rather than refused.
* **every consumer reads the list** — the CIF exporter included (review of
  #433, finding 3).

Nothing here needs a fit; the acceptance fit is in the report.
"""

from fractions import Fraction

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx.crystallography import symmetry as sym
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.operators import identification, identify
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import EmissionLine, Instrument, Source
from rietx.schemas.structure import Atom, Cell, Phase, Structure

#: The child nuclear group of Ba₂FeSbSe₅'s S3(a,b) superstructure in
#: 2a,b,a+c — **derived**, not copied: it is what
#: ``magnetic_supercell(nuclear_group="magnetic")`` (which lands with the moment
#: model, WP-1327) builds from the Pnma parent
#: at k = (½,0,½), and it is the shortest real example of the whole problem.
#: The (½,0,0) translation is the parent's own lattice vector (the nuclear
#: structure is still periodic on it) and the mirror carries a ½ along the
#: *undoubled* b, so no tabulated symbol has this list: ``P m 1 1`` times the
#: two lattice cosets omits two of these and adds two others.
S3_CHILD_OPS = ("x,y,z", "x+1/2,y,z", "x,-y+1/2,z", "x+1/2,-y+1/2,z")
S3_CHILD_LABEL = "Pm [unnamed in 2a,b,a+c]"

#: Every setting whose ``CellConstraints`` case is distinct, so the parity
#: check below covers each branch of ``cell_constraints`` rather than one.
SETTINGS = ("P n m a", "C m c m", "F d -3 m:2", "P 6_3/m m c", "R -3 c:H",
            "R -3 c:R", "P 1 21/m 1", "I 4_1/a m d:2", "P -1")

_CELLS = {
    "P n m a": (8.0, 6.0, 7.0, 90.0, 90.0, 90.0),
    "C m c m": (4.0, 11.0, 6.0, 90.0, 90.0, 90.0),
    "F d -3 m:2": (8.4, 8.4, 8.4, 90.0, 90.0, 90.0),
    "P 6_3/m m c": (5.0, 5.0, 8.0, 90.0, 90.0, 120.0),
    "R -3 c:H": (5.0, 5.0, 17.0, 90.0, 90.0, 120.0),
    "R -3 c:R": (6.4, 6.4, 6.4, 46.0, 46.0, 46.0),
    "P 1 21/m 1": (7.0, 6.0, 8.0, 90.0, 103.0, 90.0),
    "I 4_1/a m d:2": (5.8, 5.8, 9.4, 90.0, 90.0, 90.0),
    "P -1": (5.1, 6.2, 7.3, 88.0, 95.0, 101.0),
}

#: The two sites the sweep probes, verbatim from its own script: the origin,
#: and a general position with no accidental special relation in it.
SWEEP_SITES = {"origin": (Fraction(0), Fraction(0), Fraction(0)),
               "general": (Fraction(11, 100), Fraction(13, 100),
                           Fraction(17, 100))}

#: The **29** rows the all-group k-sweep (2744 rows over all 230 settings ×
#: k ∈ {0,½}³ × those two sites, 61 384 s, finished 2026-09-09) reported as
#: "unidentified candidate": spglib matches the isotropy subgroup's operator
#: list to none of the 1651 magnetic space groups.  Every one is a c- or
#: n-glide group doubled along the glide's own translation, which is the same
#: quarter-translation mechanism this module is about, one rung up (magnetic
#: rather than nuclear).  Transcribed row for row from the sweep's own summary
#: table, sites included, so the count here **is** 29 — 14 (setting, k) pairs
#: at both sites plus P6mm at the general site only, which is the one row the
#: sweep hit at one site and not the other.
SWEEP_UNNAMED = tuple(
    (setting, k, site)
    for setting, k in (
        ("P c c 2", ("1/2", "1/2", "0")),
        ("C m m 2", ("0", "0", "1/2")),
        ("P c c a", ("1/2", "1/2", "0")),
        ("P c c n", ("1/2", "1/2", "0")),
        ("P 42 c m", ("0", "0", "1/2")),
        ("P 42 c m", ("1/2", "1/2", "0")),
        ("P 42 n m", ("0", "0", "1/2")),
        ("P 4 c c", ("1/2", "1/2", "0")),
        ("P -4 c 2", ("1/2", "1/2", "0")),
        ("P 42/m c m", ("0", "0", "1/2")),
        ("P 42/n n m:1", ("0", "0", "1/2")),
        ("P 42/m n m", ("0", "0", "1/2")),
        ("P 42/n c m:1", ("0", "0", "1/2")),
        ("P n -3 m:1", ("0", "0", "1/2")),
    )
    for site in ("origin", "general")
) + (("P 6 m m", ("0", "0", "1/2"), "general"),)

INSTRUMENT = Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))
TWO_THETA = np.arange(5.0, 100.0, 0.02)


def _cell(values) -> Cell:
    a, b, c, al, be, ga = values
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=al), beta=Parameter(value=be),
                gamma=Parameter(value=ga))


def _atoms():
    return [
        Atom(label="Fe1", species="Fe", x=Parameter(value=0.1),
             y=Parameter(value=0.25), z=Parameter(value=0.3),
             occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
        Atom(label="O1", species="O", x=Parameter(value=0.33),
             y=Parameter(value=0.11), z=Parameter(value=0.62),
             occ=Parameter(value=1.0), biso=Parameter(value=0.8)),
    ]


def _phase(space_group, operations=None, cell=None):
    return Phase(name="p", space_group=space_group,
                 symmetry_operations=operations,
                 cell=_cell(cell or _CELLS.get(space_group, (7.0, 6.0, 8.0,
                                                             90.0, 97.0, 90.0))),
                 atoms=_atoms())


def _triplets(symbol) -> list[str]:
    return [op.triplet() for op in sym.get_spacegroup(symbol).operations()]


# ---------------------------------------------------------------------------
# exactly off
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("compiled_path", [False, True],
                         ids=["numpy", "compiled"])
@pytest.mark.parametrize("symbol", SETTINGS)
def test_the_explicit_list_of_a_named_group_predicts_bit_identically(
        symbol, compiled_path):
    """``predict()`` to the last bit, with and without the operation list.

    The property that makes the field additive, and the *only* test that can
    catch what would break it.  ``gemmi.GroupOps`` rebuilt from a flat
    operation list re-splits the group into coset representatives and picks
    different ones (measured on ``F d -3 m:2``: the 18th operation comes back
    as ``y,z,x`` where the table has ``y,z+1/2,x+1/2``, the same operation
    times a centring), so the orbit images — and with them the frozen
    operation subsets ``structure_factor.select_orbit_ops`` sums over — come
    out permuted.  A permuted sum of the same terms differs in the last bits of
    every intensity, which no tolerance-based assertion would see.

    Both sides run on one declared path, and on each of the two in turn
    (``tests/CLAUDE.md`` § Quoting numbers): the claim is the same list
    against the same symbol, so it must hold on the numpy builder and on the
    compiled tier alike.
    """
    from rietx.model import compiled

    bare = _phase(symbol)
    listed = _phase(symbol, _triplets(symbol))
    was = compiled.set_enabled(compiled_path)
    try:
        y_bare = rx.Refinement(Structure(phases=[bare]),
                               INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
        y_listed = rx.Refinement(Structure(phases=[listed]),
                                 INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    finally:
        compiled.set_enabled(was)
    assert np.array_equal(np.asarray(y_bare), np.asarray(y_listed))
    assert float(np.max(np.abs(np.asarray(y_bare) - np.asarray(y_listed)))) == 0.0


def test_a_phase_without_the_field_stores_none_and_resolves_the_symbol():
    """The default is exactly the old object: ``None``, and the symbol resolves."""
    phase = _phase("P n m a")
    assert phase.symmetry_operations is None
    group = sym.resolve_group(phase.space_group, phase.symmetry_operations)
    assert isinstance(group, gemmi.SpaceGroup)
    assert group.xhm() == "P n m a"


# ---------------------------------------------------------------------------
# the operations are the authority
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("symbol", SETTINGS)
def test_orbits_absences_and_cell_ties_come_out_of_the_list(symbol):
    """Every symmetry answer is the symbol's when the list is the symbol's.

    The nine settings exist to cover every distinct ``cell_constraints``
    branch (cubic, tetragonal, hexagonal, both trigonal axis choices,
    monoclinic, triclinic, orthorhombic primitive and C-centred), because the
    metric constraints of an unnamed group are the one thing that cannot be
    read off the operation list directly and go through
    :attr:`OperatorGroup.closest_type` instead.
    """
    sg = sym.get_spacegroup(symbol)
    og = sym.OperatorGroup(label=f"{symbol} [explicit]", xyz=tuple(_triplets(symbol)))
    cell = _CELLS[symbol]

    a = sym.generate_reflections(sg, cell, 1.5406, 90.0)
    b = sym.generate_reflections(og, cell, 1.5406, 90.0)
    assert np.array_equal(a.hkl, b.hkl)
    assert np.array_equal(a.multiplicity, b.multiplicity)
    assert np.array_equal(a.d, b.d)

    for xyz in ((0.1234, 0.25, 0.5678), (0.0, 0.0, 0.0), (0.5, 0.0, 0.25)):
        x = np.array(xyz)
        assert np.array_equal(sym.expand_positions(sg, x),
                              sym.expand_positions(og, x))
        assert (sym.site_orbit(sg, x).multiplicity
                == sym.site_orbit(og, x).multiplicity)

    assert sym.cell_constraints(sg) == sym.cell_constraints(og)
    assert sym.free_cell_names(sg) == sym.free_cell_names(og)
    assert np.array_equal(sym.rotation_matrices(sg), sym.rotation_matrices(og))
    assert np.array_equal(sym.reflection_orbits(sg, a.hkl[:12])[0],
                          sym.reflection_orbits(og, a.hkl[:12])[0])


def test_the_closest_type_of_a_group_no_symbol_names():
    """A half-translation is no Bravais centring, and the point group answers.

    The real S3(a,b) child.  Its (½,0,0) is the parent's lattice vector, which
    gemmi reads as a centring it has no letter for, so the symmorphic lookup
    returns nothing; the fallback — the bare point group on a P lattice —
    resolves it as ``P 1 m 1``, monoclinic with unique axis b, which is what
    the child cell 2a,b,a+c is.  The constraints that follow are the ones the
    cell needs: α and γ held at 90°, β free, no length tied.
    """
    og = sym.OperatorGroup(label=S3_CHILD_LABEL, xyz=S3_CHILD_OPS)
    assert og.closest_type.xhm() == "P 1 m 1"
    assert og.crystal_system_str() == "monoclinic"
    assert og.monoclinic_unique_axis() == "b"
    constraints = sym.cell_constraints(og)
    assert constraints.ties == {}
    assert constraints.fixed_angles == {"alpha": 90.0, "gamma": 90.0}
    assert sym.free_cell_names(og) == ("a", "b", "c", "beta")


def test_no_hermann_mauguin_symbol_generates_the_child_list():
    """The premise, asserted rather than argued.

    Every setting of every group in gemmi's table is tried, and none of them
    generates this operation list.  If a future gemmi table did hold one, this
    test fails and the whole bracketed-label mechanism becomes unnecessary for
    this case — which is the direction the failure should point.
    """
    wanted = {(tuple(int(v) for row in op.rot for v in row),
               tuple(int(v) % op.DEN for v in op.tran))
              for op in (gemmi.Op(s) for s in S3_CHILD_OPS)}
    for sg in gemmi.spacegroup_table():
        got = {(tuple(int(v) for row in op.rot for v in row),
                tuple(int(v) % op.DEN for v in op.tran))
               for op in sg.operations()}
        assert got != wanted, sg.xhm()


def test_the_label_convention_round_trips():
    assert sym.split_group_label(S3_CHILD_LABEL) == ("Pm", "unnamed in 2a,b,a+c")
    assert sym.split_group_label("P n m a") is None
    assert sym.unnamed_label("Pm", "unnamed in 2a,b,a+c") == S3_CHILD_LABEL
    assert sym.split_group_label(sym.unnamed_label(None, "no closest type")) \
        == ("", "no closest type")


# ---------------------------------------------------------------------------
# storage: JSON
# ---------------------------------------------------------------------------
def test_the_operation_list_survives_a_json_round_trip_bit_identically():
    phase = _phase(S3_CHILD_LABEL, list(S3_CHILD_OPS))
    text = phase.model_dump_json()
    back = Phase.model_validate_json(text)
    assert back.model_dump_json() == text
    assert tuple(back.symmetry_operations) == S3_CHILD_OPS
    assert back.space_group == S3_CHILD_LABEL


def test_any_spelling_of_an_operation_stores_canonically():
    """Two callers who wrote the same group differently store one document."""
    phase = _phase(S3_CHILD_LABEL,
                   [" X , Y , Z ", "x+1/2,y,z", "x,-y+1/2,z", "x+3/2,-y+1/2,z"])
    assert tuple(phase.symmetry_operations) == S3_CHILD_OPS


def test_a_repeated_operation_is_stored_once():
    phase = _phase(S3_CHILD_LABEL, list(S3_CHILD_OPS) + ["x,y,z"])
    assert tuple(phase.symmetry_operations) == S3_CHILD_OPS


# ---------------------------------------------------------------------------
# refuses rather than lies
# ---------------------------------------------------------------------------
def test_a_list_that_disagrees_with_a_plain_symbol_is_refused():
    with pytest.raises(ValueError, match="not the same group"):
        _phase("P n m a", ["x,y,z", "-x,y,-z"])


def test_the_same_list_is_accepted_once_the_label_is_bracketed():
    """The refusal above is about the *claim*, and bracketing withdraws it."""
    phase = _phase("P 1 2 1 [unnamed in this cell]", ["x,y,z", "-x,y,-z"])
    assert tuple(phase.symmetry_operations) == ("x,y,z", "-x,y,-z")


def test_a_bracketed_label_without_the_list_is_refused():
    with pytest.raises(ValueError, match="nothing is left to be the group"):
        _phase(S3_CHILD_LABEL)


def test_a_list_missing_the_identity_is_refused():
    with pytest.raises(ValueError, match="identity 'x,y,z' is not one of them"):
        _phase("P 1 [unnamed]", ["-x,y,z"])


def test_a_list_that_is_not_closed_under_composition_is_refused():
    with pytest.raises(ValueError, match="not closed under composition"):
        _phase("P 1 [unnamed]", ["x,y,z", "-x,y,z", "x,-y+1/3,z"])


def test_an_empty_list_is_refused_and_none_is_the_way_off():
    with pytest.raises(ValueError, match="empty list"):
        _phase("P n m a", [])


def test_an_unparsable_operation_is_refused_by_name():
    with pytest.raises(ValueError, match="not an 'x,y,z'-style symmetry operation"):
        _phase("P 1 [unnamed]", ["x,y,z", "q,y,z"])


def test_a_label_that_is_neither_a_symbol_nor_bracketed_is_refused():
    with pytest.raises(ValueError, match="neither a symbol this package resolves"):
        _phase("Zork", ["x,y,z"])


def test_the_closure_check_runs_once_per_list_not_once_per_assignment():
    """``validate_assignment`` reruns the check on every field write; the
    answer is a function of the list and the symbol alone, so it is cached."""
    from rietx.schemas.structure import _operation_list_refusal

    phase = _phase("F d -3 m:2 [explicit]", _triplets("F d -3 m:2"),
                   _CELLS["F d -3 m:2"])
    before = _operation_list_refusal.cache_info()
    for i in range(5):
        phase.name = f"p{i}"
    after = _operation_list_refusal.cache_info()
    assert after.misses == before.misses
    assert after.hits == before.hits + 5


# ---------------------------------------------------------------------------
# identify(): a result instead of a refusal
# ---------------------------------------------------------------------------
def test_identification_names_a_database_group_and_agrees_with_identify():
    from rietx.crystallography.magnetic.operators import magnetic_group

    group = magnetic_group("136.499")
    result = identification(group)
    assert result.named is True
    assert result.group_id is not None
    assert result.group_id.bns_number == "136.499"
    assert result.bns_number == "136.499"
    assert result.group_id == identify(group)
    assert result.reason == ""
    assert len(result.operations) == len(group.all_operations())


def test_identification_returns_a_result_where_identify_still_raises():
    """UNI 283 is the database entry spglib cannot match to itself.

    ``identify`` keeps raising there — it is the strict form, and the two tests
    that pin its message are unchanged — while ``identification`` answers with
    ``named=False``, the operator list, the closest nuclear type and the
    reason.  That is what lets ``candidates`` and ``magnetic_supercell``
    proceed instead of dropping the case.
    """
    from rietx.crystallography.magnetic.operators import magnetic_group

    group = magnetic_group(283)
    with pytest.raises(ValueError, match="did not match"):
        identify(group)
    result = identification(group)
    assert result.named is False
    assert result.group_id is None
    assert result.bns_number == "unnamed"
    assert "did not match" in result.reason
    assert len(result.operations) == len(group.all_operations())
    assert result.closest_type


# ---------------------------------------------------------------------------
# the 29 sweep cases
# ---------------------------------------------------------------------------
def test_the_sweep_case_list_is_the_sweeps_own_count():
    """29 rows, because the sweep reported 29. Guards the transcription."""
    assert len(SWEEP_UNNAMED) == 29
    assert len({(s, k) for s, k, _site in SWEEP_UNNAMED}) == 15


@pytest.mark.slow
@pytest.mark.parametrize("setting,k,site", SWEEP_UNNAMED,
                         ids=lambda v: str(v).replace(" ", ""))
def test_the_sweeps_unnamable_isotropy_subgroups_still_produce_candidates(
        setting, k, site):
    """Each case comes back with candidates, and the unnamed ones say so.

    The sweep's ``RuntimeError: unidentified candidate`` is raised by the
    *sweep script*, not by ``candidates`` — which already tolerates
    ``identify`` refusing and stores ``identification=None``.  What was missing
    is what an unnamed candidate can then be *used* for, so this asserts both
    halves: the call returns, and every candidate carries the operator list its
    label cannot supply.
    """
    kk = tuple(Fraction(c) for c in k)
    found = candidates(setting, SWEEP_SITES[site], kk)
    assert len(found) > 0
    unnamed = [c for c in found if c.identification is None]
    assert unnamed, f"{setting} at {k} ({site}) was expected an unnamed candidate"
    for candidate in unnamed:
        assert candidate.bns_number == "unidentified"
        result = identification(candidate.group)
        assert result.named is False
        assert result.operations
        assert result.reason


@pytest.mark.slow
def test_the_ba2fesbse5_s3ab_child_is_built_instead_of_refused():
    """The one real case: Pm in 2a,b,a+c, which a symbol-only phase could not state.

    The parent is a *generic* Pnma structure — generic members of the 8d and 4c
    Wyckoff classes and a nominal cell, no fitted or published number — which
    is sound because ``candidates`` reads a site only through its stabiliser
    and its orbit.
    """
    from rietx.crystallography.adp import cartesian_basis

    parent = Phase(
        name="parent", space_group="P n m a",
        cell=_cell((12.0, 9.0, 8.0, 90.0, 90.0, 90.0)),
        atoms=[
            Atom(label="Ba1", species="Ba", x=Parameter(value=0.11),
                 y=Parameter(value=0.13), z=Parameter(value=0.17),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.9)),
            Atom(label="Fe1", species="Fe", x=Parameter(value=0.19),
                 y=Parameter(value=0.25), z=Parameter(value=0.23),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
            Atom(label="Se1", species="Se", x=Parameter(value=0.29),
                 y=Parameter(value=0.31), z=Parameter(value=0.37),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.7)),
        ])
    lattice = np.asarray(cartesian_basis(*parent.cell.lengths_angles())).T
    k = ("1/2", "0", "1/2")
    per_site = [{c.label: c for c in candidates(
        parent.space_group, (a.x.value, a.y.value, a.z.value), k,
        kind="displacive", cell=lattice, verify=True)}
        for a in parent.atoms]
    assert all("S3(a,b)" in table for table in per_site)

    statement = sc.magnetic_supercell(parent, candidate=per_site[0]["S3(a,b)"],
                                      nuclear_group="magnetic")
    assert statement.child_group_named is False
    assert sym.split_group_label(statement.phase.space_group) is not None
    assert statement.phase.symmetry_operations is not None
    # The candidate's own group is now the stabiliser of its displacement
    # field, built with the coset character ε(Δ) (#679): the pure
    # anti-translation 'x+1/2,y,z' (ε = −1) is no longer in it, and the
    # group is the order-4 {x,y,z; x,-y+1/2,z; -x+1/2,y+1/2,-z;
    # -x+1/2,-y,-z} (a mirror, a screw axis and an inversion).  Each of the
    # four carries ε = +1 on the field, so
    # supercell._sign_consistent_operations keeps all four (checked by
    # propagating the field by the bare rotation); the previous order-2 set
    # was what the old grey rule left after that filter dropped its
    # ε = −1 operations.  12 atoms: the child holds 32 (16 per parent cell,
    # two parent cells), and the order-4 group's orbits leave 4 Ba, and 4 each
    # of Fe and Se, whose mirror fixes y = 1/4 (the order-2 group left 24).
    assert set(statement.phase.symmetry_operations) == {
        "x,y,z", "x,-y+1/2,z", "-x+1/2,y+1/2,-z", "-x+1/2,-y,-z"}
    assert len(statement.phase.atoms) == 12
    codes = [d.code for d in statement.diagnostics]
    assert "CHILD_GROUP_UNNAMED" in codes
    note = next(d for d in statement.diagnostics
                if d.code == "CHILD_GROUP_UNNAMED")
    assert "quarter" in note.message
    # the child compiles and predicts, which is the whole point of stating it
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all()
    assert float(np.asarray(y).max()) > 0.0


@pytest.mark.slow
def test_a_named_child_is_untouched_by_the_unnamed_path():
    """S2(a,b) of the same parent still gives the plain symbol and no list.

    The negative arm of the test above: a child whose nuclear group *is*
    reproduced by a symbol keeps the symbol, carries no operation list, and
    raises no diagnostic — so the new path cannot have been taken for it.
    """
    from rietx.crystallography.adp import cartesian_basis

    parent = Phase(
        name="parent", space_group="P n m a",
        cell=_cell((12.0, 9.0, 8.0, 90.0, 90.0, 90.0)),
        atoms=[
            Atom(label="Fe1", species="Fe", x=Parameter(value=0.19),
                 y=Parameter(value=0.25), z=Parameter(value=0.23),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
        ])
    lattice = np.asarray(cartesian_basis(*parent.cell.lengths_angles())).T
    found = {c.label: c for c in candidates(
        parent.space_group, (0.19, 0.25, 0.23), ("1/2", "0", "1/2"),
        kind="displacive", cell=lattice, verify=True)}
    statement = sc.magnetic_supercell(parent, candidate=found["S2(a,b)"],
                                      nuclear_group="magnetic")
    assert statement.child_group_named is True
    assert statement.phase.space_group == "P 1 21/m 1"
    assert statement.phase.symmetry_operations is None
    assert [d.code for d in statement.diagnostics] == []


def test_site_constraints_of_an_unnamed_group_withholds_the_wyckoff_letter():
    """Constraint bases and multiplicity yes; a Wyckoff letter no.

    The letter is a property of a tabulated setting, and spglib would answer
    for the *type* it identifies from a probe cell — which for a child cell
    whose glide translation is a quarter is not this setting.  So it is left
    empty rather than filled with a plausible wrong one; everything else here
    is read off the group's own operations and is unaffected.
    """
    from rietx.crystallography.wyckoff import site_constraints

    og = sym.OperatorGroup(label=S3_CHILD_LABEL, xyz=S3_CHILD_OPS)
    general = site_constraints(og, (0.11, 0.13, 0.17))
    assert general.wyckoff == ""
    assert general.site_symmetry == ""
    assert general.multiplicity == 4
    assert general.coord_basis.shape == (3, 3)
    special = site_constraints(og, (0.11, 0.25, 0.17))   # on the mirror
    assert special.multiplicity == 2
    assert special.coord_basis.shape == (2, 3)
    # the named twin still answers with its letter
    named = site_constraints("P n m a", (0.11, 0.25, 0.17))
    assert named.wyckoff == "4c"


def test_the_stephens_basis_reaches_an_unnamed_group_through_the_frozen_set():
    """``report.strain`` rebuilds the group from ``ReflectionSet.operations``.

    The anisotropic-strain basis depends on the rotations only, so an unnamed
    group gives what its closest type gives — but only if the consumer can get
    the group back at all, and all it has is the frozen ``spacegroup`` string,
    which for such a phase is a *label* the tables do not hold.  The list rides
    along on the set for exactly that.
    """
    from rietx.crystallography.stephens import stephens_basis

    og = sym.OperatorGroup(label=S3_CHILD_LABEL, xyz=S3_CHILD_OPS)
    refl = sym.generate_reflections(og, (14.0, 6.0, 8.0, 90.0, 97.0, 90.0),
                                    1.5406, 90.0)
    assert refl.spacegroup == S3_CHILD_LABEL
    assert refl.operations == S3_CHILD_OPS
    rebuilt = sym.resolve_group(refl.spacegroup, refl.operations)
    assert isinstance(rebuilt, sym.OperatorGroup)
    basis = stephens_basis(rebuilt)
    # the monoclinic-b Stephens subspace, which is what P 1 m 1 gives
    assert np.array_equal(basis, stephens_basis("P 1 m 1"))
    assert len(basis) == 9
    # and a named phase's set still carries no list, so nothing changed for it
    named = sym.generate_reflections("P n m a", (8.0, 6.0, 7.0, 90.0, 90.0, 90.0),
                                     1.5406, 90.0)
    assert named.operations is None


# ---------------------------------------------------------------------------
# the CIF exporter reads the list (review of #433, finding 3)
# ---------------------------------------------------------------------------
def _bonded_phase(space_group, operations, cell):
    """Fe with an O 2.0 Å up c, so the geometry table has a bond to export."""
    return Phase(
        name="p", space_group=space_group, symmetry_operations=operations,
        cell=_cell(cell),
        atoms=[Atom(label="Fe1", species="Fe", x=Parameter(value=0.1),
                    y=Parameter(value=0.1), z=Parameter(value=0.3),
                    occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
               Atom(label="O1", species="O", x=Parameter(value=0.1),
                    y=Parameter(value=0.1), z=Parameter(value=0.55),
                    occ=Parameter(value=1.0), biso=Parameter(value=0.8))])


def _exported_symops(phase, tmp_path):
    from rietx.io.exporters import write_refinement_cif

    structure = Structure(phases=[phase])
    ref = rx.Refinement(structure, INSTRUMENT.model_copy(deep=True))
    data = rx.PatternData(
        two_theta=TWO_THETA.tolist(),
        intensity=(np.asarray(ref.predict(TWO_THETA)) + 10.0).tolist())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"])]))
    assert result.geometry is not None and any(
        d.bonded for d in result.geometry.distances), "the fixture has no bond"
    path = tmp_path / "out.cif"
    write_refinement_cif(result, ref.fitted_structure, ref.instrument, path)
    block = gemmi.cif.read(str(path))[0]
    loop = block.find_loop("_space_group_symop_operation_xyz")
    return [gemmi.cif.as_string(v) for v in loop], block


def test_a_bracketed_label_phase_exports_its_own_operation_list(tmp_path):
    """``write_refinement_cif`` on an unnamed group with bond rows.

    The exporter handed the *label* to the symbol expansion, which raised
    ``unknown space group symbol`` for any bracketed phase whose result
    carried a bond; it now writes the phase's own list, in its own order.
    """
    phase = _bonded_phase(S3_CHILD_LABEL, list(S3_CHILD_OPS),
                          (14.0, 6.0, 8.0, 90.0, 97.0, 90.0))
    symops, block = _exported_symops(phase, tmp_path)
    assert symops == list(phase.symmetry_operations)
    assert block.find_loop("_geom_bond_distance")


def test_a_reordered_list_under_a_real_symbol_exports_in_the_callers_order(
        tmp_path):
    """The codes index the listed order, so the loop must be that order.

    Under a plain symbol the list must be the symbol's group, but it may be
    written in any order.  Expanding the symbol instead wrote gemmi's order
    while each ``site_symmetry`` code indexed the caller's, so every code named
    the wrong operation, silently.
    """
    ops = list(reversed(_triplets("P 1 21/c 1")))
    ops.remove("x,y,z")
    ops.insert(0, "x,y,z")
    phase = _bonded_phase("P 1 21/c 1", ops, (7.0, 6.0, 8.0, 90.0, 97.0, 90.0))
    assert list(phase.symmetry_operations) != _triplets("P 1 21/c 1")
    symops, _block = _exported_symops(phase, tmp_path)
    assert symops == list(phase.symmetry_operations)


# ---------------------------------------------------------------------------
# a moment on an operation-list phase (review of #448, item 1)
# ---------------------------------------------------------------------------
#: MnF₂, P 4₂/mnm, moment along c on Mn (Erickson 1953, *Phys. Rev.* **90**,
#: 779): its strongest magnetic row, (1 0 0), is absent in the nuclear group,
#: so the phase goes through ``merge_magnetic``.  The same fixture
#: ``test_magnetic`` uses, here under a bracketed label with the symbol's own
#: operation list.
_MNF2_SYMBOL = "P 42/m n m"
_MNF2_CELL = (4.8734, 4.8734, 3.3099, 90.0, 90.0, 90.0)


def _mnf2_listed(moment):
    from rietx.schemas.structure import Moment

    def at(label, species, xyz, m=None):
        return Atom(label=label, species=species, x=Parameter(value=xyz[0]),
                    y=Parameter(value=xyz[1]), z=Parameter(value=xyz[2]),
                    occ=Parameter(value=1.0), biso=Parameter(value=0.3),
                    moment=m)

    return Phase(
        name="MnF2", space_group=f"{_MNF2_SYMBOL} [explicit]",
        symmetry_operations=_triplets(_MNF2_SYMBOL), cell=_cell(_MNF2_CELL),
        atoms=[at("Mn", "Mn", (0.0, 0.0, 0.0),
                  Moment.from_values(moment, "Mn2+", vary=True)),
               at("F", "F", (0.3050, 0.3050, 0.0))],
        magnetic_symmetry="136.499")


def test_a_moment_on_an_operation_list_phase_keeps_the_list_through_report():
    """``merge_magnetic`` carries ``operations``, so ``report()`` resolves.

    It built the merged set from the label alone, and the strain and texture
    arms then asked ``resolve_group`` for a bracketed label with no list:
    "unknown space group symbol", after the fit had finished.
    """
    from rietx.model.forward import compile_model

    tt = np.arange(10.0, 140.0, 0.05)
    instrument = rx.Instrument.constant_wavelength_neutron(2.4)
    truth = Structure(phases=[_mnf2_listed((0.0, 0.0, 4.6))])
    flat = rx.PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())
    model = compile_model(truth, instrument, flat)
    refl = model.phases[0].reflections
    assert refl.operations == tuple(truth.phases[0].symmetry_operations)
    assert refl.spacegroup == truth.phases[0].space_group
    assert (1, 0, 0) in {tuple(map(int, h)) for h in refl.hkl}, \
        "the fixture has no magnetic-only row, so it never reaches the merge"

    from rietx.params.vector import ParameterTable
    table = ParameterTable(truth, instrument)
    y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64) + 20.0
    ref = rx.Refinement(Structure(phases=[_mnf2_listed((0.0, 0.0, 3.5))]),
                        instrument.model_copy(deep=True))
    ref.fit(rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist()),
            plan=rx.RefinementPlan(stages=[
                rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
                rx.Stage("moment", ["phases.*.atoms.*.moment.dof*"])]))
    report = ref.report()
    assert len(report.strain) == 1 and len(report.texture) == 1
    assert len(report.magnetic) == 1


# ---------------------------------------------------------------------------
# a structure CIF carries the list and reads back (review of #448, item 3)
# ---------------------------------------------------------------------------
def test_a_structure_cif_of_an_operation_list_phase_reads_back_bit_identically(
        tmp_path):
    """``structure_to_cif`` → ``structure_from_cif``: label, list and order.

    ``write_structure_block`` wrote the bracketed label and no operations, so
    the file named a group no reader could expand ("unrecognised space group").
    """
    from rietx.crystallography.cif import structure_from_cif, structure_to_cif

    for label, ops, cell in (
            (S3_CHILD_LABEL, list(S3_CHILD_OPS), (14.0, 6.0, 8.0, 90.0, 97.0, 90.0)),
            # a named group's list, reordered: the bracket keeps gemmi from
            # resolving it to the symbol and the file's order is kept
            ("P 1 21/c 1 [explicit]",
             ["x,y,z", *reversed(_triplets("P 1 21/c 1")[1:])],
             (7.0, 6.0, 8.0, 90.0, 97.0, 90.0))):
        phase = _phase(label, ops, cell)
        path = tmp_path / "s.cif"
        structure_to_cif(Structure(phases=[phase]), str(path))
        back = structure_from_cif(str(path)).phases[0]
        assert back.space_group == phase.space_group
        assert back.symmetry_operations == phase.symmetry_operations
        assert [(a.x.value, a.y.value, a.z.value) for a in back.atoms] == \
            [(a.x.value, a.y.value, a.z.value) for a in phase.atoms]


def test_a_refinement_cif_without_geometry_rows_still_carries_the_list(tmp_path):
    """The symop loop no longer depends on the phase having a bond to report."""
    from rietx.crystallography.cif import structure_from_cif
    from rietx.io.exporters import write_refinement_cif

    phase = _phase(S3_CHILD_LABEL, list(S3_CHILD_OPS),
                   (14.0, 6.0, 8.0, 90.0, 97.0, 90.0))
    phase.atoms = phase.atoms[:1]
    ref = rx.Refinement(Structure(phases=[phase]), INSTRUMENT.model_copy(deep=True))
    data = rx.PatternData(
        two_theta=TWO_THETA.tolist(),
        intensity=(np.asarray(ref.predict(TWO_THETA)) + 10.0).tolist())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"])]))
    assert result.geometry is None or not result.geometry.distances
    path = tmp_path / "out.cif"
    write_refinement_cif(result, ref.fitted_structure, ref.instrument, path)
    back = structure_from_cif(str(path)).phases[0]
    assert back.space_group == S3_CHILD_LABEL
    assert back.symmetry_operations == list(S3_CHILD_OPS)


@pytest.mark.parametrize("writer", [
    "rietx.io.projects.gsas:write_gsas_exp",
    "rietx.io.projects.gsas2:write_gsas2_phase_cif",
    "rietx.io.projects.topas:write_topas_inp",
    "rietx.io.projects.fullprof:write_fullprof_pcr",
])
def test_a_symbol_only_project_writer_refuses_the_list_by_name(writer, tmp_path):
    """Each of these formats states a group only as a symbol, so the phase is
    refused — naming the operation list, not "unknown space group symbol"."""
    import importlib

    module, name = writer.split(":")
    write = getattr(importlib.import_module(module), name)
    phase = _phase(S3_CHILD_LABEL, list(S3_CHILD_OPS),
                   (14.0, 6.0, 8.0, 90.0, 97.0, 90.0))
    with pytest.raises(ValueError, match=r"4 symmetry_operations under the "
                                         r"bracketed label") as err:
        write(Structure(phases=[phase]), tmp_path / "out")
    assert "unknown space group symbol" not in str(err.value)
    assert not (tmp_path / "out").exists()
