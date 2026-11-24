"""Build the misuse-rule probe: a toy package in rietx's shape, three rule variants.

v0: today's Rule 4 API test.   v3: + the misuse clause as prose (option 3).
v4: + the misuse clause with a test obligation, meta-tests, and mode checked at entry (option 4).

Run dirs: runs/<variant>-hold, runs/<variant>-exclude (implementers), runs/<variant>-review.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
RUNS = ROOT / "runs"

RULES_BASE = """# Design rules (minirefine)

minirefine is a toy refinement package: a parameter table, staged plans, a fit. These rules
govern every change. Cite them by number.

1. **Decisions.** The package acts alone only where every competent user would act the same
   way, and records that it did. Where the data can rank alternatives it ranks them. Otherwise
   it reports the number and stops.
2. **A new output.** An unmeasured value is `None`, never a default that reads as an answer.
3. **A new API.** It takes the shape the surface already has: a verb in, a typed result out, a
   raise on failure. The signature and docstring are enough for a first call to be right.{extra}
4. **Convention.** A change takes the shape the package already uses for the same job. One shape
   sets fewer traps for a person or an agent learning the package.
5. **Tests.** A change lands with tests, and `python -m pytest tests -q` passes.
"""

EXTRA_V3 = """
   It names its likeliest misuse. That misuse is defined out of existence where rule 1's first
   kind allows, and otherwise raises at the first bad call, naming the fix: level 5 or above on
   Russell's (2008) misuse scale. (The scale: 10 impossible to get wrong; 9 the compiler won't
   let you; 8 the compiler warns; 7 the obvious use is probably right; 6 the name tells you how;
   5 do it wrong and it always breaks at runtime; 4 follow convention and you'll get it right;
   3 read the docs; 2 read the implementation; down to -7 the obvious use is wrong and -10
   impossible to get right.) A warning is for a request that changed less than it named.
   Silence is for the rows a sweep skips, where the sweep changed something."""

EXTRA_V4 = """
   It lands with a misuse test: in `tests/test_misuse.py`, one `test_misuse_<verb>` per public
   verb. The test makes the likeliest wrong call and asserts that it raises before any work is
   done, with a message naming the argument and the fix. A mistake the package can remove
   without guessing (rule 1's first kind) is removed instead, and the test asserts the right
   result. A warning is for a request that changed less than it named. Silence is for the rows
   a sweep skips, where the sweep changed something. `tests/test_meta.py` enforces the
   per-verb test and checks that every `Literal`-typed argument is refused at entry."""

INIT = '''"""minirefine: a toy refinement package (a parameter table, staged plans, a fit)."""
from .model import Entry, Model
from .fitting import PLANS, Pattern, Result, StageRecord, fit

__all__ = ["Entry", "Model", "PLANS", "Pattern", "Result", "StageRecord", "fit"]
'''

MODEL = '''"""The parameter table.  Paths are dot-separated; globs use fnmatch."""
from __future__ import annotations

import difflib
import fnmatch
from dataclasses import dataclass


@dataclass
class Entry:
    path: str
    value: float
    vary: bool = False
    locked: bool = False      # fixed by symmetry; never freed
    tie: str | None = None    # follows another path's value; never freed itself


def is_literal(glob: str) -> bool:
    return not any(c in glob for c in "*?[")


class Model:
    """A parameter table."""

    def __init__(self, entries: list[Entry]):
        self.entries = {e.path: e for e in entries}

    @classmethod
    def example(cls) -> "Model":
        return cls([Entry("scale", 1.0), Entry("zero_shift", 0.0),
                    Entry("cell.a", 5.0), Entry("cell.b", 5.0, tie="cell.a"),
                    Entry("cell.c", 7.0), Entry("cell.alpha", 90.0, locked=True),
                    Entry("biso.O1", 0.5), Entry("biso.Si1", 0.4),
                    Entry("background.c0", 10.0), Entry("background.c1", 0.0)])

    def _refuse_unknown_literals(self, globs: list[str]) -> None:
        for g in globs:
            if is_literal(g) and g not in self.entries:
                near = difflib.get_close_matches(g, list(self.entries), n=1)
                hint = f"; did you mean {near[0]!r}?" if near else ""
                raise ValueError(f"unknown parameter path {g!r}{hint}")

    def set_vary(self, path_globs: str | list[str], vary: bool = True) -> list[str]:
        """Free (or fix) every parameter matching ``path_globs``; return the paths changed.

        A literal path the model lacks raises ``ValueError`` naming the nearest path.  A glob
        that matches nothing is silent, since a plan's globs reach parameters a model may not
        declare.  Locked and tied entries never match.  Note that ``fit`` runs a plan, and each
        stage of a plan replaces the vary flags.
        """
        globs = [path_globs] if isinstance(path_globs, str) else list(path_globs)
        self._refuse_unknown_literals(globs)
        changed = []
        for e in self.entries.values():
            if e.locked or e.tie is not None:
                continue
            if any(fnmatch.fnmatchcase(e.path, g) for g in globs) and e.vary != vary:
                e.vary = vary
                changed.append(e.path)
        return changed

    def set_values(self, values: dict[str, float]) -> None:
        """Set values by literal path; an unknown path raises before anything is set."""
        self._refuse_unknown_literals(list(values))
        for p, v in values.items():
            self.entries[p].value = float(v)

    def free_paths(self) -> list[str]:
        return [p for p, e in self.entries.items() if e.vary]
'''

FIT = '''"""The fit: a plan runs stages, and each stage solves for its free parameters."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from .model import Model

#: Each stage lists the globs it frees.  A stage *replaces* the vary flags: anything it does
#: not name is fixed for that stage.
PLANS: dict[str, list[list[str]]] = {
    "default": [["scale", "background.*"],
                ["scale", "background.*", "zero_shift", "cell.*"],
                ["*"]],
    "profile_only": [["scale", "background.*", "zero_shift"]],
}
MODES = ("rietveld", "lebail")

#: Work counter: the number of stage solves run in this process.
SOLVE_CALLS = 0


@dataclass
class Pattern:
    two_theta: list[float]
    intensity: list[float]
    targets: dict[str, float]   # toy stand-in for the data: where each parameter would land

    @classmethod
    def example(cls) -> "Pattern":
        tt = [10.0 + 0.1 * i for i in range(401)]          # 10 to 50 degrees
        return cls(tt, [100.0] * len(tt),
                   {"scale": 2.0, "zero_shift": 0.01, "cell.a": 5.1, "cell.c": 7.2,
                    "biso.O1": 0.8, "biso.Si1": 0.6, "background.c0": 12.0,
                    "background.c1": -0.5})


@dataclass
class StageRecord:
    index: int
    free: list[str]


@dataclass
class Result:
    mode: str
    values: dict[str, float]
    stages: list[StageRecord]
    n_points: int                      # channels fitted
    diagnostics: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"Result.mode must be one of {MODES}, got {self.mode!r}")


