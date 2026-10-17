"""The refinement history DAG: immutable nodes, mutable named refs.

Hand-rolled parent pointers rather than a graph library — the dependency
budget is locked at numpy/scipy/pydantic/gemmi (docs/DESIGN.md), and the
operations needed here (lineage, children, leaves, best) are a few lines each
over a dict.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..crystallography.twins import merge_site_twins
from ..schemas.common import SCHEMA_VERSION, Diagnostic
from ..schemas.history import (
    Annotation,
    HistoryNode,
    HistoryRecord,
    NodeAction,
    NodeMetrics,
    PlanSpec,
    RefinementState,
    TreeHeader,
)
from ..schemas.migrate import (
    UNSTAMPED_SCHEMA,
    declared_range_repairs,
    newest_declared_since,
    restore_declared_ranges,
    schema_key,
)
from ..schemas.pattern import PatternData
from .store import append_record, fingerprint, read_records, write_records

HEAD = "head"

def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _merge_stored_twins(pending: Sequence[Any]) -> list[Diagnostic]:
    """Put each stored site whose own images coincide on its special position.

    Applied to every node's structure as a log is read (issue #1007), so a
    coordinate a script or an older release stored a few 1e-5 off a mirror
    counts the atoms it does everywhere else.  Nodes of one history repeat the
    same stored coordinate, so the finding is said once per site, naming how
    many nodes held it.
    """
    found: dict[str, list[Diagnostic]] = {}
    for item in pending:
        if not isinstance(item, HistoryNode):
            continue
        local: list[Diagnostic] = []
        merged = merge_site_twins(item.state.structure, diagnostics=local,
                                  source="this history")
        if local:
            item.state.structure = merged
        for d in local:
            found.setdefault(d.message, []).append(d)
    out: list[Diagnostic] = []
    for message, group in found.items():
        first = group[0]
        out.append(first if len(group) == 1 else first.model_copy(update={
            "message": f"{message} (stored in {len(group)} nodes)"}))
    return out


class RefinementTree:
    """A record of every state a refinement passed through, and how.

    Nodes are append-only and never mutated in place except through
    :meth:`annotate`, which is itself recorded as an overlay.  ``refs`` maps
    names (``head`` and any user tags) to node ids.
    """

    def __init__(self, header: TreeHeader, *, path: str | Path | None = None):
        self.header = header
        self.path = Path(path) if path is not None else None
        self.nodes: dict[str, HistoryNode] = {}
        self.order: list[str] = []
        self.refs: dict[str, str] = {}

    # -- construction ---------------------------------------------------
    @classmethod
    def for_data(cls, data: PatternData, *, path: str | Path | None = None,
                 plan: Any = None, package_version: str = "") -> "RefinementTree":
        created = _utcnow()
        # The pattern's abscissa **as measured** — ``x()`` rather than
        # ``two_theta``, which is ``None`` on a time-of-flight histogram.  The
        # fingerprint is a hash of the bytes and the count is a channel count,
        # so neither is a statement about the quantity: what a tree pins is
        # *this data*, and it pins it the same way on either axis.
        x = data.x()
        fp = fingerprint(x, data.intensity)
        header = TreeHeader(
            tree_id=f"t{fp[:8]}",
            created_utc=created,
            data_fingerprint=fp,
            data_source=data.metadata.get("source_file", ""),
            n_points=len(x),
            plan=PlanSpec.from_plan(plan) if plan is not None else None,
            package_version=package_version,
        )
        tree = cls(header, path=path)
        if tree.path is not None:
            append_record(tree.path, HistoryRecord(record="header", header=header))
        return tree

    @classmethod
    def load(cls, path: str | Path, *,
             diagnostics: list[Diagnostic] | None = None) -> "RefinementTree":
        """Rebuild a tree from its JSONL log.

        ``diagnostics``, when a list is passed, collects what the load
        **repaired** — the channel :func:`~rietx.io.readers.read_pattern` and
        :func:`~rietx.crystallography.cif.structure_from_cif` take, for the
        same reason: a reader may correct a document only where it can say that
        it did.  Today that is one repair: a caller's own ``Parameter`` that a
        release before its class inherited left unbounded (issue #204) gets
        its field's declared range back in every node that stored it, one
        ``DECLARED_RANGE_RESTORED`` per parameter; where any node's value lies
        outside that range the parameter is left as stored in all of them, as
        ``DECLARED_RANGE_NOT_RESTORED``.  No value ever moves
        (:func:`~rietx.schemas.migrate.restore_declared_ranges`).  The other
        repair moves a coordinate: a site whose own images sit closer than
        0.02 Å (a stored ``y = 0.2501`` on a mirror at ¼) is put on the
        special position they collapse to, in every node that stored it, and
        said once per site as ``SITE_TWINS_MERGED`` (issue #1007).

        Records are applied **in file order**, replaying exactly what the
        in-memory tree did as each was appended: a node record advances HEAD
        (:meth:`add` does), an annotation's refs overlay whatever HEAD was when
        it was written.  File order is the only thing that says which of the two
        came last, and reading it wrongly cost both halves of "resume where the
        session left off" (WP-1005): nodes-then-annotations put HEAD at the node
        an old ``checkout`` had annotated rather than at the last node committed
        after it, and a log written by a plain ``fit`` — which appends nodes and
        no annotation at all — reloaded with **no HEAD**, so ``tree["head"]``
        raised and there was nothing to resume from.
        """
        header: TreeHeader | None = None
        pending: list[HistoryNode | Annotation] = []
        for rec in read_records(path):
            if rec.record == "header" and rec.header is not None:
                header = rec.header
            elif rec.record == "node" and rec.node is not None:
                pending.append(rec.node)
            elif rec.record == "annotation" and rec.annotation is not None:
                pending.append(rec.annotation)
        if header is None:
            raise ValueError(f"{path}: no header record; not a history log")

        # a header that never stamped its schema is older than any inheritance;
        # a node carries its own stamp once one exists, since a log outlives
        # the release that began it (``HistoryNode.schema_version``)
        written = (header.schema_version if "schema_version" in header.model_fields_set
                   else UNSTAMPED_SCHEMA)
        found: dict[str, list[tuple[str, dict]]] = {}
        if schema_key(written) < newest_declared_since():
            for item in pending:
                if not isinstance(item, HistoryNode):
                    continue
                at = item.schema_version or written
                for model, prefix in ((item.state.structure, ""),
                                      (item.state.instrument, "instrument.")):
                    for c in declared_range_repairs(model, at, prefix):
                        found.setdefault(c["path"], []).append((item.id, c))
        notes = restore_declared_ranges(found, "this history")
        notes.extend(_merge_stored_twins(pending))
        if diagnostics is not None:
            diagnostics.extend(notes)

        tree = cls(header, path=path)
        for item in pending:
            if isinstance(item, HistoryNode):
                tree.nodes[item.id] = item
                tree.order.append(item.id)
                tree.refs[HEAD] = item.id  # committing advanced HEAD, as in add()
            else:
                tree._apply_annotation(item)
        return tree

    # -- mutation -------------------------------------------------------
    def add(self, *, parents: Sequence[str], action: NodeAction,
            state: RefinementState, metrics: NodeMetrics | None = None,
            diagnostics: Iterable = (), label: str = "") -> HistoryNode:
        node = HistoryNode(
            schema_version=SCHEMA_VERSION,
            id=f"n{len(self.order):04d}",
            parents=list(parents),
            action=action,
            state=state,
            metrics=metrics or NodeMetrics(),
            diagnostics=list(diagnostics),
            label=label,
            created_utc=_utcnow(),
        )
        self.nodes[node.id] = node
        self.order.append(node.id)
        self.refs[HEAD] = node.id  # committing advances HEAD, as in git
        if self.path is not None:
            append_record(self.path, HistoryRecord(record="node", node=node))
        return node

    def annotate(self, node_id: str, *, label: str | None = None,
                 scores: dict[str, float] | None = None,
                 notes: dict[str, str] | None = None,
                 refs: dict[str, str] | None = None) -> None:
        ann = Annotation(node_id=self.resolve(node_id), label=label,
                         scores=scores or {}, notes=notes or {}, refs=refs or {})
        self._apply_annotation(ann)
        if self.path is not None:
            append_record(self.path, HistoryRecord(record="annotation", annotation=ann))

    def _apply_annotation(self, ann: Annotation) -> None:
        self.refs.update(ann.refs)
        node = self.nodes.get(ann.node_id)
        if node is None:
            return
        if ann.label is not None:
            node.label = ann.label
        node.scores.update(ann.scores)
        node.notes.update(ann.notes)

    def tag(self, node_id: str, name: str) -> None:
        """Name a node, so branches are addressable by intent not by index."""
        if name == HEAD:
            raise ValueError("'head' is reserved; use checkout() to move it")
        self.annotate(node_id, refs={name: self.resolve(node_id)})

    def set_head(self, node_id: str) -> None:
        self.annotate(node_id, refs={HEAD: self.resolve(node_id)})

    # -- queries --------------------------------------------------------
    def resolve(self, key: str) -> str:
        """Accept either a node id or a ref name."""
        if key in self.refs:
            return self.refs[key]
        if key in self.nodes:
            return key
        raise KeyError(f"unknown node or ref {key!r}; "
                       f"known refs: {sorted(self.refs)}")

    def __getitem__(self, key: str) -> HistoryNode:
        return self.nodes[self.resolve(key)]

    def __len__(self) -> int:
        return len(self.order)

    def __str__(self) -> str:
        """:meth:`summary`, so ``print(tree)`` and a notebook cell draw the tree
        (WP-1544)."""
        return self.summary()

    def _repr_pretty_(self, p, cycle) -> None:
        p.text(str(self))

    def __contains__(self, key: str) -> bool:
        return key in self.nodes or key in self.refs

    @property
    def head(self) -> str | None:
        return self.refs.get(HEAD)

    @property
    def root(self) -> HistoryNode | None:
        for nid in self.order:
            if not self.nodes[nid].parents:
                return self.nodes[nid]
        return None

    def children(self, node_id: str) -> list[HistoryNode]:
        target = self.resolve(node_id)
        return [self.nodes[n] for n in self.order if target in self.nodes[n].parents]

    def leaves(self) -> list[HistoryNode]:
        parented = {p for n in self.nodes.values() for p in n.parents}
        return [self.nodes[n] for n in self.order if n not in parented]

    def lineage(self, node_id: str) -> list[HistoryNode]:
        """Root → node, following first parents."""
        chain: list[HistoryNode] = []
        cur: str | None = self.resolve(node_id)
        seen: set[str] = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            node = self.nodes[cur]
            chain.append(node)
            cur = node.parent
        return list(reversed(chain))

    def ancestors(self, node_id: str) -> set[str]:
        """All ancestors (following *every* parent), including the node."""
        out: set[str] = set()
        stack = [self.resolve(node_id)]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            stack.extend(self.nodes[cur].parents)
        return out

    def common_ancestor(self, a: str, b: str) -> str | None:
        """The merge base: the latest node that is an ancestor of both.

        "Latest" by insertion order — ids are sequential, so the max over the
        intersection is the most recent shared state (sufficient for a DAG
        grown by append-only commits)."""
        shared = self.ancestors(a) & self.ancestors(b)
        if not shared:
            return None
        return max(shared, key=lambda nid: self.order.index(nid))

    def best(self, metric: str = "rwp", *, minimize: bool = True) -> HistoryNode:
        scored = [n for n in self.nodes.values()
                  if n.metrics.statistics is not None
                  and getattr(n.metrics.statistics, metric, None) is not None]
        if not scored:
            raise ValueError("no node carries statistics yet")
        return (min if minimize else max)(
            scored, key=lambda n: getattr(n.metrics.statistics, metric))

    def compare(self, node_ids: Sequence[str]) -> list[dict]:
        """A flat metric table for the given nodes — for humans and for agents."""
        rows = []
        for key in node_ids:
            node = self[key]
            stats = node.metrics.statistics
            rows.append({
                "id": node.id,
                "label": node.label,
                "action": f"{node.action.kind}:{node.action.name}".rstrip(":"),
                "status": node.metrics.status,
                "n_free": stats.n_free_parameters if stats else None,
                "rwp": stats.rwp if stats else None,
                "gof": stats.gof if stats else None,
                "chi2": stats.chi2 if stats else None,
            })
        return rows

    def diff(self, a: str, b: str, *, rtol: float = 1e-12) -> dict[str, tuple[float, float]]:
        """Parameter values that differ between two nodes."""
        va, vb = self._values(self[a]), self._values(self[b])
        out: dict[str, tuple[float, float]] = {}
        for path in sorted(set(va) | set(vb)):
            x, y = va.get(path), vb.get(path)
            if x is None or y is None or abs(x - y) > rtol * max(1.0, abs(x), abs(y)):
                out[path] = (x, y)  # type: ignore[assignment]
        return out

    @staticmethod
    def _values(node: HistoryNode) -> dict[str, float]:
        from ..params.vector import VAR_PREFIX, ParameterTable

        table = ParameterTable(node.state.structure, node.state.instrument)
        values = {e.path: e.value for e in table.entries}
        # a named variable (WP-1119) has no model field, so a table built from
        # the structure and instrument alone has no row for it; its value is on
        # the state, and without this a diff of two nodes a variable moved
        # between reports its dependents and never the quantity that moved them
        values.update({f"{VAR_PREFIX}{name}": prm.value
                       for name, prm in node.state.variables.items()})
        return values

    # -- rendering ------------------------------------------------------
    def summary(self) -> str:
        """The tree with Rwp per node; ``*`` marks HEAD.

        Indentation marks a fork, never a step: a node with one child is
        followed by that child in the same column, as ``git log --graph``
        draws a straight history.  Indenting every child put a 40-stage chain
        40 levels deep and made the text wider than the screen (WP-1545).
        """
        head = self.head
        lines = [f"{self.header.tree_id}  {len(self.order)} nodes"
                 f"  data={self.header.data_source or self.header.data_fingerprint[:8]}"]

        def line(node: HistoryNode, prefix: str) -> str:
            mark = "*" if node.id == head else " "
            rwp = node.rwp
            stat = f"Rwp {rwp:.4f}" if rwp is not None else "—"
            name = f"{node.action.kind}:{node.action.name}".rstrip(":")
            tags = [k for k, v in self.refs.items() if v == node.id and k != HEAD]
            tag = f"  [{', '.join(sorted(tags))}]" if tags else ""
            return f"{prefix}{mark}{node.id}  {name:<22} {stat}{tag}"

        def render(node: HistoryNode, first: str, rest: str) -> None:
            # a chain is a loop rather than a recursion, so its length is not
            # bounded by the interpreter's stack
            lines.append(line(node, first))
            kids = self.children(node.id)
            while len(kids) == 1:
                node = kids[0]
                lines.append(line(node, rest))
                kids = self.children(node.id)
            for i, kid in enumerate(kids):
                last = i == len(kids) - 1
                render(kid, rest + ("└─ " if last else "├─ "),
                       rest + ("   " if last else "│  "))

        root = self.root
        if root is not None:
            render(root, "", "")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for nid in self.order:
            node = self.nodes[nid]
            rwp = node.rwp
            stat = f"<br/>Rwp {rwp:.4f}" if rwp is not None else ""
            name = f"{node.action.kind}:{node.action.name}".rstrip(":")
            lines.append(f'    {nid}["{nid}<br/>{name}{stat}"]')
            for parent in node.parents:
                lines.append(f"    {parent} --> {nid}")
        return "\n".join(lines)

    # -- persistence ----------------------------------------------------
    def records(self) -> list[HistoryRecord]:
        recs = [HistoryRecord(record="header", header=self.header)]
        recs += [HistoryRecord(record="node", node=self.nodes[n]) for n in self.order]
        if self.refs:
            recs.append(HistoryRecord(record="annotation", annotation=Annotation(
                node_id=self.refs.get(HEAD, ""), refs=dict(self.refs))))
        return recs

    def save(self, path: str | Path) -> None:
        write_records(path, self.records())
        self.path = Path(path)
