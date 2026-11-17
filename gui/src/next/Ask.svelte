<script lang="ts" module>
  /** One typed field of a small form: a name, a species, a coordinate. */
  export type AskField = { id: string; label: string; value: string; mono?: boolean };
</script>

<script lang="ts">
  /**
   * A small form floating beside what it is about (WP-2216): Rename…, Change
   * species… and Add atom… from the phase and atom menus. A menu's row that
   * needs a typed value opens one, as a menu's "…" promises (macOS HIG).
   *
   * It floats over the page, drawn as every floating layer is (`gui/STYLE.md`
   * § Components), so opening it moves nothing. Enter sends; Esc, a click
   * elsewhere and a resize close it, and Esc is taken in the capture phase so
   * it backs out of the form and no further (interaction rule 2). A refusal
   * stays in the form, in the verb's own words, with the typed text kept.
   */
  let {
    at,
    label,
    fields,
    submit,
    onsubmit,
    onclose,
  }: {
    at: { x: number; y: number };
    /** the form's accessible name, never drawn: a form takes no heading that
     *  restates the row that opened it */
    label: string;
    fields: AskField[];
    /** the button's verb */
    submit: string;
    /** resolves to "" when it landed, or the refusal */
    onsubmit: (values: Record<string, string>) => Promise<string>;
    onclose: () => void;
  } = $props();

  let el: HTMLFormElement | undefined = $state();
  let width = $state(0);
  /** the fields' first values: the form is made for one question and closed
   *  after, so later props are not followed */
  const initial = () => Object.fromEntries(fields.map((f) => [f.id, f.value]));
  let values = $state<Record<string, string>>(initial());
  let error = $state("");
  let sending = $state(false);

  const left = $derived(Math.max(4, Math.min(at.x, window.innerWidth - width - 4)));

  async function send(event: SubmitEvent) {
    event.preventDefault();
    if (sending) return;
    sending = true;
    try {
      error = await onsubmit({ ...values });
      if (!error) onclose();
    } finally {
      sending = false;
    }
  }

  function keydown(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    event.preventDefault();
    onclose();
  }

  function away(event: MouseEvent) {
    const target = event.target as Node | null;
    if (target && el?.contains(target)) return;
    onclose();
  }

  $effect(() => {
    const first = el?.querySelector<HTMLInputElement>("input");
    first?.focus({ preventScroll: true });
    first?.select();
  });
</script>

<svelte:window onkeydowncapture={keydown} onpointerdowncapture={away} onresize={onclose} />

<form class="ask" aria-label={label} bind:this={el} bind:offsetWidth={width}
  style="left: {left}px; top: {at.y}px" onsubmit={send}>
  <div class="fields" class:row={fields.length > 2}>
    {#each fields as f (f.id)}
      <label>
        <span class="muted">{f.label}</span>
        <input class:mono={f.mono} bind:value={values[f.id]} disabled={sending}
          autocomplete="off" spellcheck="false" />
      </label>
    {/each}
  </div>
  {#if error}<p class="bad">{error}</p>{/if}
  <div class="foot">
    <button type="button" class="ghost" onclick={onclose}>Cancel</button>
    <button type="submit" disabled={sending}>{submit}</button>
  </div>
</form>

<style>
  .ask {
    position: fixed;
    z-index: 20;
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-width: 420px;
    padding: 10px 12px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  .fields {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  /* label, species and a position read as one line, as an atom row does */
  .fields.row {
    flex-direction: row;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: var(--text-sm);
  }

  input {
    width: 16ch;
    border: 1px solid var(--line-strong);
    background: var(--bg);
    color: var(--fg);
  }

  .fields.row input {
    width: 7ch;
  }

  .mono {
    font-family: var(--mono-family);
  }

  .bad {
    margin: 0;
    max-width: 380px;
    color: var(--bad);
    font-size: var(--text-sm);
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
