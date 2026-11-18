"""The scalar-chain memo in ``CompiledModel.phase_peaks`` (WP-1109).

``_peak_chain_column`` re-runs the whole of ``phase_peaks`` once per Jacobian
column, at a θ where most of its blocks did not move: a column perturbing a
Biso leaves the cell block alone, one perturbing a profile width leaves both
the cell block and |F|² alone.  Each block is therefore memoised on the small
set of decoded scalars it reads, reused iff they compare bit-equal — the
contract ``_cached_fcj_nodes`` already uses one rank down.

The failure mode this file is written against is a **key narrower than its
block**: the memo then hands back a stale array and the fit quietly optimises
the wrong model.  So the main test does not check the keys by reading them.  It
perturbs every parameter the table carries, one at a time, and demands the
memoised model agree bit-for-bit with a model that has no cache at all.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    AnisoU,
    Atom,
    Cell,
    Phase,
    PreferredOrientation,
    StephensStrain,
    Structure,
)


def _rich_models():
    """A model that exercises every block the memo covers at once.

    Bragg-Brentano so the displacement and transparency shifts are live, a Cu
    Kα doublet so the per-line blocks have more than one entry, and a first
    phase carrying preferred orientation, anisotropic strain and an
    anisotropic ADP.  A single-block model would let a narrow key pass.
    """
    rutile_cell = Cell(a=Parameter(value=4.5941), b=Parameter(value=4.5941),
        c=Parameter(value=2.9589), alpha=Parameter(value=90.0),
        beta=Parameter(value=90.0), gamma=Parameter(value=90.0))
    rutile = Phase(
        name="rutile", space_group="P42/mnm", cell=rutile_cell,
        atoms=[
            # anisotropic, so the |F|² key has to reach the six U^ij too
            Atom(label="Ti", species="Ti", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0),
                 biso=Parameter(value=0.5, vary=False),
                 aniso=AnisoU.isotropic(0.006, rutile_cell)),
            Atom(label="O", species="O", x=Parameter(value=0.3053),
                 y=Parameter(value=0.3053), z=Parameter(value=0.0),
                 biso=Parameter(value=0.7)),
        ],
        preferred_orientation=PreferredOrientation(axis=(0, 0, 1),
                                                   r=Parameter(value=0.9)),
        microstrain=StephensStrain.isotropic(800.0, rutile_cell),
    )
    rutile.scale.value = 1e-3
    rutile.lor_size.value = 0.02
    rutile.gauss_size.value = 0.01

    fluorite = Phase(
        name="fluorite", space_group="Fm-3m",
        cell=Cell(a=Parameter(value=5.4626), b=Parameter(value=5.4626),
                  c=Parameter(value=5.4626), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[
            Atom(label="Ca", species="Ca", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0),
                 biso=Parameter(value=0.6)),
            Atom(label="F", species="F", x=Parameter(value=0.25),
                 y=Parameter(value=0.25), z=Parameter(value=0.25),
                 biso=Parameter(value=0.9)),
        ],
    )
    fluorite.scale.value = 5e-4

    structure = Structure(phases=[rutile, fluorite])
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 8e-3
    ins.profile.u.value = 2e-3
    ins.profile.x.value = 5e-3
    ins.profile.y.value = 4e-3
    ins.geometry.sample_displacement.value = 0.01
    ins.geometry.sample_transparency.value = 0.005
    tt = np.arange(20.0, 90.0, 0.05)
    pattern = rx.PatternData(two_theta=tt.tolist(),
                             intensity=np.full(tt.shape, 100.0).tolist())
    return structure, ins, pattern


@pytest.fixture(scope="module")
def rich():
    structure, ins, pattern = _rich_models()
    table = ParameterTable(structure, ins)
    cached = compile_model(structure, ins, pattern, mode="rietveld")
    plain = compile_model(structure, ins, pattern, mode="rietveld")
    for cp in plain.phases:          # the same model with the memo denied
        cp.scalar_cache = None
    return cached, plain, table


@pytest.fixture
def fresh_memo(rich):
    """``rich`` with every memo slot emptied on entry **and on exit**.

    ``rich`` is module-scoped, so a test that pins an expansion point would
    otherwise hand its pins to every test after it in file order.
    """
    cached = rich[0]
    for cp in cached.phases:
        cp.scalar_cache.clear()
    yield rich
    for cp in cached.phases:
        cp.scalar_cache.clear()


def _same(a, b) -> bool:
    return all(np.array_equal(x, y)
               for pa, pb in zip(a, b, strict=True)
               for x, y in zip(pa, pb, strict=True))


def test_the_memo_is_allocated_and_actually_used(rich):
    cached, plain, table = rich
    assert all(cp.scalar_cache == {} for cp in cached.phases)
    values = table.decode(table.x0())
    cached.phase_peaks(0, values)
    filled = cached.phases[0].scalar_cache
    # every block this model exercises has a slot
    assert set(filled) == {"cell", "f2", "po", "aniso", "pos", "widths",
                           "lp", "abs"}
    assert all(cp.scalar_cache is None for cp in plain.phases)


def _paths(table):
    return [e.path for e in table.entries]


def test_every_parameter_defeats_the_memo_it_should(rich):
    """The one that matters.  For each parameter in turn: prime the memo at the
    base point, perturb that parameter alone, and demand the memoised model
    agree bit-for-bit with a model that has no memo.

    A key too narrow for its block fails here and nowhere else — the arrays
    returned would be the base point's, which is a plausible-looking answer to
    every tolerance-based check.  Written over the whole table rather than a
    chosen list, so a parameter added later is covered on arrival.
    """
    cached, plain, table = rich
    base = table.decode(table.x0())
    paths = _paths(table)
    assert len(paths) > 40, f"fixture too thin to discriminate ({len(paths)})"

    for path in paths:
        for ip in range(len(cached.phases)):
            perturbed = dict(base)
            v = perturbed[path]
            perturbed[path] = v + (1e-4 * abs(v) if v else 1e-4)
            cached.phase_peaks(ip, base)          # prime at the base point
            got = cached.phase_peaks(ip, perturbed)
            want = plain.phase_peaks(ip, perturbed)
            assert _same(got, want), (
                f"stale memo for phase {ip} after perturbing {path!r} — some "
                f"block's key does not read it")


def test_a_repeated_call_returns_the_same_numbers(rich):
    """A hit must be a reuse, not a re-derivation: equal inputs give bit-equal
    outputs either way, which is what keeps the backend goldens identical."""
    cached, plain, table = rich
    values = table.decode(table.x0())
    first = cached.phase_peaks(0, values)
    second = cached.phase_peaks(0, values)
    assert _same(first, second)
    assert _same(first, plain.phase_peaks(0, values))


def test_a_whole_fit_is_bit_identical_with_the_memo_denied():
    """End to end, because the per-call check above cannot see an error that
    only compounds: a full staged refinement with the memo and without it must
    reach the same numbers, not merely close ones."""
    structure, ins, pattern = _rich_models()
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile", ["instrument.profile.w", "instrument.profile.u"]),
        rx.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])

    def run(deny_memo: bool):
        import rietx.model.forward as fwd

        original = fwd.compile_model
        if deny_memo:
            def no_memo(*args, **kwargs):
                model = original(*args, **kwargs)
                for cp in model.phases:
                    cp.scalar_cache = None
                return model
            fwd.compile_model = no_memo
        try:
            s = structure.model_copy(deep=True)
            i = ins.model_copy(deep=True)
            return rx.Refinement(s, i).fit(pattern, plan=plan)
        finally:
            fwd.compile_model = original

    with_memo = run(False)
    without = run(True)
    assert with_memo.statistics.rwp == without.statistics.rwp
    for a, b in zip(with_memo.parameters, without.parameters, strict=True):
        assert a.path == b.path
        assert a.value == b.value, a.path
        assert a.stderr == b.stderr, a.path


def test_memoised_arrays_are_read_only(rich):
    """Before the memo every call allocated its own arrays, so a consumer
    writing into one hurt nobody.  Now the same array is shared across calls,
    ``phase_peaks`` is public, and an in-place write would poison every later
    evaluation of that phase without raising anything.  Freezing costs nothing
    per call and turns that into a ValueError naming the write."""
    cached, plain, table = rich
    values = table.decode(table.x0())
    pos, w1, w2, intensity = cached.phase_peaks(0, values)[0]
    for arr, name in ((pos, "position"), (w1, "w1"), (w2, "w2")):
        assert not arr.flags.writeable, name
        with pytest.raises(ValueError):
            arr[0] = 0.0
    # the intensity is rebuilt every call and carries no such constraint
    assert intensity.flags.writeable
    # and a model without the memo hands back ordinary writeable arrays
    assert plain.phase_peaks(0, values)[0][0].flags.writeable


# -- the key is a thunk, and why (WP-1109) --------------------------------

def test_the_memo_never_builds_its_key_off_the_numpy_path(rich, monkeypatch):
    """Every memo key is built by calling ``float()`` on decoded values, and
    under a trace those values are tracers where ``float()`` raises.  So the
    key must be computed **only** when the memo is live — which is why
    ``_memo`` takes a thunk rather than a tuple.

    Passing the key itself evaluated it at the call site, before the backend
    test inside ``_memo``, and took the entire jax matrix down (21 rows across
    ``test_backend_jax`` and ``test_cross_backend``) on a change whose numpy
    runs were green, because a ``[dev]``-only venv skips every jax row.  Pinned
    here on numpy so the contract cannot be tidied back into an eager tuple by
    someone who cannot run the jax rows either.
    """
    import rietx.model.forward as fwd

    cached, plain, _table = rich

    def exploding_key():
        raise AssertionError("memo key built off the numpy path")

    # (a) no cache allocated at all
    assert plain.phases[0].scalar_cache is None
    assert plain._memo(plain.phases[0], "cell", exploding_key,
                       lambda: "built") == "built"

    # (b) cache allocated, but the active backend is not numpy — the case that
    # broke, reached here without needing jax installed
    class _NotNumpy:
        name = "jax"

    monkeypatch.setattr(fwd, "get_backend", lambda: _NotNumpy())
    assert cached.phases[0].scalar_cache is not None
    assert cached._memo(cached.phases[0], "cell", exploding_key,
                        lambda: "built") == "built"


def test_the_memo_does_build_its_key_when_it_is_live(rich):
    """The other side of it: on numpy with a cache, the key is built and used,
    so the test above cannot pass by the memo simply never running."""
    cached, _plain, _table = rich
    built = []

    def counted_key():
        built.append(1)
        return (1.0, 2.0)

    assert cached._memo(cached.phases[0], "probe", counted_key,
                        lambda: "first") == "first"
    assert len(built) == 1
    # same key ⇒ a hit, and the thunk is consulted again to find that out
    assert cached._memo(cached.phases[0], "probe", counted_key,
                        lambda: "second") == "first"
    assert len(built) == 2


def test_an_alternation_between_two_states_stops_rebuilding(rich):
    """The WP-1121 shape: a Jacobian column asks for the expansion point, one
    perturbed state, the expansion point again, and so on.

    One key per slot turns that into a rebuild on *every* call — the memo
    answers nothing while still paying for its key — and it is not a corner
    case: the column seam hit 63.6 % of its lookups at depth 1 on the trigger
    cold fit, against 72.9 % for a cache with no bound at all.

    Reuse is asserted by **object identity**, not by value: a rebuilt block
    would carry the same numbers (every block here is a deterministic
    function of its key), so an equality check would pass for the cache that
    is not working, which is exactly the bug.
    """
    cached, _plain, table = rich
    base = table.decode(table.x0())
    other = dict(base)
    other["phases.0.cell.a"] = base["phases.0.cell.a"] * 1.001

    first_base = cached.phase_peaks(0, base)
    first_other = cached.phase_peaks(0, other)
    for _ in range(4):
        again_base = cached.phase_peaks(0, base)
        again_other = cached.phase_peaks(0, other)
        # position and both widths come straight out of memoised blocks
        for il in range(len(first_base)):
            for k in (0, 1, 2):
                assert again_base[il][k] is first_base[il][k], \
                    f"the base arm was rebuilt (line {il}, slot {k})"
                assert again_other[il][k] is first_other[il][k], \
                    f"the perturbed arm was rebuilt (line {il}, slot {k})"


def test_the_recent_trail_is_bounded_and_evicts_its_oldest_key(fresh_memo):
    """The bound is real, and that is the point of it.

    The keys are decoded θ, so an unbounded map grows an entry per parameter
    vector a fit visits — thousands — which is a leak, not a cache.  Off the
    expansion point (nothing pinned here: no ``derivative_bases`` ran) one
    state more than ``_MEMO_DEPTH`` costs the oldest key rather than joining
    it.
    """
    from rietx.model.forward import _MEMO_DEPTH

    cached, _plain, table = fresh_memo
    base = table.decode(table.x0())
    first_base = cached.phase_peaks(0, base)
    for step in range(1, _MEMO_DEPTH + 1):
        other = dict(base)
        other["phases.0.cell.a"] = base["phases.0.cell.a"] * (1 + 1e-3 * step)
        cached.phase_peaks(0, other)          # base is now the oldest key
    held = cached.phases[0].scalar_cache["cell"]
    assert held.pin is None
    assert len(held.recent) == _MEMO_DEPTH
    back = cached.phase_peaks(0, base)
    assert back[0][0] is not first_base[0][0], \
        "a state past the bound did not evict, so the cache is unbounded"


def test_the_lookup_scans_every_key_it_holds(fresh_memo, monkeypatch):
    """WP-1945: the lookup compared ``held[0]`` and ``held[1]`` and nothing
    else, whatever ``_MEMO_DEPTH`` said, so a deeper memo held keys it could
    never return — and WP-1121's depth-8 measurement, which built exactly the
    blocks depth 2 did, could not have come out any other way.

    Here the depth is raised to four and the key asked for is the oldest of
    them, a position the two-compare lookup could not reach.
    """
    import rietx.model.forward as fwd

    monkeypatch.setattr(fwd, "_MEMO_DEPTH", 4)
    cached, _plain, table = fresh_memo
    base = table.decode(table.x0())
    first_base = cached.phase_peaks(0, base)
    for step in (1, 2, 3):
        other = dict(base)
        other["phases.0.cell.a"] = base["phases.0.cell.a"] * (1 + 1e-3 * step)
        cached.phase_peaks(0, other)
    assert [k for k, _v in cached.phases[0].scalar_cache["cell"].recent][-1] \
        == _cell_key(cached, base)
    again = cached.phase_peaks(0, base)
    assert again[0][0] is first_base[0][0], \
        "a key fourth in the list was rebuilt rather than found"


def _cell_key(model, values):
    cell = tuple(float(values[f"phases.0.cell.{k}"])
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    return cell + tuple(float(x) for x in model.line_lambdas(values))


def test_two_cell_columns_cannot_evict_the_expansion_point(fresh_memo, monkeypatch):
    """WP-1945's case: a phase with two cell columns.

    ``derivative_bases`` builds the expansion point's peaks; the Jacobian then
    perturbs ``cell.a``, then ``cell.c``, and the next column of the same
    phase — a width, which moves no cell — wants the expansion point's cell
    block again.  Two keys deep and unpinned it was gone by then, so that
    column rebuilt d, 2θ and |F|² at a state the memo had already built
    (129 of 172 ``lor_size`` columns on the trigger fit).  Pinned, it hits.

    Reuse is asserted on the builders themselves, counted, and by object
    identity on the positions; a rebuilt block carries the same numbers, so
    an equality check would pass for the memo that is not working.
    """
    import rietx.model.forward as fwd

    cached, _plain, table = fresh_memo
    base = table.decode(table.x0())
    cached.derivative_bases(base)                # pins the expansion point
    first = cached.phase_peaks(0, base)
    for path in ("phases.0.cell.a", "phases.0.cell.c"):
        moved = dict(base)
        moved[path] = base[path] * 1.001
        cached.phase_peaks(0, moved)

    built = {"cell": 0, "f2": 0}
    cell_block, total_f2 = fwd.CompiledModel._cell_block, fwd.CompiledModel._total_f2

    def counted_cell(self, *a, **k):
        built["cell"] += 1
        return cell_block(self, *a, **k)

    def counted_f2(self, *a, **k):
        built["f2"] += 1
        return total_f2(self, *a, **k)

    monkeypatch.setattr(fwd.CompiledModel, "_cell_block", counted_cell)
    monkeypatch.setattr(fwd.CompiledModel, "_total_f2", counted_f2)
    width = dict(base)
    width["phases.0.lor_size"] = base["phases.0.lor_size"] * 1.001
    peaks = cached.phase_peaks(0, width)
    assert built == {"cell": 0, "f2": 0}, \
        f"the expansion point was evicted by two cell columns: {built}"
    for il in range(len(first)):
        assert peaks[il][0] is first[il][0], f"positions rebuilt (line {il})"


def test_the_next_expansion_point_takes_the_pin(fresh_memo):
    """An accepted step: the solver evaluates the residual at a trial point,
    then the next Jacobian expands there.  ``derivative_bases`` finds the
    trial's blocks on the recent trail and pins them without a rebuild, and
    the old expansion point leaves the pin."""
    cached, _plain, table = fresh_memo
    base = table.decode(table.x0())
    cached.derivative_bases(base)
    trial = dict(base)
    trial["phases.0.cell.a"] = base["phases.0.cell.a"] * 1.001
    at_trial = cached.phase_peaks(0, trial)          # the residual's call
    held = cached.phases[0].scalar_cache["cell"]
    assert held.pin[0] == _cell_key(cached, base)
    cached.derivative_bases(trial)
    assert held.pin[0] == _cell_key(cached, trial)
    assert all(k != _cell_key(cached, trial) for k, _v in held.recent)
    assert cached.phase_peaks(0, trial)[0][0] is at_trial[0][0]


def test_the_slots_only_a_magnetic_phase_uses_keep_their_pin(monkeypatch):
    """WP-1945, from the review of #1603: a magnetic phase whose second
    family is built runs ``phase_peaks`` twice inside ``derivative_bases``,
    once per component, and the pin governs ``f2mag`` and ``widths_mag`` as
    well as the slots the two calls share.

    The shared slots hold because both components send them the same key,
    so the second call hits the pin the first one set.  A component-dependent
    term in a shared key would make the two calls replace each other's pin on
    every Jacobian and silently undo the gain, so this asserts the outcome:
    after two cell columns of both components, a column that moves none of
    these blocks rebuilds nothing on either component, and every slot still
    holds the pin ``derivative_bases`` set.
    """
    import rietx.model.forward as fwd
    from tests.test_magnetic_width import SIZE, _mnf2, _state

    model, _table, base = _state(_mnf2(size=SIZE), moving=None)
    assert model.mag_split(0)
    cp = model.phases[0]
    model.derivative_bases(base)                 # pins the expansion point
    assert {"f2mag", "widths_mag"} <= set(cp.scalar_cache)
    pinned = {slot: held.pin for slot, held in cp.scalar_cache.items()}
    for path in ("phases.0.cell.a", "phases.0.cell.c"):
        moved = dict(base)
        moved[path] = base[path] * 1.001
        for component in (0, 1):
            model.phase_peaks(0, moved, component=component)

    built = {"cell": 0, "f2": 0, "f2mag": 0, "widths": 0, "widths_mag": 0}
    cell_block = fwd.CompiledModel._cell_block
    nuclear_f2 = fwd.CompiledModel._nuclear_f2
    magnetic_f2 = fwd.CompiledModel._magnetic_f2
    width_block = fwd.CompiledModel._width_block

    def counted_cell(self, *a, **k):
        built["cell"] += 1
        return cell_block(self, *a, **k)

    def counted_nuclear(self, *a, **k):
        built["f2"] += 1
        return nuclear_f2(self, *a, **k)

    def counted_magnetic(self, *a, **k):
        built["f2mag"] += 1
        return magnetic_f2(self, *a, **k)

    def counted_widths(self, *a, **k):
        built["widths_mag" if k.get("magnetic") else "widths"] += 1
        return width_block(self, *a, **k)

    monkeypatch.setattr(fwd.CompiledModel, "_cell_block", counted_cell)
    monkeypatch.setattr(fwd.CompiledModel, "_nuclear_f2", counted_nuclear)
    monkeypatch.setattr(fwd.CompiledModel, "_magnetic_f2", counted_magnetic)
    monkeypatch.setattr(fwd.CompiledModel, "_width_block", counted_widths)
    scale = dict(base)
    scale["phases.0.scale"] = base["phases.0.scale"] * 1.001
    for component in (0, 1):
        model.phase_peaks(0, scale, component=component)
    assert built == dict.fromkeys(built, 0), \
        f"two cell columns evicted the magnetic expansion point: {built}"
    assert all(pin is not None for pin in pinned.values()), \
        sorted(slot for slot, pin in pinned.items() if pin is None)
    for slot, held in cp.scalar_cache.items():
        assert held.pin is pinned[slot], f"slot {slot!r} lost its pin"