def _solve(model: Model, data: Pattern, free: list[str]) -> None:
    global SOLVE_CALLS
    SOLVE_CALLS += 1
    time.sleep(0.02)
    for p in free:
        if p in data.targets:
            e = model.entries[p]
            e.value += 0.5 * (data.targets[p] - e.value)
    for e in model.entries.values():
        if e.tie is not None:
            e.value = model.entries[e.tie].value


def fit(model: Model, data: Pattern, *, mode: Literal["rietveld", "lebail"] = "rietveld",
        plan: str = "default") -> Result:
    """Run ``plan``'s stages on ``model`` against ``data``; return the result."""{mode_check}
    if plan not in PLANS:
        raise ValueError(f"unknown plan {plan!r}; available: {sorted(PLANS)}")
    stages = []
    for i, turn_on in enumerate(PLANS[plan]):
        for e in model.entries.values():
            e.vary = False
        model.set_vary(turn_on, True)
        free = model.free_paths()
        _solve(model, data, free)
        stages.append(StageRecord(i, free))
    return Result(mode, {p: e.value for p, e in model.entries.items()}, stages,
                  len(data.two_theta))
'''

MODE_CHECK = '''
    if mode not in MODES:
        raise ValueError(f"fit(mode=) takes one of {list(MODES)}, got {mode!r}")'''

TEST_BASIC = '''import minirefine as mr


