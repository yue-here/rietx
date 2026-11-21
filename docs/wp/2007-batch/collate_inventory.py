"""Collate WP-2007's inventory into inventory.json (the inventory and the proposed tiers).

    .venv/bin/python docs/wp/2007-batch/collate_inventory.py              # writes inventory.json
    .venv/bin/python docs/wp/2007-batch/collate_inventory.py --skeleton   # prints what a judgement reads

Everything mechanical is derived from the tree, as WP-2005's and WP-2006's scripts do:
the codes from `docs/reference_pages.diagnostic_index()` (never a literal grep), their
raise sites, levels and guarding conditions by AST; every module-level assignment holding
a number in `indexing/`, `solve/` and `schemas/indexing.py` by AST, dicts, lists and
strings-with-numbers included, so the numbers the audit walk cannot see are listed beside
the ones it can; the functions that read each name; the comment block above each; the
default and suggestion rows of the subsystem; and every row's tier from `rietx._audit.ROWS`.

The only hand-written input is `judgements.json` beside this file: per code the condition
in words, the kind of ambiguity of its verdict (DESIGN.md § Rules, 1) and a *proposed* tier
for each part (statistic, threshold, action); per constant and default its role, what it
decides, the dataset it was measured on, and a proposed tier with the evidence. A proposal
is this WP's reading for the maintainer's batch, never a ruling: no row of the audit table
moves here. The script stops on an item with no judgement, on a judgement the tree no longer
has, and on a hand-written text cut short (WP-2006's rule).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
from docs.reference_pages import diagnostic_index  # noqa: E402
from rietx import _audit  # noqa: E402
from rietx.help import DIAGNOSTIC_HELP  # noqa: E402

SRC = REPO / "src" / "rietx"
TESTS = REPO / "tests"
#: What this WP owns: `_audit.WALKED` maps both directories to 2007, and its docstring
#: hands `schemas/indexing.py`'s rows here.
OWNED = ("indexing", "solve")
OWNED_FILES = ("schemas/indexing.py",)
#: WP-2002's batch class B13 proposed handing these to this WP, pending the maintainer's
#: ruling (the WP's Inherited): `flag_ghosts` drops a flagged line from `PeakList.usable()`.
B13_MODULE = "rietx.background.diagnostics"
B13_PREFIXES = ("GHOST_", "_ANODE_MATCH_TOL", "_KBETA")
LEVELS = {"info", "warning", "error"}
#: Modules that name every code without raising one: the audit table's ``Row("CODE", "code")``
#: and the help entries would read as positional raise sites (WP-2007 review).
NOT_RAISERS = {"rietx._audit", "rietx.help"}
KINDS = {1: "the data settle it", 2: "the data can rank it", 3: "the data cannot settle it"}
TIERS = {1, 2, 3, "invariant", "caller", "unaudited", "n/a"}
ROLES = {"threshold", "budget", "cap", "tolerance", "numerical floor", "unit", "arithmetic",
         "physics", "count", "seed", "version", "enumeration", "label", "protocol"}
CITE = re.compile(r"WP-\d{4}|#\d{3,4}\b|[A-Z][a-zà-ÿ]+(?: (?:&|and) [A-Z][a-zà-ÿ]+| et al\.)? \(?(?:19|20)\d\d")
ABBREV_STOP = re.compile(r"(?:\bet al|\bVol|\bi\.e|\be\.g|\bcf|\bca|\bvs|\bFig|\bEq|\bNo|\bTable|\bpp?)\.$")


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def owned(path: Path) -> bool:
    r = path.relative_to(SRC).as_posix()
    return r.split("/")[0] in OWNED or r in OWNED_FILES


def module_of(path: Path) -> str:
    return ("rietx." + ".".join(path.relative_to(SRC).with_suffix("").parts)).removesuffix(".__init__")


def cut(text: str) -> bool:
    t = text.rstrip()
    return (not t.endswith((".", ")", "?")) or bool(ABBREV_STOP.search(t))
            or t.count("(") > t.count(")"))


def n_numbers(node: ast.AST) -> int:
    return sum(isinstance(x, ast.Constant) and isinstance(x.value, (int, float))
               and not isinstance(x.value, bool) for x in ast.walk(node))


def shape(v: ast.AST) -> str:
    if isinstance(v, (ast.Constant, ast.UnaryOp)):
        return "scalar"
    for t, n in ((ast.Tuple, "tuple"), (ast.List, "list"), (ast.Dict, "dict"), (ast.Set, "set"),
                 (ast.BinOp, "expr"), (ast.ListComp, "comp"), (ast.DictComp, "comp")):
        if isinstance(v, t):
            return n
    if isinstance(v, ast.Call):
        return "call:" + ast.unparse(v.func)
    return type(v).__name__


def comment_above(lines: list[str], lineno: int) -> str:
    """The `#`/`#:` block directly above line `lineno` (1-based), joined."""
    out, i = [], lineno - 2
    while i >= 0 and lines[i].lstrip().startswith("#"):
        out.append(lines[i].lstrip().lstrip("#:").strip())
        i -= 1
    return " ".join(reversed(out))


class Module:
    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()
        self.tree = ast.parse(self.text)
        self.name = module_of(path)
        self.parents = {c: n for n in ast.walk(self.tree) for c in ast.iter_child_nodes(n)}

    def enclosing(self, node: ast.AST):
        conds, fn, child, p = [], None, node, self.parents.get(node)
        while p is not None:
            if isinstance(p, (ast.If, ast.While)):
                if child in p.body:
                    conds.append(ast.unparse(p.test))
                elif child in p.orelse:
                    conds.append("not (" + ast.unparse(p.test) + ")")
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn is None:
                fn = p
            child, p = p, self.parents.get(p)
        return list(reversed(conds)), fn


def modules() -> list[Module]:
    return [Module(p) for p in sorted(SRC.rglob("*.py"))]


def constants(mods: list[Module]) -> list[dict]:
    walked = _audit.constants()
    rows = {r.name: r for r in _audit.ROWS}
    out = []
    for m in mods:
        if not owned(m.path):
            continue
        for node in m.tree.body:
            if isinstance(node, ast.Assign):
                tg, val = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                tg, val = [node.target], node.value
            else:
                continue
            names = [e.id for t in tg for e in (t.elts if isinstance(t, ast.Tuple) else [t])
                     if isinstance(e, ast.Name) and not e.id.startswith("__")]
            if not names or not (n_numbers(val) or any(f"{m.name}.{nm}" in walked for nm in names)):
                continue  # a derived number the walk sees (UNCANCELLABLE_METRIC_RTOL) is kept
            above = comment_above(m.lines, node.lineno)
            for nm in names:
                full = f"{m.name}.{nm}"
                row = rows.get(full)
                out.append({"name": full, "where": f"{rel(m.path)}:{node.lineno}",
                            "shape": shape(val), "n_numbers": n_numbers(val),
                            "value": ast.unparse(val)[:160],
                            "walked_by_audit": full in walked,
                            "tier": row.tier if row else None,
                            "comment": above[:600],
                            "cites": sorted(set(CITE.findall(above)))})
    return out


def readers(mods: list[Module], full: set[str]) -> dict[str, list[str]]:
    """Every function or module/class body reading one of the constants in `full`, keyed
    by the constant's full name: in its defining module by bare name, elsewhere only through
    an import of that name or an attribute of an imported module (`engines.NAME`, or
    `rietx.indexing.engines.NAME` after a plain `import`), so two modules' same bare name
    never merge (WP-2007 review). A function that binds the bare name itself (argument,
    assignment, loop target) reads its local, not the constant (PR #1591 review)."""
    out: dict[str, set[str]] = defaultdict(set)

    def resolve_from(m: Module, node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module or ""
        base = m.name.split(".")
        if not m.path.name == "__init__.py":
            base = base[:-1]
        base = base[:len(base) - (node.level - 1)]
        return ".".join(base + ([node.module] if node.module else []))

    def outside_functions(node: ast.AST):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            yield ch
            yield from outside_functions(ch)

    modnames = {m.name for m in mods}
    for m in mods:
        names = {f.rsplit(".", 1)[1]: f for f in full if f.rsplit(".", 1)[0] == m.name}
        aliases: dict[str, str] = {}
        roots: set[str] = set()
        for node in ast.walk(m.tree):
            if isinstance(node, ast.ImportFrom):
                src = resolve_from(m, node)
                for a in node.names:
                    if f"{src}.{a.name}" in full:
                        names[a.asname or a.name] = f"{src}.{a.name}"
                    elif f"{src}.{a.name}" in modnames:
                        aliases[a.asname or a.name] = f"{src}.{a.name}"
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in modnames and a.asname:
                        aliases[a.asname] = a.name
                    elif a.asname is None:
                        # `import rietx.indexing.engines` binds `rietx`; the constant is
                        # read as the dotted chain `rietx.indexing.engines.NAME`
                        roots.add(a.name.split(".")[0])

        def dotted(n: ast.AST) -> str | None:
            parts = []
            while isinstance(n, ast.Attribute):
                parts.append(n.attr)
                n = n.value
            if not isinstance(n, ast.Name):
                return None
            return ".".join([n.id, *reversed(parts)])

        def hit(n: ast.AST) -> str | None:
            if isinstance(n, ast.Name):
                return names.get(n.id)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                tm = aliases.get(n.value.id)
                if tm and f"{tm}.{n.attr}" in full:
                    return f"{tm}.{n.attr}"
            if isinstance(n, ast.Attribute):
                chain = dotted(n.value)
                if (chain and chain.split(".")[0] in roots and chain in modnames
                        and f"{chain}.{n.attr}" in full):
                    return f"{chain}.{n.attr}"
            return None

        def local_names(fn: ast.AST) -> set[str]:
            """Names a function binds itself (arguments, assignments, loop and `with`
            targets), less those it declares global: a read of one is a local, not the
            module's constant."""
            bound = {a.arg for a in ast.walk(fn.args) if isinstance(a, ast.arg)}
            declared: set[str] = set()
            for n in ast.walk(fn):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    bound.add(n.id)
                elif isinstance(n, (ast.Global, ast.Nonlocal)):
                    declared.update(n.names)
            return bound - declared

        here = m.name.removeprefix("rietx.")
        for n in outside_functions(m.tree):
            k = hit(n)
            # the defining assignment itself is a Store, not a read
            if k and not (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)):
                out[k].add(f"{here}.<module or class body>")
        for fn in ast.walk(m.tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local = local_names(fn)
                # defaults and decorators are evaluated in the enclosing scope
                outer = {id(x) for e in (*fn.args.defaults, *fn.args.kw_defaults,
                                         *fn.decorator_list) if e is not None
                         for x in ast.walk(e)}
                for n in ast.walk(fn):
                    if isinstance(n, ast.Name) and n.id in local and id(n) not in outer:
                        continue
                    k = hit(n)
                    if k:
                        out[k].add(f"{here}.{fn.name}")
    return {k: sorted(v) for k, v in out.items()}


def raise_sites(mods: list[Module], wanted: set[str], const_short: set[str]) -> list[dict]:
    out = []
    for m in mods:
        if m.name in NOT_RAISERS:
            continue
        for node in ast.walk(m.tree):
            if not isinstance(node, ast.Call):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            c = kw.get("code")
            code = c.value if isinstance(c, ast.Constant) and c.value in wanted else None
            if code is None:
                code = next((a.value for a in node.args[:3] if isinstance(a, ast.Constant)
                             and a.value in wanted), None)
            if code is None:
                continue
            lv = kw.get("level")
            level = (lv.value if isinstance(lv, ast.Constant) else "computed" if lv is not None
                     else next((a.value for a in node.args[:3] if isinstance(a, ast.Constant)
                                and a.value in LEVELS), None))
            conds, fn = m.enclosing(node)
            names = ({n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} if fn else set())
            out.append({"code": code, "where": f"{rel(m.path)}:{node.lineno}", "level": level,
                        "function": fn.name if fn else None, "guards": conds,
                        "constants_in_function": sorted(names & const_short)})
    return out


def tests_naming(codes: set[str]) -> dict[str, int]:
    count: Counter = Counter()
    for p in TESTS.rglob("test_*.py"):
        t = p.read_text(encoding="utf-8", errors="replace")
        for c in codes:
            if re.search(rf"\b{c}\b", t):
                count[c] += 1
    return dict(count)


def collect():
    idx = diagnostic_index()
    wanted = {c for c, v in idx.items()
              if any(f.split("/")[1] in OWNED or f.removeprefix("rietx/") in OWNED_FILES
                     for f in v["files"])}
    mods = modules()
    consts = constants(mods)
    short = {c["name"].rsplit(".", 1)[-1] for c in consts}
    sites = raise_sites(mods, wanted, short)
    rd = readers(mods, {c["name"] for c in consts})
    rows = {r.name: r for r in _audit.ROWS}
    defaults = [r for r in _audit.ROWS if r.kind == "default"
                and _audit.DEFAULT_SEATS.get(r.name.split(":")[0]) == 2007]
    sugg = [r for r in _audit.ROWS if r.kind == "suggestion"
            and (r.name.split(".suggestion")[0] in wanted
                 or r.name.startswith(("rietx.indexing.", "rietx.solve.")))]
    b13 = [r for r in _audit.ROWS if r.kind == "constant" and r.name.startswith(B13_MODULE + ".")
           and r.name.rsplit(".", 1)[-1].startswith(B13_PREFIXES)]
    actions = [r for r in _audit.ROWS if r.kind == "action" and "indexing" in r.name]
    return idx, wanted, sites, consts, rd, rows, defaults, sugg, b13, actions


def skeleton() -> None:
    idx, wanted, sites, consts, rd, rows, defaults, sugg, b13, actions = collect()
    by: dict[str, list] = defaultdict(list)
    for s in sites:
        by[s["code"]].append(s)
    out = {"codes": {c: {"tier": rows[c].tier if c in rows else None,
                         "explanation": getattr(DIAGNOSTIC_HELP.get(c), "description", "")[:400],
                         "sites": [{k: s[k] for k in ("where", "level", "function", "guards",
                                                      "constants_in_function")} for s in by[c]]}
                     for c in sorted(wanted)},
           "constants": {c["name"]: {**{k: c[k] for k in ("where", "value", "tier", "comment",
                                                            "walked_by_audit")},
                                     "read_by": rd.get(c["name"], [])[:12]}
                         for c in consts},
           "defaults": {r.name: {"value": repr(r.value), "tier": r.tier} for r in defaults}}
    print(json.dumps(out, indent=1, ensure_ascii=False))


def build() -> dict:
    idx, wanted, sites, consts, rd, rows, defaults, sugg, b13, actions = collect()
    judg = json.loads((HERE / "judgements.json").read_text(encoding="utf-8"))
    jc, jk, jd = judg["codes"], judg["constants"], judg["defaults"]
    missing = ([c for c in wanted if c not in jc] + [c["name"] for c in consts if c["name"] not in jk]
               + [r.name for r in defaults if r.name not in jd])
    gone = ([c for c in jc if c not in wanted] + [k for k in jk if k not in {c["name"] for c in consts}]
            + [k for k in jd if k not in {r.name for r in defaults}])
    if missing or gone:
        sys.exit(f"no judgement for: {sorted(missing)}\njudgement for an item the tree no longer has: {sorted(gone)}")
    texts = ({f"codes:{k}:{f}": v[f] for k, v in jc.items() for f in ("condition", "evidence")}
             | {f"constants:{k}:{f}": v[f] for k, v in jk.items() for f in ("decides", "evidence")}
             | {f"defaults:{k}:{f}": v[f] for k, v in jd.items() for f in ("decides", "evidence")}
             | {f"{g}:{k}:question": v["question"] for g, jj in (("codes", jc), ("constants", jk),
                                                                ("defaults", jd))
                for k, v in jj.items() if v.get("question")})
    bad = [k for k, t in texts.items() if cut(t)]
    bad += [f"codes:{k}:kind" for k, v in jc.items() if v["kind"] not in KINDS]
    bad += [f"codes:{k}:{p}" for k, v in jc.items() for p in ("statistic", "threshold", "action")
            if v[p] not in TIERS]
    bad += [f"constants:{k}:role" for k, v in jk.items() if v["role"] not in ROLES]
    bad += [f"constants:{k}:proposed" for k, v in jk.items() if v["proposed"] not in TIERS]
    bad += [f"defaults:{k}:proposed" for k, v in jd.items() if v["proposed"] not in TIERS]
    if bad:
        sys.exit(f"hand-written entries cut short or outside their vocabulary: {bad}")
    tests = tests_naming(wanted)
    by: dict[str, list] = defaultdict(list)
    for s in sites:
        by[s["code"]].append(s)
    codes = []
    for c in sorted(wanted):
        j = jc[c]
        codes.append({"name": c, "kind_of_row": "code",
                      "tier_now": rows[c].tier if c in rows else None,
                      "levels": sorted({s["level"] for s in by[c] if s["level"]}) or sorted(idx[c]["levels"]),
                      "sites": [{k: s[k] for k in ("where", "level", "function", "guards",
                                                   "constants_in_function")} for s in by[c]],
                      "files": sorted(idx[c]["files"]),
                      "suggestion_sites": next((r.value for r in sugg
                                                if r.name == f"{c}.suggestion"), 0),
                      "tests_naming_it": tests.get(c, 0),
                      **{k: j[k] for k in ("condition", "kind", "statistic", "threshold", "action",
                                           "measured_on", "evidence")},
                      "question": j.get("question", "")})
    crows = []
    for c in consts:
        j = jk[c["name"]]
        crows.append({**{k: c[k] for k in ("name", "where", "shape", "value", "n_numbers",
                                          "walked_by_audit", "cites")},
                      "tier_now": c["tier"],
                      "read_by": rd.get(c["name"], []),
                      **{k: j[k] for k in ("role", "decides", "measured_on", "proposed", "evidence")},
                      "question": j.get("question", "")})
    drows = [{"name": r.name, "value": repr(r.value), "tier_now": r.tier,
              **{k: jd[r.name][k] for k in ("decides", "proposed", "evidence")},
              "question": jd[r.name].get("question", "")} for r in defaults]
    counts = {
        "codes": len(codes),
        "codes_by_tier_now": dict(Counter(str(r["tier_now"]) for r in codes)),
        "codes_by_kind": dict(Counter(r["kind"] for r in codes)),
        "code_sites": sum(len(r["sites"]) for r in codes),
        "codes_by_proposed_action_tier": dict(Counter(str(r["action"]) for r in codes)),
        "constants": len(crows),
        "constants_seen_by_audit_walk": sum(r["walked_by_audit"] for r in crows),
        "constants_by_tier_now": dict(Counter(str(r["tier_now"]) for r in crows)),
        "constants_by_role": dict(Counter(r["role"] for r in crows)),
        "constants_by_proposed_tier": dict(Counter(str(r["proposed"]) for r in crows)),
        "constants_with_no_reader": sum(not r["read_by"] for r in crows),
        "defaults": len(drows),
        "defaults_by_tier_now": dict(Counter(str(r["tier_now"]) for r in drows)),
        "defaults_by_proposed_tier": dict(Counter(str(r["proposed"]) for r in drows)),
        "suggestion_rows": len(sugg),
        "suggestion_rows_by_tier_now": dict(Counter(str(r.tier) for r in sugg)),
        "action_rows": [r.name for r in actions],
        "b13_constants_pending_handover": len(b13),
    }
    return {"counts": counts, "codes": codes, "constants": crows, "defaults": drows,
            "suggestions": [{"name": r.name, "sites": r.value, "tier_now": r.tier} for r in sugg],
            "b13_pending": [{"name": r.name, "value": repr(r.value), "tier_now": r.tier} for r in b13]}


def main() -> None:
    if "--skeleton" in sys.argv:
        skeleton()
        return
    inv = build()
    (HERE / "inventory.json").write_text(json.dumps(inv, indent=1, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
    print(json.dumps(inv["counts"], indent=1))


if __name__ == "__main__":
    main()
