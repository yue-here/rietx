<script lang="ts">
  /**
   * The offer of unapplied edits kept from the last session (WP-2209).
   *
   * Reopening a project whose pending edits were kept asks one question with
   * two answers: put the edits back, or delete them.  It is interaction rule
   * 11's asking-to-choose (`gui/STYLE.md`), so the dialog names what was kept
   * and offers both outcomes, and confirms nothing.  It is modal, because an
   * edit made before the answer would have to overwrite the kept copy or be
   * lost.  Escape answers neither: it closes the dialog and keeps the copy,
   * which is offered again when the project next opens (the maintainer's
   * ruling of 2026-11-10).  Every key is held here, so no shortcut acts
   * behind the question (the shell's Escape cancels a fit).
   */
  import { offerText, type Draft } from "../lib/recovery";

  let {
    draft,
    savedUtc = null,
    moved = false,
    onrestore = () => {},
    ondiscard = () => {},
    onlater = () => {},
  }: {
    draft: Draft;
    /** when the copy was last written, ISO 8601 */
    savedUtc?: string | null;
    /** the project's head has moved since the edits were made */
    moved?: boolean;
    onrestore?: () => void;
    ondiscard?: () => void;
    /** Escape: neither restored nor discarded, offered at the next open */
    onlater?: () => void;
  } = $props();

  let dialog = $state<HTMLElement | null>(null);

  /** No shortcut acts behind the question: every key stops here, in the
   *  capture phase, while its default (Enter or Space on a button) still
   *  happens.  Escape closes the dialog and keeps the copy.  Tab moves
   *  between the two buttons and never out of the dialog: stopping a key's
   *  listeners does not stop its default, so focus that left could type an
   *  edit behind the question, which nothing would keep. */
  function keydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onlater();
      return;
    }
    if (event.key === "Tab" && dialog) {
      event.preventDefault();
      const buttons = [...dialog.querySelectorAll<HTMLButtonElement>("button")];
      const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
      const step = event.shiftKey ? -1 : 1;
      buttons[(at + step + buttons.length) % buttons.length]?.focus();
    }
    event.stopPropagation();
  }
</script>

<svelte:window onkeydowncapture={keydown} />

<div class="backdrop">
  <div class="rc-dialog" bind:this={dialog} role="dialog" aria-modal="true" aria-labelledby="rc-title">
    <h2 id="rc-title">Unapplied edits</h2>
    <p>{offerText(draft, savedUtc)}</p>
    {#if moved}<p class="muted">The project has been refined or edited since. Restored values will replace the current ones.</p>{/if}
    <footer>
      <button type="button" class="ghost" onclick={ondiscard}>Discard</button>
      <!-- svelte-ignore a11y_autofocus -->
      <button type="button" autofocus onclick={onrestore}>Restore</button>
    </footer>
  </div>
</div>

<style>
  /* FileMenu's dialog drawing, the one floating layer (gui/STYLE.md) */
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

  .rc-dialog {
    width: min(420px, 100%);
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

  p {
    margin: 0;
  }

  footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding-top: 4px;
  }
</style>
