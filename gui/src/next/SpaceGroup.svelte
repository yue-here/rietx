<script lang="ts">
  /**
   * Change space group… (WP-2216, WP-2214 row 125): a dialog holding the
   * preview, opened from a phase's ⋯ menu.
   *
   * The preview is today's (WP-1035): what the typed symbol would do, applying
   * nothing, as a diff of two `ParameterTable`s the server builds. This dialog
   * formats it with `lib/symmetry.ts` and decides nothing. Change is the
   * dialog's one filled button and is enabled only by a preview that changes
   * the setting and is not blocked; the server re-runs the preview and gates
   * on it, so the button is a convenience and never the check.
   *
   * Enter previews the typed symbol. Esc closes the dialog (interaction rule
   * 2), as a click on the scrim does.
   */
  import { api } from "../api";
  import { entryLines, noteTone, siteLines, symbolChanged } from "../lib/symmetry";

  let {
    phase,
    name,
    current,
    say,
    onchanged,
    onclose,
  }: {
    phase: number;
    name: string;
    current: string;
    say: (line: string) => void;
    onchanged: () => void;
    onclose: () => void;
  } = $props();

  /** the symbol the dialog opened on, typed over from there */
  const opened = () => current;
  let typed = $state(opened());
  let preview = $state<any>(null);
  let shown = $state("");
  let error = $state("");
  let busy = $state(false);
  let field: HTMLInputElement | undefined = $state();

  const changed = $derived(symbolChanged(typed, current));
  /** a preview answers the symbol it was asked about, and no other */
  const fresh = $derived(preview !== null && shown === typed.trim());
  const entries = $derived(fresh && !preview.blocked ? entryLines(preview.entries) : []);
  const sites = $derived(fresh && !preview.blocked ? siteLines(preview.sites) : []);

  $effect(() => {
    field?.focus({ preventScroll: true });
    field?.select();
  });

  async function previewIt() {
    const wanted = typed.trim();
    if (!wanted || busy) return;
    busy = true;
    error = "";
    try {
      preview = await api.symmetryPreview(phase, wanted);
      shown = wanted;
    } catch (exc) {
      preview = null;
      error = (exc as Error).message;
    } finally {
      busy = false;
    }
  }

  async function change() {
    const wanted = typed.trim();
    if (!fresh || preview.blocked || !preview.changed || busy) return;
    busy = true;
    error = "";
    try {
      await api.setSymmetry(phase, wanted);
      say(`structure.phases[${phase}].space_group = "${wanted}"  # ref.edit(structure=…)`);
      onchanged();
      onclose();
    } catch (exc) {
      error = (exc as Error).message;
    } finally {
      busy = false;
    }
  }

  function keydown(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    event.preventDefault();
    onclose();
  }
</script>

<svelte:window onkeydowncapture={keydown} />

<div class="scrim" role="presentation" onpointerdown={(e) => e.target === e.currentTarget && onclose()}>
  <div class="dlg" role="dialog" aria-modal="true" aria-labelledby="sg-title">
    <h2 id="sg-title">Change the space group of {name}</h2>
    <form class="row" onsubmit={(e) => { e.preventDefault(); void previewIt(); }}>
      <input class="mono" bind:this={field} bind:value={typed} aria-label="Space group"
        autocomplete="off" spellcheck="false" disabled={busy} />
      <button type="submit" class="ghost" disabled={busy || !typed.trim()}>Preview</button>
    </form>
    {#if error}<p class="bad">{error}</p>{/if}
    {#if fresh}
      <div class="preview">
        <p><span class="mono">{preview.to?.xhm ?? "?"}</span>
          {#if !preview.changed}: the same setting, so nothing would change.
          {:else if preview.blocked}: this model cannot carry it.
          {:else if preview.to?.constraints}: {preview.to.constraints}{/if}</p>
        {#each preview.refusals ?? [] as refusal (refusal.where)}
          <p class="bad">{refusal.message}</p>
        {/each}
        {#each preview.notes ?? [] as note (note.kind + note.where.join())}
          <p class={noteTone(note.kind)}>{note.message}</p>
        {/each}
        {#each [...entries, ...sites] as line (line)}
          <p class="muted">{line}</p>
        {/each}
        {#if !preview.blocked && preview.changed && !entries.length && !sites.length}
          <p class="muted">No parameter gains or loses a tie. The reflection list is what moves.</p>
        {/if}
      </div>
    {/if}
    <div class="foot">
      <button class="ghost" onclick={onclose}>Cancel</button>
      <button disabled={!fresh || preview.blocked || !preview.changed || busy || !changed}
        onclick={change}>Change</button>
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
    width: 480px;
    max-width: calc(100vw - 32px);
    padding: 18px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  h2 {
    margin: 0 0 14px;
  }

  .row {
    display: flex;
    gap: 8px;
  }

  .row input {
    flex: 1 1 auto;
    min-width: 0;
    border: 1px solid var(--line-strong);
    background: var(--bg);
    color: var(--fg);
  }

  .mono {
    font-family: var(--mono-family);
  }

  .preview {
    margin-top: 12px;
    max-height: 40vh;
    overflow: auto;
  }

  p {
    margin: 4px 0;
    font-size: var(--text-sm);
  }

  .muted {
    color: var(--muted);
  }

  .bad {
    color: var(--bad);
  }

  .warn {
    color: var(--warn);
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 18px;
  }
</style>
