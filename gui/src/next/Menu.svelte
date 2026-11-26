<script lang="ts" module>
  /** One row of a menu: an action, a checkbox or one option of a radio set. */
  export type MenuItem = {
    id: string;
    label: string;
    disabled?: boolean;
    /** a verb phrase, or why the row is disabled */
    title?: string;
    /** a checkbox row's state; a radio row is `checked` with `radio` set */
    checked?: boolean;
    radio?: boolean;
    /** a submenu, opened by hover, a click or → on this row */
    sub?: MenuEntry[];
    /** a short fact after the label, in the muted ink: a count */
    note?: string;
  };
  export type MenuEntry = MenuItem | "-";
  /** Where the menu opens: `x` is its left edge, or its right edge under `align: "right"`. */
  export type MenuAt = { x: number; y: number; align?: "left" | "right" };
</script>

<script lang="ts">
  /**
   * A menu floating over the page (written for WP-2213's graph window, carried
   * into the rebuild by WP-2215 as the one menu every piece uses), drawn as the File menu is
   * (`gui/STYLE.md` § Components: floating layers share one drawing). It opens
   * over the page, so opening it moves nothing (principle 4).
   *
   * A row closes the menu, except a checkbox row, since "a menu of checkboxes
   * stays open while you tick" (2026-11-08). Esc, a click elsewhere and a
   * resize close it; Esc is taken in the capture phase, so it backs out of the
   * menu and no further (`gui/STYLE.md` § Interaction, rule 2).
   *
   * A row with `sub` opens its submenu beside it on hover, a click or →, and
   * ← or Esc backs out of it (`gui/STYLE.md` § Components: "Submenus open on
   * hover, click or the arrow key"). The open submenu is the row's id, so it
   * stays open while its checkboxes are ticked and the items re-render.
   */
  let {
    at,
    items,
    label,
    anchor = null,
    onchoose,
    onclose,
  }: {
    at: MenuAt;
    items: MenuEntry[];
    label: string;
    /** the button that opened the menu: a click on it toggles, never re-opens */
    anchor?: HTMLElement | null;
    onchoose: (id: string) => void;
    onclose: () => void;
  } = $props();

  let el: HTMLDivElement | undefined = $state();
  let width = $state(0);
  let height = $state(0);
  /** the row whose submenu is open, and where that submenu opens */
  let openSub = $state<string | null>(null);
  let subAt = $state<{ x: number; y: number; left: number } | null>(null);
  let subEl: HTMLDivElement | undefined = $state();
  let subWidth = $state(0);
  let subHeight = $state(0);
  const subRow = $derived(items.find((e): e is MenuItem => e !== "-" && e.id === openSub) ?? null);
  const subItems = $derived(subRow?.sub ?? null);
  const subLabel = $derived(subRow?.label ?? "");
  /** The submenu's left edge: right of its row, or left of the menu where
   *  the window has no room to the right. */
  const subLeft = $derived(subAt ? (subAt.x + subWidth + 4 > window.innerWidth
    ? Math.max(4, subAt.left - subWidth) : subAt.x) : 0);
  const subTop = $derived(subAt ? Math.max(4, Math.min(subAt.y - 4,
    window.innerHeight - subHeight - 4)) : 0);

  function showSub(item: MenuItem, row: HTMLElement, focus = false) {
    if (item.disabled || !item.sub) return;
    const r = row.getBoundingClientRect(), m = el!.getBoundingClientRect();
    subAt = { x: m.right - 2, y: r.top, left: m.left + 2 };
    openSub = item.id;
    if (focus) {
      queueMicrotask(() => subEl?.querySelector<HTMLButtonElement>("button:not(:disabled)")
        ?.focus({ preventScroll: true }));
    }
  }

  function closeSub(back = false) {
    const id = openSub;
    openSub = null;
    subAt = null;
    if (back && id) el?.querySelector<HTMLButtonElement>(`[data-sub="${CSS.escape(id)}"]`)?.focus();
  }

  /** The left edge, kept inside the window. */
  const left = $derived(Math.max(4, Math.min(
    at.align === "right" ? at.x - width : at.x,
    window.innerWidth - width - 4)));
  /** The top edge: below the point, or above it where the window has no room
   * below, as a desktop's context menu turns (a History row sits at the
   * window's foot, WP-2211). */
  const top = $derived(at.y + height + 4 > window.innerHeight
    ? Math.max(4, at.y - height) : at.y);

  function choose(item: MenuItem, row?: HTMLElement) {
    if (item.disabled) return;
    // a click opens, never toggles: the pointer's hover opened it a moment ago
    if (item.sub) {
      if (row) showSub(item, row, true);
      return;
    }
    onchoose(item.id);
    if (item.checked === undefined || item.radio) onclose();
  }

  function keydown(event: KeyboardEvent) {
    const target = event.target as HTMLElement | null;
    if (event.key === "ArrowRight" && target?.dataset.sub) {
      const item = items.find((e) => e !== "-" && e.id === target.dataset.sub);
      if (item && item !== "-") showSub(item, target, true);
      event.preventDefault();
      return;
    }
    if (openSub && (event.key === "ArrowLeft" || event.key === "Escape")
        && (event.key === "Escape" || subEl?.contains(target))) {
      event.stopPropagation();
      event.preventDefault();
      closeSub(true);
      return;
    }
    if (event.key !== "Escape") return;
    event.stopPropagation();
    event.preventDefault();
    // read before closing: the opener's props are getters over the state
    // onclose clears, so the anchor is gone once it has run
    const back = anchor;
    onclose();
    back?.focus();
  }

  function away(event: MouseEvent) {
    const target = event.target as Node | null;
    if (target && (el?.contains(target) || subEl?.contains(target) || anchor?.contains(target))) return;
    onclose();
  }

  $effect(() => {
    el?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus({ preventScroll: true });
  });