def test_default_plan_runs_three_stages():
    m = mr.Model.example()
    r = mr.fit(m, mr.Pattern.example())
    assert len(r.stages) == 3
    assert "cell.b" not in r.stages[-1].free          # tied
    assert r.values["cell.b"] == r.values["cell.a"]


def test_set_vary_returns_changed_paths():
    m = mr.Model.example()
    assert m.set_vary("cell.*") == ["cell.a", "cell.c"]
'''

TEST_MISUSE = '''"""One test_misuse_<verb> per public verb (rule 3)."""
import pytest

import minirefine as mr
from minirefine import fitting as fitmod


def test_misuse_set_vary():
    with pytest.raises(ValueError, match="did you mean 'cell.a'"):
        mr.Model.example().set_vary("cell.aa")


def test_misuse_set_values():
    with pytest.raises(ValueError, match="did you mean 'scale'"):
        mr.Model.example().set_values({"scael": 1.0})


def test_misuse_free_paths():
    # takes no argument: nothing to misuse
    assert mr.Model.example().free_paths() == []


def test_misuse_fit():
    before = fitmod.SOLVE_CALLS
    with pytest.raises(ValueError, match="mode"):
        mr.fit(mr.Model.example(), mr.Pattern.example(), mode="rietvled")
    assert fitmod.SOLVE_CALLS == before
'''

TEST_META = '''"""Meta-tests for rule 3: a misuse test per public verb, Literal arguments refused at entry."""
import inspect
import typing
from pathlib import Path

import pytest

import minirefine as mr
from minirefine import fitting as fitmod


def public_verbs():
    out = {}
    for name in mr.__all__:
        obj = getattr(mr, name)
        if inspect.isfunction(obj):
            out[name] = obj
        elif inspect.isclass(obj) and name == "Model":
            for m, f in inspect.getmembers(obj, inspect.isfunction):
                if not m.startswith("_") and m != "example":
                    out[m] = f
    return out


#: How to call each verb with good arguments.  A verb with a Literal argument needs a row.
EXAMPLES = {
    "fit": lambda **kw: mr.fit(mr.Model.example(), mr.Pattern.example(), **kw),
}


def test_every_public_verb_has_a_misuse_test():
    text = (Path(__file__).parent / "test_misuse.py").read_text(encoding="utf-8")
    missing = [v for v in public_verbs() if f"def test_misuse_{v}(" not in text]
    assert not missing, f"add test_misuse_<verb> to tests/test_misuse.py for: {missing}"


@pytest.mark.parametrize("verb", sorted(public_verbs()))
def test_literal_arguments_are_refused_at_entry(verb):
    f = public_verbs()[verb]
    hints = typing.get_type_hints(f)
    literal = [p for p, t in hints.items() if typing.get_origin(t) is typing.Literal]
    if not literal:
        return
    assert verb in EXAMPLES, f"add a row for {verb!r} to EXAMPLES in tests/test_meta.py"
    for p in literal:
        before = fitmod.SOLVE_CALLS
        with pytest.raises(ValueError, match=p):
            EXAMPLES[verb](**{p: "not-a-member"})
        assert fitmod.SOLVE_CALLS == before, f"{verb}({p}=) did work before refusing"
