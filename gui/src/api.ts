/** The HTTP surface as typed calls, and the one place an error envelope is read.
 *
 * Every route answers `{...}` on success or `{error: {code, message, where,
 * details}}` with a 4xx/5xx status, so this module turns a refusal into a thrown
 * `ApiError` carrying the *code* — which is what callers branch on.  Two codes
 * are not failures in the UI sense and are named here so panels can say so:
 * `RUN_IN_FLIGHT` (a mutating verb during a run — disable the control, do not
 * toast) and `NO_RESULT` / `NO_PROJECT` (an empty state, not an error).
 */

export class ApiError extends Error {
  code: string;
  status: number;
  where: string[];
  details: Array<{ line?: number; message: string; where?: string; text?: string }>;

  constructor(status: number, payload: any) {
    const error = payload?.error ?? {};
    super(error.message ?? `HTTP ${status}`);
    this.code = error.code ?? "HTTP_ERROR";
    this.status = status;
    this.where = error.where ?? [];
    this.details = error.details ?? [];
  }

  /** True when the refusal is "a run is in flight", not "you did it wrong". */
  get busy(): boolean {
    return this.code === "RUN_IN_FLIGHT";
  }

  /** True when there is simply nothing to show yet. */
  get empty(): boolean {
    return this.code === "NO_RESULT" || this.code === "NO_PROJECT";
  }
}

async function call(method: string, path: string, body?: unknown): Promise<any> {
  const init: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(path, init);
  const text = await response.text();
  let payload: any = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { error: { code: "BAD_RESPONSE", message: text.slice(0, 200) } };
  }
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

/**
 * The upload routes, which are the only ones whose body is not JSON.
 *
 * A `File` goes up as its own bytes with the filename and the reader options in
 * the query string (WP-1014); `token` re-reads a file the server already holds,
 * which is what flipping the aniso checkbox or picking another pdCIF block does.
 * Base64 in a JSON envelope would inflate the body by a third and change
 * nothing else.
 */