</script>

<svelte:window onkeydowncapture={keydown} onpointerdowncapture={away} onresize={onclose} />

<div class="rx-menu" role="menu" aria-label={label} bind:this={el} bind:offsetWidth={width}
  bind:offsetHeight={height} style="left: {left}px; top: {top}px">
  {@render rows(items, false)}
</div>

{#if subItems && subAt}
  <div class="rx-menu sub" role="menu" aria-label={subLabel || label} bind:this={subEl} bind:offsetWidth={subWidth} bind:offsetHeight={subHeight}
    style="left: {subLeft}px; top: {subTop}px">
    {@render rows(subItems, true)}
  </div>
{/if}

{#snippet rows(list: MenuEntry[], inSub: boolean)}
  {#each list as entry, i (entry === "-" ? `-${i}` : entry.id)}
    {#if entry === "-"}
      <div class="sep" role="separator"></div>
    {:else if entry.sub}
      <button class="pick item" class:open={openSub === entry.id} disabled={entry.disabled}
        title={entry.title} role="menuitem" aria-haspopup="menu" aria-expanded={openSub === entry.id}
        data-sub={entry.id}
        onpointerenter={(ev) => showSub(entry, ev.currentTarget)}
        onclick={(ev) => choose(entry, ev.currentTarget)}>
        <span class="mark" aria-hidden="true"></span>
        <span class="label">{entry.label}</span>
        {#if entry.note}<span class="note">{entry.note}</span>{/if}
        <svg class="chev" viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 3l3 3-3 3" /></svg>
      </button>
    {:else}
      <button class="pick item" disabled={entry.disabled} title={entry.title}
        role={entry.checked === undefined ? "menuitem"
          : entry.radio ? "menuitemradio" : "menuitemcheckbox"}
        aria-checked={entry.checked === undefined ? undefined : entry.checked}
        onpointerenter={() => { if (!inSub && openSub) closeSub(); }}
        onclick={() => choose(entry)}>
        <span class="mark" aria-hidden="true">{#if entry.checked}<svg viewBox="0 0 16 16"
          ><path d="M3.5 8.5l3 3 6-7" /></svg>{/if}</span>
        <span class="label">{entry.label}</span>
        {#if entry.note}<span class="note">{entry.note}</span>{/if}
      </button>
    {/if}
  {/each}
{/snippet}

<style>
  .rx-menu {
    position: fixed;
    z-index: 20;
    display: flex;
    flex-direction: column;
    min-width: 200px;
    padding: 4px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  .item {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 5px 10px 5px 6px;
    border-radius: var(--r-control);
    white-space: nowrap;
    text-align: left;
    font-weight: 400;
  }

  .item:hover:not(:disabled) {
    background: var(--hover);
  }

  .item:disabled {
    color: var(--muted);
  }

  /* the tick's column is kept on every row, so the labels share one edge */
  .mark {
    flex: none;
    display: inline-flex;
    width: 16px;
  }

  .mark svg {
    width: 14px;
    height: 14px;
    fill: none;
    stroke: var(--accent-ink);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .label {
    flex: 1 1 auto;
  }

  .note {
    flex: none;
    margin-left: 12px;
    color: var(--muted);
  }

  /* a submenu's row: its chevron at the right, lit while its submenu shows */
  .chev {
    flex: none;
    width: 10px;
    height: 10px;
    margin-left: 8px;
    fill: none;
    stroke: var(--muted);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .item.open {
    background: var(--hover);
  }

  .sep {
    height: 1px;
    margin: 4px 6px;
    background: var(--line);
  }
</style>
