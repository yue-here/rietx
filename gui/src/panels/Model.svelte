<script lang="ts">
  /**
   * The model pane: the structure and instrument editors.  Making a project
   * is the New project dialog's (`NewProject.svelte`, WP-2131), and opening
   * one is the start screen's.
   *
   * A **mode over the whole window**, not a sixth tab — WP-1013's argument, and
   * for the same reason one rank up: an atom table is eight columns wide and the
   * sidebar is `clamp(340px, 38%, 560px)`.  (WP-1034 later made it a tab whose
   * column can take the window.)
   *
   * Every edit here goes one of two ways, and which one is not a taste:
   *
   * - **The parameter table owns what it has.**  A cell edge, an occupancy, a
   *   Biso, a profile term, a coordinate DOF — those are rows in `/api/params`,
   *   so they go through `PATCH /api/params`, where ties, locks, mode-fixing and
   *   bounds already live.  A cubic `b` refuses by naming the `a` it follows;
   *   that sentence is the verb's, and re-deriving it here would be a second copy
   *   of the crystal systems.
   * - **The model owns its shape.**  A species, a label, an atom added or
   *   removed, a geometry declared, a wavelength, a background family — none of
   *   those is a number in θ, and each changes what the parameter table
   *   *contains*.  They go as a whole validated model, against a **freshly read**
   *   one: a PATCH built from the model on screen would silently revert every
   *   field it did not touch (WP-1009's rule, third outing).
   *
   * Coordinates **are** typed as x/y/z, and the site answers (WP-1215).  `x` is
   * an affine tie onto `…dof.k`, so what goes over the wire is a displacement:
   * `POST /api/structure/position` projects the typed position onto the site's
   * own basis and refuses an unreachable one *naming the nearest it can reach*.
   * That is a change of shape, not of rule — WP-1014 made a violation
   * unrepresentable by offering the DOF boxes instead, which is the safe form
   * and not a readable one, and the refusal is now what carries the same fact.
   * An atom whose site allows no freedom has read-only cells, with the reason
   * where the control would be.
   */
  import { ApiError, api } from "../api";
  import Help from "../Help.svelte";
  import {
    applyFields,
    atomRows,
    axialWarning,
    clone,
    editableValue,
    fieldParam,
    fieldText,
    instrumentFields,
    newAtom,
    phaseFields,
    positionEdits,
    splitEdits,
    structureFields,
    xyzText,
    withAtom,
    withoutAtom,
    type Field,
    type FieldGroup,
    type Site,
  } from "../lib/model";
  import {
    entryLines,
    noteTone,
    siteLines,
    symbolChanged,
    symmetryLine,
    wyckoffLabel,
    type PhaseSymmetry,
    type SiteLetter,
  } from "../lib/symmetry";
  import {
    editState,
    formatEsd,
    formatValue,
    heldGlyph,
    normalize,
    varyEdit,
    varyEditFor,
    varyOf,
    varyOfAll,
    varyStillPending,
    type ParamRow,
  } from "../lib/table";
  import { MODEL_MIN, fitColumns, modelStacks } from "../lib/resize";
  import type { Theme } from "../lib/theme";
  import Splitter from "./Splitter.svelte";
  import Structure3D from "./Structure3D.svelte";

  let {
    project = null,
    capabilities = null,
    head = null,
    busy = false,
    simple = true,
    active = true,
    columns = null,
    theme = "light",
    say = (_line: string) => {},
    oncolumns = (_widths: number[], _done: boolean) => {},
    onmoved = () => {},
  }: {
    project?: any;
    capabilities?: any;
    head?: string | null;
    busy?: boolean;
    simple?: boolean;
    active?: boolean;
    /** the first two columns' widths in px, or `null` while the flex defaults
     *  hold — the shell owns the `ui` key, this pane only reports drags */
    columns?: number[] | null;
    /** passed through to the 3D viewer, whose draw effect depends on it */
    theme?: Theme;
    say?: (line: string) => void;
    oncolumns?: (widths: number[], done: boolean) => void;
    onmoved?: () => void;
  } = $props();

  /** The narrowest a form column may be, and what the 3D column must keep.
   *
   *  `MODEL_MIN.form` rather than a literal: the stacking threshold is that
   *  number's arithmetic, so a second copy here would be the drag's floor and
   *  the threshold's floor disagreeing about the same column.  The CSS basis
   *  reads it too, through `--col-min` on `.editors`. */
  const COL_MIN = MODEL_MIN.form;
  const VIEW_KEEP = 260;

  /** The cell edges as crystallography writes them.  The *path* keeps the
   *  spelled-out name — it is a parameter path, and a glyph in one would be a
   *  second vocabulary for the same field. */
  const CELL_GLYPH: Record<string, string> = { alpha: "α", beta: "β", gamma: "γ" };

  // -- the three columns ---------------------------------------------
  /** what the drag has set, ahead of the round trip that persists it */
  let colLocal = $state<number[] | null>(null);
  let colMeasured = $state([0, 0]);
  let editorsEl: HTMLElement | undefined = $state();
  let editorsWidth = $state(0);
  /** One column, stacked, when three cannot each hold their floor (WP-1034).
   *
   * The pane is a tab now, so it is routinely rendered into 340-560 px — and
   * three columns there are not a squeeze but a *loss*: the atom table needs
   * `MODEL_MIN.structure` and side-scrolls the whole column, cell row and
   * headings included, below it.  Stacked, everything keeps its width and the
   * pane scrolls
   * vertically, which is what a narrow column can actually do.  The threshold
   * is arithmetic over the three floors (`lib/resize.ts`), not a taste. */
  const stacked = $derived(modelStacks(editorsWidth));
  /** Clamped at *render*, not only at drag: widths chosen in one window have to
   *  survive being reopened in a smaller one, and no drag is present to clamp
   *  them.  A browser found the alternative — a 3D column 24 px wide.  Stacked,
   *  a stored width means nothing: the columns are rows. */
  const cols = $derived(stacked
    ? null
    : fitColumns(colLocal ?? columns, editorsWidth, COL_MIN, VIEW_KEEP));

  /** The rendered width of column `i`, in px — its stored value if it has one,
   *  else whatever the flex default is currently producing. */
  function colWidth(i: number): number {
    return cols?.[i] ?? colMeasured[i] ?? 0;
  }

  function dragColumn(i: number, next: number, done: boolean) {
    const widths = [colWidth(0), colWidth(1)];
    widths[i] = next;
    colLocal = widths;
    oncolumns(widths, done);
  }

  // -- the editors ---------------------------------------------------
  let structure = $state<any>(null);
  /**
   * A project with no phase yet (WP-1207): the pattern is loaded, the
   * instrument and the background are editable, and there is no structure to
   * draw, name or give a cell to. Every phase-indexed control below reads
   * `structure.phases[phase]`, so this gates the section rather than each of
   * them, and the 3D column is hidden with it — an empty viewer beside an
   * empty form is two ways of saying the same nothing.
   */
  const noPhases = $derived(!!structure && !structure.phases?.length);
  let sites = $state<Site[]>([]);
  /** `GET /api/structure`'s free arms: what each phase's symbol *is*, and which
   *  symmetry holds each held row.  Both ride on the route this pane already
   *  refetches, so neither costs a request. */
  let symmetry = $state<PhaseSymmetry[]>([]);
  let causes = $state<Record<string, string>>({});
  /** …and the tier that is *not* free: a spglib search per atom.  Fetched
   *  alongside the other three since WP-1215 — the server memoises it on
   *  (space group, positions), so a head move that leaves the structure alone
   *  costs 1-3 us instead of 2.0-5.5 ms an atom, and the `site` column can be a
   *  column rather than a button.  A *miss* still costs what WP-1035 measured,
   *  which is why it is still a route of its own and still fetched in parallel:
   *  the table draws without waiting for it. */
  let letters = $state<SiteLetter[]>([]);
  let lettersBusy = $state(false);
  /** why the `site` column is empty, when it is — its own field, since a column
   *  that failed to arrive is not a refused edit (see `loadLetters`) */
  let letterError = $state("");
  /** the oriented-site-symmetry causes, held apart from the free tier's so the
   *  two concurrent fetches cannot decide the sentence by arrival order */
  let letterCauses = $state<Record<string, string>>({});
  /** which ask the letters on screen answer — see `loadLetters` */
  let lettersSeq = 0;
  /** the symbol being typed, the preview it produced, and the verb's refusal —
   *  three separate fields for WP-1014's reason: a verb's refusal and a panel's
   *  load error must not share one.  `null` is *untouched* rather than empty, so
   *  deleting the field leaves it empty instead of springing back to the model's
   *  symbol mid-edit. */
  let symbolDraft = $state<string | null>(null);
  let symPreview = $state<any>(null);
  let symError = $state("");
  let symBusy = $state(false);
  let instrument = $state<any>(null);
  let rows = $state<ParamRow[]>([]);
  let phase = $state(0);
  /** typed text for model fields, keyed by the field's path in the model */
  let edits = $state(new Map<string, string>());
  /** typed text for raw parameter rows (the ADP patterns) */
  let pedits = $state(new Map<string, string>());
  /** typed coordinates, keyed by the *model* path `phases.i.atoms.j.x|y|z`.
   *
   *  Their own buffer rather than `edits`, because they are the one value in
   *  this panel that is neither a model field nor a parameter row: x is a tie,
   *  so it has no column of its own to set and no place in a whole-model PATCH
   *  either — it goes to `POST /api/structure/position`, which solves it back
   *  onto the DOFs (WP-1215). */
  let xyzEdits = $state(new Map<string, string>());
  /** which atoms have their U^ij patterns open, by base path.
   *
   *  A disclosure rather than a sub-row on every atom: the sub-rows were what
   *  made an atom one to three `<tr>`s, and their separator sat on the next
   *  atom's inputs. */
  let openAdp = $state(new Set<string>());
  /** the refine flags this pane has toggled, keyed by **parameter** path.
   *
   *  Keyed by the parameter path rather than the model path because that is
   *  what `set_vary` takes, and because two of the paths here are not the same
   *  string (`source.polarization` is `instrument.polarization` in θ).  They
   *  ride the same Apply as the value edits and go in the same `PATCH
   *  /api/params`, one `set_vary` node per path — the parameter table's own
   *  per-row behaviour, reached from where the model is read (WP-1214). */
  let varyEdits = $state(new Map<string, boolean>());
  /** The last verb's refusal.  Separate from `loadError` because they are
   *  different facts: found in a browser, an unknown species was refused with a
   *  400 and the message vanished, because `apply` reloads after a failure (the
   *  server may be half-ahead) and `load` cleared the one variable both used.
   *  Same shape as WP-1013's wiped squiggle — two answers sharing one field. */
  let error = $state("");
  let loadError = $state("");
  let note = $state("");
  /** where the last `Save profile…` wrote, or "".
   *
   *  Cleared by `load()`, so the line only ever stands beside the model it was
   *  written from: an export moves no head, and every head move that follows
   *  makes the file a description of something else. */
  let profileSaved = $state("");
  let draft = $state({ label: "", species: "", x: "0", y: "0", z: "0" });
  /** The 3D view is a **third column of this pane**, not a sixth tab and not a
   *  window of its own: it answers questions about the rows beside it (is that
   *  ADP a balloon? did that coordinate DOF move the atom off its axis?), and a
   *  view you have to switch to in order to check an edit is a view nobody
   *  checks. Toggleable because a narrow window has room for two columns. */
  let viewer = $state(true);
  /** Bumped by every successful `load()`; the 3D view redraws on it. */
  let stamp = $state(0);

  const insFields = $derived(instrument ? instrumentFields(instrument) : []);
  const strFields = $derived(structure ? structureFields(structure) : []);
  const atoms = $derived(structure ? atomRows(structure, sites, rows, phase) : []);
  const insDelta = $derived(instrument
    ? splitEdits(instrument, insFields, edits, rows, "instrument")
    : null);
  const strDelta = $derived(structure
    ? splitEdits(structure, strFields, edits, rows, "structure")
    : null);
  /** the phase's own numbers: the scale and the four sample-broadening terms */
  const phFields = $derived(structure && !noPhases ? phaseFields(phase) : []);
  /** the typed coordinates, gathered per atom into whole positions */
  const posDelta = $derived(structure ? positionEdits(structure, phase, xyzEdits)
    : { moves: [], invalid: [], touched: 0 });
  const warning = $derived(instrument ? axialWarning(instrument) : "");
  const byPath = $derived(new Map(rows.map((r) => [r.path, r])));
  /** the toggles that still say something, against the rows as they now stand.
   *
   *  `load()` keeps the typed edits across a head move — a run, a checkout, a
   *  free/fix from the parameter panel — and a value edit that the new state
   *  already matches drops itself, because `splitEdits` compares against what
   *  the cell shows.  A flag has no such comparison of its own, so it is made
   *  here: without it a box ticked before someone else freed the same path
   *  stayed pending and Apply sent a `set_vary` whose hits are empty, which is
   *  the node-saying-nothing `varyEdit` exists to prevent (WP-1214). */
  const varyPending = $derived(new Map([...varyEdits].filter(
    ([key, flag]) => varyStillPending(rows, key, flag))));
  const pending = $derived(editState(rows, pedits, varyPending.size));
  /** the instrument column's own unapplied *values* — what `Save profile…`
   *  waits on.  Not `dirty`, which counts a renamed atom too, and not the
   *  refine flags, which a profile does not carry (`load_instrument_profile`
   *  holds every stored parameter). */
  const insPending = $derived((insDelta?.touched ?? 0) > 0);
  const dirty = $derived((insDelta?.touched ?? 0) + (strDelta?.touched ?? 0)
    + pending.touched + posDelta.touched);
  const invalid = $derived([...(insDelta?.invalid ?? []), ...(strDelta?.invalid ?? []),
                            ...pending.invalid, ...posDelta.invalid]);
  const phaseSym = $derived<PhaseSymmetry | null>(symmetry[phase] ?? null);
  const symLine = $derived(symmetryLine(phaseSym));
  const symDirty = $derived(symbolChanged(symbolDraft ?? "",
    structure?.phases?.[phase]?.space_group ?? ""));

  /** A held row's tooltip: the verb's own `held_because`, and — where symmetry
   *  is the subject — the symmetry that is responsible.  Two sentences rather
   *  than one rewritten, because `held_because` is the parameter surface's
   *  wording and this pane may not restate it (WP-1011). */
  /** The held reason, with the symmetry that causes it.
   *
   * Two sources, read in order rather than merged: `/api/structure` names the
   * symmetry for free and `/api/structure/symmetry` names it *with the oriented
   * site symbol*, which is strictly better.  Since WP-1215 both are in flight at
   * once, so the better one is kept in its own field — merged into `causes`, the
   * sentence a user sees would be decided by which response happened to land
   * last.
   */
  function why(path: string): string {
    const held = byPath.get(path)?.held_because ?? "";
    const cause = letterCauses[path] ?? causes[path] ?? "";
    return [held, cause].filter(Boolean).join(" — ");
  }

  /** Reload on every head move — the head *is* the working state (WP-1005), and
   *  a run, a checkout, a text apply and a form edit all move it.  Only while
   *  shown: this panel is mounted whether or not it is the current mode, and
   *  three routes per head move for a pane nobody is looking at is waste.
   *
   *  `projectKey`, not `project`: a `ui`-only PATCH (a theme, a pane width)
   *  replaces the project *object* without moving the head, and reading the
   *  object here made every such write reload three routes and refetch the 3D
   *  geometry (WP-1029 q).  The *path* rather than a boolean, because the head
   *  cannot tell two projects apart — node ids are sequential (`n0000`), so
   *  two fresh projects share a head — and a switch must reload even when the
   *  heads collide.  (Today `App.opened()` also forces `mode = "panes"`, so a
   *  switch re-enters through `active` anyway; the key means this effect stays
   *  correct the day that side effect changes.) */
  const projectKey = $derived(project?.path ?? null);
  $effect(() => {
    void head;
    if (projectKey !== null && active) load();
  });

  /** The `site` column's own effect, beside `load`'s rather than inside it
   *  (WP-1215).  Beside, because a cache **miss** still costs a spglib search
   *  per atom and the table has no reason to hold its other ten columns behind
   *  one.
   *
   *  Keyed on `stamp` rather than on `head`, which is the whole point: a local
   *  write — an atom added, a coordinate typed — calls `load()` directly and
   *  moves no head prop, and those are exactly the edits that change a Wyckoff
   *  letter.  `stamp` is bumped by `load()` on both paths already.  Plus
   *  `phase`, since switching phase changes the letters and moves neither. */
  $effect(() => {
    void stamp;
    void phase;
    if (projectKey !== null && active) loadLetters();
  });

  async function load() {
    try {
      const [s, i, p] = await Promise.all([api.structure(), api.instrument(),
                                           api.params()]);
      structure = s.structure;
      sites = s.sites ?? [];
      symmetry = s.symmetry ?? [];
      causes = s.causes ?? {};
      instrument = i.instrument;
      rows = normalize(p.parameters);
      loadError = "";
      symPreview = null;
      symbolDraft = null;
      profileSaved = "";
      // the signal the 3D view follows: this runs on every head move *and*
      // immediately after every local write, which is one frame earlier than
      // the head reaches the shell
      stamp += 1;
    } catch (exc) {
      if (!(exc instanceof ApiError && exc.empty)) loadError = (exc as Error).message;
    }
  }

  function type(path: string, text: string) {
    edits = new Map(edits).set(path, text);
  }

  function typeParam(path: string, text: string) {
    pedits = new Map(pedits).set(path, text);
  }

  function typeCoord(path: string, text: string) {
    xyzEdits = new Map(xyzEdits).set(path, text);
  }

  function toggleAdp(base: string) {
    const next = new Set(openAdp);
    if (!next.delete(base)) next.add(base);
    openAdp = next;
  }

  function revert() {
    edits = new Map();
    pedits = new Map();
    xyzEdits = new Map();
    varyEdits = new Map();
    error = "";
    note = "";
  }

  /** Free or hold one row, pending Apply. */
  function toggleVary(row: ParamRow, checked: boolean) {
    varyEdits = varyEdit(varyEdits, row, checked);
  }

  /** …and one *glob*, for a group that is freed together (WP-1215).
   *
   *  An atom's coordinate DOFs are the only such group here: `set_vary` is told
   *  `phases.i.atoms.j.dof.*` and records one node, which is both what the
   *  parameter table does anyway ("per-axis intent does not map onto rows such
   *  as [1,1,0]") and the glob the structural plans carry. */
  function toggleVaryGlob(glob: string, checked: boolean) {
    varyEdits = varyEditFor(varyEdits, rows, glob, checked);
  }

  /** Send the delta: values through the parameter table, shape through the model.
   *
   * Values first — the same order `params_patch` uses, and the reason the model
   * read below is fresh rather than the one on screen. */
  async function apply() {
    if (invalid.length) return;
    error = note = "";   // a refusal must not read as the last success's note
    const values = { ...(insDelta?.values ?? {}), ...(strDelta?.values ?? {}),
                     ...pending.values };
    const vary = Object.fromEntries(varyPending);
    const moves: string[] = [];
    try {
      // One PATCH for both, because the route applies values then vary flags —
      // "put it here, then let it move", which is also the order that leaves the
      // freed parameter's node last in the log.  It runs *before* the model
      // patches below for the same reason their model is read fresh: a whole
      // model carries every `vary` on it, so a flag set after the read would be
      // reverted by the PATCH that follows.
      if (Object.keys(values).length || Object.keys(vary).length) {
        await api.patchParams({ values, vary });
        if (Object.keys(values).length) {
          say(`ref.set_values({${Object.entries(values)
            .map(([k, v]) => `"${k}": ${v}`).join(", ")}})`);
          moves.push(`${Object.keys(values).length} value(s)`);
        }
        for (const [path, flag] of varyPending) {
          say(`ref.set_vary(${JSON.stringify(path)}, ${flag ? "True" : "False"})`);
        }
        if (varyPending.size) moves.push(`${varyPending.size} refine flag(s)`);
      }
      // Positions next, and before the model patches for the reason the params
      // PATCH is: a whole-model PATCH carries the x, y, z of the model it was
      // built from, so a coordinate moved after that read would be reverted by
      // it.  One route call per atom, because the projection is per site.
      for (const move of posDelta.moves) {
        await api.position(move.atom, move.xyz);
        say(`# ${move.atom} → (${move.xyz.join(", ")})`
          + `  ref.set_values({…dof…})`);
      }
      if (posDelta.moves.length) {
        moves.push(`${posDelta.moves.length} position(s)`);
      }
      if (strDelta?.fields.length) {
        const fresh = (await api.structure()).structure;
        await api.patchStructure(applyFields(fresh, strDelta.fields, edits),
                                 "structure edited");
        say("ref.edit(structure=…)");
        moves.push(`${strDelta.fields.length} structure field(s)`);
      }
      if (insDelta?.fields.length) {
        const fresh = (await api.instrument()).instrument;
        await api.patchInstrument(applyFields(fresh, insDelta.fields, edits),
                                  "instrument edited");
        say("ref.edit(instrument=…)");
        moves.push(`${insDelta.fields.length} instrument field(s)`);
      }
      revert();
      note = moves.length ? `applied ${moves.join(" + ")}` : "";
      onmoved();
      await load();
    } catch (exc) {
      // a tied path, a locked one, a bound, or a run in flight — each has a
      // different fix, so the message travels intact
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the model is read-only until it ends"
        : (exc as Error).message;
      await load();
    }
  }

  // -- symmetry (WP-1035) --------------------------------------------
  /** Fetch the Wyckoff letters for the phase on screen.
   *
   * Refetched on every head move since WP-1215, because the server memoises the
   * search on (space group, positions): a move that leaves the structure alone
   * is a dict lookup, and one that does not has different letters to report.
   * No per-phase gate for the same reason — the gate was standing in for the
   * cache, and it could not tell "same phase" from "same structure".
   *
   * A failure here is **not** `symError`, which is the space-group verb's:
   * losing a column is not losing an edit, and putting them in one field made a
   * fetch that failed on its own look like a refused symbol.  It is not
   * `loadError` either — the panel loaded. */
  async function loadLetters() {
    const wanted = phase;
    // latest ask wins: the stale *response* is dropped rather than the fresh
    // request, or a phase switch (or an edit) mid-flight lands the old letters
    const seq = ++lettersSeq;
    lettersBusy = true;
    try {
      const out = await api.symmetry(wanted);
      if (seq !== lettersSeq) return;
      letters = out.letters ?? [];
      // the better sentences: the same causes, with the oriented site symmetry
      letterCauses = out.causes ?? {};
      letterError = "";
    } catch (exc) {
      if (seq !== lettersSeq) return;
      letters = [];
      letterCauses = {};
      letterError = (exc as Error).message;
    } finally {
      if (seq === lettersSeq) lettersBusy = false;
    }
  }

  /** What the typed symbol would do — applying nothing. */
  async function previewSymbol() {
    symBusy = true;
    symError = "";
    try {
      symPreview = await api.symmetryPreview(phase, (symbolDraft ?? "").trim());
    } catch (exc) {
      symPreview = null;
      symError = (exc as Error).message;
    } finally {
      symBusy = false;
    }
  }

  /** …and apply it.  The server re-runs the same preview and gates on it, so
   *  this button is a convenience and never the check itself. */
  async function applySymbol() {
    symBusy = true;
    symError = "";
    try {
      const wanted = (symbolDraft ?? "").trim();
      await api.setSymmetry(phase, wanted);
      say(`structure.phases[${phase}].space_group = "${wanted}"  # ref.edit(structure=…)`);
      symbolDraft = null;
      symPreview = null;
      onmoved();
      await load();
    } catch (exc) {
      symError = (exc as Error).message;
    } finally {
      symBusy = false;
    }
  }

  /** A model change that is not a field: an atom added or removed. */
  async function patchStructure(next: any, label: string, echo: string) {
    try {
      await api.patchStructure(next, label);
      say(echo);
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = (exc as Error).message;
    }
  }

  async function addAtom() {
    if (!draft.label.trim() || !draft.species.trim()) {
      error = "a new atom needs a label and a species";
      return;
    }
    const xyz = [draft.x, draft.y, draft.z].map(Number);
    if (xyz.some((v) => !Number.isFinite(v))) {
      error = "a new atom's position must be three numbers";
      return;
    }
    const atom = newAtom(draft.label.trim(), draft.species.trim(), xyz);
    await patchStructure(withAtom(structure, phase, atom), `added ${atom.label}`,
      `structure.phases[${phase}].atoms.append(Atom("${atom.label}", `
      + `"${atom.species}", ${xyz.join(", ")}))`);
    draft = { label: "", species: "", x: "0", y: "0", z: "0" };
  }

  async function removeAtom(index: number) {
    const label = structure.phases[phase].atoms[index].label;
    await patchStructure(withoutAtom(structure, phase, index), `removed ${label}`,
      `del structure.phases[${phase}].atoms[${index}]  # ${label}`);
  }

  async function toggleAniso(base: string, on: boolean) {
    try {
      await api.aniso(base, on);
      say(`# ${base}: aniso ${on ? "on — AnisoU.isotropic(Uiso, cell)" : "off — Biso from U_eq"}`);
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = (exc as Error).message;
    }
  }

  /** The Chebyshev term count is a *shape* change, so it is not a Field. */
  async function setBackgroundTerms(n: number) {
    const next = clone(instrument);
    const current = next.background.coefficients as any[];
    if (n === current.length || n < 1) return;
    next.background.coefficients = n < current.length
      ? current.slice(0, n)
      : [...current, ...Array.from({ length: n - current.length }, () => ({ value: 0 }))];
    try {
      await api.patchInstrument(next, `background: ${n} terms`);
      say(`instrument.background = BackgroundChebyshev.with_terms(${n})`);
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = (exc as Error).message;
    }
  }

  /** Replace the whole structure or instrument from a file, in one node. */
  async function replaceFrom(kind: "cif" | "instrument", event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const preview = await api.uploadFile(kind, file);
      if (kind === "cif") {
        await api.patchStructure({ upload: preview.upload }, `structure from ${file.name}`);
        say(`ref.edit(structure=structure_from_cif("${file.name}"))`);
      } else {
        await api.patchInstrument({ upload: preview.upload }, `instrument from ${file.name}`);
        say(`ref.edit(instrument=load_instrument_profile("${file.name}"))`);
      }
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = (exc as Error).message;
    } finally {
      input.value = "";
    }
  }

  /** Freeze this instrument to a profile file under the project's `exports/`.
   *
   * The counterpart of `Load profile…` beside it, and the same file format, so
   * a lab calibrates once and every later sample loads it (`io/
   * instrument_profile.py` has the three-step workflow).  The route is
   * **model-gated**, not result-gated like the rest of the export family: the
   * profile describes the instrument as it stands, and the fit that calibrated
   * it has already put its numbers there.
   *
   * What the file does *not* carry is the server's decision, not this button's:
   * the background, the specimen displacement and transparency, the roughness
   * and the specimen absorption all describe one mounted sample rather than the
   * goniometer.
   */
  async function saveProfile() {
    try {
      const out = await api.export("instrument_profile");
      profileSaved = out.path;
      say(`save_instrument_profile(ref.fitted_instrument, "${out.path}")`);
      error = "";
    } catch (exc) {
      profileSaved = "";
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the model is read-only until it ends"
        : (exc as Error).message;
    }
  }

  /** A field's current text: what the user typed, else what the cell shows. */
  function text(model: any, field: Field, kind: "structure" | "instrument"): string {
    return edits.get(field.path) ?? fieldText(model, field, byPath, kind);
  }

  function heldReason(field: Field, kind: "structure" | "instrument"): string {
    return byPath.get(fieldParam(kind, field))?.held_because ?? "";
  }

