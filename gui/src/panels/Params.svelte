<script lang="ts">
  /**
   * The Parameters panel (WP-2126): every row of the θ vector, read as a
   * crystallographer reads a refinement.
   *
   * Per phase, single parameters are rows and each family for one effect is
   * a group, in the order a refinement frees them (grouping B, 2026-11-07);
   * the cell's held rows fold into one line; one atom is one row. The tree is
   * `lib/paramtree.ts`, the numbers `lib/numslot.ts`, so nothing here decides
   * what a row is or how a number is written.
   *
   * Rules carried from the old table. A row that cannot be freed gets **no
   * checkbox**: its mark says which of the five reasons holds it, and
   * `held_because` is its help text (WP-1004, WP-1214). A hold is the one
   * reason a user can lift, so its mark is the padlock and pressing it
   * unholds. A bulk free/fix sends the filter's **glob**, one `set_vary` and
   * one history node (WP-1011). Edits gather until the action bar's Apply
   * (WP-2123), which sends one `PATCH /api/params`.
   *
   * The layout rule (2026-11-07): no click moves the layout unless it asks
   * to. So the editor and its popover float (`position: fixed`), a pending
   * edit is a tint, a box and a padlock share one 18 px slot, and every
   * number sits in slots sized from the last fit, never from what is typed.
   */
  import { ApiError, api } from "../api";
  import Help from "../Help.svelte";
  import { paramKey, resolve, type HelpCorpus } from "../lib/help";
  import { editText, expText, numParts, slotWidth, slotsFor, type NumParts,
           type Slots } from "../lib/numslot";
  import { buildTree, triState, type AtomRow, type Group, type Line,
           type Section } from "../lib/paramtree";
  import type { ParamsDraft } from "../lib/recovery";
  import { typesetSpaceGroup } from "../lib/spacegroup";
  import { asGlob, editState, heldGlyph, matches, normalize, selection,
           validateEdit, varyEdit, varyOf, type ParamRow } from "../lib/table";

  let {
    head = null,
    busy = false,
    corpus = null,
    say = (_line: string) => {},
    onpending = (_touched: number, _invalid: string) => {},
  }: {
    head?: string | null;
    busy?: boolean;
    corpus?: HelpCorpus | null;
    say?: (line: string) => void;
    /** the pending edits, reported to the shell's action bar (WP-2123): how
     *  many, and the first invalid one's reason or "" */
    onpending?: (touched: number, invalid: string) => void;
  } = $props();

  type Limits = [number | null, number | null];
  type Restraint = { target: number; sigma: number } | null;

  let rows = $state<ParamRow[]>([]);
  let nFree = $state(0);
  let structure = $state<any>(null);
  let sites = $state<any[]>([]);
  let symmetry = $state<any[]>([]);
  let letters = $state<any[]>([]);
  let query = $state("");
  let error = $state("");
  /** A verb's refusal, in its own words. Its own field, because the reload a
   *  moved head triggers clears `error`, and an apply that lands its first
   *  call and fails its second moves the head (gui/CLAUDE.md, WP-1014). */
  let refusal = $state("");
  let loading = $state(false);
  /** user-closed sections and groups; everything starts open, and nothing
   *  closes itself (first review: a section never folds itself) */
  let closed = $state(new Set<string>());
  /** fold lines the user opened */
  let unfolded = $state(new Set<string>());
  let edits = $state(new Map<string, string>());
  let varyEdits = $state(new Map<string, boolean>());
  let holdEdits = $state(new Map<string, boolean>());
  let limitEdits = $state(new Map<string, Limits>());
  let restraintEdits = $state(new Map<string, Restraint>());
  /** typed coordinates, per atom path: a position is one verb (WP-1215) */
  let positionEdits = $state(new Map<string, Record<string, string>>());
  let picked = $state(new Set<string>());
  let anchor = $state<{ key: string; column: string } | null>(null);
  let boxAnchor = $state<{ key: string; column: string } | null>(null);

  interface Editor {
    keys: string[];
    left: number;
    top: number;
    width: number;
    height: number;
    below: boolean;
    error: string;
  }
  let editor = $state<Editor | null>(null);
  let editorInput = $state<HTMLInputElement | null>(null);
  /** The editor's text, outside `editor`: the input's binding writes it after
   *  the event that closed the editor, so it must not hang off that object. */
  let editorText = $state("");
  let scroller = $state<HTMLElement | null>(null);
  let skipClick = false;

  const glob = $derived(asGlob(query));
  const matched = $derived(new Set(matches(rows, glob).map((r) => r.path)));
  const AXES = ["x", "y", "z"] as const;
  const byPath = $derived(new Map(rows.map((r) => [r.path, r])));
  const bulk = $derived(selection(rows, glob));

  const tree = $derived<Section[]>(buildTree(rows, {
    phases: (structure?.phases ?? []).map((p: any, i: number) => ({
      name: p.name, space_group: p.space_group,
      crystal_system: symmetry[i]?.crystal_system,
      ties: symmetry[i]?.ties, fixed_angles: symmetry[i]?.fixed_angles,
      atoms: (p.atoms ?? []).map((a: any) => ({ label: a.label, species: a.species })),
    })),
    sites,
    letters,
    titleOf: (key) => {
      const entry = resolve(corpus, paramKey(key) ?? "");
      return entry?.title ?? null;
    },
    keep: query.trim() ? (path) => matched.has(path) : undefined,
  }));

  /** the slots each column's numbers share, from the last fit's values */
  const slots = $derived.by(() => {
    const out = new Map<string, Slots>();
    const columns = new Map<string, Array<{ value: number; esd: number | null }>>();
    const add = (column: string, row: ParamRow | null) => {
      if (!row) return;
      const list = columns.get(column);
      if (list) list.push({ value: row.value, esd: row.esd });
      else columns.set(column, [{ value: row.value, esd: row.esd }]);
    };
    for (const section of tree) {
      for (const item of section.items) {
        if (item.kind === "row") add(item.column, item.row);
        else if (item.kind === "group") {
          for (const l of [...item.lines, ...(item.fold?.lines ?? [])]) add(l.column, l.row);
        }
      }
    }
    for (const [column, values] of columns) out.set(column, slotsFor(values, true));
    for (const section of tree) {
      for (const item of section.items) {
        if (item.kind !== "atoms") continue;
        for (const field of ["x", "y", "z", "occ", "biso"] as const) {
          const values = item.atoms.map((a) => (field === "occ" || field === "biso"
            ? a[field] : a[field].row)).filter((r): r is ParamRow => !!r)
            .map((r) => ({ value: r.value, esd: r.esd }));
          out.set(`${item.key}:${field}`, slotsFor(values, false));
        }
      }
    }
    return out;
  });

  /** one value-box width for every scalar row, so units form one column
   *  (round 6, 2026-11-07) */
  const inkWidth = $derived.by(() => {
    let widest = 6;
    for (const [column, s] of slots) {
      if (!column.includes(":")) widest = Math.max(widest, slotWidth(s));
    }
    return widest;
  });

  const restraintsOf = $derived.by(() => {
    const out = new Map<string, { target: number; sigma: number }>();
    for (const phase of structure?.phases ?? []) {
      for (const r of phase.restraints ?? []) {
        if (typeof r.path === "string" && "target" in r && "sigma" in r && !("atoms" in r)) {
          out.set(r.path, { target: r.target, sigma: r.sigma });
        }
      }
    }
    return out;
  });

  /** The rows with their pending limits in place: a value typed with its new
   *  limit is checked against that limit, as the server applies them (the
   *  limit first, in the same model edit). */
  const limitedRows = $derived(limitEdits.size ? rows.map((r) => {
    const pair = limitEdits.get(r.path);
    return pair ? { ...r, lo: pair[0] ?? -Infinity, hi: pair[1] ?? Infinity } : r;
  }) : rows);
  const limitedByPath = $derived(new Map(limitedRows.map((r) => [r.path, r])));
  const valueState = $derived(editState(limitedRows, edits, 0));
  const limitInvalid = $derived([...limitEdits].filter(([, [lo, hi]]) =>
    lo !== null && hi !== null && lo > hi)
    .map(([path]) => ({ path, why: "lower limit above the upper one" })));
  const positionInvalid = $derived.by(() => {
    const bad: Array<{ path: string; why: string }> = [];
    for (const [atom, fields] of positionEdits) {
      for (const [axis, text] of Object.entries(fields)) {
        if (text.trim() === "" || !Number.isFinite(Number(text))) {
          bad.push({ path: `${atom}.${axis}`, why: "not a number" });
        }
      }
    }
    return bad;
  });
  const touched = $derived(valueState.touched + varyEdits.size + holdEdits.size
    + limitEdits.size + restraintEdits.size + positionEdits.size);
  const invalid = $derived([...valueState.invalid, ...positionInvalid, ...limitInvalid]);

  $effect(() => {
    const first = invalid[0];
    onpending(touched, first ? `${first.path.split(".").pop()}: ${first.why}` : "");
  });

  async function load() {
    loading = true;
    try {
      const [p, s] = await Promise.all([api.params(), api.structure()]);
      rows = normalize(p.parameters);
      nFree = p.n_free;
      structure = s.structure;
      sites = s.sites ?? [];
      symmetry = s.symmetry ?? [];
      error = "";
      const n = s.structure?.phases?.length ?? 0;
      // the Wyckoff letters are their own route (WP-1035: a miss costs
      // milliseconds an atom), so the site column fills in behind the table
      const sets = await Promise.all(
        Array.from({ length: n }, (_, i) => api.symmetry(i).catch(() => null)));
      letters = sets.flatMap((set: any) => set?.letters ?? []);
    } catch (exc) {
      rows = [];
      error = exc instanceof ApiError && exc.empty ? "" : (exc as Error).message;
    } finally {
      loading = false;
    }
  }

  // reload when the working state moved: the head *is* the working state
  $effect(() => {
    void head;
    load();
  });

  function clearPending() {
    edits = new Map();
    varyEdits = new Map();
    holdEdits = new Map();
    limitEdits = new Map();
    restraintEdits = new Map();
    positionEdits = new Map();
  }

  async function patch(body: Record<string, unknown>): Promise<boolean> {
    try {
      const payload = await api.patchParams(body);
      rows = normalize(payload.parameters);
      nFree = payload.n_free;
      refusal = "";
      return true;
    } catch (exc) {
      // a refusal is the useful answer, in the verb's own words; a 409 says a
      // run owns the table
      refusal = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the table is read-only until it ends"
        : (exc as Error).message;
      return false;
    }
  }

  async function bulkVary(vary: boolean) {
    say(`ref.set_vary(${JSON.stringify(glob)}, ${vary ? "True" : "False"})`);
    await patch({ vary: { [glob]: vary } });
  }

  /** Apply the pending edits; true when there were none or they all landed,
   *  which is what "Apply and refine" waits on before it runs anything. */
  export async function apply(): Promise<boolean> {
    closeEditor(true);
    if (!touched) return true;
    if (invalid.length) return false;
    const { values } = valueState;
    const body: Record<string, unknown> = { values, vary: Object.fromEntries(varyEdits) };
    if (holdEdits.size) body.hold = Object.fromEntries(holdEdits);
    if (limitEdits.size) body.limits = Object.fromEntries(limitEdits);
    if (restraintEdits.size) body.restraints = Object.fromEntries(restraintEdits);
    if (Object.keys(values).length) say(`ref.set_values(${JSON.stringify(values)})`);
    for (const [path, flag] of varyEdits) {
      say(`ref.set_vary(${JSON.stringify(path)}, ${flag ? "True" : "False"})`);
    }
    for (const [path, flag] of holdEdits) {
      say(`ref.${flag ? "hold" : "unhold"}(${JSON.stringify(path)})`);
    }
    if (limitEdits.size || restraintEdits.size) {
      const onInstrument = [...limitEdits.keys()].some((p) => p.startsWith("instrument."));
      const onStructure = restraintEdits.size > 0
        || [...limitEdits.keys()].some((p) => !p.startsWith("instrument."));
      const args = [onStructure ? "structure=…" : "", onInstrument ? "instrument=…" : ""]
        .filter(Boolean).join(", ");
      say(`ref.edit(${args})  # limits and restraints`);
    }
    const needsPatch = Object.keys(values).length || varyEdits.size || holdEdits.size
      || limitEdits.size || restraintEdits.size;
    if (needsPatch) {
      if (!(await patch(body))) return false;
      // landed: a retry after a refused position below must not send these
      // again (an unhold of a path no longer held is refused)
      edits = new Map();
      varyEdits = new Map();
      holdEdits = new Map();
      limitEdits = new Map();
      restraintEdits = new Map();
    }
    for (const [atom, fields] of positionEdits) {
      const xyz = ["x", "y", "z"].map((axis) =>
        axis in fields ? Number(fields[axis]) : (byPath.get(`${atom}.${axis}`)?.value ?? 0));
      // no verb of this name exists: the server projects the position onto
      // the site's DOFs and records a set_values node (WP-1215)
      say(`# ${atom} moved to ${JSON.stringify(xyz)}, set on its site's dof.k`);
      try {
        await api.position(atom, xyz);
      } catch (exc) {
        // what landed before this changed the structure; the panel re-reads it
        await load();
        refusal = (exc as Error).message;
        return false;
      }
      const next = new Map(positionEdits);
      next.delete(atom);
      positionEdits = next;
    }
    clearPending();
    // a limit, a restraint and a position change the structure as well as the
    // rows, so the whole panel re-reads
    await load();
    return true;
  }

  export function revert() {
    closeEditor(false);
    clearPending();
    picked = new Set();
    error = "";
    refusal = "";
  }

  /** The pending edits as plain data, for the recovery copy (WP-2209), or
   *  `null` when nothing is pending.  Reading the six maps here is what lets
   *  the shell's writer follow every change, a retyped value included. */
  export function draft(): ParamsDraft | null {
    const all = [edits, varyEdits, holdEdits, limitEdits, restraintEdits, positionEdits];
    if (all.every((m) => m.size === 0)) return null;
    return {
      edits: Object.fromEntries(edits),
      vary: Object.fromEntries(varyEdits),
      hold: Object.fromEntries(holdEdits),
      limits: Object.fromEntries(limitEdits),
      restraints: Object.fromEntries(restraintEdits),
      positions: Object.fromEntries(positionEdits),
    };
  }

  /** Put recovered edits back as pending edits, in place of any on screen. */
  export function restoreDraft(d: ParamsDraft) {
    closeEditor(false);
    edits = new Map(Object.entries(d.edits ?? {}));
    varyEdits = new Map(Object.entries(d.vary ?? {}));
    holdEdits = new Map(Object.entries(d.hold ?? {}));
    limitEdits = new Map(Object.entries(d.limits ?? {})) as Map<string, Limits>;
    restraintEdits = new Map(Object.entries(d.restraints ?? {})) as Map<string, Restraint>;
    positionEdits = new Map(Object.entries(d.positions ?? {}));
  }

  export function focusFilter() {
    document.querySelector<HTMLInputElement>("#param-filter")?.focus();
  }

  export const freeSelection = () => bulkVary(true);
  export const fixSelection = () => bulkVary(false);

  // ---------------------------------------------------------------- display

  const COORD = /^(phases\.\d+\.atoms\.\d+)\.(x|y|z)$/;

  function pendingText(key: string): string | undefined {
    const m = COORD.exec(key);
    if (m) return positionEdits.get(m[1])?.[m[2]];
    return edits.get(key);
  }

  function partsFor(row: ParamRow, sci: boolean): { parts: NumParts; edited: boolean; bad: string } {
    const text = pendingText(row.path);
    if (text !== undefined) {
      const bad = COORD.test(row.path)
        ? (Number.isFinite(Number(text)) && text.trim() !== "" ? "" : "not a number")
        : validateEdit(limitedByPath.get(row.path) ?? row, text);
      if (!bad) return { parts: numParts(Number(text), null, sci), edited: true, bad };
      return { parts: { int: text, frac: "", tail: "", exp: null }, edited: true, bad };
    }
    return { parts: numParts(row.value, row.esd, sci), edited: false, bad: "" };
  }

  function unitOf(row: ParamRow): string {
    return resolve(corpus, paramKey(row.help_key) ?? "")?.unit ?? "";
  }

  /** A value the user may type: not tied, not structurally fixed. A coordinate
   *  is typed when its site has a DOF to move it; the server projects it. */
  function editable(row: ParamRow): boolean {
    if (COORD.test(row.path)) return !!row.tie;
    return !row.tie && !row.locked;
  }

  function limitsOf(row: ParamRow): Limits {
    const pending = limitEdits.get(row.path);
    if (pending) return pending;
    return [Number.isFinite(row.lo) ? row.lo : null, Number.isFinite(row.hi) ? row.hi : null];
  }

  /** "at or near a limit": a free or just-typed value within 2 esd of one
   *  (constraints round, 2026-11-08); held and fixed values say nothing */
  function limitCue(row: ParamRow): "" | "lo" | "hi" {
    const text = pendingText(row.path);
    const free = varyOf(row, varyEdits);
    if (!free && text === undefined) return "";
    const value = text !== undefined ? Number(text) : row.value;
    if (!Number.isFinite(value)) return "";
    const [lo, hi] = limitsOf(row);
    const near = text !== undefined ? 0 : 2 * (row.esd ?? 0);
    const slack = (limit: number) => Math.max(1e-9 * Math.max(1, Math.abs(limit)), near);
    if (lo !== null && value <= lo + slack(lo)) return "lo";
    if (hi !== null && value >= hi - slack(hi)) return "hi";
    return "";
  }

  function isOpen(key: string): boolean {
    return query.trim() !== "" || !closed.has(key);
  }

  function toggleOpen(key: string) {
    const next = new Set(closed);
    if (!next.delete(key)) next.add(key);
    closed = next;
  }

  function toggleFold(key: string) {
    const next = new Set(unfolded);
    if (!next.delete(key)) next.add(key);
    unfolded = next;
  }

  function freeCount(section: Section): number {
    let n = 0;
    for (const r of rows) {
      if ((r.path.startsWith(`${section.key}.`) || (section.key === "instrument"
        && r.path.startsWith("instrument."))) && varyOf(r, varyEdits)) n += 1;
    }
    return n;
  }

  // ---------------------------------------------------------------- vary, hold

  function holdPending(glob: string): boolean | undefined {
    return holdEdits.get(glob);
  }

  /** Is this path held, counting a pending hold or unhold? */
  function isHeld(row: ParamRow, atomGlob = ""): boolean {
    const pending = holdPending(atomGlob || row.path);
    return pending !== undefined ? pending : row.held;
  }

  function setVary(targets: ParamRow[], flag: boolean) {
    let next = varyEdits;
    for (const row of targets) {
      if (row.refinable || row.vary) next = varyEdit(next, row, flag);
    }
    varyEdits = next;
  }

  function toggleHold(glob: string, current: boolean, serverHeld: boolean) {
    const next = new Map(holdEdits);
    const want = !current;
    if (want === serverHeld) next.delete(glob);
    else next.set(glob, want);
    holdEdits = next;
  }

  function atomGlob(atom: AtomRow): string {
    return `${atom.path}.dof.*`;
  }

  function atomHeld(atom: AtomRow): boolean {
    const pending = holdEdits.get(atomGlob(atom));
    if (pending !== undefined) return pending;
    return atom.dofs.length > 0 && atom.dofs.every((d) => d.held);
  }

  function groupState(members: ParamRow[]): boolean | null {
    return triState(members.filter((m) => !isHeld(m)).map((m) => varyOf(m, varyEdits)));
  }

  function indeterminate(node: HTMLInputElement, value: boolean | null) {
    node.indeterminate = value === null;
    return { update(v: boolean | null) { node.indeterminate = v === null; } };
  }

  /** The boxes of one column, in document order: what a shift-click range
   *  runs over (round 6, 2026-11-07). */
  function boxColumn(column: string): ParamRow[] {
    const out: ParamRow[] = [];
    for (const section of tree) {
      for (const item of section.items) {
        if (column === "r") {
          if (item.kind === "row") out.push(item.row);
          else if (item.kind === "group" && isOpen(item.key)) out.push(...item.lines.map((l) => l.row));
        } else if (item.kind === "atoms" && column.startsWith(`${item.key}:`)) {
          const field = column.slice(item.key.length + 1);
          for (const atom of item.atoms) {
            if (atomHeld(atom) && field !== "occ" && field !== "biso") continue;
            const cell = field === "occ" ? atom.occ : field === "biso" ? atom.biso
              : (atom as any)[field].dof;
            if (cell) out.push(cell);
          }
        }
      }
    }
    return out.filter((r) => (r.refinable || r.vary) && !isHeld(r));
  }

  /** Shift on a box acts on mouse-down, so the browser's own shift-click text
   *  selection never starts and an open editor's commit cannot swallow the
   *  click (round 8, 2026-11-07). */
  function boxDown(event: MouseEvent, row: ParamRow, column: string) {
    if (!event.shiftKey || !boxAnchor || boxAnchor.column !== column) return;
    event.preventDefault();
    skipClick = true;
    const list = boxColumn(column);
    const a = list.findIndex((r) => r.path === boxAnchor!.key);
    const b = list.findIndex((r) => r.path === row.path);
    if (a < 0 || b < 0) return;
    const flag = !varyOf(row, varyEdits);
    setVary(list.slice(Math.min(a, b), Math.max(a, b) + 1), flag);
    boxAnchor = { key: row.path, column };
  }

  function boxClick(event: MouseEvent, row: ParamRow, column: string) {
    if (skipClick) {
      skipClick = false;
      event.preventDefault();
      return;
    }
    setVary([row], (event.currentTarget as HTMLInputElement).checked);
    boxAnchor = { key: row.path, column };
  }

  // ---------------------------------------------------------------- selection, editor

  /** The values of one column in document order: plain rows are one column
   *  ("r"), and in an atom table each field is its own. */
  function valueColumn(column: string): string[] {
    const out: string[] = [];
    for (const section of tree) {
      for (const item of section.items) {
        if (column === "r") {
          if (item.kind === "row" && editable(item.row)) out.push(item.row.path);
          else if (item.kind === "group" && isOpen(item.key)) {
            out.push(...item.lines.filter((l) => editable(l.row)).map((l) => l.row.path));
          }
        } else if (item.kind === "atoms" && column.startsWith(`${item.key}:`)) {
          const field = column.slice(item.key.length + 1);
          for (const atom of item.atoms) {
            const row = field === "occ" ? atom.occ : field === "biso" ? atom.biso
              : (atom as any)[field].row;
            if (row && editable(row)) out.push(row.path);
          }
        }
      }
    }
    return out;
  }

  function valueDown(event: MouseEvent, row: ParamRow, column: string) {
    const meta = event.metaKey || event.ctrlKey;
    if (!meta && !event.shiftKey) return;
    event.preventDefault();
    skipClick = true;
    closeEditor(true);
    const next = new Set(picked);
    if (event.shiftKey && anchor && anchor.column === column) {
      const list = valueColumn(column);
      const a = list.indexOf(anchor.key);
      const b = list.indexOf(row.path);
      if (a >= 0 && b >= 0) list.slice(Math.min(a, b), Math.max(a, b) + 1).forEach((k) => next.add(k));
    } else if (next.has(row.path) && meta) {
      next.delete(row.path);
    } else {
      next.add(row.path);
    }
    picked = next;
    anchor = { key: row.path, column };
  }

  function valueClick(event: MouseEvent, row: ParamRow, column: string) {
    if (skipClick) {
      skipClick = false;
      return;
    }
    if (busy) return;
    const keys = picked.has(row.path) && picked.size > 1 ? [...picked] : [row.path];
    if (!picked.has(row.path)) picked = new Set();
    anchor = { key: row.path, column };
    openEditor(event.currentTarget as HTMLElement, keys);
  }

  function currentText(key: string): string {
    const pending = pendingText(key);
    if (pending !== undefined) return pending;
    const row = byPath.get(key);
    if (!row) return "";
    return editText(row.value, row.esd, !COORD.test(key) && !/\.atoms\.\d+\.(occ|biso)$/.test(key));
  }

  function openEditor(target: HTMLElement, keys: string[]) {
    closeEditor(true);
    const rect = target.getBoundingClientRect();
    const texts = keys.map(currentText);
    const text = texts.every((t) => Number(t) === Number(texts[0])) ? texts[0] : "";
    const width = Math.max(rect.width + 10, (Math.max(text.length + 4, 12)) * 8);
    const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8);
    editorText = text;
    editor = { keys, left, top: rect.top, width, height: rect.height,
               below: rect.bottom + 180 < window.innerHeight, error: "" };
    queueMicrotask(() => {
      editorInput?.focus();
      editorInput?.select();
    });
  }

  /** Write the editor's text into every key it edits, as pending edits. A
   *  text equal to what the cell already drew is no edit (WP-1009). */
  function commit(): boolean {
    if (!editor) return true;
    const text = editorText.trim();
    if (editor.keys.length > 1 && text === "") return true;   // "Mixed", untouched
    let nextEdits = edits;
    let nextPositions = positionEdits;
    for (const key of editor.keys) {
      const row = byPath.get(key);
      if (!row) continue;
      const drawn = editText(row.value, row.esd,
        !COORD.test(key) && !/\.atoms\.\d+\.(occ|biso)$/.test(key));
      const same = text === drawn || (text !== "" && Number(text) === Number(drawn));
      const m = COORD.exec(key);
      if (m) {
        const fields = { ...(nextPositions.get(m[1]) ?? {}) };
        if (same) delete fields[m[2]];
        else fields[m[2]] = text;
        nextPositions = new Map(nextPositions);
        if (Object.keys(fields).length) nextPositions.set(m[1], fields);
        else nextPositions.delete(m[1]);
      } else {
        nextEdits = new Map(nextEdits);
        if (same) nextEdits.delete(key);
        else nextEdits.set(key, text);
      }
    }
    edits = nextEdits;
    positionEdits = nextPositions;
    if (editor.keys.length > 1) say(`# ${editor.keys.length} values set to ${text}`);
    return true;
  }

  function closeEditor(save: boolean) {
    if (!editor) return;
    if (save) commit();
    editor = null;
  }

  function editorKey(event: KeyboardEvent) {
    if (event.key === "Enter") {
      event.preventDefault();
      closeEditor(true);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeEditor(false);
    }
  }

  function editorBlur(event: FocusEvent) {
    const next = event.relatedTarget as Node | null;
    if (next && document.getElementById("value-popover")?.contains(next)) return;
    closeEditor(true);
  }

  function panelKey(event: KeyboardEvent) {
    if (event.key === "Escape" && !editor && picked.size) picked = new Set();
  }

  /** A real scroll of the pane commits an open editor, which floats and would
   *  otherwise be left over the wrong row. */
  function scrolled() {
    if (editor) closeEditor(true);
  }

  const editRow = $derived(editor && editor.keys.length === 1 ? byPath.get(editor.keys[0]) ?? null : null);
  /** limits live on the model; a DOF, a coordinate and a user variable (which
   *  lives on the refinement, not the model) store none */
  const hasLimits = $derived(!!editRow && !/\.dof\.\d+$/.test(editRow.path)
    && !COORD.test(editRow.path) && !editRow.path.startsWith("vars.") && !editRow.tie);

  function setLimit(side: 0 | 1, text: string) {
    if (!editRow) return;
    const current = limitsOf(editRow);
    const value = text.trim() === "" ? null : Number(text);
    if (value !== null && !Number.isFinite(value)) {
      // NaN would travel as JSON null, which the server reads as "no limit"
      editor!.error = "A limit is a number, or empty for none.";
      return;
    }
    const pair: Limits = side === 0 ? [value, current[1]] : [current[0], value];
    const stored: Limits = [Number.isFinite(editRow.lo) ? editRow.lo : null,
                            Number.isFinite(editRow.hi) ? editRow.hi : null];
    const next = new Map(limitEdits);
    if (pair[0] === stored[0] && pair[1] === stored[1]) next.delete(editRow.path);
    else next.set(editRow.path, pair);
    limitEdits = next;
    editor!.error = pair[0] !== null && pair[1] !== null && pair[0] > pair[1]
      ? "The lower limit is above the upper one." : "";
  }

  function restraintOf(path: string): Restraint {
    return restraintEdits.has(path) ? restraintEdits.get(path)! : restraintsOf.get(path) ?? null;
  }

  function setRestraint(path: string, next: Restraint) {
    const stored = restraintsOf.get(path) ?? null;
    const map = new Map(restraintEdits);
    const same = (next === null && stored === null) || (next && stored
      && next.target === stored.target && next.sigma === stored.sigma);
    if (same) map.delete(path);
    else map.set(path, next);
    restraintEdits = map;
  }

  function toggleRestrain(row: ParamRow, on: boolean) {
    if (!on) return setRestraint(row.path, null);
    const target = Number(row.value.toPrecision(4));
    const sigma = row.esd && row.esd > 0 ? Number(row.esd.toPrecision(2))
      : Number((Math.abs(row.value) * 0.05 || 0.01).toPrecision(2));
    setRestraint(row.path, { target, sigma });
  }

  function editRestraint(row: ParamRow, field: "target" | "sigma", text: string) {
    const current = restraintOf(row.path);
    if (!current) return;
    const value = Number(text);
    if (!Number.isFinite(value) || (field === "sigma" && value <= 0)) {
      editor!.error = field === "sigma" ? "σ must be above zero." : "Not a number.";
      return;
    }
    editor!.error = "";
    setRestraint(row.path, { ...current, [field]: value });
  }

  /** Mouse-down inside the popover keeps focus in the editor, so pressing a
   *  button or the Restrain word never commits first; its own fields still
   *  take focus. */
  function popoverDown(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (target instanceof HTMLInputElement && target.type !== "checkbox") return;
    if (target.closest("label")) return;
    event.preventDefault();
  }

  function popoverKey(event: KeyboardEvent) {
    if (event.key === "Enter") {
      event.preventDefault();
      closeEditor(true);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeEditor(false);
    }
  }
