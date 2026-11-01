"""The parameter surface: rows as data, the two edit verbs, plan metadata.

WP-1004.  Everything here is plain API — the GUI is a consumer, not a premise.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

import rietx as rx
from rietx._nearmiss import did_you_mean, near_misses
from rietx.params.vector import (
    Entry,
    is_literal_path,
    retired_spelling,
    unknown_paths_among,
)
from rietx.schemas.instrument import HumpComponent
from rietx.schemas.params import ParameterRow, TieSpec
from rietx.strategy.staged import PLAN_INFO, PLAN_PRESETS
from tests.test_refine_synthetic import perturbed_models, synthesize

#: obs/calc/diff panels for visual inspection, gitignored (tests/CLAUDE.md):
#: Rwp hides a locally bad fit, and the hold case is one where the *worse* Rwp
#: is the right answer, so the picture is the check that nothing else broke.
OUT = Path(__file__).parent / "output"

SHORT = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=20),
    rx.Stage("cell", ["phases.*.cell.*"], max_iter=20),
])

#: Fields ``ParameterRow`` adds to ``Entry``'s, declared here so the anti-drift
#: test asserts the addition rather than silently tolerating any difference.
#:
#: The first three are held-reasons an ``Entry`` cannot carry, for the same
#: reason: they are not facts about the parameter.  ``esd`` comes from the last
#: fit, ``mode_fixed`` from the intensity mode, and ``needs_held_cell`` from
#: whether this histogram's *cell* is currently free — the only one that changes
#: with another parameter's state, which is why it cannot be an ``Entry.locked``
#: flag and has to be recomputed each time the surface is read.
#:
#: ``body`` (WP-1805) names the rigid body writing a row, which outranks
#: ``locked`` in ``held_because`` because its remedy differs — and is
#: outranked by ``mode_fixed``, which force-fixes that remedy too.
#:
#: ``help_key`` (WP-1202) is not a held-reason at all: it names the
#: ``rietx.help`` family that describes the path, which is a fact about the
#: path's *shape* and so belongs to no single entry.
DELIBERATE_EXTRAS = {"esd", "mode_fixed", "needs_held_cell", "help_key", "body",
                     "origin_axis"}


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture
def ref():
    structure, ins = perturbed_models()
    return rx.Refinement(structure, ins)


# ------------------------------------------------------------------ the schema
def test_parameter_row_mirrors_entry_plus_declared_extras():
    entry_fields = {f.name for f in dataclasses.fields(Entry)}
    row_fields = set(ParameterRow.model_fields)
    assert row_fields - entry_fields == DELIBERATE_EXTRAS
    assert entry_fields - row_fields == set(), "an Entry field is not exposed"


def test_a_wavelength_is_held_by_the_cell_and_says_so():
    """The fourth held-reason, and the only dynamic one.

    ``refinable`` promises "``set_vary`` could free this row".  With the cell
    free, ``set_vary`` skips a wavelength — so without this flag the promise
    would be false while ``held_because`` said nothing, which is exactly the
    defaulted-``False`` shape WP-1076 removes.  Both directions asserted: a
    held-because that never clears is the old hard lock in disguise.
    """
    import rietx as rx

    WL = "instrument.source.lines.0.wavelength"
    ins = rx.Instrument.debye_scherrer(wavelength=1.5406)

    def structure(cell_vary):
        st = rx.Structure(phases=[rx.Phase(
            name="LaB6", space_group="P m -3 m",
            cell=rx.Cell.cubic(4.15689, vary=cell_vary),
            atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                           y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))])])
        return st

    free = rx.Refinement(structure(True), ins, history=False)
    row = next(r for r in free.parameters() if r.path == WL)
    assert row.needs_held_cell and not row.refinable
    assert "cell held" in row.held_because
    assert not row.locked, "a dynamic reason must not masquerade as structural"

    held = rx.Refinement(structure(False), ins, history=False)
    row = next(r for r in held.parameters() if r.path == WL)
    assert not row.needs_held_cell and row.refinable and row.held_because == ""


def test_tie_spec_describes_its_right_hand_side():
    tie = TieSpec(terms=[("phases.0.atoms.1.dof.0", 1.0)], const=0.1993)
    assert tie.sources == ["phases.0.atoms.1.dof.0"]
    assert tie.describe() == "0.1993 + 1·phases.0.atoms.1.dof.0"
    assert TieSpec(terms=[], const=0.0).describe() == "0"


# ------------------------------------------------------------------- listing
def test_parameters_lists_the_whole_table(ref):
    rows = {r.path: r for r in ref.parameters()}
    # free, tied, locked and merely-fixed all present — a caller deciding what
    # to free next has to see the parts it may not touch
    assert rows["phases.0.cell.a"].refinable
    assert rows["phases.0.cell.b"].tie is not None
    assert not rows["phases.0.cell.b"].refinable
    assert rows["phases.0.cell.alpha"].locked
    assert rows["phases.0.extinction"].refinable and not rows["phases.0.extinction"].vary
    # bounds come through, so a client can build an editor
    assert rows["phases.0.scale"].lo == 0.0
    assert not hasattr(rows["phases.0.scale"], "transform")


def test_parameters_reports_why_a_row_is_held(ref):
    rows = {r.path: r for r in ref.parameters()}
    assert "symmetry" in rows["phases.0.cell.alpha"].held_because
    assert rows["phases.0.cell.b"].held_because == "tied: = 1·phases.0.cell.a"
    assert rows["phases.0.cell.a"].held_because == ""


def test_parameters_merges_the_last_fits_esds(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.a"].esd is not None and rows["phases.0.cell.a"].esd > 0
    # a tied dependent reports the propagated esd, not None
    assert rows["phases.0.cell.b"].esd == pytest.approx(rows["phases.0.cell.a"].esd)
    # something never freed has no esd rather than a stale one
    assert rows["phases.0.extinction"].esd is None


def test_parameters_reflects_the_free_set_after_a_stage(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.a"].vary and rows["phases.0.scale"].vary
    assert not rows["instrument.profile.w"].vary


def test_lebail_mode_marks_the_dummy_atom_not_editable(ref, pattern):
    """A Le Bail phase must carry an atom to exist; it must not look editable.

    ``Phase`` refuses an empty atom list, so a Le Bail-only phase (indexing
    constructs these routinely) carries a dummy atom that contributes nothing —
    ``_run_stage`` force-fixes every ``.atoms.`` path in that mode.  A row shown
    as editable would invite refining something the mode discards.
    """
    ref.fit(pattern, mode="lebail", plan="profile_only")
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.0.biso"].mode_fixed
    assert not rows["phases.0.atoms.0.biso"].refinable
    assert "mode" in rows["phases.0.atoms.0.biso"].held_because
    assert rows["phases.0.scale"].mode_fixed  # degenerate with the intensities
    # ...and it is not *locked*: switching back to rietveld frees it again
    assert not rows["phases.0.scale"].locked
    assert rows["phases.0.cell.a"].refinable


# --------------------------------------------------------------------- verbs
def test_set_vary_frees_by_glob_and_refuses_locked(ref):
    hits = ref.set_vary(["phases.*.cell.*"])
    assert hits == ["phases.0.cell.a"]  # b, c tied; the angles locked
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.a"].vary
    assert not rows["phases.0.cell.alpha"].vary
    # a string is accepted as a single glob (the GUI passes one row's path)
    assert ref.set_vary("phases.0.extinction") == ["phases.0.extinction"]
    assert ref.set_vary(["phases.*.cell.*"], False) == ["phases.0.cell.a"]


def test_set_values_writes_through_to_the_models(ref):
    ref.set_values({"phases.0.cell.a": 4.2, "phases.0.extinction": 1e-4})
    assert ref.structure.phases[0].cell.a.value == 4.2
    # the tied dependents follow their source — otherwise the cubic symmetry the
    # tie exists to enforce would be silently broken
    assert ref.structure.phases[0].cell.b.value == 4.2
    assert ref.structure.phases[0].cell.c.value == 4.2
    assert {r.path: r.value for r in ref.parameters()}["phases.0.cell.b"] == 4.2


def test_set_values_refuses_with_an_actionable_message(ref):
    with pytest.raises(ValueError, match="unknown parameter path"):
        ref.set_values({"phases.0.cell.aa": 4.2})
    with pytest.raises(ValueError, match="structurally fixed"):
        ref.set_values({"phases.0.cell.alpha": 91.0})
    with pytest.raises(ValueError, match=r"follows 'phases\.0\.cell\.a'"):
        ref.set_values({"phases.0.cell.b": 4.2})
    with pytest.raises(ValueError, match="outside its bounds"):
        ref.set_values({"phases.0.scale": -1.0})
    # a refused call changes nothing
    assert ref.structure.phases[0].cell.alpha.value == 90.0


def test_set_values_invalidates_the_stale_result(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    assert ref.result_ is not None
    ref.set_values({"phases.0.cell.a": 4.2})
    assert ref.result_ is None  # the fitted curve described the old values


# ------------------------------------------------------- verbs ↔ history nodes
def test_verbs_record_the_reserved_node_kinds(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    n_before = len(ref.history)
    ref.set_vary(["instrument.profile.w"])
    ref.set_values({"instrument.profile.w": 0.02})
    kinds = [ref.history[i].action.kind for i in ref.history.order[n_before:]]
    assert kinds == ["set_vary", "set_value"]
    # the free set and the value are in the recorded state, so a checkout
    # restores an edit exactly like it restores a stage
    node = ref.history[ref.history.order[-1]]
    assert "instrument.profile.w" in node.state.free_paths
    assert node.state.instrument.profile.w.value == 0.02


def test_recorded_api_call_evaluates_back_to_the_same_call(ref, pattern):
    """A history log doubles as a session script, so the rendering must run.

    The plural/singular mismatch this pins was real: ``api_call`` rendered
    ``ref.set_values(...)`` for the singular ``"set_value"`` node kind, and no
    such method existed until WP-1004 (the verb is plural — a GUI edits a table,
    not a cell — and the NodeKind literal stays as persisted).
    """
    ref.fit(pattern, plan=SHORT)
    ref.set_vary(["instrument.profile.w"])
    ref.set_values({"instrument.profile.w": 0.02})
    ids = ref.history.order[-2:]
    calls = [ref.history[i].action.api_call() for i in ids]
    assert calls[0] == "ref.set_vary(['instrument.profile.w'], True)"
    assert calls[1] == "ref.set_values({'instrument.profile.w': 0.02})"

    # eval the rendered strings against a fresh refinement: same state out
    structure, ins = perturbed_models()
    replayed = rx.Refinement(structure, ins)
    replayed.fit(pattern, plan=SHORT)
    for call in calls:
        eval(call, {"ref": replayed, "rx": rx, "data": pattern})  # noqa: S307
    assert replayed.structure.phases[0].cell.a.value == pytest.approx(
        ref.structure.phases[0].cell.a.value)
    assert replayed.instrument.profile.w.value == 0.02
    assert {r.path: r for r in replayed.parameters()}["instrument.profile.w"].vary


def test_set_vary_without_history_still_edits():
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    assert ref.set_vary(["phases.*.cell.*"]) == ["phases.0.cell.a"]
    ref.set_values({"phases.0.cell.a": 4.2})
    assert ref.history is None
    assert ref.structure.phases[0].cell.a.value == 4.2



def _declaring_only(path):
    """``perturbed_models`` with every model ``vary`` flag cleared but ``path``'s.

    ``path`` is a ``phases.…`` or ``instrument.…`` dot-path to a ``Parameter``.
    """
    from pydantic import BaseModel

    from rietx.schemas.common import Parameter

    def clear(obj):
        if isinstance(obj, Parameter):
            obj.vary = False
        elif isinstance(obj, BaseModel):
            for name in type(obj).model_fields:
                clear(getattr(obj, name))
        elif isinstance(obj, (list, tuple)):
            for o in obj:
                clear(o)

    structure, ins = perturbed_models()
    clear(structure)
    clear(ins)
    target = structure if path.startswith("phases.") else ins
    for part in path.split(".")[1 if target is ins else 0:]:
        target = target[int(part)] if part.isdigit() else getattr(target, part)
    target.vary = True
    return structure, ins


def _free(ref):
    return sorted(r.path for r in ref.parameters() if r.vary)


@pytest.mark.parametrize("also_free", [[], ["instrument.zero_shift"]],
                         ids=["the-last-free-path", "one-of-two"])
def test_holding_a_model_declared_path_outlasts_the_next_set_vary(also_free):
    """``set_vary(path, False)`` is a declaration, and an empty one is too.

    The models' ``vary`` flags are the declaration only until the refinement
    has one of its own.  Holding the *last* free path used to leave an empty
    free set that read as "none declared yet", so the next table build went
    back to the model flags: the row reported free again, and the next
    ``set_vary`` folded it into the declared set, where ``run_stage`` refined
    it.  The second case is the positive arm: with another path still free the
    hold always held.
    """
    ref = rx.Refinement(*_declaring_only("phases.0.lor_size"), history=False)
    if also_free:
        ref.set_vary(also_free)
    assert _free(ref) == sorted(["phases.0.lor_size", *also_free])

    assert ref.set_vary(["phases.0.lor_size"], False) == ["phases.0.lor_size"]
    assert _free(ref) == sorted(also_free)

    ref.set_vary(["phases.0.scale"])
    assert _free(ref) == sorted(["phases.0.scale", *also_free])


def test_a_stage_after_holding_the_last_free_path_leaves_it_held(pattern):
    ref = rx.Refinement(*_declaring_only("phases.0.lor_size"), history=False)
    ref.set_vary(["phases.0.lor_size"], False)
    ref.set_vary(["instrument.background.*"])
    result = ref.run_stage(pattern, rx.Stage("scale", ["phases.0.scale"], max_iter=5))
    refined = {p.path for p in result.parameters}
    assert "phases.0.scale" in refined
    assert "phases.0.lor_size" not in refined


def test_a_checkout_of_an_all_held_node_keeps_it_all_held(ref, pattern):
    """A node after the root records a declared free set, empty or not."""
    ref.fit(pattern, plan=SHORT)
    fitted = ref.history.head
    assert _free(ref)
    ref.set_vary(["*"], False)
    empty = ref.history.head
    assert _free(ref) == []

    ref.checkout(fitted)
    assert _free(ref)
    ref.checkout(empty)
    assert _free(ref) == []


@pytest.mark.parametrize("edit", ["set_values", "edit", "add_variable", "merge"])
def test_a_checkout_of_a_node_that_declared_nothing_keeps_the_model_flags(pattern, edit):
    """``Project.open`` checks out the head, so a project whose last act was a
    value edit must open with the model's own ``vary`` flags still the free set.

    Those node kinds snapshot the free set without declaring one, so the node's
    *kind* cannot say whether an empty set is a declaration (#788 review).
    """
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    ref._ensure_history(pattern)
    before = _free(ref)
    assert before
    if edit == "set_values":
        ref.set_values({"instrument.profile.w": 0.02})
    elif edit == "edit":
        new = ref.structure.model_copy(deep=True)
        new.phases[0].cell.a.value += 0.001
        ref.edit(structure=new)
    elif edit == "add_variable":
        ref.add_variable("tilt", 0.1)
    else:
        ref.set_values({"instrument.profile.w": 0.02})
        other = ref.history.head
        ref.checkout(ref.history.root.id)
        ref.set_values({"instrument.profile.v": -0.01})
        ref.merge(other)
    assert _free(ref) == before
    ref.checkout(ref.history.head)
    assert _free(ref) == before


def test_a_declaration_survives_a_node_kind_that_does_not_declare(pattern):
    """The other half: an all-held free set, then an edit, then a checkout."""
    ref = rx.Refinement(*perturbed_models())
    ref._ensure_history(pattern)
    ref.set_vary(["*"], False)
    assert _free(ref) == []
    ref.set_values({"instrument.profile.w": 0.02})
    ref.checkout(ref.history.head)
    assert _free(ref) == []


def test_a_state_without_free_declared_reads_as_not_declared():
    """A document written before the field loads, and an empty set there is the
    old reading (the models' flags)."""
    from rietx.schemas.history import RefinementState

    structure, ins = perturbed_models()
    state = RefinementState(structure=structure, instrument=ins)
    assert state.free_declared is False
    dumped = state.model_dump(mode="json")
    dumped.pop("free_declared")
    assert RefinementState.model_validate(dumped).free_declared is False


# ------------------------------------------------- user constraints (WP-1070)
BISOS = ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]


def test_tie_equal_makes_one_parameter_of_a_group(ref):
    """The verb §7 asks for: the first match carries the freedom, rest follow."""
    assert ref.tie_equal(BISOS) == ["phases.0.atoms.1.biso"]
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie.sources == ["phases.0.atoms.0.biso"]
    assert not rows["phases.0.atoms.1.biso"].refinable
    assert rows["phases.0.atoms.0.biso"].refinable, "the source keeps the freedom"
    # the dependent takes the source's value at once, so nothing is left
    # describing the pre-tie state
    ref.set_values({"phases.0.atoms.0.biso": 0.71})
    assert ref.structure.phases[0].atoms[1].biso.value == 0.71
    # ...and the constraint is a *reduction*: one fewer column in θ
    assert ref.set_vary(["phases.0.atoms.*.biso"]) == ["phases.0.atoms.0.biso"]


def test_tie_is_the_general_affine_form(ref):
    """Complementary occupancies: occ₁ = 1 − occ₀, the other case §7 names."""
    ref.set_values({"phases.0.atoms.0.occ": 0.6})
    ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0, offset=1.0)
    assert ref.structure.phases[0].atoms[1].occ.value == pytest.approx(0.4)
    ref.set_values({"phases.0.atoms.0.occ": 0.75})
    assert ref.structure.phases[0].atoms[1].occ.value == pytest.approx(0.25)
    row = {r.path: r for r in ref.parameters()}["phases.0.atoms.1.occ"]
    assert row.held_because == "tied: = 1 + -1·phases.0.atoms.0.occ"


