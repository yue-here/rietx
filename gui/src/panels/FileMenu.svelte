<script lang="ts">
  /**
   * The File menu, on the project's name in the top bar (WP-2133).
   *
   * The maintainer's save model A (2026-11-07): work saves itself, so there is
   * no Save, and ⌘S only says "Saved". The menu acts on the project's folder:
   * Save a copy… copies it with its history and the window stays on this one,
   * Rename… edits the name in place, Move to… picks a folder, Close returns to
   * the start screen. Export writes the server's export kinds into a folder
   * the person picks, starting beside the project. A browser cannot show the
   * system's save dialog, so every folder comes from the folder browser
   * (WP-1205), which is confined to the home and working directories.
   *
   * The menu, its submenus, the dialogs and the toast are all overlays in
   * viewport coordinates: the header clips its project line, and no click
   * here may move the layout (the maintainer's rule of 2026-11-07). The rename
   * box is laid over the name for the same reason.
   */
  import { ApiError, api } from "../api";
  import { EXPORT_KINDS, type Entry, type ExportKind, type MenuItem,
           fileMenu, folderOf, projectStem, shortcut } from "../lib/filemenu";
  import Browse from "./Browse.svelte";

  let {
    project = null,
    busy = false,
    hasResult = false,
    say = (_line: string) => {},
    onnew = () => {},
    onopen = async (_path: string) => "",
    onproject = (_doc: any) => {},
    onclosed = () => {},
  }: {
    /** `GET /api/project`, or null on the start screen */
    project?: any;
    busy?: boolean;
    hasResult?: boolean;
    say?: (line: string) => void;
    onnew?: () => void;
    onopen?: (path: string) => Promise<string>;
    /** a rename or a move answered with the project document */
    onproject?: (doc: any) => void;
    onclosed?: () => void;
  } = $props();

  const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform ?? "");

  let trigger = $state<HTMLButtonElement | null>(null);
  let menuEl = $state<HTMLDivElement | null>(null);
  /** where the menu and its open submenu sit, in viewport pixels */
  let menuAt = $state<{ left: number; top: number } | null>(null);
  let sub = $state<{ id: string; left: number; top: number } | null>(null);
  let recent = $state<any[]>([]);
  let renaming = $state(false);
  let renameText = $state("");
  let renameEl = $state<HTMLInputElement | null>(null);
  /** the Save a copy and Export dialogs, which share one shape */
  let dialog = $state<{ kind: "copy" | ExportKind; name: string; where: string;
                        error: string; replace: boolean; working: boolean } | null>(null);
  /** the folder browser, and what it was opened for */
  let browse = $state<null | "open" | "move" | "where">(null);
  let toast = $state<{ text: string; left: number; top: number } | null>(null);
  let toastTimer: ReturnType<typeof setTimeout> | undefined;

  const path = $derived<string | null>(project?.path ?? null);
  const name = $derived(path ? projectStem(path) : "");
  const items = $derived(fileMenu({
    hasProject: !!project, busy, hasResult, nPhases: project?.n_phases ?? 0,
    mode: project?.doc?.mode ?? "", recent, current: path, mac,
  }));
  const subItems = $derived<Entry[]>(
    sub ? ((items.find((e) => e !== "-" && e.id === sub!.id) as MenuItem)?.sub ?? []) : []);

  async function openMenu() {
    if (menuAt) return closeMenu();
    const r = trigger!.getBoundingClientRect();
    menuAt = { left: r.left, top: r.bottom + 4 };
    try {
      recent = (await api.recent()).recent ?? [];
    } catch {
      recent = [];
    }
  }

  function closeMenu() {
    menuAt = null;
    sub = null;
  }

  function showSub(item: MenuItem, el: HTMLElement) {
    if (!item.sub || item.disabled) return;
    const r = el.getBoundingClientRect();
    // to the right of the item; to its left where the window ends first
    const left = r.right + 220 > window.innerWidth ? r.left - 222 : r.right + 2;
    sub = { id: item.id, left, top: r.top - 5 };
  }

  function flash(text: string, ms = 1600) {
    const r = trigger?.getBoundingClientRect();
    toast = { text, left: r?.left ?? 8, top: (r?.bottom ?? 40) + 6 };
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast = null), ms);
  }

  function refused(error: unknown): string {
    const message = error instanceof ApiError ? error.message : String(error);
    say(`refused: ${message}`);
    return message;
  }

  function choose(item: MenuItem) {
    if (item.disabled) return;
    if (item.sub) return;
    closeMenu();
    const id = item.id;
    if (id === "new") onnew();
    else if (id === "open") browse = "open";
    else if (id.startsWith("recent:")) {
      onopen(id.slice("recent:".length)).then((error) => { if (error) flash(error, 4000); });
    }
    else if (id === "recent-clear") clearRecent();
    else if (id === "copy") startCopy();
    else if (id === "rename") startRename();
    else if (id === "move") browse = "move";
    else if (id.startsWith("export:")) startExport(id.slice("export:".length));
    else if (id === "close") close();
  }

  async function clearRecent() {
    try {
      recent = (await api.clearRecent()).recent ?? [];
      say("session.recent_clear()");
    } catch (error) {
      flash(refused(error), 4000);
    }
  }

  function startCopy() {
    if (!path || busy) return;
    dialog = { kind: "copy", name: `${name} copy`, where: folderOf(path), error: "",
               replace: false, working: false };
  }

  function startExport(kind: string) {
    const k = EXPORT_KINDS.find((e) => e.kind === kind);
    if (!k || !path) return;
    dialog = { kind: k, name: k.file, where: folderOf(path), error: "", replace: false,
               working: false };
  }

  async function submit() {
    if (!dialog || dialog.working) return;
    const d = dialog;
    d.working = true;
    d.error = "";
    try {
      if (d.kind === "copy") {
        const out = await api.copyProject(d.where, d.name);
        say(`shutil.copytree("${path}", "${out.path}")  # the folder, history included`);
        dialog = null;
        flash(`Saved a copy as ${out.name}`);
      } else {
        const out = await api.export(d.kind.kind, { directory: d.where, filename: d.name,
                                                    overwrite: d.replace });
        say(exportEcho(d.kind.kind, out.path));
        dialog = null;
        flash(`Exported ${out.name}`);
      }
    } catch (error) {
      d.error = refused(error);
      // a file already there is asked about once, with the dialog's own button;
      // a folder is never replaced, so Save a copy only says so
      d.replace = d.kind !== "copy" && error instanceof ApiError
        && error.code === "DESTINATION_EXISTS";
      d.working = false;
    }
  }

  /** The Python call an export makes, for the console. */
  function exportEcho(kind: string, to: string): string {
    const calls: Record<string, string> = {
      cif: `ref.write_cif("${to}")`,
      reflections: `ref.write_reflection_table("${to}")`,
      qpa: `ref.write_qpa_table("${to}")`,
      html: `rx.viz.html.write_html(ref.result_, "${to}")`,
      result_json: `open("${to}", "w").write(ref.result_.model_dump_json(indent=2))`,
      instrument_profile: `rx.save_instrument_profile(ref.instrument, "${to}")`,
    };
    return calls[kind] ?? `# export ${kind} to ${to}`;
  }

  function startRename() {
    if (!path || busy) return;
    renameText = name;
    renaming = true;
    queueMicrotask(() => { renameEl?.focus(); renameEl?.select(); });
  }

  async function endRename(commit: boolean) {
    if (!renaming) return;
    renaming = false;
    const text = renameText.trim();
    if (!commit || !text || text === name || !path) return;
    try {
      const doc = await api.renameProject(text);
      say(`Path("${path}").rename("${doc.path}")`);
      onproject(doc);
      flash(`Renamed to ${projectStem(doc.path)}.rex`);
    } catch (error) {
      flash(refused(error), 4000);
    }
    trigger?.focus();
  }

  async function moveTo(directory: string) {
    browse = null;
    try {
      const doc = await api.moveProject(directory);
      say(`shutil.move("${path}", "${doc.path}")`);
      onproject(doc);
      flash(`Moved to ${folderOf(doc.path)}`);
    } catch (error) {
      flash(refused(error), 4000);
    }
  }

  async function close() {
    try {
      await api.closeProject();
      say("# project closed");
      onclosed();
    } catch (error) {
      flash(refused(error), 4000);
    }
  }

  async function saved() {
    if (!project) return;
    try {
      await api.save();
      flash("Saved");
    } catch (error) {
      flash(refused(error), 4000);
    }
  }

  function keydown(event: KeyboardEvent) {
    // capture phase, so Escape closing a menu never reaches the shell's own
    // Escape, which cancels a running fit; the folder browser answers its own
    if (event.key === "Escape" && !browse && (menuAt || dialog)) {
      event.stopPropagation();
      event.preventDefault();
      if (sub) sub = null;
      else if (menuAt) { closeMenu(); trigger?.focus(); }
      else dialog = null;
      return;
    }
    const which = shortcut(event);
    if (!which || browse || renaming) return;
    event.preventDefault();
    event.stopPropagation();
    if (which === "open" && !busy) browse = "open";
    else if (which === "copy") startCopy();
    else if (which === "saved") saved();
  }

  function away(event: MouseEvent) {
    if (!menuAt) return;
    const target = event.target as Node | null;
    if (target && (menuEl?.contains(target) || trigger?.contains(target))) return;
    if (target && (target as HTMLElement).closest?.(".fm-sub")) return;
    closeMenu();
  }