</script>

<section class="model">
  <header>
    <h1>Structure & instrument</h1>
    <span class="spacer"></span>
    {#if !noPhases}
      <button class="ghost" class:on={viewer} onclick={() => (viewer = !viewer)}
        title="the cell, the symmetry images, the bonds and the displacement
               ellipsoids — drawn from the model on screen">3D</button>
    {/if}
    {#if dirty > 0}
      <span class="muted">{dirty} edit{dirty === 1 ? "" : "s"}</span>
      <button class="ghost" disabled={busy || invalid.length > 0} onclick={apply}>Apply</button>
      <button class="ghost" onclick={revert}>Revert</button>
    {/if}
  </header>

  <!-- The refine flag, drawn once and rendered beside every value this pane
       shows (WP-1214).  A checkbox where `set_vary` could free the row, and
       **no checkbox at all** where it could not — the parameter table's rule
       (WP-1011), with the same three marks and the same sentence, because both
       come from `lib/table.ts` rather than from two panels that agree today.
       `why()` supplies the reason: `held_because` plus, on a structure path,
       the symmetry that is responsible. -->
  {#snippet varyBox(path: string)}
    {@const row = byPath.get(path)}
    {#if row?.refinable}
      <input
        type="checkbox"
        class="vary"
        data-vary={path}
        checked={varyOf(row, varyEdits)}
        disabled={busy}
        aria-label="refine {path}"
        onchange={(e) =>
          toggleVary(row, (e.currentTarget as HTMLInputElement).checked)} />
    {:else if row}
      <span class="vary muted" data-vary={path} title={why(path)}>{heldGlyph(row)}</span>
    {/if}
  {/snippet}

  <!-- One group of the instrument form (WP-1216), under its own heading: the
       source, the geometry, the profile.  Which fields those are is
       `lib/model.ts`'s `group`, so this snippet chooses nothing — including the
       two that disagree with their own path, the axial apertures and the zero
       shift.  A choice takes the whole row (`.fullrow`), which keeps the
       geometry select's intrinsic width out of the tracks the numbers line up
       in, and the profile grid's rows start where `PROFILE_ROWS` says
       (`.rowstart`), so U is above X whatever the column is doing. -->
  {#snippet insGrid(group: FieldGroup)}
    {@const shown = insFields.filter(
      (f) => f.group === group && (!f.advanced || !simple))}
    <div class="grid" class:profile={group === "profile"}>
      {#each shown as field (field.path)}
        {@const held = heldReason(field, "instrument")}
        {@const row = byPath.get(fieldParam("instrument", field))}
        <!-- `title` is the *held* reason here, which is the verb's own words
             about this instrument; what the field IS comes from the corpus, and
             the two fields with no entry say so in `lib/model.ts` (WP-1203). -->
        <label class="cell" title={held} class:fullrow={field.kind === "choice"}
          class:rowstart={field.startsRow}>
          <span class="muted">
            {#if field.help}<Help for={field.help}>{field.label}</Help>
            {:else}<span title={field.title}>{field.label}</span>{/if}
            {field.unit ? ` (${field.unit})` : ""}</span>
          {#if field.kind === "choice"}
            <select class="mono" data-field={field.path}
              value={text(instrument, field, "instrument")}
              onchange={(e) => type(field.path,
                (e.currentTarget as HTMLSelectElement).value)}>
              {#each field.choices ?? [] as choice (choice)}
                <option value={choice}>{choice}</option>
              {/each}
            </select>
          {:else if held && held.includes("structurally")}
            <span class="mono fixed">{text(instrument, field, "instrument")}</span>
          {:else}
            <input class="mono" data-field={field.path}
              value={text(instrument, field, "instrument")}
              placeholder={field.kind === "optnumber" ? "unset" : ""}
              oninput={(e) => type(field.path,
                (e.currentTarget as HTMLInputElement).value)} />
          {/if}
          <!-- geometry, shape, the radius and the specimen dimensions are not
               in θ, so `varyBox` draws nothing for them: the row it asks for
               does not exist (WP-1214).  The esd beside it is the one the cell
               row and the phase grid already draw — the same slot, the same
               call: a refined U with no esd here read as a number nobody had
               measured (WP-1216). -->
          <span class="varyline">
            {@render varyBox(fieldParam("instrument", field))}
            <span class="muted">{row ? formatEsd(row.value, row.esd) : ""}</span>
          </span>
        </label>
      {/each}
    </div>
  {/snippet}

  {#if structure && instrument}
    <!-- ---------------------------------------------------------- -->
    <p class="muted caption">
      A box beside a value frees it for the next fit, through the same
      <span class="mono">set_vary</span> the parameter table calls. Where a value
      is held, the reason stands in place of the box.
    </p>
    <div class="editors" class:stacked bind:this={editorsEl} bind:clientWidth={editorsWidth}
      style:--col-min="{MODEL_MIN.form}px"
      style:--structure-min="{MODEL_MIN.structure}px">
      <div class="column structure" bind:clientWidth={colMeasured[0]}
        style:flex={cols ? `0 0 ${cols[0]}px` : null}>
        <h2>Structure
          <label class="file inline-file">
            <input type="file" accept=".cif" onchange={(e) => replaceFrom("cif", e)} />
            <span>Replace from CIF…</span>
          </label>
        </h2>
        {#if noPhases}
          <p class="muted">
            No phase yet. Pick peaks and index them in the Peaks panel, then
            adopt a candidate cell — or replace the model from a CIF above.
            Refining is unavailable until this project has a phase.
          </p>
        {:else}
        {#if structure.phases.length > 1}
          <nav class="phases segmented" role="group" aria-label="phase">
            {#each structure.phases as p, i (i)}
              <button class:on={phase === i} onclick={() => (phase = i)}>{p.name}</button>
            {/each}
          </nav>
        {/if}

        <div class="grid">
          <label class="cell fullrow"><span class="muted">name</span>
            <input class="mono" data-field="phases.{phase}.name"
              value={text(structure, { path: `phases.${phase}.name`,
              label: "phase", kind: "text" }, "structure")}
              oninput={(e) => type(`phases.${phase}.name`,
                (e.currentTarget as HTMLInputElement).value)} /></label>
        </div>

        <!-- Symmetry is not one read-only string any more (WP-1035): it is the
             one field whose *effects* fill the rest of this column, so it says
             what it is, what it holds, and what changing it would invalidate —
             before anything is applied. -->
        <div class="symmetry">
          <div class="symrow">
            <span class="muted">space group</span>
            <input class="mono sym" data-field="phases.{phase}.space_group"
              value={symbolDraft ?? structure.phases[phase].space_group}
              title="the Hermann-Mauguin symbol or its IT number; a setting
                extension (:H, :R) is part of it"
              oninput={(e) => (symbolDraft =
                (e.currentTarget as HTMLInputElement).value)} />
            <button class="ghost" disabled={!symDirty || symBusy || busy}
              onclick={previewSymbol}>Preview…</button>
          </div>
          <p class="muted nowrapish">{symLine}</p>
          {#if phaseSym?.constraints}
            <p class="muted">holds: {phaseSym.constraints}</p>
          {/if}
          <!-- the button that used to buy the letters is gone (WP-1215): the
               search is memoised on (space group, positions), so the `site`
               column fetches itself and a head move that changes no coordinate
               costs a dict lookup -->
          {#if letterError}<p class="bad">site symmetry: {letterError}</p>{/if}
          {#if symError}<p class="bad">{symError}</p>{/if}

          {#if symPreview}
            <div class="preview" class:blocked={symPreview.blocked}>
              <p>
                <strong class="mono">{symPreview.to?.xhm ?? "?"}</strong>
                {#if !symPreview.changed}
                  — the same setting; nothing would change.
                {:else if symPreview.blocked}
                  — this model cannot carry it:
                {:else}
                  — {symPreview.to?.constraints}
                {/if}
              </p>
              {#each symPreview.refusals as refusal (refusal.where)}
                <p class="bad">{refusal.message}</p>
              {/each}
              {#each symPreview.notes as note2 (note2.kind + note2.where.join())}
                <p class="{noteTone(note2.kind)}">{note2.message}</p>
              {/each}
              {#if !symPreview.blocked}
                {#each entryLines(symPreview.entries) as line (line)}
                  <p class="muted">{line}</p>
                {/each}
                {#each siteLines(symPreview.sites) as line (line)}
                  <p class="muted">{line}</p>
                {/each}
                {#if !entryLines(symPreview.entries).length
                     && !siteLines(symPreview.sites).length && symPreview.changed}
                  <p class="muted">no parameter gains or loses a tie — the
                    reflection list is what moves.</p>
                {/if}
              {/if}
              <div class="symrow">
                <button class="ghost" disabled={symPreview.blocked || !symPreview.changed
                  || symBusy || busy} onclick={applySymbol}>Apply</button>
                <button class="ghost"
                  onclick={() => { symPreview = null; symbolDraft = null; }}
                  >Discard</button>
              </div>
            </div>
          {/if}
        </div>

        <h3>Cell</h3>
        <!-- one row of six, because that is how a cell is written.  A
             wrap-when-it-must flex grid put it on three ragged rows at a 309 px
             column and hid the fact that α β γ are one family. -->
        <div class="cellrow">
          {#each ["a", "b", "c", "alpha", "beta", "gamma"] as edge (edge)}
            {@const path = `phases.${phase}.cell.${edge}`}
            {@const row = byPath.get(path)}
            {@const field = { path, label: edge, kind: "number" } as Field}
            <!-- `title` is the symmetry cause, which is `causes`' own sentence
                 about this phase; what a cell edge *is* comes from the corpus. -->
            <label class="cell" title={why(path)}>
              <span class="muted"><Help for="parameters:phases.*.cell.{edge}"
                >{CELL_GLYPH[edge] ?? edge}</Help></span>
              {#if !editableValue(row)}
                <span class="mono fixed">{formatValue(row!.value, row!.esd)}</span>
              {:else}
                <input class="mono" data-field={path}
                  value={text(structure, field, "structure")}
                  oninput={(e) => type(path, (e.currentTarget as HTMLInputElement).value)} />
              {/if}
              <span class="varyline">
                {@render varyBox(path)}
                <span class="muted">{row ? formatEsd(row.value, row.esd) : ""}</span>
              </span>
            </label>
          {/each}
        </div>

        <h3>Phase</h3>
        <!-- The scale and the sample broadening: the phase's half of the
             instrument ⊕ sample split, two columns from the instrument's own
             U V W X Y.  `lib/model.ts:phaseFields` says why the corrections are
             not here. -->
        <div class="grid">
          {#each phFields as field (field.path)}
            {@const row = byPath.get(field.path)}
            <label class="cell" title={why(field.path)}>
              <span class="muted">
                <Help for={field.help!}>{field.label}</Help>{field.unit
                  ? ` (${field.unit})` : ""}</span>
              {#if !editableValue(row)}
                <span class="mono fixed">{formatValue(row!.value, row!.esd)}</span>
              {:else}
                <input class="mono" data-field={field.path}
                  value={text(structure, field, "structure")}
                  oninput={(e) => type(field.path,
                    (e.currentTarget as HTMLInputElement).value)} />
              {/if}
              <span class="varyline">
                {@render varyBox(field.path)}
                <span class="muted">{row ? formatEsd(row.value, row.esd) : ""}</span>
              </span>
            </label>
          {/each}
        </div>

        <h3>Atoms <span class="muted">{atoms.length}</span></h3>
        <!-- One row per atom (WP-1215).  The table scrolls, not the column: its
             `min-content` is MODEL_MIN.structure (`lib/resize.ts`, measured) and
             a column narrower than that used to take the cell row and the
             headings sideways with it. -->
        <div class="tablewrap">
        <table class="atoms">
          <thead>
            <tr><th>label</th><th>species</th><th>site</th>
              <th>x</th><th>y</th><th>z</th>
              <th><Help for="parameters:phases.*.atoms.*.occ">occ</Help></th>
              <th><Help for="parameters:phases.*.atoms.*.biso">Biso</Help></th>
              <th><Help for="parameters:phases.*.atoms.*.adp.*">aniso</Help></th>
              <th><Help for="parameters:phases.*.atoms.*.dof.*">vary</Help></th>
              <th></th></tr>
          </thead>
          <tbody>
            {#each atoms as row (row.base)}
              {@const moves = (row.site?.dof_directions ?? [])
                .map((d) => `[${d.join(" ")}]`).join(", ")}
              {@const coordTitle = row.frozen
                || (moves ? `moves along ${moves}` : "")}
              <tr>
                <td><input class="mono narrow" data-field="{row.base}.label"
                  value={text(structure,
                  { path: `${row.base}.label`, label: "label", kind: "text" }, "structure")}
                  oninput={(e) => type(`${row.base}.label`,
                    (e.currentTarget as HTMLInputElement).value)} /></td>
                <td><input class="mono narrow" data-field="{row.base}.species"
                  value={text(structure,
                  { path: `${row.base}.species`, label: "species", kind: "text" }, "structure")}
                  oninput={(e) => type(`${row.base}.species`,
                    (e.currentTarget as HTMLInputElement).value)} /></td>
                <!-- the Wyckoff letter and the oriented site symbol, fetched by
                     the panel rather than by a button (WP-1215).  "…" while the
                     search is in flight and "—" only once it is not: a cache
                     miss is 2.0-5.5 ms an atom, so on a large structure the
                     column is empty for a moment, and an em dash there is a
                     wrong *answer* about the site rather than an absent one. -->
                <td class="site mono" title={why(`${row.base}.x`) || coordTitle}
                  >{wyckoffLabel(letters, row.base)
                    || (lettersBusy ? "…" : "—")}</td>
                <!-- x, y, z: typed, and solved back onto the site's DOFs on
                     Apply.  Read-only where the site allows nothing to move —
                     there is no control to grey out, so there is none. -->
                {#each ["x", "y", "z"] as axis (axis)}
                  {@const path = `${row.base}.${axis}`}
                  {@const value = row.xyz["xyz".indexOf(axis)]}
                  <td class="coord">
                    {#if row.frozen}
                      <span class="mono fixed" title={row.frozen}
                        >{xyzText(value)}</span>
                    {:else}
                      <input class="mono narrow" data-coord={path}
                        title={coordTitle}
                        value={xyzEdits.get(path) ?? xyzText(value)}
                        oninput={(e) => typeCoord(path,
                          (e.currentTarget as HTMLInputElement).value)} />
                    {/if}
                  </td>
                {/each}
                {#each [`${row.base}.occ`, `${row.base}.biso`] as path (path)}
                  {@const prow = byPath.get(path)}
                  {@const cell = { path, label: path, kind: "number" } as Field}
                  <td>
                    <span class="valrow">
                      {#if !editableValue(prow)}
                        <span class="mono fixed" title={why(path)}
                          >{formatValue(prow!.value, prow!.esd)}</span>
                      {:else}
                        <input class="mono narrow" data-field={path}
                          value={text(structure, cell, "structure")}
                          oninput={(e) => type(path,
                            (e.currentTarget as HTMLInputElement).value)} />
                      {/if}
                      {@render varyBox(path)}
                    </span>
                  </td>
                {/each}
                <!-- `data-aniso` names it the way every value cell here is
                     named by `data-field`: this column is one of several
                     checkboxes in the row now, and "the first one in the table"
                     stopped being an address the day the refine flags arrived. -->
                <td class="anisocell">
                  <span class="valrow">
                    <input type="checkbox" data-aniso={row.base}
                      checked={row.site?.aniso ?? false}
                      disabled={busy}
                      aria-label="anisotropic ADPs for {row.base}"
                      onchange={(e) => toggleAniso(row.base,
                        (e.currentTarget as HTMLInputElement).checked)} />
                    {#if row.adps.length}
                      <button class="ghost" data-adp={row.base}
                        aria-expanded={openAdp.has(row.base)}
                        title="the U^ij patterns this site symmetry allows"
                        onclick={() => toggleAdp(row.base)}
                        >{openAdp.has(row.base) ? "▾" : "▸"}</button>
                    {/if}
                  </span>
                </td>
                <!-- the position's refine flag, and there is one rather than
                     three: the site's DOFs are freed together, so the box is
                     about the glob `…dof.*` (WP-1215) -->
                <td class="varycell">
                  {#if row.dofs.length}
                    {@const glob = `${row.base}.dof.*`}
                    {#if row.dofs.some((dof) => dof.refinable)}
                      {@const state = varyOfAll(rows, varyEdits, glob)}
                      <input type="checkbox" class="vary" data-vary={glob}
                        checked={state === true}
                        indeterminate={state === null}
                        disabled={busy}
                        aria-label="refine the position of {row.base}"
                        onchange={(e) => toggleVaryGlob(glob,
                          (e.currentTarget as HTMLInputElement).checked)} />
                    {:else}
                      <!-- held for a reason the whole group shares — a Le Bail
                           or Pawley mode force-fixes every `.atoms.` path — so
                           the mark rather than a box, which is what `varyBox`
                           draws for every other flag in this row -->
                      <span class="vary muted" data-vary={glob}
                        title={why(row.dofs[0].path)}
                        >{heldGlyph(row.dofs[0])}</span>
                    {/if}
                  {:else}
                    {@render varyBox(`${row.base}.x`)}
                  {/if}
                </td>
                <td><button class="ghost" disabled={busy}
                  title="remove this atom" onclick={() => removeAtom(row.index)}>×</button></td>
              </tr>
              {#if row.adps.length && openAdp.has(row.base)}
                <tr class="adprow"><td colspan="11">
                  <span class="sublabel">U<sup>ij</sup> patterns</span>
                  <!-- a grid, not a wrapping row: a six-component pattern and a
                       one-component one are different widths, and letting them
                       find their own put the brackets and the boxes on
                       different rhythms -->
                  <div class="dofs wide-patterns">
                    {#each row.adps as adp, k (adp.path)}
                      <label class="dof mono" title={adp.path}>
                        <span class="pattern">[{(row.site?.adp_patterns?.[k] ?? []).join(" ")}]</span>
                        <input class="mono narrow" data-field={adp.path}
                          value={pedits.get(adp.path)
                          ?? formatValue(adp.value, adp.esd)}
                          oninput={(e) => typeParam(adp.path,
                            (e.currentTarget as HTMLInputElement).value)} />
                        {@render varyBox(adp.path)}
                      </label>
                    {/each}
                  </div>
                </td></tr>
              {/if}
            {/each}
          </tbody>
        </table>
        </div>

        <div class="add">
          <input class="mono narrow" placeholder="label" bind:value={draft.label} />
          <input class="mono narrow" placeholder="species" bind:value={draft.species} />
          <input class="mono narrow" placeholder="x" bind:value={draft.x} />
          <input class="mono narrow" placeholder="y" bind:value={draft.y} />
          <input class="mono narrow" placeholder="z" bind:value={draft.z} />
          <button class="ghost" disabled={busy} onclick={addAtom}>Add atom</button>
        </div>
        <p class="muted">
          A new atom's position decides its site symmetry, and therefore how many
          DOFs it gets — which is why it is typed here and moved by them afterwards.
        </p>
        {/if}
      </div>

      <!-- no grip between rows: stacked, a column's width is the pane's -->
      {#if !stacked}
        <Splitter size={colWidth(0)} grow="right" min={COL_MIN}
          keep={colWidth(1) + VIEW_KEEP} flow="inline"
          extent={() => editorsEl?.clientWidth ?? 0}
          onsize={(next, done) => dragColumn(0, next, done)}
          title="drag to resize the structure column" />
      {/if}

      <div class="column" bind:clientWidth={colMeasured[1]}
        style:flex={cols ? `0 0 ${cols[1]}px` : null}>
        <h2>Instrument
          <label class="file inline-file">
            <input type="file" onchange={(e) => replaceFrom("instrument", e)} />
            <span>Load profile…</span>
          </label>
          <!-- refused while this column has unapplied edits: the file is
               written from the instrument the *server* holds, so a typed W
               nobody applied would be absent from it with nothing said. -->
          <button class="ghost" disabled={busy || insPending}
            title={insPending
              ? "apply the instrument edits first — a profile is written from "
                + "the model the server holds"
              : "freeze this instrument to a profile file under exports/"}
            onclick={saveProfile}>Save profile…</button>
        </h2>
        {#if profileSaved}
          <p class="muted mono">wrote {profileSaved}</p>
        {/if}

        <!-- The order a crystallographer expects, which is the order the
             quantities are decided in: what the radiation is, where the
             specimen sits, what shape that makes a peak, and what is under it
             all (WP-1216). -->
        <h3>Source</h3>
        {@render insGrid("source")}

        <h3>Geometry</h3>
        {@render insGrid("geometry")}

        <h3>Profile</h3>
        <!-- inside Profile, because the pair it is about is drawn here: S/L and
             H/L are the last row of this grid -->
        {#if warning}
          <p class="warn">{warning} Nudge one if you free both — the guard
            reports the pair, and two solvers escape the corner in two
            unprincipled directions.</p>
        {/if}
        {@render insGrid("profile")}

        <h3>Background</h3>
        <p class="muted">
          {instrument.background.kind}
          {#if instrument.background.kind === "chebyshev"}
            — the coefficients themselves are parameters; the count is a shape
            change, so it lands as a model edit.
          {/if}
        </p>
        {#if instrument.background.kind === "chebyshev"}
          <label class="inline">
            terms
            <input class="mono narrow" type="number" min="1" max="30"
              value={instrument.background.coefficients.length}
              onchange={(e) => setBackgroundTerms(
                Number((e.currentTarget as HTMLInputElement).value))} />
          </label>
        {/if}
      </div>

      {#if viewer && !noPhases}
        {#if !stacked}
          <Splitter size={colWidth(1)} grow="right" min={COL_MIN} keep={VIEW_KEEP}
            flow="inline"
            extent={() => (editorsEl?.clientWidth ?? 0) - colWidth(0)}
            onsize={(next, done) => dragColumn(1, next, done)}
            title="drag to resize the instrument column" />
        {/if}
        <!-- stacked, this is a section under the forms rather than a third of a
             400 px pane, and the header's `3D` button is its collapse control —
             one control for one choice (WP-1029), not a second one down here -->
        <div class="column view">
          {#if stacked}<h2>3D</h2>{/if}
          <Structure3D {stamp} {theme} {say} />
        </div>
      {/if}
    </div>

    <footer>
      {#if error}<p class="bad">{error}</p>{/if}
      {#if loadError}<p class="bad">{loadError}</p>{/if}
      {#if invalid.length}
        <p class="bad">{invalid.map((i) => `${i.path}: ${i.why}`).join(" · ")}</p>
      {/if}
      {#if note}<p class="muted">{note}</p>{/if}
      {#if dirty > 0}
        <p class="muted">
          {Object.keys({ ...(insDelta?.values ?? {}), ...(strDelta?.values ?? {}),
                         ...pending.values }).length} through
          <code>set_values</code> ·
          {varyPending.size} through <code>set_vary</code> ·
          {(insDelta?.fields.length ?? 0) + (strDelta?.fields.length ?? 0)} as a
          model edit
        </p>
      {/if}
    </footer>
  {:else}
    <p class="muted">{loadError || "loading…"}</p>
  {/if}
</section>


<style>
  /* The form's two widths, each written once (WP-1216).  `--w-num` is what a
     numeric input measures — the same number in every grid, which is the
     alignment that was asked for — and it is the track floor too, so how many
     columns a group gets is that one number against the column's width.
     `--w-sel` caps a select: the geometry one's longest option
     (`flat_plate_transmission`) is what made the old wrapping row's cells
     unequal, and a control that cannot decide a track's width cannot move the
     fields beside it. */
  section.model {
    --w-num: 92px;
    --w-sel: 200px;
    --grid-gap: 10px;
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-bottom: 1px solid var(--line);
    flex: 0 0 auto;
  }

  .spacer {
    margin-left: auto;
  }

  h1 {
    font-size: var(--text);
    margin: 0;
  }

  /* wraps, because two of these headings carry controls: at the form column's
     200 px floor `Save profile…` was clipped to `Sa… prof` rather than moving
     to a line of its own (WP-1215 measured it; WP-1034's rule is that overflow
     is wrap and never truncation, and it applies to a heading too) */
  h2 {
    margin: 10px 0 var(--s2);
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--s3);
  }

  /* a sub-heading *inside* a section, so deliberately not the section-heading
     register: it names a block of the form, not the form */
  h3 {
    font-size: var(--text-sm);
    text-transform: none;
    letter-spacing: 0;
    color: inherit;
    margin: 10px 0 3px;
  }

  p {
    margin: var(--s1) 0;
  }






  /* the path is the disambiguator and the name is the target: clip the path */



  /* `.pick` gives up its box because the *row* is the target, which means the
     row has to say so — "what says selected is the row's background, not a
     control's chrome" (app.css).  Without this the three examples read as
     three paragraphs of prose that happen to be clickable; found by looking at
     the page, and invisible to jsdom, which has no hover and no cursor. */


  /* the row is the target, and `.pick` is the one register app.css lets a
     panel lay out — a block, not a flex row, because the description is a
     sentence that has to wrap rather than a label that can be clipped */



  /* `.segmented` is `display: flex`, and every other use in the app sits in a
     flex row already; a wizard step is a block, so the register stretched to
     the full 90ch and drew a rule across the page (found in a browser, and
     invisible to jsdom, which lays nothing out).  A width, not a size: what the
     register owns is how tall the buttons are and how they are padded. */





  .inline-file {
    font-weight: 400;
  }

  .inline {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 4px 0;
    flex-wrap: wrap;
  }


  .editors {
    display: flex;
    gap: 0;
    overflow: hidden;
    flex: 1 1 auto;
    min-height: 0;
  }

  /* one column, stacked, below the width three floors need (`lib/resize.ts`).
     The pane scrolls once rather than each column scrolling separately, which
     is the difference between reading a form and hunting for it. */
  .editors.stacked {
    flex-direction: column;
    overflow: auto;
  }

  .editors.stacked > .column {
    flex: 0 0 auto;
    overflow: visible;
    border-left: 0;
  }

  .editors.stacked > .column + .column {
    border-top: 1px solid var(--line);
  }

  /* the scene needs a height of its own once it is a row: a 3D view in a
     `flex: 0 0 auto` row would otherwise be its content's height, which is zero */
  .editors.stacked > .column.view {
    height: 340px;
    padding-top: 8px;
  }

  /* Each column starts at **its own floor** and shares what is left over.
     Equal `flex: 1 1 0` shares looked fair and was not: at a 1000 px pane it
     gave the structure column 306 px against the 472 its atom table needs,
     while the two columns that needed less had more than enough (measured in a
     browser, WP-1034).  A basis is not a maximum — a drag still overrides both
     with `flex: 0 0 Npx` — and the 3D column keeps the 1.25 growth WP-1015 gave
     it, so free space still favours the only two-dimensional content here. */
  .column {
    /* the basis is `MODEL_MIN.form`, handed down as `--col-min` (the fallback is
       for a render before the style directive lands): the form column's floor
       is the width its three columns need, and it is stated once */
    flex: 1 1 var(--col-min, 320px);
    min-width: 0;
    overflow: auto;
    padding: 4px 12px 16px;
    position: relative;
  }

  /* the same `MODEL_MIN.structure` the stacking threshold is arithmetic over,
     as the column's preferred width.  Found stale in a browser (WP-1215): the
     number was *written* here as well as in `lib/resize.ts`, and only the
     latter had a test, so at exactly the stacking threshold the column came out
     505 px and side-scrolled a table the threshold exists to give room to.  It
     is handed down as `--structure-min` now, the way `--col-min` is, so the
     constant is stated once and this basis cannot go stale again. */
  .column.structure {
    flex-basis: var(--structure-min, 666px);
  }

  /* only where no splitter sits between them — the grip carries the rule
     itself, so a column next to one must not draw a second */
  .column + .column {
    border-left: 1px solid var(--line);
  }

  /* the viewer scrolls nothing: its plot fills the column and its controls sit
     under it, so an overflow here would scroll a 3D scene out of view */
  .column.view {
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding-bottom: 6px;
    /* a quarter more of the *free* space than the two form columns, because
       this is the only one whose content is two-dimensional: a form reads fine
       in a narrow column and a cell drawn in one is a cell drawn small */
    flex: 1.25 1 260px;
  }

  /* choosing one of N phases is the `.segmented` register (app.css) — as N
     plain buttons every phase wore the primary fill and `class:on` said
     nothing, so a two-phase model showed no selection at all.  `width:
     fit-content` because the register is `display: flex` and this `nav` is a
     block-level child of a *block* column, so it filled the column with 394 px
     of empty bordered strip (measured in Chrome; `align-self` is inert here,
     there being no flex parent to align in). */
  nav.phases {
    margin: var(--s2) 0;
    width: fit-content;
    max-width: 100%;
  }

  /* One grid of three columns, everywhere in this panel (WP-1216) — neither a
     wrapping flex nor a count the container picks.  A wrapping row let its
     widest item decide where the break fell, which is how one `<select>` moved
     every field after it; and a count that follows the width gave the profile
     three columns while the source beside it had five, so the two groups of one
     form did not line up (measured at the 559 px ceiling).  Three is the
     profile's own row — U V W over X Y — and the whole form is read against it.
     `max-width` is what stops a wide column stretching a number to 170 px, and
     `min(…, 100%)` lets the tracks fall below the floor rather than side-scroll
     the column: a valve that never opens while `MODEL_MIN.form` is this
     arithmetic (`lib/resize.ts`, crossed against these constants in
     `resize.test.ts`). */
  .grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(min(var(--w-num), 100%), 1fr));
    gap: 6px var(--grid-gap);
    max-width: calc(3 * var(--w-num) + 2 * var(--grid-gap));
    margin: 2px 0;
  }

  /* the rows start where `lib/model.ts:PROFILE_ROWS` says; the third slot of
     the second row is empty because this profile has no Z */
  .grid.profile .cell.rowstart {
    grid-column: 1;
  }

  /* A field is three lines — label, value, flag — and `subgrid` is what lines
     the three up *across* a row: without it a label that wraps to two lines
     pushes its own input below its neighbours', which is the other half of what
     "not aligned" meant.  The rows belong to the group; the 1 px between them
     is the cell's own, and the 6 px between rows of fields the group's. */
  .cell {
    display: grid;
    grid-template-rows: subgrid;
    grid-row: span 2;
    row-gap: 1px;
    font-size: var(--text-sm);
    min-width: 0;
  }

  /* …and a cell carrying a refine flag is three rows deep rather than two.
     Asked of the cell rather than declared on the grid, because a grid told the
     wrong number is a defect nothing catches: a subgrid clamps a child past its
     last track *into* it, so the flag would draw on top of the value. */
  .cell:has(.varyline) {
    grid-row: span 3;
  }

  /* a control whose content is a word rather than a number takes the whole row
     and caps its own width there.  Spanning the tracks is the point: a
     `<select>` that sits *in* one contributes its longest option to that track,
     which is how `flat_plate_transmission` set the width of the field beside
     it — and a phase named `fluorapatite` in a 92 px box is the same defect
     read from the other end. */
  .cell.fullrow {
    grid-column: 1 / -1;
    max-width: var(--w-sel);
  }

  .cellrow {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 2px 6px;
    margin: 2px 0;
  }

  /* the *value*, and only it — the refine flag beside it is a control of fixed
     size.  The child combinator is the fence: the flag lives inside
     `.varyline`, and a rule that reached it took all 84 px of the line and left
     the esd at zero width (WP-1214).  The width is the *track's*, and the grid
     caps itself at three `--w-num` tracks, so every control in the panel
     measures the same without one of them naming a width. */
  .grid .cell > input,
  .grid .cell > select,
  .grid .cell > .fixed {
    width: 100%;
  }

  /* the cell edges take their whole track: they carry a value and its esd, and
     six of them across a 666 px column is already the narrowest they get */
  .cellrow .cell > input,
  .cellrow .cell > .fixed {
    width: 100%;
  }

  /* The refine flag's own line, under the value it is about.  A line of its own
     rather than beside the box because a cell row is six columns wide: at the
     structure column's 472 px floor a shared line leaves ~57 px for a number
     that wants seven characters.  Rendered whether or not the field has a
     parameter row, so the cells of a wrapped grid keep one rhythm — an esd
     appearing after a fit must not move the form (WP-1213's rule one panel
     over). */
  .varyline {
    display: flex;
    align-items: center;
    gap: 4px;
    min-height: 16px;
    min-width: 0;
  }

  .varyline span {
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }

  /* …and beside the value where the row *is* the layout: a table cell and a
     DOF's bracketed pattern both read left to right. */
  .valrow {
    display: flex;
    align-items: center;
    gap: 3px;
    min-width: 0;
  }

  .vary {
    flex: 0 0 auto;
    margin: 0;
  }

  .caption {
    margin: 0;
    padding: 0 12px 4px;
    font-size: var(--text-sm);
  }

  /* the size is the control register's (app.css); this is the chrome */
  input,
  select {
    border: 1px solid var(--line);
    background: var(--bg);
    color: inherit;
    border-radius: 3px;
    padding: 1px 4px;
    min-width: 0;
    max-width: 100%;
  }

  input:focus,
  select:focus {
    border-color: var(--accent);
    outline: none;
  }

  input.narrow {
    width: 72px;
  }

  .fixed {
    opacity: 0.65;
    padding: 1px 4px;
    border: 1px solid transparent;
  }

  .tablewrap {
    overflow-x: auto;
  }

  table.atoms {
    width: 100%;
    /* its own floor, so the wrapper scrolls it instead of the browser shrinking
       eleven columns into an unreadable smear.  **Measured** (WP-1215) on the
       fluorapatite example, in the widest state it reaches: 642 px with one
       anisotropic atom, 610 without (599 / 567 on NAC).  `lib/resize.ts` adds
       the column's own padding to it, and states the same number for the same
       reason it always has — one is a CSS floor and the other is arithmetic,
       and neither can read the other. */
    min-width: 642px;
    border-collapse: collapse;
    font-size: var(--text-sm);
  }

  table.atoms th {
    text-align: left;
    font-weight: 600;
    color: var(--muted);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--line);
    padding: 2px 3px;
  }

  table.atoms td {
    padding: 1px 3px;
    vertical-align: middle;
  }

  /* the column is resizable now, so the fields follow it rather than a fixed
     72 px each summing past the column's own width */
  table.atoms input.narrow {
    width: 100%;
    min-width: 44px;
  }

  /* The `tr.sub td` separator went with the sub-rows (WP-1215): it was the last
     sub-row's bottom edge, so it sat directly on the next atom's inputs. The
     ADP disclosure is opened one atom at a time and needs no rule to be found. */
  tr.adprow td {
    padding-bottom: 4px;
  }

  /* the Wyckoff letter: a fact, not a control, so it reads back rather than
     competing with the ten cells that are */
  .site {
    opacity: 0.7;
    white-space: nowrap;
  }

  /* three coordinate cells that have to line up down the column, and a number
     whose digits move under the cursor is the one thing a table cannot do */
  td.coord input,
  td.coord .fixed {
    font-variant-numeric: tabular-nums;
  }

  /* the checkbox and its disclosure, and the position's one flag: both are the
     row's narrowest cells, so they do not take width from the numbers */
  td.anisocell,
  td.varycell {
    white-space: nowrap;
    width: 1%;
  }

  /* the disclosure's captions in the same register as the table's own headers —
     they used to be a plain muted span against uppercase tracked `th`s */
  .sublabel {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin: 1px 0;
  }

  .sublabel sup {
    text-transform: none;
    letter-spacing: 0;
  }

  /* `min(…, 100%)` rather than a bare track floor, and it is not cosmetic
     (WP-1215): this grid now lives in a `colspan` cell, and a track floor is
     part of the cell's min-content, so four 210 px patterns made the *whole
     atom table* 840 px wide the moment a disclosure was opened — scrolling
     label, species and site off the left edge of a table nobody had resized.
     `min()` lets the tracks fall below their preferred width when the container
     is narrower, which is the only thing that keeps the row a row. */
  .dofs {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(160px, 100%), 1fr));
    gap: 2px 8px;
  }

  /* six components rather than three, so the bracket needs the room */
  .dofs.wide-patterns {
    grid-template-columns: repeat(auto-fill, minmax(min(210px, 100%), 1fr));
  }

  label.dof {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
  }

  .dof .pattern {
    flex: 0 0 auto;
    color: var(--muted);
  }

  /* the *value*, and only it.  WP-1214 put a refine flag inside this label and
     the rule aimed at the box reached the checkbox beside it — the same trap
     `.cellrow input { width: 100% }` sprang on the esd, drawing it at zero
     width.  Here it drew the flag as a squashed circle instead, which reads as
     a control that half-rendered rather than as one that is wrong. */
  .dof input:not(.vary) {
    flex: 1 1 auto;
    width: auto;
    min-width: 0;
  }

  .dof input.vary {
    flex: 0 0 auto;
  }

  .add {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    margin-top: 6px;
  }

  footer {
    flex: 0 0 auto;
    border-top: 1px solid var(--line);
    padding: 4px 12px;
  }

  footer p {
    margin: 2px 0;
  }

  /* an `info` note is a fact about the change, not a complaint about it — the
     third tone `noteTone` returns, and the reason the two above are not enough */
  .info {
    opacity: 0.75;
  }

  /* ---- symmetry (WP-1035) ----
     A block rather than a `.cell`, because it is a field *and* three lines of
     consequence, and at 340 px (the sidebar's floor) those do not sit beside a
     label.  Every paragraph in it wraps: WP-1034's rule is that overflow is
     wrap, never truncation, and a refusal that says "the nearest allowed
     tensor is …" is exactly the sentence that must not be cut. */
  .symmetry {
    margin: 4px 0 2px;
  }

  .symrow {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .symrow input.sym {
    flex: 1 1 96px;
    min-width: 84px;
  }

  .symmetry p {
    margin: 2px 0 0;
    /* the refusals carry six-component tensors; they have to be able to break */
    overflow-wrap: anywhere;
  }

  .nowrapish {
    /* the summary is one line where there is room and two where there is not —
       never a scrollbar, which is what `white-space: nowrap` would have made */
    line-height: 1.35;
  }

  .preview {
    margin-top: 5px;
    padding: 5px 6px;
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: 3px;
    background: var(--surface, transparent);
  }

  .preview.blocked {
    border-left-color: var(--bad);
  }

  .preview .symrow {
    margin-top: 6px;
  }

  /* the letter rides in the coordinate cell rather than in a column of its own:
     the atom table's `min-content` is already 448 px (WP-1034 task 1) and a
     seventh column would take the whole column sideways at the sidebar's floor */
  .wyckoff {
    margin-left: 6px;
    opacity: 0.75;
    font-size: var(--text-xs);
  }
</style>