def test_a_tied_row_says_whose_tie_holds_it(ref):
    """``user`` is what separates a row a caller may release from one it may not.

    Both populations hold a row the same way and read the same in
    ``held_because``, so without the flag a client has to *try* an untie to
    find out — and the answer differs for two rows that look identical.
    """
    ref.tie_equal(BISOS)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie.user
    assert not rows["phases.0.cell.b"].tie.user, "a cell tie is the space group's"


def test_a_tie_refuses_and_names_the_holder(ref):
    with pytest.raises(ValueError, match="unknown parameter path"):
        ref.tie("phases.0.atoms.9.biso", "phases.0.atoms.0.biso")
    with pytest.raises(ValueError, match="structurally fixed"):
        ref.tie("phases.0.cell.alpha", "phases.0.cell.a")
    with pytest.raises(ValueError, match="symmetry outranks a user tie"):
        ref.tie("phases.0.cell.b", "phases.0.cell.a")
    with pytest.raises(ValueError, match="carries no freedom of its own"):
        ref.tie("phases.0.atoms.0.biso", "phases.0.cell.b")
    with pytest.raises(ValueError, match="cannot be tied to itself"):
        ref.tie("phases.0.atoms.0.biso", "phases.0.atoms.0.biso")
    with pytest.raises(ValueError, match="that is set_values"):
        ref.tie(*BISOS, scale=0.0)
    with pytest.raises(ValueError, match="outside its bounds"):
        # Atom.occ declares a floor of 0; B had [0, 25] until WP-1534
        ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0)
    # a refused call changes nothing — not the table, not the models
    assert {r.path: r for r in ref.parameters()}["phases.0.atoms.0.biso"].refinable
    assert ref.history is None or len(ref.history) == 0


