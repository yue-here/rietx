<script lang="ts">
  /**
   * The start screen (WP-2131): what the window shows with no project open.
   *
   * The maintainer's round-9 design of 2026-11-08, after the four-part screen
   * of VS Code, JetBrains, Xcode and Blender: New, Open, a recent list and a
   * small learning area, with no tour and no news.  Left: the wordmark and
   * version, New project… (the view's one filled button), Open…, and links to
   * the manual and the tutorials.  Right: Recent, then Examples.  A first run
   * has no recent list, so it shows Examples alone, which is the list being
   * empty rather than a remembered flag (WP-1017's rule for a first-run aid).
   *
   * Each row is one target, with a ⋯ button and a right-click for the rest of
   * its verbs (interaction rules, adopted 2026-11-08).  A recent project that
   * has moved stays listed as "Not found", with Locate… and Remove from list,
   * because a row that vanished between two launches says nothing about why.
   * Show in Finder waits for the desktop app: a browser page cannot reveal a
   * folder.
   */
  import SpaceGroup from "../SpaceGroup.svelte";
  import { lastSeparator } from "../lib/wizard";
  import Browse from "./Browse.svelte";

  let {
    version = "",
    recent = [],
    examples = [],
    busy = false,
    docsUrl = null,
    error = "",
    hasProject = false,
    onnew = () => {},
    onopen = async (_path: string) => "",
    onexample = async (_name: string, _reset?: boolean) => "",
    onremove = async (_path: string) => {},
    onback = () => {},
  }: {
    version?: string;
    /** `GET /api/recent`: newest first, a moved project marked `missing` */
    recent?: any[];
    /** `GET /api/examples`: each with whether it has been built yet */
    examples?: any[];
    busy?: boolean;
    /** the manual's root for this version, from the help corpus */
    docsUrl?: string | null;
    /** the last refused open, in the verb's own words */
    error?: string;
    /** shown over an open project, from the header's Open… */
    hasProject?: boolean;
    onnew?: () => void;
    onopen?: (path: string) => Promise<string>;
    onexample?: (name: string, reset?: boolean) => Promise<string>;
    onremove?: (path: string) => Promise<void>;
    onback?: () => void;
  } = $props();

  type Item = { label: string; run: () => void; disabled?: boolean };
  /** the one open row menu: which row, and its items */
  let menu = $state<{ key: string; items: Item[] } | null>(null);
  /** the folder browser, for Open… or for Locate…ing a moved project */
  let browse = $state<{ locate: string | null } | null>(null);

  const manual = $derived(docsUrl ? `${docsUrl.replace(/\/+$/, "")}/` : null);
  const tutorials = $derived(manual ? `${manual}start/tutorials.html` : null);

  /** A date a person reads, from the list's UTC stamp; "" when it has none. */
  function when(utc: string): string {
    const t = Date.parse(utc);
    if (!Number.isFinite(t)) return "";
    return new Date(t).toLocaleDateString(undefined,
      { day: "numeric", month: "short", year: "numeric" });
  }

  /** The folder a project sits in. */
  function folder(path: string): string {
    const cut = lastSeparator(path);
    return cut > 0 ? path.slice(0, cut) : path;
  }

  function recentItems(entry: any): Item[] {
    return entry.missing
      ? [{ label: "Locate…", run: () => (browse = { locate: entry.path }) },
         { label: "Remove from list", run: () => onremove(entry.path) }]
      : [{ label: "Open", run: () => onopen(entry.path), disabled: busy },
         { label: "Remove from list", run: () => onremove(entry.path) }];
  }

  function exampleItems(ex: any): Item[] {
    return [
      { label: "Open", run: () => onexample(ex.name), disabled: busy },
      // the old Reset: the built copy is thrown away and made again
      { label: "Open a fresh copy", run: () => onexample(ex.name, true),
        disabled: busy || !ex.built },
    ];
  }

  function toggle(key: string, items: Item[]) {
    menu = menu?.key === key ? null : { key, items };
  }

  function choose(item: Item) {
    menu = null;
    item.run();
  }

  function openRecent(entry: any) {
    if (entry.missing) toggle(`r:${entry.path}`, recentItems(entry));
    else onopen(entry.path);
  }

  /** Locate…: open the project where it now is, then drop the stale row. */
  async function located(path: string): Promise<string> {
    const stale = browse?.locate;   // read first: an open replaces this screen
    const refusal = await onopen(path);
    if (!refusal && stale && stale !== path) await onremove(stale);
    return refusal;
  }

  function away(event: MouseEvent) {
    if (!menu) return;
    const target = event.target as HTMLElement | null;
    // a click on the row that owns the menu is that row's own business
    if (target?.closest?.("li")?.dataset.key !== menu.key) menu = null;
  }

  function keydown(event: KeyboardEvent) {
    if (event.key === "Escape" && menu) menu = null;
  }
</script>

<svelte:window onclick={away} onkeydown={keydown} />

