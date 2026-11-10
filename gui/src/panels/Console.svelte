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
   * It is a **sized** pane, not a flexible one. Sharing the sidebar with
   * `flex: 1 1 auto` gave the log half the column and the parameter table the
   * other half, which is the wrong split for a panel you read in glances: the
   * table is the work and the console is the receipt. So the height is explicit,
   * draggable from the top edge, and persisted through `ProjectDoc.ui` — the
   * owner of that key is the shell, as it is for the disclosure flag, so this
   * component reports a new height and never writes one.
   *
   * The drag itself is `Splitter.svelte`'s since WP-1029, which is where that
   * last rule now lives for all three splits in the app.
   */
  import { clampSize } from "../lib/resize";
  import Splitter from "./Splitter.svelte";

  let {
    lines,
    dropped,
    height = 150,
    onresize = (_height: number) => {},
  }: {
    lines: string[];
    dropped: number;
    height?: number;
    onresize?: (height: number) => void;
  } = $props();

  /** Header only — the floor a drag can reach, and what "collapsed" means. */
  const SHUT = 26;
  /** How much of the panel above must survive a drag. */
  const KEEP = 120;

  let node: HTMLPreElement | undefined = $state();
  let section: HTMLElement | undefined = $state();
  let pinned = $state(true);
  /** what a drag or a collapse set locally; `null` means "whatever was saved".
   *  Derived rather than copied from the prop, so this component has one height
   *  and not two that have to be kept in step. */
  let local = $state<number | null>(null);
  const size = $derived(Math.max(SHUT, local ?? height));

  /** The height to restore when the header is clicked open again. Plain, not
   *  `$state`: it is only ever read inside an event handler. */
  let restore = 150;
  $effect(() => {
    if (height > SHUT) restore = height;
  });

  $effect(() => {
    lines;
    if (pinned && node) node.scrollTop = node.scrollHeight;
  });

  function onScroll() {
    if (!node) return;
    pinned = node.scrollHeight - node.scrollTop - node.clientHeight < 24;
  }

  /** never drag the panel above out of existence */
  function clamp(value: number): number {
    return clampSize(value, SHUT, KEEP, section?.parentElement?.clientHeight ?? 0);
  }

  function sized(next: number, done: boolean) {
    local = next;
    if (!done) return;
    if (next > SHUT) restore = next;
    onresize(next);
  }

  function toggle() {
    if (size > SHUT) restore = size;
    local = size > SHUT ? SHUT : clamp(restore);
    onresize(local);
  }
</script>

<section class="console" bind:this={section} style:flex="0 0 {size}px"
  class:shut={size <= SHUT}>
  <Splitter {size} grow="up" min={SHUT} keep={KEEP} onsize={sized}
    extent={() => section?.parentElement?.clientHeight ?? 0} />
  <h2>
    <button class="caret ghost" onclick={toggle} title={size > SHUT ? "collapse" : "expand"}>
      {size > SHUT ? "▾" : "▸"} Console
    </button>
    {#if dropped > 0}
      <span class="warn" title="the server's event ring is 4096 frames">
        {dropped} frames dropped
      </span>
    {/if}
    {#if !pinned && size > SHUT}
      <button class="ghost" onclick={() => (pinned = true)}>follow</button>
    {/if}
  </h2>
  <pre bind:this={node} onscroll={onScroll}>{lines.join("\n")}</pre>
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    border-top: 1px solid var(--line);
    position: relative;
  }

  /* the section-heading register (app.css), doubling as this panel's own bar */
  h2 {
    margin: 0;
    padding: var(--s2) 10px var(--s1);
    display: flex;
    align-items: center;
    gap: var(--s3);
    flex: 0 0 auto;
  }

  /* a ghost button that *is* the heading — the register supplies the rest */
  .caret {
    color: var(--muted);
  }

  pre {
    flex: 1 1 auto;
    overflow: auto;
    margin: 0;
    padding: 2px 10px 8px;
    font: var(--mono);
    color: var(--fg);
    white-space: pre;
    min-height: 0;
  }

  section.shut pre {
    display: none;
  }

  /* a fact beside the heading, at a chip's size rather than the heading's */
  .warn {
    color: var(--warn);
    font-size: var(--text-xs);
  }
</style>
