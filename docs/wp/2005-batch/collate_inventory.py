"""Collate WP-2005's inventory into inventory.json (part 1; no tiers).

    .venv/bin/python docs/wp/2005-batch/collate_inventory.py              # writes inventory.json
    .venv/bin/python docs/wp/2005-batch/collate_inventory.py --skeleton   # prints what a judgement reads

Everything mechanical is derived from the tree, as WP-2006's script does: the codes
from `docs/reference_pages.diagnostic_index()` (never a literal grep), their raise
sites, levels and guarding conditions by AST, the module-level names each raising
function reads, every numeric literal inside a raising function, the code's audit
rows, its `rietx.help.DIAGNOSTIC_HELP` entry and the tests that name it.

The only judgements are in `judgements.json` beside this file: per code the
condition in words and the kind of ambiguity its verdict has (DESIGN.md § Rules, 1);
per literal its role.  The script stops on a code or literal with no judgement,
and on a judgement for one the tree no longer has, so part 2 sees a change in the
tree as a failure, not a silent omission.
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
from docs.reference_pages import diagnostic_index  # noqa: E402
from rietx import _audit  # noqa: E402
from rietx.help import DIAGNOSTIC_HELP  # noqa: E402

SRC = REPO / "src" / "rietx"
TESTS = REPO / "tests"
#: The five codes the WP takes from outside refine.py (its Context, "Five codes no seam names").
OUTSIDE = {
    "BACKGROUND_ORDER_AT_CAP": "background/select.py",
    "BRINDLEY_OUTSIDE_REGIME": "optimize/qpa.py",
    "MICROABSORPTION_SKIPPED": "optimize/qpa.py",
    "DECLARED_RANGE_RESTORED": "schemas/migrate.py",
    "DECLARED_RANGE_NOT_RESTORED": "schemas/migrate.py",
}
LEVELS = {"info", "warning", "error"}
#: Literal values never listed: identities of arithmetic (WP-2005 counts the rest).
TRIVIAL = {0, 1, -1}
#: The kinds of ambiguity, DESIGN.md § Rules, 1.
KINDS = {1: "the data settle it", 2: "the data can rank it", 3: "the data cannot settle it"}
ROLES = {"threshold", "unit", "arithmetic", "numerical floor", "listing cap", "count"}
ABBREV_STOP = re.compile(r"(?:\bet al|\bi\.e|\be\.g|\bcf|\bca|\bvs|\bFig|\bEq|\bNo|\bpp?)\.$")


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def cut(text: str) -> bool:
    """A hand-written text cut short (WP-2006's rule): it must end in a full stop or a
    closing bracket that is not an abbreviation's, with no "(" left unclosed."""
    t = text.rstrip()
    return (not t.endswith((".", ")")) or bool(ABBREV_STOP.search(t))
            or t.count("(") > t.count(")"))


def number(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool))