<section class="start" aria-label="Start">
  <div class="cols">
    <div class="left">
      <div class="wordmark">rietx</div>
      <div class="muted version">{version ? `Version ${version}` : ""}</div>
      <button disabled={busy} onclick={onnew}>New project…</button>
      <button class="ghost" disabled={busy} onclick={() => (browse = { locate: null })}
        >Open…</button>
      {#if hasProject}
        <button class="ghost" onclick={onback}>Back to the project</button>
      {/if}
      {#if manual}
        <div class="links">
          <a class="link" href={manual} target="_blank" rel="noopener">Manual</a>
          <a class="link" href={tutorials} target="_blank" rel="noopener">Tutorials</a>
        </div>
      {/if}
    </div>

    <div class="right">
      {#if error}<p class="bad">{error}</p>{/if}
      {#if recent.length}
        <h2>Recent</h2>
        <ul>
          {#each recent as entry (entry.path)}
            {@const key = `r:${entry.path}`}
            <li class:missing={entry.missing} data-key={key}
              oncontextmenu={(e) => { e.preventDefault(); menu = { key, items: recentItems(entry) }; }}>
              <button class="pick row" disabled={busy && !entry.missing} title={entry.path}
                onclick={() => openRecent(entry)}>
                <span class="name">{entry.name.replace(/\.rex$/, "")}</span>
                <span class="muted when">{entry.missing ? "Not found" : when(entry.opened_utc)}</span>
                <span class="muted sub">{#each entry.phases ?? [] as p, i (i)}{i ? ", " : ""}{p[0]}
                  <SpaceGroup symbol={p[1]} />{/each}{entry.phases?.length ? " · " : ""}{folder(entry.path)}</span>
              </button>
              <button class="ghost more" aria-label="More for {entry.name}"
                aria-haspopup="menu" aria-expanded={menu?.key === key}
                onclick={() => toggle(key, recentItems(entry))}>⋯</button>
              {#if menu?.key === key}
                {@render menuList(menu.items)}
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
      {#if examples.length}
        <h2>Examples</h2>
        <ul>
          {#each examples as ex (ex.name)}
            {@const key = `x:${ex.name}`}
            <li data-key={key}
              oncontextmenu={(e) => { e.preventDefault(); menu = { key, items: exampleItems(ex) }; }}>
              <button class="pick row" disabled={busy} onclick={() => onexample(ex.name)}>
                <span class="name">{ex.title}</span>
                <span class="when"></span>
                <span class="muted sub">{ex.description}</span>
              </button>
              <button class="ghost more" aria-label="More for the {ex.title} example"
                aria-haspopup="menu" aria-expanded={menu?.key === key}
                onclick={() => toggle(key, exampleItems(ex))}>⋯</button>
              {#if menu?.key === key}
                {@render menuList(menu.items)}
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </div>
</section>

{#snippet menuList(items: Item[])}
  <div class="menu" role="menu">
    {#each items as item (item.label)}
      <button class="pick" role="menuitem" disabled={item.disabled}
        onclick={() => choose(item)}>{item.label}</button>
    {/each}
  </div>
{/snippet}

{#if browse}
  <Browse mode="open" onclose={() => (browse = null)}
    onopen={browse.locate ? located : onopen} />
{/if}

<style>
  .start {
    height: 100%;
    overflow: auto;
    background: var(--bg);
  }

  /* the prototype's measure: a 188 px left column and the lists beside it,
     centred in at most 940 px */
  .cols {
    display: flex;
    gap: 56px;
    max-width: 940px;
    margin: 0 auto;
    padding: clamp(24px, 9vh, 96px) 32px 48px;
  }

  .left {
    flex: none;
    width: 188px;
    display: flex;
    flex-direction: column;
    gap: var(--s3);
  }

  .left > button {
    justify-content: flex-start;
  }

  .version {
    margin: 2px 0 20px;
  }

  .links {
    display: flex;
    gap: 16px;
    margin-top: 20px;
  }

  /* an anchor's own underline, which the `.link` register draws on hover only */
  .links a:not(:hover) {
    text-decoration: none;
  }

  .right {
    flex: 1 1 auto;
    min-width: 0;
  }

  /* sentence case, the maintainer's heading ruling of 2026-11-06, over the
     app's uppercase section heading (app.css); placed over the rows' text */
  h2 {
    margin: 0 0 4px;
    padding-left: 10px;
    font-size: var(--text);
    font-weight: 500;
    text-transform: none;
    letter-spacing: normal;
  }

  ul {
    list-style: none;
    margin: 0 0 28px;
    padding: 0;
  }

  li {
    position: relative;
  }

  /* the `.pick` register gives up its box, so the row carries its own hover
     (gui/CLAUDE.md, the examples' rule) */
  .row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    column-gap: 16px;
    width: 100%;
    padding: 7px 44px 7px 10px;
    border-radius: 8px;
    cursor: pointer;
  }

  .row:hover:not(:disabled) {
    background: color-mix(in srgb, var(--fg) 5%, var(--panel));
  }

  .name {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .when {
    font-size: var(--text-sm);
    white-space: nowrap;
    align-self: center;
  }

  .sub {
    grid-column: 1 / -1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .missing .name {
    color: var(--muted);
  }

  /* shown on hover, on focus and while its menu is open; opacity, so its
     appearing moves nothing */
  .more {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    opacity: 0;
  }

  li:hover .more,
  .more:focus-visible,
  .more[aria-expanded="true"] {
    opacity: 1;
  }

  .menu {
    position: absolute;
    right: 8px;
    top: calc(100% - 4px);
    z-index: 5;
    display: flex;
    flex-direction: column;
    min-width: 180px;
    padding: 4px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  .menu .pick {
    padding: 6px 10px;
    border-radius: var(--r-control);
  }

  .menu .pick:hover:not(:disabled) {
    background: color-mix(in srgb, var(--fg) 6%, var(--panel));
  }

  .menu .pick:disabled {
    color: var(--muted);
  }

  /* below 640 px the two columns stack (the round-9 design) */
  @media (max-width: 640px) {
    .cols {
      flex-direction: column;
      gap: 24px;
      padding: 24px 16px;
    }

    .left {
      width: auto;
      flex-direction: row;
      flex-wrap: wrap;
      align-items: center;
    }

    .wordmark,
    .version,
    .links {
      flex-basis: 100%;
    }

    .version {
      margin: 0 0 8px;
    }

    .links {
      margin-top: 4px;
    }
  }
</style>