'''

TASK_HOLD = """Add `Model.hold(path_globs)` and `Model.unhold(path_globs)` to minirefine.

A user who wants a parameter kept fixed for a whole fit cannot get that today: `set_vary(p,
False)` is undone by the next stage of a plan, because each stage replaces the vary flags. A
held parameter stays fixed through every stage of `fit`, even when a stage's globs match it,
until `unhold` releases it. Both verbs take a glob or a list of globs, like `set_vary`, and
return the paths whose hold state they changed."""

TASK_EXCLUDE = """Add excluded regions to `minirefine.fit`.

`fit(model, data, *, exclude=..., exclude_policy=...)`. `exclude` is a list of 2θ intervals
`(lo, hi)` in degrees; channels inside an interval are left out of the fit. `exclude_policy`
chooses how: `"drop"` (the default) removes the channels, `"zero_weight"` keeps them with zero
weight. Either way `Result.n_points` is the number of channels the fit used (for
`"zero_weight"`, the channels with non-zero weight). No exclusion by default."""

FLAWED_HOLD_MODEL = '''
    def hold(self, path_globs: str | list[str]) -> list[str]:
        """Hold every parameter matching ``path_globs`` fixed through every stage of a fit."""
        held = getattr(self, "_held", set())
        changed = []
        for g in path_globs:
            for p in self.entries:
                if fnmatch.fnmatchcase(p, g) and p not in held:
                    held.add(p)
                    changed.append(p)
        self._held = held
        return changed

    def unhold(self, path_globs: str | list[str]) -> list[str]:
        """Release a hold."""
        held = getattr(self, "_held", set())
        changed = [p for p in list(held) for g in path_globs if fnmatch.fnmatchcase(p, g)]
        held.difference_update(changed)
        return changed
'''

FLAWED_HOLD_FIT_OLD = "        model.set_vary(turn_on, True)\n"
FLAWED_HOLD_FIT_NEW = ("        model.set_vary(turn_on, True)\n"
                       "        for p in getattr(model, \"_held\", ()):\n"
                       "            model.entries[p].vary = False\n")

FLAWED_HOLD_TEST = '''

def test_hold_survives_a_plan():
    m = mr.Model.example()
    m.hold(["zero_shift"])
    r = mr.fit(m, mr.Pattern.example())
    assert all("zero_shift" not in s.free for s in r.stages)
    assert r.values["zero_shift"] == 0.0


def test_unhold_releases():
    m = mr.Model.example()
    m.hold(["zero_shift"])
    m.unhold(["zero_shift"])
    r = mr.fit(m, mr.Pattern.example())
    assert "zero_shift" in r.stages[1].free
'''


def write_pkg(d: Path, variant: str) -> None:
    pkg = d / "minirefine"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(INIT)
    (pkg / "model.py").write_text(MODEL)
    (pkg / "fitting.py").write_text(FIT.replace("{mode_check}", MODE_CHECK if variant == "v4" else ""))
    tests = d / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text(
        "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parents[1]))\n")
    (tests / "test_basic.py").write_text(TEST_BASIC)
    if variant == "v4":
        (tests / "test_misuse.py").write_text(TEST_MISUSE)
        (tests / "test_meta.py").write_text(TEST_META)
    extra = {"v0": "", "v3": EXTRA_V3, "v4": EXTRA_V4}[variant]
    (d / "RULES.md").write_text(RULES_BASE.replace("{extra}", extra))


def main() -> None:
    if RUNS.exists():
        shutil.rmtree(RUNS)
    for v in ("v0", "v3", "v4"):
        for task, text in (("hold", TASK_HOLD), ("exclude", TASK_EXCLUDE)):
            d = RUNS / f"{v}-{task}"
            write_pkg(d, v)
            (d / "TASK.md").write_text(text + "\n")
        d = RUNS / f"{v}-review"
        write_pkg(d, v)
        model = (d / "minirefine" / "model.py").read_text()
        (d / "minirefine" / "model.py").write_text(
            model.replace("    def free_paths(self)", FLAWED_HOLD_MODEL.lstrip("\n") + "\n    def free_paths(self)"))
        fit = (d / "minirefine" / "fitting.py").read_text()
        (d / "minirefine" / "fitting.py").write_text(fit.replace(FLAWED_HOLD_FIT_OLD, FLAWED_HOLD_FIT_NEW))
        with open(d / "tests" / "test_basic.py", "a") as fh:
            fh.write(FLAWED_HOLD_TEST)
        (d / "TASK.md").write_text(TASK_HOLD + "\n")
    print("built", sorted(p.name for p in RUNS.iterdir()))


if __name__ == "__main__":
    main()