def test_a_tie_refuses_a_chain_naming_what_to_tie_to_instead(ref):
    ref.tie_equal(BISOS)
    with pytest.raises(ValueError, match=r"follows 'phases\.0\.atoms\.0\.biso' "
                                         r"\(a user tie\)"):
        ref.tie("phases.0.atoms.0.occ", "phases.0.atoms.1.biso")
    with pytest.raises(ValueError, match="untie it first"):
        ref.tie("phases.0.atoms.1.biso", "phases.0.atoms.0.occ")


def test_a_tie_past_a_coordinates_bound_refuses_in_ties_voice_and_leaves_nothing():
    """#246: a displacement DOF has no bounds of its own, so the bound a tie on
    one breaks is on the coordinate its symmetry tie reaches.  The refusal
    names what the caller wrote (target, source, offset), the coordinate, the
    atom and the bound; and a refused tie is not left in the register, where
    the corrected retry used to meet "already follows ... untie it first".

    Made-up triclinic cell, so every coordinate has a free DOF.
    """
    P = rx.Parameter
    s = rx.Structure(phases=[rx.Phase(
        name="X", space_group="P 1",
        cell=rx.Cell(a=P(value=5.1), b=P(value=5.2), c=P(value=5.3),
                     alpha=P(value=91.0), beta=P(value=92.0), gamma=P(value=93.0)),
        atoms=[rx.Atom(label="Al1", species="Al", x=P(value=0.1), y=P(value=0.2),
                       z=P(value=0.3)),
               rx.Atom(label="O1", species="O", x=P(value=0.2482), y=P(value=0.6),
                       z=P(value=0.7))])])
    for atom in s.phases[0].atoms:
        for name in ("x", "y", "z"):
            getattr(atom, name).min, getattr(atom, name).max = 0.0, 1.0
    ref = rx.Refinement(s, rx.Instrument.debye_scherrer(wavelength=1.5406))
    with pytest.raises(ValueError) as refused:
        ref.tie("phases.0.atoms.1.dof.0", "phases.0.atoms.0.dof.0", offset=3.0)
    message = str(refused.value)
    assert message.startswith("tying phases.0.atoms.1.dof.0 to "
                              "1\u00b7phases.0.atoms.0.dof.0 + 3 implies ")
    assert "phases.0.atoms.1.x=3.2482" in message
    assert "atom O1 of phase X" in message
    assert "outside its bounds [0, 1]" in message
    assert ref._ties == {}
    assert {r.path: r for r in ref.parameters()}["phases.0.atoms.1.dof.0"].tie is None
    assert ref.structure.phases[0].atoms[1].x.value == 0.2482
    ref.tie("phases.0.atoms.1.dof.0", "phases.0.atoms.0.dof.0")   # the corrected retry


