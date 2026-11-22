<script lang="ts">
  /**
   * The Console: the session as a script (WP-2212).
   *
   * DESIGN.md's console story: what the GUI does is printed as the call a script
   * would have made, so the log doubles as a session transcript a user can
   * paste. Each entry is one action: a timestamp, its calls behind `>>>` (each
   * further call behind `...`), and what came back, muted. Comments are italic,
   * and string literals take `--code-string`. A run's engine events fold into
   * one muted line under the call that started it, closed by default (the
   * maintainer's ruling of 2026-11-21); a click lists them. Every field of an
   * event's open `data` dict is rendered, so a field added to a kind shows up
   * here without this panel knowing about it.
   *
   * The prompt sits in a fixed gutter, so every line's text starts at one edge
   * whatever its kind, and the fold's chevron hangs in the same gutter.
   *
   * Since WP-2206 it is a tab of the bottom panel, which owns the height, the
   * drag and whether it shows (WP-1029's sized pane, one rank out). It fills its
   * pane and keeps only what is about the log: following the end, the dropped
   * frames, and Copy, which takes the calls alone into a script.
   */
  import { clock, copyText, entries, foldSummary, pieces, type Line } from "./console";

  let {
    lines,
    dropped,
    shown = true,
  }: {
    lines: readonly Line[];
    dropped: number;
    /** Whether the pane is on screen. A hidden pane has no scroll height, so
     *  lines that arrived while it was hidden are followed when it shows. */
    shown?: boolean;
  } = $props();

  let node: HTMLDivElement | undefined = $state();
  let pinned = $state(true);
  let copied = $state(false);
  /** the entries whose events are listed; an entry's id is stable */
  let open = $state.raw<ReadonlySet<number>>(new Set());

  const drawn = $derived(entries(lines));
  const copyable = $derived(copyText(lines));

  $effect(() => {
    drawn;
    if (shown && pinned && node) node.scrollTop = node.scrollHeight;
  });

  function onScroll() {
    if (!node) return;
    pinned = node.scrollHeight - node.scrollTop - node.clientHeight < 24;
  }

  function follow() {
    pinned = true;
    if (node) node.scrollTop = node.scrollHeight;
  }

  function toggle(id: number) {
    const next = new Set(open);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    open = next;
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(copyable);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      // no clipboard here (an insecure origin, a denied permission): the text
      // stays selectable, which is the fallback a reader already knows
      copied = false;
    }
  }

  /** The prompt a line takes: the first call of an entry `>>>`, a further one
   *  `...`, and nothing for what came back. */
  function prompts(entryLines: readonly Line[]): string[] {
    let seen = false;
    return entryLines.map((l) => {
      if (l.kind !== "call") return "";
      const p = seen ? "..." : ">>>";
      seen = true;
      return p;
    });
  }
</script>

<section class="console" aria-label="console">
  <div class="scroll" bind:this={node} onscroll={onScroll}>
    <!-- sticky at the top of the log, as the prototype's Copy is; both buttons
         always drawn and each word in a fixed slot, so a press moves nothing -->
    <div class="bar">
      {#if dropped > 0}
        <span class="warn" title="the server's event ring is 4096 frames">
          {dropped} frames dropped
        </span>
      {/if}
      <button class="ghost" class:gone={pinned} onclick={follow}
        title="Scroll to the newest line and stay there">Follow</button>
      <button class="ghost" onclick={copy} disabled={!copyable}
        title="Copy the calls as a script"><span class="slot"><span
          class:gone={copied}>Copy</span><span class:gone={!copied}>Copied</span></span></button>
    </div>
    <div class="log">
      {#each drawn as e (e.id)}
        <div class="entry" data-entry={e.id}>
          <div class="ln t">{clock(e.t)}</div>
          {#each e.lines as line, i (i)}
            {@const prompt = prompts(e.lines)[i]}
            <div class="ln {line.kind}" data-kind={line.kind}>
              {#if prompt}<span class="pr" aria-hidden="true">{prompt} </span>{/if}{#if line.kind === "call"}{#each pieces(line.text) as piece, j (j)}{#if piece.cls}<span
                class={piece.cls}>{piece.text}</span>{:else}{piece.text}{/if}{/each}{:else}{line.text}{/if}
            </div>
          {/each}
          {#if e.events.length}
            <button class="ln fold pick" aria-expanded={open.has(e.id)} onclick={() => toggle(e.id)}><span
              class="pr chev" aria-hidden="true">{open.has(e.id) ? "▾" : "▸"}</span>{foldSummary(e.events)}</button>
            {#if open.has(e.id)}
              {#each e.events as line, k (k)}
                <div class="ln event">{line.text}</div>
              {/each}
            {/if}
          {/if}
        </div>
      {/each}
    </div>
  </div>
</section>

<style>
  section {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow: auto;
  }

  .bar {
    position: sticky;
    top: 0;
    /* each line is positioned for its prompt gutter and would paint over it */
    z-index: 1;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: var(--s2);
    padding: var(--s1) var(--s3) 0;
    background: var(--panel);
  }

  .gone {
    visibility: hidden;
  }

  /* the two words share one grid cell, so the button is as wide as the
     longer and keeps that width whichever shows */
  .slot {
    display: inline-grid;
  }

  .slot > span {
    grid-area: 1 / 1;
  }

  .log {
    padding: var(--s1) 10px 8px;
    font: var(--mono);
    color: var(--fg);
  }

  /* every line's text starts at the gutter's edge; the prompt and the fold's
     chevron hang in the gutter, out of the copied text's way */
  .ln {
    position: relative;
    padding-left: 4ch;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .pr {
    position: absolute;
    left: 0;
    color: var(--muted);
    user-select: none;
  }

  .t,
  .output,
  .refusal,
  .event,
  .fold {
    color: var(--muted);
  }

  .comment,
  .cm {
    color: var(--muted);
    font-style: italic;
  }

  .str {
    color: var(--code-string);
  }

  .event {
    padding-left: 6ch;
  }

  /* the fold is a row of the log that answers a click: a `.pick`, with the
     row's own hover ground */
  .fold {
    display: block;
    width: 100%;
    cursor: pointer;
  }

  .fold:hover {
    background: var(--hover);
  }

  .warn {
    color: var(--warn);
  }
</style>
