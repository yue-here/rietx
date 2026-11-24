<script lang="ts">
  /**
   * A tab strip's `?` button and the box it opens (WP-2231, the maintainer's
   * look of 2026-11-21, item 6). As in the prototype, the button sits at the
   * strip's right in a fixed place, and the box explains the tab that is up.
   * The box floats, drawn as every floating layer is (`gui/STYLE.md`
   * § Components), so opening it moves nothing. Esc, a click elsewhere,
   * Close and a resize close it; Esc is taken in the capture phase, so it
   * backs out of the box and no further.
   */
  import type { HelpBoxEntry } from "./helpbox";

  let {
    entry,
    label,
    docsUrl = null,
  }: {
    entry: HelpBoxEntry;
    /** the button's accessible name, "About the Text tab" */
    label: string;
    docsUrl?: string | null;
  } = $props();

  let open = $state(false);
  let button: HTMLButtonElement | undefined = $state();
  let box: HTMLDivElement | undefined = $state();
  /** `top` below the button, or `bottom` above it where the window has no
   *  room below, as on the bottom panel's strip (WP-2211) */
  let at = $state<{ right: number; top?: number; bottom?: number }>({ right: 0, top: 0 });
  /** the room the box wants below its button before it opens above instead */
  const ROOM_PX = 280;

  // the box takes focus as it opens, as every help popover does (gui/CLAUDE.md)
  $effect(() => {
    if (open && box) box.focus();
  });

  const manual = $derived(docsUrl
    ? `${docsUrl.replace(/\/+$/, "")}/reference/gui-guide.html#${entry.anchor}` : null);

  function toggle(event: MouseEvent) {
    if (open) { open = false; return; }
    const r = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const right = Math.max(8, window.innerWidth - r.right);
    at = window.innerHeight - r.bottom < ROOM_PX && r.top > ROOM_PX
      ? { right, bottom: window.innerHeight - r.top + 6 } : { right, top: r.bottom + 6 };
    open = true;
  }

  function close(refocus = false) {
    open = false;
    if (refocus) button?.focus();
  }

  function keydown(event: KeyboardEvent) {
    if (!open || event.key !== "Escape") return;
    event.stopPropagation();
    event.preventDefault();
    close(true);
  }

  function away(event: PointerEvent) {
    if (!open) return;
    const target = event.target as Node | null;
    if (target && (box?.contains(target) || button?.contains(target))) return;
    close();
  }
</script>

<svelte:window onkeydowncapture={keydown} onpointerdowncapture={away}
  onresize={() => close()} />

<button class="ib help" bind:this={button} aria-label={label} aria-haspopup="dialog"
  aria-expanded={open} title="Help for this tab" onclick={toggle}>?</button>

{#if open}
  <div class="helpbox" role="dialog" tabindex="-1" aria-label={entry.title} bind:this={box}
    style:right="{at.right}px" style:top={at.top != null ? `${at.top}px` : null}
    style:bottom={at.bottom != null ? `${at.bottom}px` : null}>
    <p class="title">{entry.title}</p>
    {#if entry.lead}<p>{entry.lead}</p>{/if}
    <ul>
      {#each entry.items as item (item)}<li>{item}</li>{/each}
    </ul>
    <div class="foot">
      {#if manual}
        <a class="link" href={manual} target="_blank" rel="noopener">Open in the manual</a>
      {:else}
        <span></span>
      {/if}
      <button class="ghost" onclick={() => close(true)}>Close</button>
    </div>
  </div>
{/if}

<style>
  .help {
    align-self: center;
    margin-left: auto;
    font-weight: 600;
    color: var(--muted);
  }

  /* focused as it opens, for a screen reader; the box itself draws no ring */
  .helpbox:focus {
    outline: none;
  }

  .helpbox {
    position: fixed;
    z-index: 20;
    width: 340px;
    max-width: calc(100vw - 16px);
    box-sizing: border-box;
    padding: 12px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
    line-height: 1.45;
    text-align: left;
  }

  .helpbox p {
    margin: 0 0 8px;
  }

  .helpbox .title {
    margin-bottom: 4px;
    font-weight: 600;
  }

  .helpbox ul {
    margin: 0 0 8px;
    padding-left: 18px;
  }

  .foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 8px;
    border-top: 1px solid var(--line);
  }
</style>