class Module:
    """One source file: its tree, parents, module-level numbers and imported names."""

    def __init__(self, path: Path):
        self.path = path
        self.rel = rel(path)
        self.tree = ast.parse(path.read_text(encoding="utf-8"), filename=self.rel)
        self.parents = {c: n for n in ast.walk(self.tree) for c in ast.iter_child_nodes(n)}
        mod = "rietx." + ".".join(path.relative_to(SRC).with_suffix("").parts)
        self.mod = mod.removesuffix(".__init__")
        self.local: dict[str, int] = {}
        self.imported: dict[str, str] = {}
        for node in self.tree.body:
            for name in _audit._assigned(node) if isinstance(node, (ast.Assign, ast.AnnAssign)) else []:
                self.local[name] = node.lineno
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and node.level and node.module is not None:
                base = self.mod.rsplit(".", node.level)[0]
                for a in node.names:
                    self.imported[a.asname or a.name] = f"{base}.{node.module}.{a.name}"

    def functions(self) -> dict:
        """Module-level functions and methods of module-level classes, by name;
        a name defined twice (two classes) is left out, since a call cannot say which."""
        seen: dict[str, list] = defaultdict(list)
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seen[node.name].append(node)
            elif isinstance(node, ast.ClassDef):
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        seen[m.name].append(m)
        return {k: v[0] for k, v in seen.items() if len(v) == 1}

    def function_of(self, node: ast.AST):
        while node in self.parents:
            node = self.parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node
        return None

    def guards(self, node: ast.AST) -> list[str]:
        """The conditions under which a raise site is reached: every enclosing ``if``,
        ``while`` or conditional expression, and every earlier ``if …:`` in an enclosing
        block whose body leaves it (``return``, ``continue``, ``break``, ``raise``),
        written ``not (…)``.  A ``try`` it sits in is not a condition and is not listed."""
        conds, child, p = [], node, self.parents.get(node)
        while p is not None:
            for field in ("body", "orelse", "finalbody", "handlers"):
                block = getattr(p, field, None)
                if isinstance(block, list) and child in block:
                    for st in reversed(block[:block.index(child)]):
                        if (isinstance(st, ast.If) and st.body and isinstance(
                                st.body[-1], (ast.Return, ast.Continue, ast.Break, ast.Raise))):
                            conds.append("not (" + ast.unparse(st.test) + ")")
            if isinstance(p, (ast.If, ast.While)):
                if child in p.body:
                    conds.append(ast.unparse(p.test))
                elif child in p.orelse:
                    conds.append("not (" + ast.unparse(p.test) + ")")
            elif isinstance(p, ast.IfExp):
                if child is p.body:
                    conds.append(ast.unparse(p.test))
                elif child is p.orelse:
                    conds.append("not (" + ast.unparse(p.test) + ")")
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
                break
            child, p = p, self.parents.get(p)
        return list(reversed(conds))

    def names_read(self, fn) -> dict[str, str]:
        """UPPER_CASE names a function reads: module-level here, or imported."""
        out = {}
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and n.id.isupper() and len(n.id) > 1:
                if n.id in self.local:
                    out[n.id] = f"{self.mod}.{n.id}"
                elif n.id in self.imported:
                    out[n.id] = self.imported[n.id]
            elif (isinstance(n, ast.Attribute) and n.attr.isupper() and len(n.attr) > 1
                  and isinstance(n.value, ast.Name) and n.value.id in self.imported):
                # ``lm.SLOW_DESCENT_ESD``: an attribute of an imported module
                out[f"{n.value.id}.{n.attr}"] = f"{self.imported[n.value.id]}.{n.attr}"
        return dict(sorted(out.items()))

    def helpers(self, fn) -> list:
        """Functions of this file ``fn`` calls by name (``helper(...)``, ``self.helper(...)``)."""
        defs, out = self.functions(), []
        for n in ast.walk(fn):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            name = (f.id if isinstance(f, ast.Name) else
                    f.attr if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                    and f.value.id == "self" else None)
            if name in defs and defs[name] is not fn and defs[name] not in out:
                out.append(defs[name])
        return out

    def literals(self, fn) -> list[dict]:
        """Every numeric literal in a function but the identities and subscripts."""
        out = []
        for x in ast.walk(fn):
            if not number(x) or x.value in TRIVIAL:
                continue
            par = self.parents[x]
            if isinstance(par, (ast.Subscript, ast.Slice)):
                continue
            if isinstance(par, ast.UnaryOp) and isinstance(self.parents[par], (ast.Subscript, ast.Slice)):
                continue
            q, in_compare = x, False
            while q in self.parents and not isinstance(self.parents[q], ast.stmt):
                q = self.parents[q]
                in_compare |= isinstance(q, ast.Compare)
            inner = par
            while isinstance(inner, (ast.BinOp, ast.UnaryOp)) and inner in self.parents and isinstance(
                    self.parents[inner], (ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call)):
                inner = self.parents[inner]
            out.append({"line": x.lineno, "value": x.value, "in_comparison": in_compare,
                        "expression": ast.unparse(inner)[:160]})
        return sorted(out, key=lambda d: (d["line"], d["expression"]))


