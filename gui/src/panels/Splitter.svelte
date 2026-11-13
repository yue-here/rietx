<script lang="ts">
  /**
   * One grip, wherever two panes meet.
   *
   * The rule it carries is `Console.svelte`'s, generalised rather than copied:
   * **the component reports a size and never writes one.**  The pane's width or
   * height belongs to whoever owns the state it is persisted from — the shell,
   * for every `ProjectDoc.ui` key (WP-1005) — so this emits `(size, done)` and
   * lets that owner decide what to render and when to save.  `done` is the
   * difference between a live drag and a round trip: false on every pointer
   * move, true once on release, which is what keeps a drag from POSTing per
   * pixel.
   *
   * `extent` is a function rather than a number because the space two panes
   * share is only knowable at grab time — a prop read at render would be a
   * measurement from before the layout that matters.
   */
  import { axisOf, clampSize, dragged, type Grow } from "../lib/resize";

  let {
    size,
    grow = "up",
    min = 40,
    keep = 120,
    flow = "overlay",
    extent = () => 0,
    onsize,
    onreset,
    title = "drag to resize",
  }: {
    /** the pane's current size in px, as the owner is rendering it */
    size: number;
    grow?: Grow;
    /** the floor a drag cannot cross */
    min?: number;
    /** how much of the pane on the other side must survive */
    keep?: number;
    /** `overlay` sits on the pane's own edge and needs a positioned ancestor;
     *  `inline` is a flex item *between* two panes, which is what a scrolling
     *  pane needs — an absolute grip inside `overflow: auto` scrolls away with
     *  the content it is supposed to be an edge of */
    flow?: "overlay" | "inline";
    /** the extent the two panes share, measured when the drag starts */
    extent?: () => number;
    onsize: (size: number, done: boolean) => void;
    /** a double-click puts the pane back to its default size, as a VS Code
     *  sash does (WP-2123); absent, a double-click does nothing */
    onreset?: () => void;
    title?: string;
  } = $props();

  const axis = $derived(axisOf(grow));
  let dragging = $state(false);

  function grab(event: PointerEvent) {
    const start = size;
    const from = axis === "y" ? event.clientY : event.clientX;
    const available = extent();
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
    event.preventDefault();
    dragging = true;

    let next = start;
    const move = (moved: PointerEvent) => {
      const at = axis === "y" ? moved.clientY : moved.clientX;
      next = clampSize(dragged(start, from, at, grow), min, keep, available);
      onsize(next, false);
    };
    const drop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", drop);
      dragging = false;
      onsize(next, true); // one write per drag, not one per pixel
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", drop);
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="grip" data-axis={axis} data-grow={grow} data-flow={flow} class:dragging
  onpointerdown={grab} ondblclick={() => onreset?.()} {title}></div>

<style>
  .grip[data-flow="overlay"] {
    position: absolute;
    z-index: 3;
  }

  .grip[data-flow="inline"] {
    flex: 0 0 5px;
    align-self: stretch;
    border-left: 1px solid var(--line);
  }

  .grip[data-flow="inline"][data-axis="x"] {
    cursor: ew-resize;
  }

  .grip[data-flow="inline"][data-axis="y"] {
    cursor: ns-resize;
  }

  .grip[data-flow="overlay"][data-axis="y"] {
    left: 0;
    right: 0;
    height: 7px;
    cursor: ns-resize;
  }

  .grip[data-flow="overlay"][data-axis="x"] {
    top: 0;
    bottom: 0;
    width: 7px;
    cursor: ew-resize;
  }

  .grip[data-flow="overlay"][data-grow="up"] {
    top: -3px;
  }

  .grip[data-flow="overlay"][data-grow="down"] {
    bottom: -3px;
  }

  .grip[data-flow="overlay"][data-grow="left"] {
    left: -3px;
  }

  .grip[data-flow="overlay"][data-grow="right"] {
    right: -3px;
  }

  .grip:hover,
  .grip.dragging {
    background: color-mix(in srgb, var(--accent) 35%, transparent);
  }
</style>