</script>

{#snippet number(parts: NumParts, s: Slots | undefined, edited: boolean)}
  <span class="int" style:width="{s?.int ?? 1}ch">{parts.int}</span><span class="pt"
    >{parts.frac || parts.tail ? "." : (s?.frac ? " " : "")}</span><span class="frac"
    style:width="{s?.frac ?? 0}ch">{parts.frac}<span class="tail">{parts.tail}</span></span
  >{#if s?.exp}<span class="exp" class:edited style:width="{s.exp}ch"
    >{#if parts.exp !== null}×10<sup>{expText(parts.exp)}</sup>{/if}</span>{/if}
{/snippet}

{#snippet value(row: ParamRow, column: string, sci: boolean)}
  {@const shown = partsFor(row, sci)}
  {@const cue = limitCue(row)}
  {#if editable(row) && !busy}
    <button class="ink" class:edited={shown.edited} class:bad={shown.bad !== ""}
      class:picked={picked.has(row.path)} class:open={editor?.keys.includes(row.path)}
      class:cue-lo={cue === "lo"} class:cue-hi={cue === "hi"}
      data-path={row.path}
      title={shown.bad || (cue ? (cue === "lo" ? "at or near its lower limit" : "at or near its upper limit") : null)}
      onmousedown={(e) => valueDown(e, row, column)}
      onclick={(e) => valueClick(e, row, column)}
      >{@render number(shown.parts, slots.get(column), shown.edited)}</button>
  {:else}
    <span class="ink fixed" data-path={row.path}
      >{@render number(shown.parts, slots.get(column), false)}</span>
  {/if}
{/snippet}

{#snippet box(row: ParamRow, column: string)}
  {#if row.held || holdEdits.has(row.path)}
    <button class="lock" class:on={isHeld(row)} aria-pressed={isHeld(row)}
      disabled={busy}
      onclick={() => toggleHold(row.path, isHeld(row), row.held)}
      >{@render padlock(isHeld(row))}<span class="sr">{isHeld(row) ? "release" : "hold"}</span></button>
  {:else if row.refinable || row.vary}
    <input type="checkbox" class="vary" checked={varyOf(row, varyEdits)} disabled={busy}
      aria-label="refine"
      onmousedown={(e) => boxDown(e, row, column)}
      onclick={(e) => boxClick(e, row, column)} />
  {:else}
    <!-- no checkbox: a control that errors on click is worse than an absent
         one, and the mark says which reason holds it (WP-1214) -->
    <span class="mark muted">
      <Help text={row.held_because} title="This row is held"
        label="why this row is held">{heldGlyph(row)}</Help>
    </span>
  {/if}
{/snippet}

{#snippet padlock(on: boolean)}
  <svg viewBox="0 0 14 14" width="14" height="14" aria-hidden="true">
    <rect x="2.5" y="6" width="9" height="6.5" rx="1.5"
      fill={on ? "currentColor" : "none"} stroke="currentColor" stroke-width="1.3" />
    <path d={on ? "M4.5 6V4.5a2.5 2.5 0 0 1 5 0V6" : "M4.5 6V4.5a2.5 2.5 0 0 1 5 0"}
      fill="none" stroke="currentColor" stroke-width="1.3" />
  </svg>
{/snippet}

{#snippet rowLine(l: Line, top: boolean)}
  {@const row = l.row}
  <div class="row" class:top class:held={!row.refinable && !row.vary} data-row={row.path}>
    <span class="label">
      <Help for={paramKey(row.help_key)}>{l.label}</Help>
    </span>
    <span class="slot">{@render box(row, "r")}</span>
    <span class="vc">{@render value(row, l.column, true)}<span class="unit muted">{unitOf(row)}</span></span>
  </div>
{/snippet}

{#snippet groupBlock(g: Group)}
  {@const state = groupState(g.members)}
  <div class="head" data-group={g.key}>
    <button class="pick ht" aria-expanded={g.lines.length || g.fold ? isOpen(g.key) : undefined}
      onclick={() => toggleOpen(g.key)}>
      <span class="chev" class:down={isOpen(g.key)} aria-hidden="true">›</span>{g.title}
    </button>
    <span class="slot">
      {#if g.members.length}
        <input type="checkbox" class="vary" checked={state === true} disabled={busy}
          aria-label="refine the {g.title.toLowerCase()} group"
          use:indeterminate={state}
          onclick={(e) => setVary(g.members.filter((m) => !isHeld(m)),
                                  (e.currentTarget as HTMLInputElement).checked)} />
      {/if}
    </span>
    <span class="muted hs">{g.summary ?? ""}</span>
  </div>
  {#if isOpen(g.key)}
    {#each g.lines as l (l.key)}{@render rowLine(l, false)}{/each}
    {#if g.fold}
      <button class="pick fold" aria-expanded={unfolded.has(g.key)} onclick={() => toggleFold(g.key)}>
        <span class="chev" class:down={unfolded.has(g.key)} aria-hidden="true">›</span>{g.fold.text}
      </button>
      {#if unfolded.has(g.key)}
        {#each g.fold.lines as l (l.key)}{@render rowLine(l, false)}{/each}
      {/if}
    {/if}
  {/if}
{/snippet}

{#snippet cellBox(atom: AtomRow, dof: ParamRow | null, column: string)}
  {#if dof && !atomHeld(atom)}
    <input type="checkbox" class="vary" checked={varyOf(dof, varyEdits)} disabled={busy}
      aria-label="refine {atom.label} position"
      onmousedown={(e) => boxDown(e, dof, column)}
      onclick={(e) => boxClick(e, dof, column)} />
  {/if}
{/snippet}

{#snippet atomTable(item: { key: string; atoms: AtomRow[] })}
  {@const allDofs = item.atoms.filter((a) => !atomHeld(a)).flatMap((a) => a.dofs)}
  {@const occs = item.atoms.map((a) => a.occ).filter((r): r is ParamRow => !!r && (r.refinable || r.vary))}
  {@const bisos = item.atoms.map((a) => a.biso).filter((r): r is ParamRow => !!r && (r.refinable || r.vary))}
  {@const posState = triState(allDofs.map((d) => varyOf(d, varyEdits)))}
  {@const occState = triState(occs.map((d) => varyOf(d, varyEdits)))}
  {@const bisoState = triState(bisos.map((d) => varyOf(d, varyEdits)))}
  <div class="atomsw">
    <table class="atomtab">
      <thead>
        <tr>
          <th class="aname">Atom</th>
          <th>Species</th>
          <th>Site</th>
          <th class="lk" aria-label="hold"></th>
          <th colspan="3" class="thc">
            <span class="slot">{#if allDofs.length}<input type="checkbox" class="vary"
              checked={posState === true} use:indeterminate={posState} disabled={busy}
              aria-label="refine every position"
              onclick={(e) => setVary(allDofs, (e.currentTarget as HTMLInputElement).checked)} />{/if}</span>Position
          </th>
          <th class="thc">
            <span class="slot">{#if occs.length}<input type="checkbox" class="vary"
              checked={occState === true} use:indeterminate={occState} disabled={busy}
              aria-label="refine every occupancy"
              onclick={(e) => setVary(occs, (e.currentTarget as HTMLInputElement).checked)} />{/if}</span>Occ
          </th>
          <th class="thc">
            <span class="slot">{#if bisos.length}<input type="checkbox" class="vary"
              checked={bisoState === true} use:indeterminate={bisoState} disabled={busy}
              aria-label="refine every Biso"
              onclick={(e) => setVary(bisos, (e.currentTarget as HTMLInputElement).checked)} />{/if}</span>B<sub>iso</sub>
            <span class="unit muted">Å²</span>
          </th>
          <th class="mult">Mult</th>
        </tr>
      </thead>
      <tbody>
        {#each item.atoms as atom (atom.key)}
          <tr data-atom={atom.path}>
            <td class="aname">{atom.label}</td>
            <td>{atom.species}</td>
            <td title={atom.siteSymmetry ? `site symmetry ${atom.siteSymmetry}` : null}>{atom.wyckoff}</td>
            <td class="lk">
              {#if atom.dofs.length}
                <button class="lock" class:on={atomHeld(atom)} aria-pressed={atomHeld(atom)}
                  disabled={busy}
                  title={atomHeld(atom) ? `release ${atom.label}'s position` : `hold ${atom.label}'s position`}
                  onclick={() => toggleHold(atomGlob(atom), atomHeld(atom),
                    atom.dofs.length > 0 && atom.dofs.every((d) => d.held))}
                  >{@render padlock(atomHeld(atom))}</button>
              {/if}
            </td>
            {#each AXES as axis (axis)}
              {@const cell = atom[axis]}
              <td class="v" class:faint={atomHeld(atom)}>
                <span class="slot">{@render cellBox(atom, cell.dof, `${item.key}:${axis}`)}</span>
                {#if cell.row}{@render value(cell.row, `${item.key}:${axis}`, false)}{/if}
              </td>
            {/each}
            <td class="v">
              <span class="slot">{#if atom.occ}{@render box(atom.occ, `${item.key}:occ`)}{/if}</span>
              {#if atom.occ}{@render value(atom.occ, `${item.key}:occ`, false)}{/if}
            </td>
            <td class="v">
              <span class="slot">{#if atom.biso}{@render box(atom.biso, `${item.key}:biso`)}{/if}</span>
              {#if atom.biso}{@render value(atom.biso, `${item.key}:biso`, false)}{/if}
            </td>
            <td class="mult mono">{atom.multiplicity ?? ""}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/snippet}

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<section class="params" onkeydown={panelKey} aria-label="parameters">
  <header>
    <input id="param-filter" class="mono" placeholder="filter: a word, or a glob like phases.*.cell.*"
      bind:value={query} disabled={!rows.length} />
    <span class="muted count">{nFree} free of {rows.length}</span>
    <button class="ghost" disabled={busy || !bulk.toFree} onclick={() => bulkVary(true)}
      title="one set_vary call on the filter's glob, one history node">Free {bulk.toFree}</button>
    <button class="ghost" disabled={busy || !bulk.toFix} onclick={() => bulkVary(false)}
      >Fix {bulk.toFix}</button>
  </header>

  {#if error || refusal}<p class="bad">{refusal || error}</p>{/if}

  <div class="scroller" bind:this={scroller} onscroll={scrolled} style:--inkw="{inkWidth + 1}ch">
    {#if loading && !rows.length}
      <p class="muted pad">Loading the table…</p>
    {:else if !rows.length}
      <p class="muted pad">No parameters. Open a project.</p>
    {:else if !tree.length}
      <p class="muted pad">Nothing matches <span class="mono">{glob}</span>.</p>
    {:else}
      {#each tree as section, si (section.key)}
        <div class="band" class:first={si === 0} data-section={section.key}>
          <button class="pick bt" aria-expanded={isOpen(section.key)} onclick={() => toggleOpen(section.key)}>
            <span class="chev" class:down={isOpen(section.key)} aria-hidden="true">›</span>
            <span class="title">{section.title}</span>
            {#if section.spaceGroup}
              <span class="sg" aria-label={section.spaceGroup}>
                {#each typesetSpaceGroup(section.spaceGroup) as t, ti (ti)}
                  {#if t.kind === "italic"}<i>{t.text}</i>
                  {:else if t.kind === "bar"}<span class="bar">{t.text}</span>
                  {:else if t.kind === "screw"}{t.text}<sub>{t.sub}</sub>
                  {:else if t.kind === "slash"}/
                  {:else if t.kind === "ext"}<small>{t.text}</small>
                  {:else}{t.text}{/if}
                {/each}
              </span>
            {/if}
            {#if section.system}<span class="muted">{section.system}</span>{/if}
          </button>
          <span class="muted nfree">{freeCount(section)} free</span>
        </div>
        {#if isOpen(section.key)}
          {#each section.items as item (item.key)}
            {#if item.kind === "row"}{@render rowLine(item, true)}
            {:else if item.kind === "group"}{@render groupBlock(item)}
            {:else}{@render atomTable(item)}{/if}
          {/each}
        {/if}
      {/each}
    {/if}
  </div>
</section>

{#if editor}
  <input class="editor mono" bind:this={editorInput} bind:value={editorText}
    placeholder={editor.keys.length > 1 ? "Mixed" : ""}
    style:left="{editor.left}px" style:top="{editor.top}px" style:width="{editor.width}px"
    style:height="{editor.height}px"
    onkeydown={editorKey} onblur={editorBlur} aria-label="value" />
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div id="value-popover" class="popover-panel" role="group" aria-label="value settings"
    style:left="{editor.left}px"
    style:top={editor.below ? `${editor.top + editor.height + 4}px` : null}
    style:bottom={editor.below ? null : `${window.innerHeight - editor.top + 4}px`}
    onmousedown={popoverDown} onkeydown={popoverKey}>
    {#if editor.keys.length > 1}
      <div class="pp muted">{editor.keys.length} values</div>
    {:else if editRow}
      {#if hasLimits}
        {@const pair = limitsOf(editRow)}
        {@const restraint = restraintOf(editRow.path)}
        <div class="pp">
          <span class="pl">Limits</span>
          <input class="vi mono" aria-label="lower limit" placeholder="none" value={pair[0] ?? ""}
            onchange={(e) => setLimit(0, (e.currentTarget as HTMLInputElement).value)} />
          <span class="muted">to</span>
          <input class="vi mono" aria-label="upper limit" placeholder="none" value={pair[1] ?? ""}
            onchange={(e) => setLimit(1, (e.currentTarget as HTMLInputElement).value)} />
          <span class="unit muted">{unitOf(editRow)}</span>
        </div>
        <div class="pp">
          <label class="pl"><input type="checkbox" class="vary" checked={restraint !== null}
            onchange={(e) => toggleRestrain(editRow!, (e.currentTarget as HTMLInputElement).checked)}
            />Restrain</label>
          <input class="vi mono" aria-label="restraint target" disabled={restraint === null}
            value={restraint?.target ?? ""}
            onchange={(e) => editRestraint(editRow!, "target", (e.currentTarget as HTMLInputElement).value)} />
          <span class="muted">±</span>
          <input class="vi mono" aria-label="restraint sigma" disabled={restraint === null}
            value={restraint?.sigma ?? ""}
            onchange={(e) => editRestraint(editRow!, "sigma", (e.currentTarget as HTMLInputElement).value)} />
        </div>
      {:else}
        <div class="pp muted">{editRow.tie ? "This value follows its site's position." : "No limits are stored for this value."}</div>
      {/if}
    {/if}
    {#if editor.error}<div class="pp bad">{editor.error}</div>{/if}
  </div>
{/if}

<style>
  .params {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
    /* the label column, then a 26 px box column, as the prototype measured */
    --label-w: 12.5em;
    --box-w: 26px;
    --row-h: 30px;
  }

  header {
    display: flex;
    gap: 6px;
    align-items: center;
    padding: 6px 8px;
    font-size: var(--text-sm);
  }

  header input {
    flex: 1 1 auto;
    min-width: 0;
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--fg);
  }

  .count {
    white-space: nowrap;
  }

  .scroller {
    flex: 1 1 auto;
    overflow: auto;
    border-top: 1px solid var(--line);
    min-height: 120px;
    font-size: var(--text-sm);
    padding-bottom: 12px;
  }

  .pad {
    padding: 10px;
  }

  .bad {
    color: var(--bad);
    padding: 0 8px;
    margin: 2px 0;
  }

  /* a phase band: where the next phase starts, findable at a glance */
  .band {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 34px;
    margin-top: 14px;
    padding: 0 8px 0 0;
    border-top: 2px solid var(--line);
    background: color-mix(in srgb, var(--fg) 4%, var(--panel));
    font-size: var(--text);
  }

  .band.first {
    margin-top: 0;
  }

  .bt {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex: 1 1 auto;
    min-width: 0;
    font-weight: 600;
  }

  .nfree {
    font-size: var(--text-sm);
    white-space: nowrap;
  }

  .chev {
    display: inline-block;
    width: 12px;
    color: var(--muted);
    transition: transform 0.1s;
  }

  .chev.down {
    transform: rotate(90deg);
  }

  /* space groups in a serif face, no comma (second review, 2026-11-07) */
  .sg {
    font-family: "STIX Two Text", "Cambria Math", "Times New Roman", Times, serif;
    font-weight: 400;
    letter-spacing: 0.015em;
  }

  .sg i {
    margin-right: 0.08em;
  }

  .sg sub {
    font-size: var(--text-xs);
  }

  .sg .bar {
    text-decoration: overline;
  }

  .row,
  .head {
    display: grid;
    grid-template-columns: calc(var(--label-w) - 8px) var(--box-w) max-content 1fr;
    align-items: center;
    min-height: var(--row-h);
    padding-left: 8px;
  }

  .row.top {
    grid-template-columns: var(--label-w) var(--box-w) max-content 1fr;
    padding-left: 0;
  }

  /* overflow is wrap, never truncation (WP-1034): a long name takes a second
     line and its row grows, which a reader expects of a name */
  .row .label {
    padding-left: 26px;
    padding-block: 3px;
    overflow-wrap: anywhere;
    min-width: 0;
  }

  .row:not(.top) .label {
    padding-left: 18px;
  }

  .row.held .label {
    color: var(--muted);
  }

  /* a gap and a rule above each group: grouping B (2026-11-07) */
  .head {
    margin-top: 10px;
    border-top: 1px solid var(--line);
  }

  .ht {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
  }

  .hs {
    padding-left: 6px;
  }

  .fold {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: var(--row-h);
    margin-left: 8px;
    color: var(--muted);
  }

  .slot {
    display: inline-flex;
    width: 18px;
    height: 18px;
    align-items: center;
    justify-content: center;
    flex: 0 0 18px;
  }

  .vc {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .unit {
    white-space: nowrap;
  }

  /* an editable number is tinted (second review, 2026-11-07), the whole box
     the click target; a fixed one is bare and faint */
  .ink {
    display: inline-flex;
    align-items: baseline;
    min-width: var(--inkw);
    min-height: 22px;
    box-sizing: border-box;
    padding: 1px 4px;
    border: 1px solid transparent;
    border-radius: 4px;
    background: color-mix(in srgb, var(--fg) 5%, var(--panel));
    color: var(--fg);
    font-family: var(--mono-family);
    font-size: var(--text-sm);
    font-weight: 400;
    white-space: pre;
    text-align: left;
    cursor: text;
    user-select: none;
  }

  .ink:hover {
    background: color-mix(in srgb, var(--fg) 9%, var(--panel));
  }

  .ink.fixed {
    background: transparent;
    color: var(--muted);
    cursor: default;
  }

  .ink.edited {
    background: color-mix(in srgb, var(--accent) 16%, var(--panel));
    color: var(--accent-ink, var(--accent));
  }

  .ink.bad {
    color: var(--bad);
    border-color: var(--bad);
  }

  .ink.picked {
    outline: 2px solid var(--accent);
    outline-offset: -1px;
  }

  .ink.open {
    visibility: hidden;
  }

  /* at or near a limit: red text and a 2 px bar on the limit's side
     (round 10b, 2026-11-08) */
  .ink.cue-lo,
  .ink.cue-hi {
    color: var(--bad);
  }

  .ink.cue-lo {
    box-shadow: inset 2px 0 0 var(--bad);
  }

  .ink.cue-hi {
    box-shadow: inset -2px 0 0 var(--bad);
  }

  .int {
    display: inline-block;
    text-align: right;
  }

  .frac {
    display: inline-block;
    text-align: left;
  }

  .tail {
    color: var(--muted);
  }

  .exp {
    display: inline-block;
    padding-left: 0.3ch;
    box-sizing: border-box;
    color: var(--muted);
  }

  .exp sup {
    color: var(--fg);
    font-weight: 500;
    font-size: var(--text-xs);
  }

  .exp.edited sup {
    color: var(--accent-ink, var(--accent));
  }

  /* a ticked box is a pale accent tint with an accent tick (round 6) */
  input.vary {
    width: 16px;
    height: 16px;
    margin: 0;
    accent-color: color-mix(in srgb, var(--accent) 35%, var(--panel));
  }

  .mark {
    display: inline-flex;
    width: 18px;
    justify-content: center;
  }

  /* the padlock has a checkbox cell's geometry, so holding moves no number
     (fourth review, 2026-11-07) */
  .lock {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 20px;
    padding: 0;
    border: 1px solid transparent;
    border-radius: 5px;
    background: transparent;
    color: var(--muted);
  }

  .lock:hover:not(:disabled) {
    border-color: var(--line);
  }

  .lock.on {
    color: var(--accent-ink, var(--accent));
  }

  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }

  .atomsw {
    margin-top: 10px;
    border-top: 1px solid var(--line);
    overflow-x: auto;
  }

  table.atomtab {
    border-collapse: collapse;
    white-space: nowrap;
  }

  /* the table is measured to fit the panel at a 1440 px window (546 px) with
     six-decimal coordinates (fluorapatite), so the gaps are the tight ones */
  .atomtab th,
  .atomtab td {
    height: var(--row-h);
    padding: 0 2px 0 0;
    text-align: left;
    font-weight: 400;
  }

  .atomtab th {
    color: var(--muted);
  }

  .atomtab .aname {
    position: sticky;
    left: 0;
    z-index: 1;
    padding-left: 4px;
    background: var(--panel);
  }

  .atomtab td.v {
    white-space: nowrap;
  }

  .atomtab td.v > * {
    vertical-align: middle;
  }

  .atomtab td.faint .ink {
    color: var(--muted);
  }

  .atomtab .thc {
    white-space: nowrap;
  }

  .atomtab .lk {
    width: 22px;
  }

  .atomtab .ink {
    min-width: 0;
    padding-inline: 2px;
  }

  .atomtab .slot {
    width: 16px;
    flex-basis: 16px;
    margin-right: 2px;
  }

  .atomtab .mult {
    text-align: right;
  }

  /* the editor floats over its cell, so opening it moves nothing, and is wide
     enough to show the whole number (fourth review, 2026-11-07) */
  .editor {
    position: fixed;
    z-index: 31;
    box-sizing: border-box;
    padding: 1px 4px;
    border: 1px solid var(--accent);
    border-radius: 4px;
    background: var(--bg);
    color: var(--fg);
    font-size: var(--text-sm);
    outline: none;
  }

  .popover-panel {
    position: fixed;
    z-index: 30;
    min-width: 250px;
    max-width: min(420px, calc(100vw - 16px));
    box-sizing: border-box;
    padding: 6px 8px;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: var(--panel);
    box-shadow: 0 6px 20px color-mix(in srgb, var(--fg) 18%, transparent);
    font-size: var(--text-sm);
  }

  .pp {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 28px;
  }

  .pl {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 72px;
    cursor: default;
  }

  label.pl {
    cursor: pointer;
  }

  .vi {
    width: 9ch;
    border: 1px solid var(--line);
    background: var(--bg);
    color: var(--fg);
  }
</style>
