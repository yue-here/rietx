<script lang="ts">
  /**
   * The workflow menu, beside the graphs toggle in the top bar (WP-2204).
   *
   * The button names the workflow the window is in; the menu lists all five,
   * with a check beside the current one and no heading, because a menu does not
   * restate the button that opened it (the maintainer, 2026-11-07). A
   * placeholder carries `· placeholder` after its name, here and on the button,
   * so a workflow that is not built never reads as one that is.
   *
   * The menu is an overlay in viewport coordinates, as the File menu is
   * (WP-2133): opening it moves nothing, and the header's wrapping cannot clip
   * it. Its drawing is the File menu's, copied rather than shared while two
   * open pieces rewrite `app.css`; one register for both is a follow-up.
   */
  import { PLACEHOLDER_MARK, WORKFLOWS, isPlaceholder, workflow,
           type WorkflowId } from "../lib/workflows";

  let {
    current = "refine",
    disabled = false,
    onchoose = (_id: WorkflowId) => {},
  }: {
    current?: WorkflowId;
    /** with no project the button is drawn and disabled, so opening one moves nothing */
    disabled?: boolean;
    onchoose?: (id: WorkflowId) => void;
  } = $props();

  let trigger = $state<HTMLButtonElement | null>(null);
  let menuEl = $state<HTMLDivElement | null>(null);
  let menuAt = $state<{ left: number; top: number } | null>(null);

  function toggle() {
    if (menuAt) return close();
    const r = trigger!.getBoundingClientRect();
    menuAt = { left: r.left, top: r.bottom + 4 };
  }

  function close() {
    menuAt = null;
  }

  function choose(id: WorkflowId) {
    close();
    if (id !== current) onchoose(id);
    trigger?.focus();
  }

  function keydown(event: KeyboardEvent) {
    // capture phase, so Escape closing the menu never reaches the shell's own
    // Escape, which cancels a running fit (the File menu's rule)
    if (event.key === "Escape" && menuAt) {
      event.stopPropagation();
      event.preventDefault();
      close();
      trigger?.focus();
    }
  }

  function away(event: MouseEvent) {
    if (!menuAt) return;
    const target = event.target as Node | null;
    if (target && (menuEl?.contains(target) || trigger?.contains(target))) return;
    close();
  }
</script>

<svelte:window onkeydowncapture={keydown} onclick={away} onresize={close} />

<button class="pick wf-name" bind:this={trigger} aria-haspopup="menu"
  aria-expanded={!!menuAt} {disabled} title="choose a workflow" onclick={toggle}
  >{workflow(current).name}{#if isPlaceholder(current)}<span class="muted mark"
    >{` · ${PLACEHOLDER_MARK}`}</span>{/if}<span class="caret" aria-hidden="true">▾</span></button>

{#if menuAt}
  <div class="wf-menu" role="menu" aria-label="Workflow" bind:this={menuEl}
    style="left: {menuAt.left}px; top: {menuAt.top}px">
    {#each WORKFLOWS as entry (entry.id)}
      <button class="pick item" role="menuitemradio" aria-checked={entry.id === current}
        onclick={() => choose(entry.id)}>
        <span class="check" aria-hidden="true">{entry.id === current ? "✓" : ""}</span>
        <span class="label">{entry.name}</span>
        {#if isPlaceholder(entry.id)}<span class="muted">· {PLACEHOLDER_MARK}</span>{/if}
      </button>
    {/each}
  </div>
{/if}

<style>
  /* the `.pick` register gives up its box, so the button carries its own
     hover, as the File menu's name does; the name is in the heading weight,
     as the design round drew it */
  .wf-name {
    flex: 0 0 auto;
    white-space: nowrap;
    border-radius: var(--r-control);
    font-family: inherit;
    font-weight: 600;
  }

  .wf-name:hover:not(:disabled),
  .wf-name[aria-expanded="true"] {
    background: color-mix(in srgb, var(--fg) 6%, var(--panel));
  }

  .wf-name:disabled {
    color: var(--muted);
  }

  .mark {
    font-weight: 400;
  }

  .caret {
    margin-left: 4px;
    color: var(--muted);
    font-weight: 400;
  }

  .wf-menu {
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
    gap: 6px;
    width: 100%;
    padding: 5px 10px 5px 6px;
    border-radius: var(--r-control);
    white-space: nowrap;
    text-align: left;
  }

  .item:hover {
    background: color-mix(in srgb, var(--fg) 6%, var(--panel));
  }

  .check {
    flex: 0 0 14px;
    text-align: center;
  }
</style>