async function upload(kind: string, file: File | null,
                      options: Record<string, string> = {},
                      token?: string): Promise<any> {
  const query = new URLSearchParams(options);
  if (file) query.set("filename", file.name);
  if (token) query.set("upload", token);
  const response = await fetch(`/api/upload/${kind}?${query}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: file ?? new Blob([]),
  });
  const text = await response.text();
  let payload: any = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { error: { code: "BAD_RESPONSE", message: text.slice(0, 200) } };
  }
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

/**
 * A route answering float64 arrays rather than JSON (WP-1461, D4): the curves,
 * every channel once. A refusal is still the JSON error envelope.
 */
async function arrays(path: string, body?: unknown): Promise<ArrayBuffer> {
  const response = await fetch(path, body === undefined ? undefined : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (response.ok) return response.arrayBuffer();
  const text = await response.text();
  let payload: any = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { error: { code: "BAD_RESPONSE", message: text.slice(0, 200) } };
  }
  throw new ApiError(response.status, payload);
}

export const api = {
  capabilities: () => call("GET", "/api/capabilities"),
  /** The whole help corpus plus `docs_url` (WP-1202/1203).  Fetched once at
   *  boot beside capabilities: it is static for the life of the build, needs
   *  no project, and is therefore not behind the in-flight 409. */
  help: () => call("GET", "/api/help"),
  version: () => call("GET", "/api/version"),
  /** What one space-group symbol constrains (WP-1206).  Project-free, like the
   *  two above: the wizard's typed-cell step asks it before anything exists,
   *  and `free_cell` is the list of boxes the cell form then draws — the rule
   *  itself stays on the server. */
  spacegroup: (symbol: string) =>
    call("GET", `/api/spacegroup?space_group=${encodeURIComponent(symbol)}`),
  recent: () => call("GET", "/api/recent"),
  /** Drop one entry from the recent list; the project itself is untouched. */
  removeRecent: (path: string) => call("POST", "/api/recent/remove", { path }),
  clearRecent: () => call("POST", "/api/recent/clear"),

  /** The example projects shipped in the wheel (WP-1204).  `built` says
   *  whether opening one is a plain open or a build first, which is what lets
   *  the empty state be honest about what a first click costs. */
  examples: () => call("GET", "/api/examples"),
  openExample: (name: string) => call("POST", "/api/examples/open", { name }),
  resetExample: (name: string) => call("POST", "/api/examples/reset", { name }),

  /** The app's own `ui` keys — the person's, not a project's (WP-1044).  Same
   *  grammar as `patchProject`'s `ui`: a top-level merge, `null` drops a key,
   *  and it persists on the verb rather than on a save. */
  settings: () => call("GET", "/api/settings"),
  patchSettings: (ui: Record<string, unknown>) => call("POST", "/api/settings", { ui }),

  /** The open project's kept unapplied edits (WP-2209): `draft` is `null`
   *  when there are none; `head` is the node they were made against and
   *  `head_now` the project's. */
  recovery: () => call("GET", "/api/recovery"),
  /** Keep a project's pending edits, or delete the copy with `null`.  The
   *  write names its project, so the last one for a project just left lands. */
  putRecovery: (project: string, head: string | null, draft: unknown) =>
    call("PUT", "/api/recovery", { project, head, draft }),
  /** The same write from a page being closed: `keepalive` lets it outlive the
   *  page, and nobody is left to read its answer. */
  putRecoveryOnHide: (project: string, head: string | null, draft: unknown) => {
    fetch("/api/recovery", {
      method: "PUT", keepalive: true, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, head, draft }),
    }).catch(() => {});
  },

  /** Stage a file and get it back described — phase one of an import. */
  uploadFile: (kind: string, file: File, options: Record<string, string> = {}) =>
    upload(kind, file, options),
  /** Re-read a staged file with different reader options — no second upload. */
  restage: (kind: string, token: string, options: Record<string, string> = {}) =>
    upload(kind, null, options, token),
  /** What a staged multi-scan file holds, labelled — a second walk of the
   *  ranges, so it is fetched when the picker opens and never on the preview. */
  patternScans: (token: string) =>
    call("GET", `/api/upload/pattern/scans?upload=${encodeURIComponent(token)}`),
  /** Phase two: tokens become a project.  Nothing exists on disk until this. */
  newProject: (body: Record<string, unknown>) => call("POST", "/api/project/new", body),

  /** A read-only directory listing for the "Open…" browser (WP-1205), confined
   *  server-side to the home directory and the process's cwd. `path` omitted
   *  lists the home directory. */
  fs: (path?: string) =>
    call("GET", path ? `/api/fs?path=${encodeURIComponent(path)}` : "/api/fs"),

  project: () => call("GET", "/api/project"),
  openProject: (path: string) => call("POST", "/api/project/open", { path }),
  patchProject: (settings: Record<string, unknown>) => call("POST", "/api/project", settings),
  /** A flush a client may call and never must: every settings verb already
   *  saved and the model was on disk the moment its node was appended. */
  save: () => call("POST", "/api/project/save"),
  /** The File menu's folder verbs (WP-2133): each refused while a run is in
   *  flight, and none replaces a folder that is already there. */
  copyProject: (directory: string, name: string) =>
    call("POST", "/api/project/copy", { directory, name }),
  renameProject: (name: string) => call("POST", "/api/project/rename", { name }),
  moveProject: (directory: string) => call("POST", "/api/project/move", { directory }),
  closeProject: () => call("POST", "/api/project/close"),

  params: () => call("GET", "/api/params"),
  /** Values, vary flags and (WP-2126) holds, limits and value restraints, in
   *  one call; the server applies limits and restraints first, as one model
   *  edit, then values, unholds, vary flags and holds. */
  patchParams: (delta: {
    values?: Record<string, number>;
    vary?: Record<string, boolean>;
    hold?: Record<string, boolean>;
    limits?: Record<string, [number | null, number | null]>;
    restraints?: Record<string, { target: number; sigma: number } | null>;
  } | Record<string, unknown>) =>
    call("PATCH", "/api/params", delta),
  plan: () => call("GET", "/api/plan"),
  /** Either `{preset: name}` or `{plan: spec}` — a preset is stored *expanded
   *  through the mode*, so what comes back is what will actually run. */
  putPlan: (body: { preset?: string; plan?: unknown }) => call("PUT", "/api/plan", body),
  plans: () => call("GET", "/api/plans"),
  /** The stages resolved against the live parameter table (WP-1208): per stage
   *  what its globs reach, what it frees on top of the last, what it cannot
   *  free and why, and the Rwp of the node that ran it. */
  planResolve: () => call("GET", "/api/plan/resolve"),

  /** The structure **plus** three derived arms: `sites` (which `…dof.k` moves
   *  each atom, and which have none at all — a fully fixed special position),
   *  `symmetry` (one gemmi lookup per phase) and `causes` (the symmetry
   *  responsible for each held row). All three are free; the Wyckoff letter is
   *  not, and lives on `symmetry()` below. */
  structure: () => call("GET", "/api/structure"),
  /** One phase's symmetry in full — Wyckoff letters and oriented site-symmetry
   *  symbols, a spglib search per atom, memoised server-side on (space group,
   *  positions).  A route of its own because a **miss** is still 2.0-5.5 ms an
   *  atom (WP-1035, re-measured 1215) and folding that into `structure()` would
   *  put it in front of every consumer of that route.  Fetched on every head
   *  move since WP-1215: a repeat ask is 1-3 us, so the atom table's `site`
   *  column no longer waits behind a button. */
  symmetry: (phase = 0) =>
    call("GET", `/api/structure/symmetry?phase=${phase}`),
  /** What changing a phase's space group would do, applying nothing: the
   *  refusals a candidate parameter table raises, the entries that gain or lose
   *  a tie, and the notes for what a table diff cannot see. */
  symmetryPreview: (phase: number, spaceGroup: string) =>
    call("POST", "/api/structure/symmetry/preview",
         { phase, space_group: spaceGroup }),
  /** …and the apply, gated on that same preview server-side. One history node. */
  setSymmetry: (phase: number, spaceGroup: string) =>
    call("POST", "/api/structure/symmetry", { phase, space_group: spaceGroup }),
  /** The same model as *drawable geometry*: the symmetry orbit with each image's
   *  rotated displacement tensor, bonds over the 27 nearest lattice
   *  translations, and the cell frame — none of which a `Structure` dump says.
   *  The arguments are drawing thresholds, not settings, which is why they ride
   *  on the query string and are never persisted. */
  structure3d: (phase = 0, bondTolerance?: number, disorder?: "all" | "major",
                centres?: string[] | null, ligands?: string[] | null) => {
    const query = new URLSearchParams({ phase: String(phase) });
    if (bondTolerance !== undefined) {
      query.set("bond_tolerance", String(bondTolerance));
    }
    if (disorder !== undefined) query.set("disorder", disorder);
    // present and empty asks for none, so only null leaves the chemistry's
    if (centres != null) query.set("centres", centres.join(","));
    if (ligands != null) query.set("ligands", ligands.join(","));
    return call("GET", `/api/structure3d?${query}`);
  },
  instrument: () => call("GET", "/api/instrument"),
  /** A whole validated model, not a field patch — adding a phase or an ADP block
   *  changes what the parameter table *contains* (WP-1008).  One history node. */
  patchStructure: (structure: unknown, label?: string) =>
    call("PATCH", "/api/structure", { structure, label }),
  patchInstrument: (instrument: unknown, label?: string) =>
    call("PATCH", "/api/instrument", { instrument, label }),
  /** Opt one atom into anisotropic ADPs.  Its own verb because both directions
   *  are physics (the isotropic tensor is not Uiso·δ, and U_eq weights by the
   *  metric) and a client that computed either would get non-orthogonal cells
   *  wrong. */
  aniso: (path: string, on: boolean) =>
    call("POST", "/api/structure/aniso", { path, on }),
  /** Move one atom to a typed position (WP-1215).  The server projects it onto
   *  the site's DOF basis and refuses an unreachable target naming the nearest
   *  one it can reach — a coordinate is an affine tie, so what lands in theta is
   *  a displacement.  One `set_value` node, and nothing at all when the atom is
   *  already there. */
  position: (atom: string, xyz: readonly number[]) =>
    call("POST", "/api/structure/position", { atom, xyz }),

  run: (body: Record<string, unknown> = { kind: "fit" }) => call("POST", "/api/run", body),
  cancel: () => call("POST", "/api/cancel"),
  runState: () => call("GET", "/api/run/state"),

  result: () => call("GET", "/api/result"),
  /** The pattern's every channel and the fit's curves on the ones it kept, as
   *  `rxplot.mjs`'s `unpack` reads them; before a fit, the pattern alone. */
  curves: () => arrays("/api/result/curves"),
  /** The background curve, the observed pattern and the curve's esd at each
   *  fitted channel, packed as the curves are (WP-2129). Writes nothing. */
  background: () => arrays("/api/background"),
  /** The curves at values nobody has applied, writing nothing (WP-2125): the
   *  fitted channels, the model, its background, each phase, the three
   *  residuals and the ticks, with the Rwp there. */
  preview: (values: Record<string, number>) => arrays("/api/preview", { values }),
  /** The three layers **plus** an `apply` arm parallel to `suggested_actions`:
   *  whether the server would act on each one, and what it would run.  Idle-only
   *  (Layers 1-2 read the compiled model a stage would be rewriting), so this
   *  answers 409 `RUN_IN_FLIGHT` mid-run. */
  report: () => call("GET", "/api/report"),
  /** Carry out one suggestion, as one stage, through the run machinery.
   *  `paths` disambiguates when a report suggests one kind twice (two textured
   *  phases); the server refuses rather than guessing if it is omitted. */
  applyAction: (kind: string, paths?: string[]) =>
    call("POST", "/api/report/apply", paths ? { kind, paths } : { kind }),

  history: () => call("GET", "/api/history"),
  checkout: (nodeId: string) => call("POST", "/api/history/checkout", { node_id: nodeId }),
  /** Checkout **plus** a tag: this DAG has only `head` and tags, so "branch"
   *  names a fork point rather than creating a ref (WP-1008). */
  branch: (nodeId: string, name: string) =>
    call("POST", "/api/history/branch", { node_id: nodeId, name }),
  tag: (nodeId: string, name: string) =>
    call("POST", "/api/history/tag", { node_id: nodeId, name }),
  annotate: (nodeId: string, body: { label?: string; notes?: Record<string, string> }) =>
    call("POST", "/api/history/annotate", { node_id: nodeId, ...body }),
  /** Parameter values that differ between two nodes — the question a compare view
   *  actually has, and the reason a node's ~10 kB state is not in `/api/history`. */
  historyDiff: (a: string, b: string) =>
    call("GET", `/api/history/diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  historyCompare: (ids: string[]) =>
    call("GET", `/api/history/compare?ids=${encodeURIComponent(ids.join(","))}`),

  textdoc: () => call("GET", "/api/textdoc"),
  putTextdoc: (text: string, baseRevision?: string, validateOnly = false) =>
    call("PUT", "/api/textdoc", {
      text,
      base_revision: baseRevision,
      validate_only: validateOnly,
    }),

  /** The stored peak list plus the decimated raw pattern — the one payload the
   *  plot can draw before any fit exists (WP-1027). */
  peaks: () => call("GET", "/api/peaks"),
  pickPeaks: (body: { shoulders?: boolean } = {}) => call("POST", "/api/peaks", body),
  addPeak: (twoTheta: number) => call("POST", "/api/peaks/add", { two_theta: twoTheta }),
  movePeak: (index: number, twoTheta: number) =>
    call("POST", "/api/peaks/move", { index, two_theta: twoTheta }),
  removePeak: (index: number) => call("POST", "/api/peaks/remove", { index }),
  flagPeak: (index: number, body: { use_for_indexing?: boolean; flags?: string[] }) =>
    call("POST", "/api/peaks/flag", { index, ...body }),
  refitGroup: (group: number, nComponents?: number) =>
    call("POST", "/api/peaks/refit",
         nComponents === undefined ? { group } : { group, n_components: nComponents }),
  /** An indexing run on the one run state machine: same worker, same 409, the
   *  engines' own events on the same stream. */
  index: () => call("POST", "/api/index"),
  /** The last answer with the adopt gate answered per candidate — the button's
   *  enabled-ness and the route's willingness are one answer, never two. */
  indexResult: () => call("GET", "/api/index/result"),
  /** One candidate's predicted positions, for the plot overlay (WP-1211).  Its
   *  own route rather than an arm of the answer above, because it is a cost the
   *  answer should not carry: hundreds of floats per candidate, wanted for one
   *  at a time.  Over the server's cap it is a sample — read `n_total`. */
  candidateTicks: (candidate: number) =>
    call("GET", `/api/index/ticks?candidate=${candidate}`),
  adoptCandidate: (candidate: number, spaceGroup?: string) =>
    call("POST", "/api/index/adopt",
         spaceGroup ? { candidate, space_group: spaceGroup } : { candidate }),
  /** Rank one candidate's extinction classes — the same run machine, and a
   *  measurement any candidate may ask for (the gate stays on adopt). */
  screenExtinctions: (candidate: number) =>
    call("POST", "/api/index/extinction", { candidate }),
  extinctionResult: () => call("GET", "/api/index/extinction"),

  /** The staged series and its chain settings (WP-1016).  Answers before any
   *  file is staged — the empty list plus the defaults *is* the empty state. */
  series: () => call("GET", "/api/series"),
  /** Replace the list and/or the settings.  A whole-list PUT because the order
   *  **is** the series, and every file is read server-side here rather than at
   *  run time — a file that does not parse is a message about that file, not a
   *  chain that dies half way through. */
  putSeries: (body: Record<string, unknown>) => call("PUT", "/api/series", body),
  /** One run on the one run machine: same worker, same 409, and the per-pattern
   *  events on the same stream with `series_index` stamped on. */
  runSeries: (plan?: unknown) =>
    call("POST", "/api/series/run", plan ? { plan } : {}),
  /** Entries, trajectories with esds, and the fences. Each trajectory carries
   *  its largest forward/backward gap in esds (`n_sigma`) and where it sits. */
  seriesResult: () => call("GET", "/api/series/result"),
  /** One member's channels and curves, as `curves` sends the project's: built
   *  by the same function, so the σ and the residuals are the same arithmetic. */
  seriesCurves: (index: number) => arrays(`/api/series/curves?index=${index}`),
  /** That pattern's own history tree — **read-only**: a tree is pinned to its
   *  data fingerprint, so its nodes cannot be checked out into this project. */
  seriesHistory: (index: number) =>
    call("GET", `/api/series/history?index=${index}`),

  /** One export kind; with `directory` it is written there rather than into
   *  `exports/`, and an existing file is refused unless `overwrite` (WP-2133). */
  export: (kind: string, body: { directory?: string; filename?: string; overwrite?: boolean } = {}) =>
    call("POST", `/api/export/${kind}`, body),
  events: (since: number) => call("GET", `/api/events?poll=1&since=${since}`),
};