def test_tie_equal_is_all_or_nothing(ref):
    """A glob that sweeps in a row it cannot tie is a glob to narrow.

    Silently omitting it would leave a constraint the caller asked for and did
    not get — indistinguishable, from the outside, from one that landed.
    """
    with pytest.raises(ValueError, match="symmetry outranks a user tie"):
        ref.tie_equal("phases.0.cell.*")
    assert {r.path: r.tie for r in ref.parameters()}["phases.0.cell.c"].user is False
    with pytest.raises(ValueError, match="an equality group needs at least two"):
        ref.tie_equal("phases.0.atoms.0.biso")


def test_untie_releases_only_this_refinements_ties(ref):
    ref.tie_equal(BISOS)
    assert ref.untie("phases.0.atoms.*.biso") == ["phases.0.atoms.1.biso"]
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie is None
    # released, not freed: that decision belongs to set_vary
    assert not rows["phases.0.atoms.1.biso"].vary
    assert rows["phases.0.atoms.1.biso"].refinable
    # a glob sweeping symmetry ties leaves them alone...
    assert ref.untie("phases.0.cell.*") == []
    # ...but naming one is a request that has to be refused, not a no-op
    with pytest.raises(ValueError, match="tied by symmetry"):
        ref.untie("phases.0.cell.b")
    with pytest.raises(ValueError, match="is not tied"):
        ref.untie("phases.0.atoms.0.biso")


def test_a_tie_refuses_a_mode_fixed_target(ref, pattern):
    ref.fit(pattern, mode="lebail", plan="profile_only")
    with pytest.raises(ValueError, match="force-fixed by the 'lebail'"):
        ref.tie_equal(BISOS)


def test_the_esd_of_a_tied_row_is_its_sources(ref, pattern):
    """Identical to what a cell tie already reports, and by the same route.

    ``stderr_physical`` propagates through C, so an identity tie reports the
    source esd exactly and an affine one scales it.  Pinned against the derived
    tie beside it so the two can never drift into separate policies.
    """
    ref.tie("phases.0.atoms.1.biso", "phases.0.atoms.0.biso", scale=2.0)
    ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("biso", ["phases.*.scale", "phases.*.cell.*",
                          "phases.*.atoms.*.biso"], max_iter=20)]))
    rows = {r.path: r for r in ref.parameters()}
    source = rows["phases.0.atoms.0.biso"].esd
    assert source is not None and source > 0
    assert rows["phases.0.atoms.1.biso"].esd == pytest.approx(2.0 * source)
    # the derived tie beside it, on the same fit, with the same rule
    assert rows["phases.0.cell.b"].esd == pytest.approx(rows["phases.0.cell.a"].esd)


def test_tie_verbs_record_a_set_tie_node(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    n_before = len(ref.history)
    ref.tie_equal(BISOS)
    ref.untie("phases.0.atoms.1.biso")
    kinds = [ref.history[i].action.kind for i in ref.history.order[n_before:]]
    assert kinds == ["set_tie", "set_tie"]
    declared, released = (ref.history[i] for i in ref.history.order[n_before:])
    assert declared.action.ties["phases.0.atoms.1.biso"].sources == [BISOS[0]]
    assert released.action.untied == ["phases.0.atoms.1.biso"]
    # the *state* carries the register, which is what a checkout restores
    assert declared.state.ties["phases.0.atoms.1.biso"].const == 0.0
    assert released.state.ties == {}


def test_a_tie_node_renders_an_api_call_that_runs(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0, offset=1.0)
    ref.untie("phases.0.atoms.1.occ")
    calls = [ref.history[i].action.api_call() for i in ref.history.order[-2:]]
    assert calls == [
        "ref.tie('phases.0.atoms.1.occ', 'phases.0.atoms.0.occ', scale=-1.0, "
        "offset=1.0)",
        "ref.untie(['phases.0.atoms.1.occ'])"]
    structure, ins = perturbed_models()
    replayed = rx.Refinement(structure, ins)
    for call in calls:
        eval(call, {"ref": replayed, "rx": rx})  # noqa: S307
    assert {r.path: r for r in replayed.parameters()}["phases.0.atoms.1.occ"].tie is None


def test_a_checkout_restores_the_parameter_count_the_node_had(ref, pattern):
    """A tie is not a property of the models, so only the node can carry it.

    ``ParameterTable`` rederives the symmetry ties from the space group on
    every build and knows nothing about a user's — a checkout that restored
    only structure and instrument would come back with the constraint silently
    gone, and the free count one higher than the node it claims to be at.
    """
    ref.fit(pattern, plan=SHORT)
    before = ref.history.head
    ref.tie_equal(BISOS)
    ref.set_vary(["phases.0.atoms.*.biso"])
    tied_node = ref.history.head
    assert "phases.0.atoms.1.biso" not in ref.history[tied_node].state.free_paths

    ref.checkout(before)
    assert ref._ties == {}
    assert {r.path: r for r in ref.parameters()}["phases.0.atoms.1.biso"].tie is None

    ref.checkout(tied_node)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie.user
    assert rows["phases.0.atoms.0.biso"].vary and not rows["phases.0.atoms.1.biso"].vary


def test_ties_survive_a_history_file_round_trip(ref, pattern, tmp_path):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=tmp_path / "h.jsonl")
    ref.fit(pattern, plan=SHORT)
    ref.tie_equal(BISOS)
    reopened = rx.Refinement.from_node(
        rx.RefinementTree.load(tmp_path / "h.jsonl"), "head")
    row = {r.path: r for r in reopened.parameters()}["phases.0.atoms.1.biso"]
    assert row.tie is not None and row.tie.user


