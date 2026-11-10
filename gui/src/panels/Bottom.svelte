<script lang="ts">
  /**
   * The bottom panel: Console and History, across the window's foot (WP-2206).
   *
   * The maintainer asked on 2026-11-07 for a collapsible console showing what
   * the Python is doing and for a History tab. The prototype put both in one
   * panel above the status bar, as VS Code's panel holds Output and Terminal,
   * shown and hidden from the status bar's toggle and hidden at first.
   *
   * Both tabs stay mounted while hidden, as every panel does: a scrolled log or
   * a two-node comparison must survive a look at the other tab. The panel's
   * height is the shell's to persist (`ProjectDoc.ui.console_height`, the key
   * the Console's own pane used before, so a stored height carries over); this
   * component reports a new height and never writes one (WP-1029).
   */
  import { BOTTOM_TABS, type BottomTab } from "../lib/tabs";
  import Console from "./Console.svelte";
  import History from "./History.svelte";
  import Splitter from "./Splitter.svelte";

  let {
    open = false,
    tab = $bindable<BottomTab>("console"),
    height = 200,
    extent = () => 0,
    onresize = (_height: number) => {},
    lines,
    dropped,
    head = null,
    busy = false,
    say = (_line: string) => {},
    onmoved = () => {},
  }: {
    open?: boolean;
    tab?: BottomTab;
    height?: number;
    /** the height of the panes above, measured when a drag starts; this
     *  panel adds its own drawn height to it */
    extent?: () => number;
    onresize?: (height: number) => void;
    lines: string[];
    dropped: number;
    head?: string | null;
    busy?: boolean;
    say?: (line: string) => void;
    onmoved?: () => void;
  } = $props();

  /** The panel's floor: its tab strip and a few lines of log. */
  const BOTTOM_MIN = 90;
  /** The panes above must keep this much of the window through a drag. */
  const KEEP = 240;

  /** The height a double-click resets to, and the shell's default. */
  const BOTTOM_DEFAULT = 200;

  /** what a live drag sets; `null` once it lands, so the panel follows
   *  `height` again and another project's stored height is not overridden */
  let local = $state<number | null>(null);
  const size = $derived(Math.max(BOTTOM_MIN, local ?? height));
  /** The height the panel is drawn at, 0 while hidden. The CSS `max-height`
   *  can hold it under `size`, so a drag starts from this one, or the grip
   *  does nothing until the pointer has crossed the difference. */
  let drawn = $state(0);

  function sized(next: number, done: boolean) {
    local = done ? null : next;
    if (done) onresize(next);
  }

  function reset() {
    local = null;
    onresize(BOTTOM_DEFAULT);
  }
</script>

<section class="bottom" class:hidden={!open} style:flex="0 0 {size}px"
  bind:offsetHeight={drawn} aria-label="console and history">
  <Splitter size={drawn || size} grow="up" min={BOTTOM_MIN} keep={KEEP} onsize={sized}
    onreset={reset} extent={() => extent() + drawn}
    title="drag to resize the console and history; double-click resets it" />
  <nav class="tabs" aria-label="console and history">
    {#each BOTTOM_TABS as entry (entry.id)}
      <button class="tab" class:on={tab === entry.id} onclick={() => (tab = entry.id)}
        >{entry.label}</button>
    {/each}
  </nav>
  <div class="pane" class:hidden={tab !== "console"}>
    <Console {lines} {dropped} shown={open && tab === "console"} />
  </div>
  <div class="pane" class:hidden={tab !== "history"}>
    <History {head} {busy} {say} {onmoved} />
  </div>
</section>

<style>
  .bottom {
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 0;
    /* a stored height outliving the window it was chosen in must not take the
       panes above; the drag clamps against the live extent, this against a
       resize, which no drag is present for */
    max-height: max(90px, calc(100vh - 300px));
    border-top: 1px solid var(--line);
    background: var(--panel);
  }

  .bottom.hidden {
    display: none;
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--line);
    flex: 0 0 auto;
  }

  .pane {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .pane.hidden {
    display: none;
  }
</style>
