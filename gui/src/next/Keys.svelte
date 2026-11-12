<script lang="ts">
  /**
   * The list of keys, opened by `?` (WP-2215; WP-2214 row 240), as Gmail and
   * GitHub list theirs. It reads the palette's commands, so a command that
   * gains a key is listed without this file knowing about it.
   */
  import type { Command } from "../lib/palette";

  let { commands, onclose }: { commands: Command[]; onclose: () => void } = $props();

  const keyed = $derived(commands.filter((c) => c.key));
  let done: HTMLButtonElement | undefined = $state();

  $effect(() => {
    done?.focus({ preventScroll: true });
  });

  function keydown(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    event.preventDefault();
    onclose();
  }
</script>

<svelte:window onkeydowncapture={keydown} />

<div class="scrim" role="presentation" onpointerdown={(e) => e.target === e.currentTarget && onclose()}>
  <div class="dlg" role="dialog" aria-modal="true" aria-labelledby="keys-title">
    <h2 id="keys-title">Keyboard shortcuts</h2>
    <table>
      <tbody>
        {#each keyed as c (c.id)}
          <tr><td>{c.label}</td><td><kbd>{c.key}</kbd></td></tr>
        {/each}
      </tbody>
    </table>
    <div class="foot">
      <button class="ghost" bind:this={done} onclick={onclose}>Done</button>
    </div>
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 30;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 72px;
    background: color-mix(in srgb, var(--fg) 22%, transparent);
  }

  .dlg {
    min-width: 400px;
    padding: 18px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  h2 {
    margin: 0 0 10px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  td {
    padding: 4px 0;
  }

  td + td {
    text-align: right;
  }

  kbd {
    font: var(--mono);
    color: var(--muted);
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
</style>