def test_symmetry_outranks_a_user_tie_when_an_edit_creates_one(ref):
    """The one place the rule can actually be violated (``_apply_ties``).

    The verbs refuse a target that is already tied, but a tie declared while a
    path was free stays declared through an ``edit`` that makes the same path
    symmetry-tied.  Overwriting would break the symmetry the derived tie exists
    to enforce, so the user's is dropped — loudly, and at the edit that ended
    it, since a constraint that stopped applying is exactly what a caller must
    not have to guess at.
    """
    structure, ins = perturbed_models()
    structure.phases[0].space_group = "P 1"  # nothing tied, nothing locked
    ref = rx.Refinement(structure, ins, history=False)
    ref.tie("phases.0.cell.b", "phases.0.cell.a")
    assert {r.path: r for r in ref.parameters()}["phases.0.cell.b"].tie.user

    cubic = ref.structure.model_copy(deep=True)
    cubic.phases[0].space_group = "P m -3 m"
    with pytest.warns(UserWarning, match="now tied by symmetry"):
        ref.edit(structure=cubic)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.b"].tie is not None
    assert not rows["phases.0.cell.b"].tie.user, "the space group's tie, not the user's"
    # said once, at the edit: the register is reconciled with the model it left
    assert ref._ties == {}
    # and the refusals read the table too, so the message names the real holder
    with pytest.raises(ValueError, match="symmetry outranks a user tie"):
        ref.tie("phases.0.cell.b", "phases.0.cell.a")
    with pytest.raises(ValueError, match="tied by symmetry"):
        ref.untie("phases.0.cell.b")


# --------------------------------------------------- holds (WP-1435, issue #211)
CELL = "phases.0.cell.a"


def test_a_plan_frees_a_pinned_parameter_and_a_hold_is_what_stops_it(ref, pattern):
    """The defect and the fix in one test, because one implies the other.

    ``vary=False`` is not a hold.  A plan *replaces* the vary flags rather
    than continuing them (WP-1208), so a stage carrying ``phases.*.cell.*``
    frees a pinned cell and refines it — while the model goes on reading
    ``vary=False`` and ``result.parameters`` says ``True``, which is the
    contradiction issue #211 reported.
    """
    ref.structure.phases[0].cell.a.vary = False
    declared = ref.structure.phases[0].cell.a.value
    ref.fit(pattern, plan=SHORT)
    assert ref.structure.phases[0].cell.a.value != declared, "the defect is gone?"
    assert ref.structure.phases[0].cell.a.vary is False, "the model still says fixed"

    structure, ins = perturbed_models()
    pinned = rx.Refinement(structure, ins)
    assert pinned.hold(CELL) == [CELL]
    result = pinned.fit(pattern, plan=SHORT)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "wp1435_held_cell.png"))

    assert pinned.structure.phases[0].cell.a.value == declared, "bit-identical"
    # …and the value is not reported as a measurement, having never refined
    assert not any(p.path == CELL for p in result.parameters)


def test_a_blocked_stage_says_which_declaration_won(ref, pattern):
    """The half a caller could not otherwise see.

    Keyed on the hold rather than on ``vary``, which is the discriminator
    WP-1310 measured into a dead end: ``vary=False`` is the default rather
    than a decision, so a diagnostic on it names most of the table.
    """
    ref.hold(CELL)
    result = ref.fit(pattern, plan=SHORT)

    blocked = {s.name: s.blocked_by_hold for s in result.stages if s.blocked_by_hold}
    # the closing stage frees every glob the plan freed, the cell's too
    assert blocked == {"cell": [CELL], "closing": [CELL]}
    assert all(CELL not in s.freed for s in result.stages)

    hit = [d for d in result.diagnostics if d.code == "HOLD_BLOCKED_PLAN"]
    assert len(hit) == 1, "one per fit, not one per stage"
    assert hit[0].level == "info" and hit[0].where == [CELL]
    assert hit[0].value == 1.0 and "'cell'" in hit[0].message


def test_a_fit_that_declares_no_hold_is_silent_and_unchanged(ref, pattern):
    """The empty state is empty, which is every fit that predates the field."""
    result = ref.fit(pattern, plan=SHORT)
    assert all(s.blocked_by_hold == [] for s in result.stages)
    assert not [d for d in result.diagnostics if d.code == "HOLD_BLOCKED_PLAN"]


def test_a_hold_marks_the_row_and_names_itself(ref):
    ref.hold(CELL)
    row = {r.path: r for r in ref.parameters()}[CELL]
    assert row.held and not row.refinable
    assert "hold()" in row.held_because and "unhold()" in row.held_because


def test_the_reasons_a_caller_cannot_lift_outrank_a_hold(ref):
    """A hold marks a structurally fixed row and never speaks for it.

    Holding ``phases.*.cell.*`` on a cubic phase is one glob over six rows,
    five of which the space group had already taken.  Marking them is right —
    the caller did declare them — and reporting the hold first would be
    wrong, because ``unhold`` cannot give back what symmetry holds.
    """
    ref.hold("phases.0.cell.*")
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.b"].held and rows["phases.0.cell.alpha"].held
    assert rows["phases.0.cell.b"].held_because.startswith("tied:")
    assert rows["phases.0.cell.alpha"].held_because.startswith("structurally fixed")
    assert rows[CELL].held_because.startswith("held by this refinement")
    # …and the refusal reads the table too, so it never gives advice that
    # would not work: `unhold` gives a tied or locked row back no freer than
    # it was, so those keep set_vary's older answer of declining in silence
    assert ref.set_vary("phases.0.cell.b", True) == []
    assert ref.set_vary("phases.0.cell.alpha", True) == []
    with pytest.raises(ValueError, match="held by this refinement"):
        ref.set_vary(CELL, True)


def test_set_vary_refuses_a_held_path_and_sweeps_past_it(ref):
    """A literal path is a claim, a pattern is a sweep.

    The rule ``ParameterTable.set_vary`` already applies to a wavelength the
    free cell makes degenerate: turning a broad glob into an error is worse
    than declining one row of it, while a named path that cannot be honoured
    has to say so.
    """
    ref.hold(CELL)
    with pytest.raises(ValueError, match="held by this refinement"):
        ref.set_vary(CELL, True)
    assert ref.set_vary("phases.*.cell.*", True) == []
    assert not {r.path: r for r in ref.parameters()}[CELL].vary
    # holding does not block fixing, which a held row already is
    assert CELL in ref.set_vary("phases.*.cell.*", False)


def test_unhold_gives_it_back_fixed_rather_than_free(ref):
    ref.hold(CELL)
    with pytest.raises(ValueError, match="is not held"):
        ref.unhold("phases.0.atoms.0.biso")
    with pytest.raises(ValueError, match="unknown parameter path"):
        ref.unhold("phases.0.cell.nonsense")
    assert ref.unhold("phases.*.cell.*") == [CELL]
    row = {r.path: r for r in ref.parameters()}[CELL]
    assert row.refinable and not row.vary, "released, not freed"
    with pytest.raises(ValueError, match="is not held"):
        ref.unhold(CELL)          # the register no longer knows it


def test_holding_a_free_parameter_fixes_it_at_once(ref):
    """A declaration that took effect next stage would be honoured by
    everything except the solve already running."""
    ref.set_vary(CELL, True)
    assert {r.path: r for r in ref.parameters()}[CELL].vary
    ref.hold(CELL)
    assert not {r.path: r for r in ref.parameters()}[CELL].vary
    assert CELL not in ref._free_paths