def row_for(path: str, rows: dict) -> str | None:
    """The audit row a name read in a function stands for.  The import path as written
    first; where the name was re-exported (``refine`` takes ``PHASE_SUPPORT_SIGMA`` from
    ``model.forward``, whose row is ``schemas.plan``'s), the one constant row with the same
    leaf whose object is the very object the path resolves to."""
    if path in rows:
        return path
    leaf = path.rsplit(".", 1)[-1]
    try:
        obj = _audit.resolve(path)
    except (ImportError, AttributeError):
        return None
    hits = []
    for name, row in rows.items():
        if row.kind == "constant" and name.rsplit(".", 1)[-1] == leaf:
            try:
                if _audit.resolve(name) is obj:
                    hits.append(name)
            except (ImportError, AttributeError):
                continue
    return hits[0] if len(hits) == 1 else None


def literal_key(fn_name: str, lit: dict) -> str:
    """A literal's key in judgements.json: function, value and its expression, so a line
    shift leaves the key alone and a changed expression asks again."""
    return f"{fn_name}|{lit['value']!r}|{lit['expression']}"


def raise_sites(mod: Module, wanted: set[str]) -> list[dict]:
    out = []
    for node in ast.walk(mod.tree):
        if not isinstance(node, ast.Call):
            continue
        kw = {k.arg: k.value for k in node.keywords}
        c = kw.get("code")
        if not (isinstance(c, ast.Constant) and c.value in wanted):
            continue
        lv = kw.get("level")
        level = (lv.value if isinstance(lv, ast.Constant) else
                 "computed: " + ast.unparse(lv) if lv is not None else None)
        fn = mod.function_of(node)
        out.append({"code": c.value, "where": f"{mod.rel}:{node.lineno}", "level": level,
                    "function": fn.name if fn else None, "_fn": fn, "_mod": mod,
                    "guards": mod.guards(node), "has_suggestion": "suggestion" in kw})
    return out


def tests_naming(codes: list[str]) -> dict[str, dict]:
    """Per code, the test files and test functions (body or decorators) whose text names it."""
    pat = {c: re.compile(rf"\b{c}\b") for c in codes}
    out = {c: {"files": set(), "functions": 0} for c in codes}
    for path in sorted(TESTS.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        hit = [c for c in codes if pat[c].search(text)]
        if not hit:
            continue
        lines = text.splitlines()
        tree = ast.parse(text)
        for c in hit:
            out[c]["files"].add(rel(path))
        # a module-level name bound to the code (``CODE = "X"``) stands for it in a test
        alias = {c: re.compile(rf"\b{c}\b") for c in hit}
        for node in tree.body:
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                    and node.value.value in hit):
                names = "|".join(t.id for t in node.targets if isinstance(t, ast.Name))
                if names:
                    alias[node.value.value] = re.compile(rf"\b(?:{node.value.value}|{names})\b")
        # and so does a helper of the same file whose text names it, called by a test
        for node in tree.body:
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not node.name.startswith("test")):
                seg = "\n".join(lines[node.lineno - 1:node.end_lineno])
                for c in hit:
                    if alias[c].search(seg):
                        alias[c] = re.compile(rf"(?:{alias[c].pattern})|\b{node.name}\(")
        for fn in ast.walk(tree):
            if not (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name.startswith("test")):
                continue
            first = min([d.lineno for d in fn.decorator_list] + [fn.lineno])
            seg = "\n".join(lines[first - 1:fn.end_lineno])
            for c in hit:
                if alias[c].search(seg):
                    out[c]["functions"] += 1
    return {c: {"files": sorted(v["files"]), "test_functions": v["functions"]} for c, v in out.items()}


def first_sentence(text: str) -> str:
    text = " ".join(text.split())
    m = re.search(r"(?<!\be\.g)(?<!\bi\.e)(?<!\bcf)(?<!\bvs)\.(\s|$)", text)
    return text[:m.end()].strip() if m else text