</script>

<!-- a resize can move the name, a scroll cannot: the header does not scroll,
     and a panel scrolling itself (the console during a run) must not close it -->
<svelte:window onkeydowncapture={keydown} onclick={away} onresize={() => closeMenu()} />

<span class="fm">
  <button class="pick fm-name" bind:this={trigger} aria-haspopup="menu"
    aria-expanded={!!menuAt} title={path ?? "File"} onclick={openMenu}
    class:muted={!project} class:hidden={renaming}
    >{project ? name : "No project"}<span class="caret" aria-hidden="true">▾</span></button>
  {#if renaming}
    <input class="fm-rename mono" bind:this={renameEl} bind:value={renameText}
      aria-label="Project name"
      onkeydown={(e) => {
        if (e.key === "Enter") { e.preventDefault(); endRename(true); }
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); endRename(false); }
      }}
      onblur={() => endRename(true)} />
  {/if}
</span>

{#if menuAt}
  <div class="fm-menu" role="menu" bind:this={menuEl} aria-label="File"
    style="left: {menuAt.left}px; top: {menuAt.top}px">
    {@render list(items, true)}
  </div>
  {#if sub}
    <div class="fm-menu fm-sub" role="menu" style="left: {sub.left}px; top: {sub.top}px">
      {@render list(subItems, false)}
    </div>
  {/if}
{/if}

{#snippet list(entries: Entry[], top: boolean)}
  {#each entries as entry, i (entry === "-" ? `-${i}` : entry.id)}
    {#if entry === "-"}
      <div class="sep" role="separator"></div>
    {:else}
      <button class="pick item" role="menuitem" disabled={entry.disabled} title={entry.title}
        aria-haspopup={entry.sub ? "menu" : undefined}
        aria-expanded={entry.sub ? sub?.id === entry.id : undefined}
        onmouseenter={(e) => { if (top) { if (entry.sub) showSub(entry, e.currentTarget); else sub = null; } }}
        onclick={(e) => { if (entry.sub) showSub(entry, e.currentTarget); else choose(entry); }}>
        <span class="label">{entry.label}</span>
        {#if entry.key}<span class="key muted">{entry.key}</span>{/if}
        {#if entry.sub}<span class="key muted" aria-hidden="true">›</span>{/if}
      </button>
    {/if}
  {/each}
{/snippet}

{#if toast}
  <div class="fm-toast" role="status" style="left: {toast.left}px; top: {toast.top}px"
    >{toast.text}</div>
{/if}

{#if dialog}
  <div class="backdrop">
    <div class="fm-dialog" role="dialog" aria-modal="true" aria-labelledby="fm-title">
    <form onsubmit={(e) => { e.preventDefault(); submit(); }}>
      <h2 id="fm-title">{dialog.kind === "copy" ? "Save a copy"
        : `Export ${dialog.kind.label.replace(/ \(.*\)$/, "").toLowerCase()}`}</h2>
      <label class="fld">
        <span class="muted">Name</span>
        <span class="pjn">
          <!-- svelte-ignore a11y_autofocus -->
          <input class="mono" bind:value={dialog.name} autofocus
            oninput={() => { if (dialog) { dialog.replace = false; dialog.error = ""; } }} />
          {#if dialog.kind === "copy"}<span class="muted mono">.rex</span>{/if}
        </span>
      </label>
      <label class="fld">
        <span class="muted">Where</span>
        <span class="pjn">
          <input class="mono" bind:value={dialog.where}
            oninput={() => { if (dialog) { dialog.replace = false; dialog.error = ""; } }} />
          <button type="button" class="ghost" onclick={() => (browse = "where")}>Browse…</button>
        </span>
      </label>
      {#if dialog.error}<p class="bad">{dialog.error}</p>{/if}
      <footer>
        <button type="button" class="ghost" onclick={() => (dialog = null)}>Cancel</button>
        <button type="submit" disabled={dialog.working || !dialog.name.trim()}>
          {dialog.kind === "copy" ? "Save" : dialog.replace ? "Replace" : "Export"}</button>
      </footer>
    </form>
    </div>
  </div>
{/if}

{#if browse === "open"}
  <Browse mode="open" onclose={() => (browse = null)} onopen={onopen} />
{:else if browse === "move"}
  <Browse mode="pick" heading="Move to" start={path ? folderOf(folderOf(path)) : undefined}
    onclose={() => (browse = null)} onpick={moveTo} />
{:else if browse === "where"}
  <Browse mode="pick" heading="Choose a folder" start={dialog?.where}
    onclose={() => (browse = null)}
    onpick={(p) => { if (dialog) { dialog.where = p; dialog.replace = false; dialog.error = ""; } browse = null; }} />
{/if}

<style>
  .fm {
    position: relative;
    display: inline-flex;
    max-width: 100%;
    vertical-align: baseline;
  }

  /* the `.pick` register gives up its box, so the name carries its own hover,
     as the start screen's rows do */
  .fm-name {
    max-width: 28em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    border-radius: var(--r-control);
    font-family: inherit;
  }

  .fm-name:hover:not(:disabled),
  .fm-name[aria-expanded="true"] {
    background: color-mix(in srgb, var(--fg) 6%, var(--panel));
  }

  .fm-name.hidden {
    visibility: hidden;
  }

  .caret {
    margin-left: 4px;
    color: var(--muted);
  }

  /* laid over the name, so typing in it moves nothing beside it */
  .fm-rename {
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    width: max(100%, 16em);
    box-sizing: border-box;
  }

  .fm-menu {
    position: fixed;
    z-index: 20;
    display: flex;
    flex-direction: column;
    min-width: 220px;
    padding: 4px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
    font-family: var(--font, inherit);
  }

  .item {
    display: flex;
    align-items: baseline;
    gap: 18px;
    width: 100%;
    padding: 5px 10px;
    border-radius: var(--r-control);
    white-space: nowrap;
    text-align: left;
  }

  .item:hover:not(:disabled),
  .item[aria-expanded="true"] {
    background: color-mix(in srgb, var(--fg) 6%, var(--panel));
  }

  .item:disabled {
    color: var(--muted);
  }

  .label {
    flex: 1 1 auto;
  }

  .key {
    flex: none;
  }

  .sep {
    height: 1px;
    margin: 4px 6px;
    background: var(--line);
  }

  .fm-toast {
    position: fixed;
    z-index: 21;
    padding: 3px 10px;
    border-radius: var(--r-control);
    background: var(--fg);
    color: var(--panel);
    font-size: var(--text-sm);
    white-space: nowrap;
    pointer-events: none;
  }

  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 9;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 10vh 16px 16px;
    background: rgba(0, 0, 0, 0.35);
  }

  .fm-dialog {
    width: min(480px, 100%);
  }

  form {
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
    padding: 16px 20px 12px;
  }

  /* sentence case, the maintainer's heading ruling of 2026-11-06 */
  h2 {
    margin: 0;
    font-size: var(--text);
    font-weight: 600;
    color: var(--fg);
    text-transform: none;
    letter-spacing: normal;
  }

  .fld {
    display: grid;
    grid-template-columns: 4em minmax(0, 1fr);
    align-items: center;
    gap: 10px;
  }

  .pjn {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }

  .pjn input {
    flex: 1 1 auto;
    min-width: 0;
  }

  .bad {
    margin: 0;
    overflow-wrap: anywhere;
  }

  footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