def test_a_checkout_restores_the_holds_the_node_had(ref, pattern):
    """A hold that does not survive a checkout is a promise that expires."""
    ref.fit(pattern, plan=SHORT)
    before = ref.history.head
    ref.hold(CELL)
    held_node = ref.history.head
    assert ref.history[held_node].state.holds == [CELL]

    ref.checkout(before)
    assert ref._user_holds == set()
    assert not {r.path: r for r in ref.parameters()}[CELL].held

    ref.checkout(held_node)
    assert ref._user_holds == {CELL}
    assert {r.path: r for r in ref.parameters()}[CELL].held


def test_holds_survive_a_history_file_round_trip(pattern, tmp_path):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=tmp_path / "h.jsonl")
    ref.fit(pattern, plan=SHORT)
    ref.hold(CELL)
    reopened = rx.Refinement.from_node(
        rx.RefinementTree.load(tmp_path / "h.jsonl"), "head")
    assert {r.path: r for r in reopened.parameters()}[CELL].held


def test_a_hold_records_a_node_that_renders_the_call_that_made_it(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    ref.hold(CELL)
    action = ref.history[ref.history.head].action
    assert action.kind == "set_hold" and action.held == [CELL]
    assert action.api_call() == f"ref.hold({[CELL]!r})"
    ref.unhold(CELL)
    action = ref.history[ref.history.head].action
    assert action.unheld == [CELL]
    assert action.api_call() == f"ref.unhold({[CELL]!r})"


def test_a_branch_inherits_the_declarations_it_is_rivalling_under(ref, pattern):
    ref.fit(pattern, plan=SHORT)
    ref.hold(CELL)
    rival = ref.branch()
    assert rival._user_holds == {CELL}
    assert {r.path: r for r in rival.parameters()}[CELL].held


def test_a_hold_on_a_path_an_edit_removed_is_kept_and_said_out_loud(ref):
    """Opposite of a tie, which is dropped.

    A tie describes a relation, so one whose model is gone is stale and goes.
    A hold forbids, so there is nothing in it to go stale — and dropping it at
    an edit is the one way a declaration could lapse in silence.
    """
    ref.hold("phases.0.atoms.1.biso")
    thinner = ref.structure.model_copy(deep=True)
    del thinner.phases[0].atoms[1]
    with pytest.warns(UserWarning, match="hold nothing here"):
        ref.edit(structure=thinner)
    assert ref._user_holds == {"phases.0.atoms.1.biso"}, "kept, for a checkout back"


def test_hold_without_history_still_edits():
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    assert ref.hold(CELL) == [CELL]
    assert ref.history is None
    with pytest.raises(ValueError, match="unknown parameter path"):
        ref.hold("phases.0.cell.nonsense")


def test_tie_without_history_still_edits():
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    assert ref.tie_equal(BISOS) == ["phases.0.atoms.1.biso"]
    assert ref.history is None
    assert ref.structure.phases[0].atoms[1].biso.value == pytest.approx(
        ref.structure.phases[0].atoms[0].biso.value)


# --------------------------------------------- a turn_on that reached nothing
#: the working spelling of issue #265's wavelength, and the one it tried
WAVELENGTH = "instrument.source.lines.0.wavelength"
WAVELENGTH_TYPO = "instrument.source.wavelength"


def test_a_literal_names_one_path_and_a_pattern_does_not():
    assert is_literal_path("instrument.zero_shift")
    assert is_literal_path("vars.A")
    for glob in ("phases.*.scale", "phases.?.scale", "phases.[01].scale"):
        assert not is_literal_path(glob), glob


def test_an_unknown_literal_is_one_the_table_lacks_not_one_it_declined(ref):
    """Found and declined is a different fact from not found (WP-1414).

    A tied ``b``, a locked ``alpha`` and a held ``a`` all free nothing, and
    ``ParameterRow.held_because`` says why for each; none is a typo.  Only
    the literal naming no row is, and a pattern is never reported however
    little it matched.
    """
    ref.hold(CELL)
    table = ref._working_table()
    asked = ["phases.0.cell.b", "phases.0.cell.alpha", CELL,
             WAVELENGTH_TYPO, "phases.*.microstrain.dof.*", "phases.*.cel.*",
             WAVELENGTH_TYPO, "vars.A"]
    assert table.set_vary(asked, True) == []
    assert table.unknown_paths(asked) == [WAVELENGTH_TYPO, "vars.A"], (
        "order kept, repeats dropped, declined rows and patterns absent")


def test_the_near_miss_folds_case_before_it_ranks(ref):
    """Caglioti's U, typed as every paper prints it, is ``profile.u``.

    ``difflib`` alone ranks ``instrument.profile.y`` first: a real path, one
    character away, and the wrong parameter.
    """
    paths = [r.path for r in ref.parameters()]
    assert near_misses("instrument.profile.U", paths, n=1) == ["instrument.profile.u"]
    assert near_misses(WAVELENGTH_TYPO, paths, n=1) == [WAVELENGTH]
    assert near_misses("nothing.like.it", paths) == []
    assert did_you_mean("nothing.like.it", paths) == ""


@pytest.mark.parametrize("path, n_freed, says", [
    # the four rows of issue #265's reproduction, in its order
    (WAVELENGTH_TYPO, 0, "STAGE_PATH_UNKNOWN"),
    (WAVELENGTH, 1, "WAVELENGTH_CALIBRATION"),
    # a pattern the shipped `lab_sample_refine` carries, on a model with no
    # Stephens block: healthy, and the reason a pattern is never reported
    ("phases.*.microstrain.dof.*", 0, None),
    # a typo inside a pattern looks exactly like the row above, so it stays
    # silent too; `surprises.md` tells the caller to read `freed`
    ("phases.*.cel.*", 0, None),
])
def test_a_turn_on_that_reached_nothing_says_so_when_it_can(pattern, path, n_freed,
                                                           says):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    seen: list[dict] = []
    result = ref.fit(pattern, events=seen.append, plan=rx.RefinementPlan(
        stages=[rx.Stage("only", [path], max_iter=5)]))

    stage = result.stages[0]
    assert len(stage.freed) == n_freed
    codes = {d.code for d in result.diagnostics}
    unknown = [d for d in result.diagnostics if d.code == "STAGE_PATH_UNKNOWN"]
    if says == "STAGE_PATH_UNKNOWN":
        assert stage.unknown_paths == [path]
        assert len(unknown) == 1 and unknown[0].level == "warning"
        assert unknown[0].where == [path]
        assert f"Did you mean {WAVELENGTH!r}" in unknown[0].message
        # decided at stage start, so a watcher sees it before the budget goes
        start = next(e for e in seen if e["kind"] == "stage_start")
        assert start["data"]["unknown_paths"] == [path]
    else:
        assert stage.unknown_paths == [] and not unknown
    if says is not None:
        assert says in codes
    # a single-histogram fit has no elsewhere to have reached
    assert stage.unreached_histograms == {}
    assert "STAGE_FREED_NOTHING" not in codes


def test_a_stored_stage_record_says_nobody_looked_rather_than_nothing_missing():
    """WP-1076's rule on the two new fields: the default is not an answer.

    A result written before WP-1414 had typo'd literals freeing nothing in
    silence too, so opening it with ``[]`` would claim a check that never
    ran.  Every runner writes a value; only the default is ``None``.
    """
    old = rx.StageResult.model_validate_json(
        '{"name": "cell", "status": "converged", "n_iterations": 3, '
        '"cost_initial": 2.0, "cost_final": 1.0}')
    assert old.unknown_paths is None and old.unreached_histograms is None


def test_a_literal_repeated_across_stages_is_one_finding_naming_both(pattern):
    """Per path, not per stage: the hold's rule, for its reason."""
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("first", ["phases.*.scale", WAVELENGTH_TYPO], max_iter=5),
        rx.Stage("second", [WAVELENGTH_TYPO, "phases.0.cell.aa"], max_iter=5),
    ]))
    unknown = {d.where[0]: d for d in result.diagnostics
               if d.code == "STAGE_PATH_UNKNOWN"}
    assert set(unknown) == {WAVELENGTH_TYPO, "phases.0.cell.aa"}
    assert "Stages 'first', 'second'" in unknown[WAVELENGTH_TYPO].message
    assert "Did you mean 'phases.0.cell.a'" in unknown["phases.0.cell.aa"].message
    # the closing stage asks for every glob the plan freed, the typos too
    assert [s.unknown_paths for s in result.stages] == [
        [WAVELENGTH_TYPO], [WAVELENGTH_TYPO, "phases.0.cell.aa"],
        [WAVELENGTH_TYPO, "phases.0.cell.aa"]]


