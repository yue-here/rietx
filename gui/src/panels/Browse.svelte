<script lang="ts">
  /**
   * The filesystem browser (WP-1205): one modal, two jobs.
   *
   * `mode="open"` opens a project directory directly; `mode="pick"` hands a
   * directory back to the caller (the wizard's own "4 · Project" step) without
   * opening anything — a browser cannot return a path any other way, so this
   * is the one place the GUI reads the filesystem for its own sake, and it
   * reads only what `GET /api/fs` is willing to answer: the home directory and
   * the process's cwd, never the whole machine.
   */
  import { ApiError, api } from "../api";

  let {
    mode = "open",
    heading = "",
    start = undefined,
    onclose = () => {},
    onopen = async (_path: string) => "",
    onpick = (_path: string) => {},
  }: {
    mode?: "open" | "pick";
    /** the heading, where the pick is for something else than a new project
     *  (the File menu's Move to and its dialogs' folder, WP-2133) */
    heading?: string;
    /** the folder to list first; the home directory when absent */
    start?: string;
    onclose?: () => void;
    onopen?: (path: string) => Promise<string>;
    onpick?: (path: string) => void;
  } = $props();

  let path = $state<string | null>(null);
  let parent = $state<string | null>(null);
  let roots = $state<string[]>([]);
  let entries = $state<{ name: string; path: string; is_project: boolean }[]>([]);
  let typed = $state("");
  let error = $state("");
  let busy = $state(false);

  async function go(target?: string) {
    busy = true;
    try {
      const listing = await api.fs(target);
      path = listing.path;
      parent = listing.parent;
      roots = listing.roots ?? [];
      entries = listing.entries ?? [];
      typed = listing.path;
      error = "";
    } catch (err) {
      error = err instanceof ApiError ? err.message : String(err);
    } finally {
      busy = false;
    }
  }

  // the first listing only: later changes to `start` are not a navigation.  A
  // start the browser may not list (a project outside the two roots, a typed
  // Where) falls back to home, so the dialog never opens with nothing to pick
  const first = () => start;
  go(first()).then(() => { if (first() && path === null) go(); });

  async function openHere(target: string) {
    error = await onopen(target);
    if (!error) onclose();
  }

  function keydown(event: KeyboardEvent) {
    if (event.key === "Escape") onclose();
  }
</script>

<svelte:window onkeydown={keydown} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" onclick={onclose}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="panel" role="dialog" aria-label="browse the filesystem" tabindex="-1"
       onclick={(event) => event.stopPropagation()}>
    <header>
      <h2>{heading || (mode === "pick" ? "Choose a project directory" : "Open a project")}</h2>
      <button class="ghost" onclick={onclose}>Close</button>
    </header>

    <div class="nav">
      <button class="ghost" disabled={busy || !parent} onclick={() => go(parent!)}
        title="up one level">↑</button>
      {#each roots as root, i (root)}
        <button class="ghost" disabled={busy} onclick={() => go(root)}>
          {i === 0 ? "Home" : "Current directory"}
        </button>
      {/each}
      <input class="mono wide" bind:value={typed}
        onkeydown={(e) => { if (e.key === "Enter") go(typed); }}
        placeholder="/path/to/a/directory" />
      <button class="ghost" disabled={busy} onclick={() => go(typed)}>Go</button>
    </div>

    {#if error}<p class="bad">{error}</p>{/if}

    <ul>
      {#each entries as e (e.path)}
        <li>
          {#if mode === "open" && e.is_project}
            <button class="pick" disabled={busy} onclick={() => openHere(e.path)}
              title="open this project">
              <strong>{e.name}</strong>
              <span class="muted">project</span>
            </button>
          {:else}
            <button class="ghost nav-into" disabled={busy} onclick={() => go(e.path)}>
              {e.name}/
            </button>
          {/if}
        </li>
      {/each}
      {#if !entries.length}
        <li class="muted none">nothing here</li>
      {/if}
    </ul>

    {#if mode === "pick"}
      <div class="pick-here">
        <button disabled={busy || !path} onclick={() => path && onpick(path)}>
          Use this directory
        </button>
        <span class="muted mono">{path ?? ""}</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 10vh;
    z-index: 10;
  }

  .panel {
    width: min(620px, 92vw);
    max-height: 76vh;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: var(--s3) var(--s3) 0;
  }

  header h2 {
    margin: 0;
    font-size: var(--text);
  }

  .nav {
    display: flex;
    align-items: center;
    gap: var(--s2);
    padding: var(--s3);
    flex-wrap: wrap;
  }

  .nav input {
    flex: 1 1 220px;
    min-width: 0;
  }

  .bad {
    margin: 0 var(--s3) var(--s2);
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 4px;
    overflow-y: auto;
    flex: 1 1 auto;
  }

  /* the `.pick` register (app.css) — a whole row is the target, same as the
     example list beside it (Model.svelte) */
  li .pick {
    display: flex;
    align-items: baseline;
    gap: var(--s3);
    width: 100%;
    border-radius: var(--r-control);
    padding: var(--s2) var(--s3);
  }

  .nav-into {
    width: 100%;
    justify-content: flex-start;
  }

  .none {
    padding: var(--s2) var(--s3);
  }

  .pick-here {
    display: flex;
    align-items: center;
    gap: var(--s3);
    padding: var(--s3);
    border-top: 1px solid var(--line);
  }
</style>
