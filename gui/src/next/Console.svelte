<script lang="ts">
  /**
   * The event log, and the API echo beside it.
   *
   * DESIGN.md's console story: what the GUI does is printed as the call a script
   * would have made, so the log doubles as a session transcript a user can
   * paste. Engine events arrive from the stream verbatim — every field of an
   * event's open `data` dict is rendered, so a field added to a kind shows up
   * here without this panel knowing about it.
   *
   * Since WP-2206 it is a tab of the bottom panel, which owns the height, the
   * drag and whether it shows (WP-1029's sized pane, one rank out). It fills its
   * pane and keeps only what is about the log: following the end, the dropped
   * frames, and Copy, the prototype's way to take the session into a script.
   */
  let {
    lines,
    dropped,
    shown = true,
  }: {
    lines: string[];
    dropped: number;
    /** Whether the pane is on screen. A hidden pane has no scroll height, so
     *  lines that arrived while it was hidden are followed when it shows. */
    shown?: boolean;
  } = $props();

  let node: HTMLDivElement | undefined = $state();
  let pinned = $state(true);
  let copied = $state(false);

  $effect(() => {
    lines;
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

  async function copy() {
    try {
      await navigator.clipboard.writeText(lines.join("\n") + "\n");
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      // no clipboard here (an insecure origin, a denied permission): the text
      // stays selectable, which is the fallback a reader already knows
      copied = false;
    }
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
      <button class="ghost" onclick={copy} disabled={!lines.length}
        title="Copy the session as text"><span class="slot"><span
          class:gone={copied}>Copy</span><span class:gone={!copied}>Copied</span></span></button>
    </div>
    <pre>{lines.join("\n")}</pre>
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

  pre {
    margin: 0;
    padding: var(--s1) 10px 8px;
    font: var(--mono);
    color: var(--fg);
    white-space: pre;
  }

  .warn {
    color: var(--warn);
  }
</style>