def test_a_single_stage_run_says_it_too(ref, pattern):
    """``run_stage`` builds its own ``StageResult``: the second call site."""
    result = ref.run_stage(pattern, rx.Stage("typo", [WAVELENGTH_TYPO], max_iter=5))
    assert result.stages[-1].unknown_paths == [WAVELENGTH_TYPO]
    assert [d.where for d in result.diagnostics
            if d.code == "STAGE_PATH_UNKNOWN"] == [[WAVELENGTH_TYPO]]


@pytest.mark.parametrize("path, says", [
    # B on 6f (x, 1/2, 1/2): x follows the site's one direction, y is fixed
    ("phases.0.atoms.1.x", "follows phases.0.atoms.1.dof.0"),
    ("phases.0.atoms.1.y", "is fixed by symmetry or by the model"),
    # La on 1a: no direction at all
    ("phases.0.atoms.0.z", "is fixed by symmetry or by the model"),
    ("phases.0.cell.b", "follows phases.0.cell.a"),
])
def test_a_literal_the_model_will_not_free_says_which_path_would(pattern, path, says):
    """``STAGE_PATH_UNKNOWN``'s other half: the row exists and is declined.

    The measured case was an oxygen on 16h in I4₁/amd, named as
    ``atoms.2.x``: the stage froze the site at its start and said nothing.
    """
    ref = rx.Refinement(*perturbed_models(), history=False)
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("only", ["phases.*.scale", path], max_iter=5)]))
    assert path not in result.stages[0].freed
    found = [d for d in result.diagnostics if d.code == "STAGE_PATH_NOT_FREE"]
    assert len(found) == 1 and found[0].level == "warning"
    assert found[0].where == [path]
    assert f"Stage 'only' asked for {path}, which {says}" in found[0].message
    if path == "phases.0.atoms.1.x" or path == "phases.0.atoms.1.y":
        assert found[0].suggestion.startswith(
            "Free phases.0.atoms.1.dof.* (phases.0.atoms.1.dof.0)")
    elif path == "phases.0.atoms.0.z":
        assert found[0].suggestion is None
    else:
        assert found[0].suggestion.startswith("Free phases.0.cell.a instead")
    assert not [d for d in result.diagnostics if d.code == "STAGE_PATH_UNKNOWN"]


@pytest.mark.parametrize("turn_on", [
    # the positive arm: the path the warning suggests frees the site
    ["phases.0.atoms.1.dof.*"],
    # a pattern is a sweep, and a sweep declining rows is how plans work
    ["phases.*.atoms.*.x"],
    # the shipped presets name it, and a capillary locks it
    ["instrument.geometry.sample_displacement"],
], ids=["dof-glob", "pattern", "instrument-literal"])
def test_a_path_that_is_free_or_not_a_phase_literal_stays_silent(pattern, turn_on):
    ref = rx.Refinement(*perturbed_models(), history=False)
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("only", ["phases.*.scale", *turn_on], max_iter=5)]))
    assert "STAGE_PATH_NOT_FREE" not in {d.code for d in result.diagnostics}
    if turn_on == ["phases.0.atoms.1.dof.*"]:
        assert "phases.0.atoms.1.dof.0" in result.stages[0].freed


def test_a_tied_path_beside_its_own_source_stays_silent(pattern):
    """Yue's cubic probe: ``cell.a`` and ``cell.b`` named together is a common
    spelling, and the stage frees ``a`` with ``b`` following it."""
    ref = rx.Refinement(*perturbed_models(), history=False)
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("cell", ["phases.0.scale", "phases.0.cell.a",
                          "phases.0.cell.b"], max_iter=5)]))
    assert "phases.0.cell.a" in result.stages[0].freed
    assert "STAGE_PATH_NOT_FREE" not in {d.code for d in result.diagnostics}


def test_a_users_own_tie_is_not_reported(ref, pattern):
    ref.tie_equal(BISOS)
    result = ref.run_stage(pattern, rx.Stage("b", [BISOS[1]], max_iter=5))
    assert "STAGE_PATH_NOT_FREE" not in {d.code for d in result.diagnostics}


def test_a_declined_literal_is_one_finding_naming_its_stages_and_run_stage_says_it(
        ref, pattern):
    result = rx.Refinement(*perturbed_models(), history=False).fit(
        pattern, plan=rx.RefinementPlan(stages=[
            rx.Stage("first", ["phases.*.scale", "phases.0.cell.b"], max_iter=5),
            rx.Stage("second", ["phases.*.scale", "phases.0.cell.b"], max_iter=5)]))
    found = [d for d in result.diagnostics if d.code == "STAGE_PATH_NOT_FREE"]
    assert len(found) == 1
    assert found[0].message.startswith("Stages 'first', 'second' asked for")

    single = ref.run_stage(pattern, rx.Stage("x", ["phases.0.atoms.1.x"], max_iter=5))
    assert [d.where for d in single.diagnostics
            if d.code == "STAGE_PATH_NOT_FREE"] == [["phases.0.atoms.1.x"]]


#: the hump family under WP-1102's name and under the one it retired
HUMPS = "instrument.extra_components.*"
RETIRED_HUMPS = "instrument.background_peaks.*"


def _with_a_hump():
    structure, ins = perturbed_models()
    ins.extra_components = [HumpComponent(
        position=rx.Parameter(value=30.0), fwhm=rx.Parameter(value=6.0, min=1.0),
        height=rx.Parameter(value=200.0, min=0.0))]
    return structure, ins


