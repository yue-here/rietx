"""Collate WP-2006's inventory into inventory.json (part 1 of #1058; no tiers).

    .venv/bin/python docs/wp/2006-batch/collate_inventory.py

Everything mechanical is derived from the tree: the codes from
`docs/reference_pages.diagnostic_index()` (never a literal grep), their raise sites
by AST, the module-level numbers of `io/` and `crystallography/` by AST (dicts,
lists and arrays included), the GUI's HTTP error names by AST.  The only judgement is
`judgements.json` beside this file (act or judgement per code, role and what each
constant decides).  The script stops on a code or constant with no judgement, so
part 2 sees a new one as a failure, not a silent omission.
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

SRC = REPO / "src" / "rietx"
SHAPE = re.compile(r"[A-Z][A-Z0-9_]+")
LEVELS = {"info", "warning", "error"}
HELPERS = {  # codes raised through a helper that takes `code=` and builds the Diagnostic
    "written_neutral_diagnostics": "src/rietx/crystallography/scattering.py",
    "rhombohedral_restated_diagnostic": "src/rietx/crystallography/symmetry.py",
}


ABBREV_STOP = re.compile(r"(?:\bet al|\bVol|\bi\.e|\be\.g|\bcf|\bca|\bvs|\bFig|\bEq|\bNo|\bTable|\bpp?)\.$")


def cut_texts(judg: dict) -> list[str]:
    """Hand-written texts that stop mid-sentence (WP-2006 review, round 2).

    Covers every constant's `decides`, every code's `condition` and every reader
    decision; a code's `note` is a label, not a sentence.  A text is whole when it ends in a full stop or a closing bracket and the full
    stop is not an abbreviation's.  A cut one (at a length cap, a semicolon, "et al.",
    "i.e.", "p.", an unclosed bracket) reads as a half reason in a ruling, so part 2 must never inherit one.
    """
    texts = ({f"constants:{k}": v["decides"] for k, v in judg["constants"].items()}
             | {f"codes:{k}": v["condition"] for k, v in judg["codes"].items()}
             | {f"reader_decisions:{r['name']}": r["decides"]
                for r in judg["reader_decisions"]})
    # an opening bracket left unclosed is a cut; a stray ")" (the half-open "[0, 1)") is not
    return [k for k, t in texts.items()
            if not t.rstrip().endswith((".", ")")) or ABBREV_STOP.search(t.rstrip())
            or t.count("(") > t.count(")")]


def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def numbers(node: ast.AST) -> int:
    return sum(isinstance(x, ast.Constant) and isinstance(x.value, (int, float))
               and not isinstance(x.value, bool) for x in ast.walk(node))


def shape(v: ast.AST) -> str:
    if isinstance(v, ast.Constant):
        return "scalar"
    if isinstance(v, ast.UnaryOp):
        return "scalar"
    names = {ast.Tuple: "tuple", ast.List: "list", ast.Dict: "dict", ast.Set: "set",
             ast.BinOp: "expr", ast.ListComp: "comp", ast.DictComp: "comp"}
    for t, n in names.items():
        if isinstance(v, t):
            return n
    if isinstance(v, ast.Call):
        return "call:" + ast.unparse(v.func)
    return type(v).__name__


def sites(wanted: set[str]) -> list[dict]:
    out = []
    for path in sorted(SRC.rglob("*.py")):
        r = rel(path)
        if "/io/" not in r and "/crystallography/" not in r:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}

        def guards(n):
            conds, fn, child, p = [], None, n, parents.get(n)
            while p is not None:
                if isinstance(p, (ast.If, ast.While)):
                    if child in p.body:
                        conds.append(ast.unparse(p.test))
                    elif child in p.orelse:
                        conds.append("not (" + ast.unparse(p.test) + ")")
                if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn is None:
                    fn = p
                child, p = p, parents.get(p)
            return list(reversed(conds)), fn

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            code, via = None, "code="
            c = kw.get("code")
            if isinstance(c, ast.Constant) and isinstance(c.value, str) and SHAPE.fullmatch(c.value):
                code = c.value
            else:
                for a in node.args[:3]:
                    if isinstance(a, ast.Constant) and a.value in wanted:
                        code, via = a.value, "positional"
            if code is None or code not in wanted:
                continue
            lv = kw.get("level")
            level = (lv.value if isinstance(lv, ast.Constant) else
                     "computed" if lv is not None else None)
            if level is None:
                level = next((a.value for a in node.args[:3] if isinstance(a, ast.Constant)
                              and a.value in LEVELS), "computed" if via == "positional" else None)
            conds, fn = guards(node)
            callee = ast.unparse(node.func)
            helper = callee.rsplit(".", 1)[-1] in HELPERS
            out.append({"code": code, "where": f"{r}:{node.lineno}", "level": level,
                        "function": fn.name if fn else None, "guards": conds,
                        "call": callee, "helper_call": helper,
                        "names_in_function": sorted({n.id for n in ast.walk(fn)
                                                     if isinstance(n, ast.Name)}) if fn else []})
    return out


def constants() -> list[dict]:
    seen = set(_audit.constants())
    out = []
    for d in ("io", "crystallography"):
        for p in sorted((SRC / d).rglob("*.py")):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mod = "rietx." + ".".join(p.relative_to(SRC).with_suffix("").parts)
            mod = mod.removesuffix(".__init__")
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    tg, val = node.targets, node.value
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    tg, val = [node.target], node.value
                else:
                    continue
                names = [e.id for t in tg for e in (t.elts if isinstance(t, ast.Tuple) else [t])
                         if isinstance(e, ast.Name) and not e.id.startswith("__")]
                if not names or not numbers(val):
                    continue
                for nm in names:
                    out.append({"name": f"{mod}.{nm}", "where": f"{rel(p)}:{node.lineno}",
                                "shape": shape(val), "n_numbers": numbers(val),
                                "value": ast.unparse(val)[:140],
                                "walked_by_audit": f"{mod}.{nm}" in seen})
    return out


def gui_names() -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for p in sorted((SRC / "gui").glob("*.py")):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.keyword) and node.arg == "code" and isinstance(
                    node.value, ast.Constant) and isinstance(node.value.value, str):
                out[node.value.value].append(f"{rel(p)}:{node.value.lineno}")
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if (isinstance(k, ast.Constant) and k.value == "code"
                            and isinstance(v, ast.Constant) and isinstance(v.value, str)
                            and SHAPE.fullmatch(v.value)):
                        out[v.value].append(f"{rel(p)}:{v.lineno}")
    return dict(out)


def main() -> None:
    idx = diagnostic_index()
    wanted = {c for c, v in idx.items()
              if any("/io/" in f or "/crystallography/" in f for f in v["files"])}
    judg = json.loads((HERE / "judgements.json").read_text(encoding="utf-8"))
    st = sites(wanted)
    by_code: dict[str, list[dict]] = defaultdict(list)
    for s in st:
        by_code[s["code"]].append(s)
    consts = constants()
    cnames = {c["name"].rsplit(".", 1)[-1] for c in consts}
    missing = ([c for c in wanted if c not in judg["codes"]]
               + [c["name"] for c in consts if c["name"] not in judg["constants"]]
               + [c for c in wanted if c not in by_code])
    if missing:
        sys.exit(f"no judgement or no site for: {missing}")
    cut = cut_texts(judg)
    if cut:
        sys.exit(f"hand-written text cut short or not a whole sentence: {cut}")

    rows = []
    for code in sorted(wanted):
        j = judg["codes"][code]
        ss = by_code[code]
        helper_sites = [s for s in ss if s["helper_call"]]
        raise_sites = [s["where"] for s in ss if not s["helper_call"]]
        levels = sorted({s["level"] for s in ss if s["level"]})
        if not levels:
            levels = sorted(idx[code]["levels"]) or ["computed"]
        thr = sorted({n for s in ss for n in s["names_in_function"] if n in cnames})
        rows.append({"name": code, "kind": "code",
                     "where": raise_sites or [s["where"] for s in helper_sites],
                     "raised_through_helper": [s["where"] for s in helper_sites],
                     "level": levels,
                     "condition": j["condition"], "site_guards": [s["guards"] for s in ss],
                     "records": j["class"], "note": j["note"],
                     "module_constants_named_in_function": thr,
                     "directory": sorted({"io" if "/io/" in s["where"] else "crystallography"
                                          for s in ss} or {"helper"})})
    crows = []
    for c in consts:
        j = judg["constants"][c["name"]]
        crows.append({"name": c["name"], "kind": "constant", "where": c["where"],
                      "shape": c["shape"], "value": c["value"], "n_numbers": c["n_numbers"],
                      "walked_by_audit": c["walked_by_audit"], "role": j["role"],
                      "decides": j["decides"]})
    gui = gui_names()
    counts = {
        "codes_total": len(rows),
        "codes_io": sum("io" in r["directory"] for r in rows),
        "codes_crystallography": sum("crystallography" in r["directory"] for r in rows),
        "codes_by_class": dict(Counter(r["records"] for r in rows)),
        "code_sites": len(st),
        "constants_total": len(crows),
        "constants_io": sum(".io." in c["name"] for c in crows),
        "constants_crystallography": sum(".crystallography." in c["name"] for c in crows),
        "constants_seen_by_audit_walk": sum(c["walked_by_audit"] for c in crows),
        "constants_by_shape": dict(Counter(c["shape"].split(":")[0] for c in crows)),
        "constants_by_role": dict(Counter(c["role"] for c in crows)),
        "gui_names": len(gui),
    }
    json.dump({"counts": counts, "codes": rows, "constants": crows,
               "reader_decisions": judg["reader_decisions"],
               "gui_not_heuristics": {k: v for k, v in sorted(gui.items())}},
              (HERE / "inventory.json").open("w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main()
