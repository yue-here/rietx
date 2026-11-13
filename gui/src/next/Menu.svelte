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

  /** The left edge, kept inside the window. */
  const left = $derived(Math.max(4, Math.min(
    at.align === "right" ? at.x - width : at.x,
    window.innerWidth - width - 4)));

  function choose(item: MenuItem) {
    if (item.disabled) return;
    onchoose(item.id);
    if (item.checked === undefined || item.radio) onclose();
  }

  function keydown(event: KeyboardEvent) {
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
    if (target && (el?.contains(target) || anchor?.contains(target))) return;
    onclose();
  }

  $effect(() => {
    el?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus({ preventScroll: true });
  });
</script>

<svelte:window onkeydowncapture={keydown} onpointerdowncapture={away} onresize={onclose} />

<div class="rx-menu" role="menu" aria-label={label} bind:this={el} bind:offsetWidth={width}
  style="left: {left}px; top: {at.y}px">
  {#each items as entry, i (entry === "-" ? `-${i}` : entry.id)}
    {#if entry === "-"}
      <div class="sep" role="separator"></div>
    {:else}
      <button class="pick item" disabled={entry.disabled} title={entry.title}
        role={entry.checked === undefined ? "menuitem"
          : entry.radio ? "menuitemradio" : "menuitemcheckbox"}
        aria-checked={entry.checked === undefined ? undefined : entry.checked}
        onclick={() => choose(entry)}>
        <span class="mark" aria-hidden="true">{#if entry.checked}<svg viewBox="0 0 16 16"
          ><path d="M3.5 8.5l3 3 6-7" /></svg>{/if}</span>
        <span class="label">{entry.label}</span>
      </button>
    {/if}
  {/each}
</div>

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

  .sep {
    height: 1px;
    margin: 4px 6px;
    background: var(--line);
  }
</style>