def test_a_retired_spelling_is_the_migrators_and_a_current_one_is_not():
    """One authority on renamed paths: ``schemas.migrate``, asked, not copied."""
    assert retired_spelling(RETIRED_HUMPS) == HUMPS
    assert retired_spelling("instrument.background_peaks.0.height") == (
        "instrument.extra_components.0.height")
    for current in (HUMPS, "phases.*.microstrain.dof.*", WAVELENGTH_TYPO):
        assert retired_spelling(current) is None, current
    # a pattern under the old word that a caller's own variable answers is
    # answered, so it is not unknown however it is spelt
    assert unknown_paths_among(["vars.background_peaks*"],
                               {"vars.background_peaks"}) == []
    assert unknown_paths_among([RETIRED_HUMPS, HUMPS, RETIRED_HUMPS],
                               {"phases.0.scale"}) == [RETIRED_HUMPS]


def test_a_glob_under_a_retired_spelling_is_named_with_the_current_one(pattern):
    """The draft's case: the plan froze a declared hump at its seed in silence.

    WP-1102 renamed ``background_peaks`` to ``extra_components``; the class and
    the attribute under the old names raise, a stored plan is migrated as it is
    read, and a glob written in code matched nothing and said nothing.  The
    literal under the old name was already reported, but pointed at
    ``instrument.background.c0``, a different parameter.
    """
    structure, ins = _with_a_hump()
    ref = rx.Refinement(structure, ins, history=False)
    literal = "instrument.background_peaks.0.height"
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("hump", [RETIRED_HUMPS, literal], max_iter=5)]))

    stage = result.stages[0]
    assert stage.freed == [] and stage.unknown_paths == [RETIRED_HUMPS, literal]
    unknown = {d.where[0]: d for d in result.diagnostics
               if d.code == "STAGE_PATH_UNKNOWN"}
    assert set(unknown) == {RETIRED_HUMPS, literal}
    assert all(d.level == "warning" for d in unknown.values())
    assert f"The current spelling is {HUMPS!r}" in unknown[RETIRED_HUMPS].message
    assert ("The current spelling is 'instrument.extra_components.0.height'"
            in unknown[literal].message)
    assert "background.c0" not in unknown[literal].message


def test_a_hump_glob_on_a_model_without_a_hump_stays_silent(pattern):
    """The negative arm: the current spelling matching nothing is a healthy plan.

    The shipped hump stage is safe in any plan for exactly this reason
    (``strategy/staged.py``), and the retired-spelling rule must not reach it.
    """
    structure, ins = perturbed_models()
    assert not ins.extra_components
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("hump", [HUMPS], max_iter=5)]))
    assert result.stages[0].freed == [] and result.stages[0].unknown_paths == []
    assert "STAGE_PATH_UNKNOWN" not in {d.code for d in result.diagnostics}


def test_the_shipped_presets_name_no_path_a_shipped_instrument_lacks():
    """The literal rule may fire only on a caller's mistake, never on ours.

    Every preset literal (``instrument.zero_shift``, the Caglioti five,
    ``sample_displacement``, the axial pair) exists on every instrument
    constructor — force-fixed where the geometry does not use it (WP-1073),
    which is exactly why a declined row is not an unknown one.
    """
    instruments = [rx.Instrument.debye_scherrer(wavelength=1.5406),
                   rx.Instrument.bragg_brentano(),
                   rx.Instrument.flat_plate_transmission(),
                   rx.Instrument.constant_wavelength_neutron(1.5),
                   rx.Instrument.constant_wavelength_neutron(1.5, harmonics=[2])]
    structure, _ = perturbed_models()
    for ins in instruments:
        table = rx.Refinement(structure, ins, history=False)._working_table()
        for name, build in PLAN_PRESETS.items():
            for stage in build().stages:
                assert table.unknown_paths(stage.turn_on) == [], (
                    name, stage.name, ins.geometry.kind)


# ----------------------------------------------------------------- PLAN_INFO
def test_plan_info_covers_every_preset_and_no_more():
    assert set(PLAN_INFO) == set(PLAN_PRESETS)


def test_plan_info_rows_are_filled_in():
    for name, info in PLAN_INFO.items():
        assert info.title and info.description and info.when_to_use, name
        assert info.modes, name
        assert set(info.modes) <= {"rietveld", "lebail", "pawley"}, name


def test_plan_info_modes_match_what_the_plan_can_free():
    """A plan claiming ``rietveld`` only must not be the one Le Bail needs.

    Weak by design — the strong statement is the presets' own turn-on lists —
    but it catches the copy-paste that would send a Le Bail caller to a plan
    that frees structural parameters the mode discards.
    """
    for name, info in PLAN_INFO.items():
        globs = {g for stage in PLAN_PRESETS[name]().stages for g in stage.turn_on}
        structural = any(".atoms." in g for g in globs)
        if structural:
            assert info.modes == ("rietveld",), name


def test_a_user_tie_whose_source_an_edit_locks_is_dropped_not_raised():
    """The *source* half of ``_apply_ties``' rule (WP-1804).

    ``set_tie`` refuses a locked source, which is right for a verb.  A stored
    tie whose source a later model edit locked used to be flattened into d; it
    must not now stop the build — a model edit never does — so it is dropped
    with the reason beside the others, and the register is reconciled.
    """
    structure, ins = perturbed_models()
    structure.phases[0].space_group = "P 1"
    ref = rx.Refinement(structure, ins, history=False)
    # alpha is free under P 1 and locked at 90° under P m -3 m
    ref.tie("phases.0.atoms.1.biso", "phases.0.cell.alpha")
    cubic = ref.structure.model_copy(deep=True)
    cubic.phases[0].space_group = "P m -3 m"
    with pytest.warns(UserWarning, match=r"atoms\.1\.biso.*source "
                                         r"phases\.0\.cell\.alpha now structurally fixed"):
        ref.edit(structure=cubic)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.biso"].tie is None
    assert ref._ties == {}


def test_replay_skips_a_recorded_tie_whose_source_is_now_fixed(pattern):
    """``replay`` and ``checkout`` must agree about one node (WP-1804).

    A node recorded before the source rule can hold a tie whose source a later
    model edit locked (main's ``set_tie`` flattened it silently).  ``replay``
    called ``set_tie`` on every recorded tie and raised; it now skips such a tie
    with a warning, as ``_apply_ties`` does — the flattened tie had an empty C
    row, so no count, value or statistic changes.
    """
    from rietx.refine import replay
    structure, ins = perturbed_models()
    structure.phases[0].space_group = "P 1"
    ref = rx.Refinement(structure, ins)
    ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=5)]))
    ref.tie("phases.0.atoms.1.biso", "phases.0.cell.alpha")
    node = ref.history[ref.history.order[-1]]
    cubic = node.state.structure.model_copy(deep=True)
    cubic.phases[0].space_group = "P m -3 m"
    # the node an old edit recorded: cubic model, the user tie still carried
    node.state = node.state.model_copy(
        update={"structure": cubic, "ties": dict(ref._ties)})
    assert node.state.ties
    with pytest.warns(UserWarning, match=r"atoms\.1\.biso.*source "
                                         r"phases\.0\.cell\.alpha now structurally fixed"):
        result = replay(ref.history, node.id, pattern)
    assert result.statistics.n_free_parameters == len(node.state.free_paths)