def collect():
    idx = diagnostic_index()
    in_refine = sorted(c for c, v in idx.items() if "rietx/refine.py" in v["files"])
    codes = sorted(set(in_refine) | set(OUTSIDE))
    mods = {f: Module(SRC / f) for f in ["refine.py", *sorted(set(OUTSIDE.values()))]}
    sites = [s for f, m in mods.items()
             for s in raise_sites(m, set(in_refine) if f == "refine.py"
                                  else {c for c, ff in OUTSIDE.items() if ff == f})]
    by_code: dict[str, list[dict]] = defaultdict(list)
    for s in sites:
        by_code[s["code"]].append(s)
    return idx, codes, by_code


def build(idx, codes, by_code, judg, *, strict: bool = True):
    rows = {r.name: r for r in _audit.ROWS}
    tests = tests_naming(codes)
    missing = [c for c in codes if c not in by_code]
    if missing:
        sys.exit(f"no keyword raise site found for: {missing}")
    seen_fns: dict[str, tuple] = {}
    for c in codes:
        for s in by_code[c]:
            if s["_fn"] is not None:
                seen_fns[f"{s['_mod'].rel}:{s['_fn'].name}"] = (s["_mod"], s["_fn"])
    # one level down: a function of the same file a raising function calls by name
    # (``helper(...)`` or ``self.helper(...)``), where a statistic's literal can sit
    for key, (mod, fn) in list(seen_fns.items()):
        for h in mod.helpers(fn):
            seen_fns.setdefault(f"{mod.rel}:{h.name}", (mod, h))
    lits = {}
    for key, (mod, fn) in sorted(seen_fns.items()):
        for lit in mod.literals(fn):
            k = literal_key(fn.name, lit)
            if k in lits:  # the same expression twice (``a ** 2 + b ** 2``): one judgement
                lits[k]["lines"] = sorted(set(lits[k]["lines"]) | {lit["line"]})
                continue
            lits[k] = {"function": key, "lines": [lit["line"]], "value": lit["value"],
                       "in_comparison": lit["in_comparison"], "expression": lit["expression"]}
    problems = []
    if strict:
        problems += [f"code {c}: no judgement" for c in codes if c not in judg["codes"]]
        problems += [f"code {c}: judged but not in the tree" for c in judg["codes"] if c not in codes]
        problems += [f"literal {k}: no judgement" for k in lits if k not in judg["literals"]]
        problems += [f"literal {k}: judged but not in the tree" for k in judg["literals"] if k not in lits]
        for c, j in judg["codes"].items():
            if j.get("kind") not in KINDS:
                problems.append(f"code {c}: kind must be one of {sorted(KINDS)}")
            for f in ("condition", "kind_reason"):
                if cut(j.get(f, "")):
                    problems.append(f"code {c}: {f} cut short")
        for k, j in judg["literals"].items():
            if j.get("role") not in ROLES:
                problems.append(f"literal {k}: role must be one of {sorted(ROLES)}")
            if cut(j.get("reason", "")):
                problems.append(f"literal {k}: reason cut short")
        if problems:
            sys.exit("\n".join(problems))

    out_codes = []
    for c in codes:
        ss = by_code[c]
        help_entry = DIAGNOSTIC_HELP.get(c)
        row, srow = rows.get(c), rows.get(c + ".suggestion")
        names, via_helper = {}, {}
        for s in ss:
            if s["_fn"] is not None:
                names.update(s["_mod"].names_read(s["_fn"]))
                for h in s["_mod"].helpers(s["_fn"]):
                    for n, p in s["_mod"].names_read(h).items():
                        if n not in names:
                            via_helper[n] = h.name
                            names[n] = p
        consts = {}
        for n, p in names.items():
            hit = row_for(p, rows)
            if hit is not None and rows[hit].kind == "constant":
                consts[n] = hit
        rec = {
            "name": c,
            "sites": [{"where": s["where"], "function": s["function"], "level": s["level"],
                       "guards": s["guards"], "suggestion": s["has_suggestion"]} for s in ss],
            "levels": sorted({s["level"] for s in ss if s["level"]}),
            "constants_read": {n: {"row": p, "tier": str(rows[p].tier), "value": rows[p].value,
                                   **({"via": via_helper[n]} if n in via_helper else {})}
                               for n, p in sorted(consts.items())},
            "explanation": (first_sentence(help_entry.description) if help_entry else None),
            "audit_row": None if row is None else {"tier": str(row.tier), "response": row.response,
                                                   "ambiguity": row.ambiguity},
            "suggestion_row": None if srow is None else {"tier": str(srow.tier)},
            "on_unaudited_baseline": c in _audit.UNAUDITED_BASELINE,
            "on_response_baseline": c in _audit.RESPONSE_BASELINE,
            "tests": tests[c],
        }
        j = judg["codes"].get(c)
        if j is not None:
            # ``.get`` because ``--skeleton`` builds over a judgement still being written
            rec.update({"condition": j.get("condition"), "kind": j.get("kind"),
                        "kind_name": KINDS.get(j.get("kind")), "kind_reason": j.get("kind_reason")})
            if j.get("note"):
                rec["note"] = j["note"]
        out_codes.append(rec)
    out_lits = []
    for k, lit in lits.items():
        j = judg["literals"].get(k, {})
        out_lits.append({"key": k, **lit, **({"role": j.get("role"), "reason": j.get("reason")} if j else {})})
    return out_codes, out_lits


def main() -> None:
    judg_path = HERE / "judgements.json"
    judg = (json.loads(judg_path.read_text(encoding="utf-8")) if judg_path.exists()
            else {"codes": {}, "literals": {}})
    idx, codes, by_code = collect()
    if "--skeleton" in sys.argv:
        out_codes, out_lits = build(idx, codes, by_code, judg, strict=False)
        for r in out_codes:
            print(f"## {r['name']} kind={r.get('kind')} levels={r['levels']} row={r['audit_row']} tests={r['tests']['test_functions']}")
            for s in r["sites"]:
                print(f"   {s['where']} {s['function']} guards={s['guards']}")
            print(f"   consts={ {n: (v['value'], v['tier']) for n, v in r['constants_read'].items()} }")
            print(f"   help: {r['explanation']}")
        print("## literals")
        for lit in out_lits:
            print(f"   {lit['key']}  [{lit['function']}:{lit['lines']}] cmp={lit['in_comparison']}")
        return
    out_codes, out_lits = build(idx, codes, by_code, judg)
    roles = Counter(lit["role"] for lit in out_lits)
    counts = {
        "codes_total": len(out_codes),
        "codes_in_refine_py": sum(any(s["where"].startswith("src/rietx/refine.py") for s in r["sites"])
                                  for r in out_codes),
        "codes_outside_refine_py": sum(r["name"] in OUTSIDE for r in out_codes),
        "raise_sites": sum(len(r["sites"]) for r in out_codes),
        "codes_by_level": dict(Counter("/".join(r["levels"]) for r in out_codes)),
        "codes_by_kind": {KINDS[k]: n for k, n in sorted(Counter(r["kind"] for r in out_codes).items())},
        "codes_by_audit_tier": dict(Counter(r["audit_row"]["tier"] if r["audit_row"] else "no row"
                                            for r in out_codes)),
        "codes_on_unaudited_baseline": sum(r["on_unaudited_baseline"] for r in out_codes),
        "codes_with_a_suggestion_site": sum(any(s["suggestion"] for s in r["sites"]) for r in out_codes),
        "codes_no_test_names": sum(r["tests"]["test_functions"] == 0 for r in out_codes),
        "named_constants_read": len({v["row"] for r in out_codes for v in r["constants_read"].values()}),
        "literals_total": len(out_lits),
        "literals_by_role": dict(sorted(roles.items())),
    }
    doc = {"counts": counts, "codes": out_codes, "literals": out_lits}
    (HERE / "inventory.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n",
                                         encoding="utf-8")
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main()
