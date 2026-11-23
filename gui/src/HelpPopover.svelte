<script module lang="ts">
  /**
   * The app's one help popover (WP-1203), as a component each page mounts once
   * (WP-2244). It was markup in `App.svelte`, so the rebuilt page at `/next`
   * had none, and every `<Help>` term there opened nothing.
   *
   * Two halves, because a context reaches only a component's descendants and
   * the popover is a sibling of the panels that hold the terms. `provideHelp()`
   * is called in a page's own script: it sets the opener every `<Help>` reads
   * and returns the state. `<HelpPopover {host} {corpus} />` is placed in that
   * page's markup and draws the state.
   *
   * One rather than one-per-term because two open explanations is a state
   * nobody asked for, and because the popover has to escape every panel's
   * `overflow: auto`: it is `position: fixed` in viewport coordinates, which
   * is what `getBoundingClientRect` returns and what `lib/help.ts:place`
   * consumes.
   */
  import { onDestroy, setContext } from "svelte";

  import { HELP_CONTEXT, type HelpOpener, type HelpRequest } from "./lib/helpContext";

  /** What is open, and on which term. */
  export class HelpHost implements HelpOpener {
    node = $state<HTMLElement | null>(null);
    request = $state<HelpRequest | null>(null);
    anchor = $state<DOMRect | null>(null);
    /** the drawn popover, bound by `<HelpPopover>` */
    el = $state<HTMLElement | null>(null);
    size = $state({ width: 0, height: 0 });
    /** the term the popover last took focus for. A plain field rather than
     *  `$state`: it must not be a dependency of the effect that writes it. */
    focusedFor: HTMLElement | null = null;

    isOpen(node: HTMLElement): boolean {
      return this.node === node;
    }

    toggle(node: HTMLElement, request: HelpRequest): void {
      if (this.node === node) {
        this.close();
        return;
      }
      this.node = node;
      this.request = request;
      this.anchor = node.getBoundingClientRect();
      this.size = { width: 0, height: 0 };
    }

    /** `refocus` is the caller's claim (Esc); holding focus is the popover's own.
     *
     *  A click away must not steal focus back from whatever was clicked, so the
     *  second test is `contains(activeElement)` rather than "was open": the only
     *  time closing owes the term its focus is when the popover had it, which
     *  since the popover takes focus on open is every keyboard route out. */
    close(refocus = false): void {
      const held = this.el?.contains(document.activeElement) === true;
      if (refocus || held) this.node?.focus({ preventScroll: true });
      this.node = null;
      this.request = null;
      this.anchor = null;
      this.size = { width: 0, height: 0 };
      this.focusedFor = null;
    }
  }

  /** Set the page's help opener and return its state. Call it once, in the
   *  page's own script, before any panel mounts.
   *
   *  Esc is taken here, on the window in the capture phase, rather than in the
   *  popover's markup: this listener is added before any panel's or layer's,
   *  so it runs first, and `stopImmediatePropagation` keeps the same Esc from
   *  also closing a dialog the term sits in or cancelling a run. Esc means
   *  "close the thing that just opened", and the popover is drawn over every
   *  layer.
   *
   *  A press inside the popover is held back from every later window listener
   *  the same way. A layer closes on a press outside itself, and the popover
   *  explaining one of its labels floats outside it, so without this the
   *  stage settings closed when the person clicked the explanation. Holding
   *  it here covers every layer, present and future; the press's default
   *  action, a link's navigation or a text selection, is untouched. */
  export function provideHelp(): HelpHost {
    const host = new HelpHost();
    setContext<HelpOpener>(HELP_CONTEXT, host);
    const onkey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !host.request) return;
      event.stopImmediatePropagation();
      event.preventDefault();
      host.close(true);
    };
    const onpress = (event: Event) => {
      if (host.el?.contains(event.target as Node | null)) event.stopImmediatePropagation();
    };
    const presses = ["pointerdown", "mousedown", "click"] as const;
    window.addEventListener("keydown", onkey, true);
    for (const kind of presses) window.addEventListener(kind, onpress, true);
    onDestroy(() => {
      window.removeEventListener("keydown", onkey, true);
      for (const kind of presses) window.removeEventListener(kind, onpress, true);
    });
    return host;
  }
</script>

<script lang="ts">
  import { manualUrl, place, resolve, splitKey, type HelpCorpus } from "./lib/help";

  let { host, corpus }: { host: HelpHost; corpus: HelpCorpus | null } = $props();

  let viewport = $state({ width: window.innerWidth, height: window.innerHeight });

  const entry = $derived(host.request?.key ? resolve(corpus, host.request.key) : null);
  const link = $derived(manualUrl(corpus, entry));
  /** a key and a title together: the title is a summary about one row, which
   *  stands in for the entry's words while the entry still gives the manual
   *  link (the candidate table's relations, the maintainer 2026-11-23) */
  const summary = $derived(!!host.request?.key && !!host.request?.title);
  const title = $derived(summary ? host.request!.title!
    : entry?.title ?? host.request?.title ?? host.request?.key ?? "");
  const body = $derived(summary ? host.request?.text ?? ""
    : entry?.description ?? host.request?.text ?? "");
  /** the name behind a labelled term: a chip says `at bound`, and the flag it
   *  stands for is `position_at_bound`, which nothing else on screen shows
   *  (WP-1209) — so the popover carries it, and only where a label hid it:
   *  `excluded` labelled `excluded` hid nothing */
  const code = $derived.by(() => {
    const name = host.request?.key ? splitKey(host.request.key)?.name ?? null : null;
    return entry?.label && name && entry.label !== name ? name : null;
  });
  const placement = $derived(host.anchor
    ? place(host.anchor, viewport, host.size)
    : { left: 0, top: 0, flipped: false });

  /* The size is *measured* rather than declared: the flip decision needs the
   * rendered height, and a max-width in CSS plus a paragraph of prose is not a
   * height anything here could compute. The effect runs after the DOM update
   * and before the browser paints, so the correction is not a frame the eye
   * can see; under jsdom every measurement is zero, which is why the
   * arithmetic is tested in `lib/help.test.ts` and not here.
   *
   * It reads the *rendered* body, not only the request: a corpus arriving
   * after a term was opened grows the body under a height measured from "Not
   * described yet.", and this effect re-measures rather than leaving `place` a
   * stale number. */
  $effect(() => {
    const el = host.el;
    if (!el || !host.request) return;
    void [title, body, entry, link];
    const width = el.offsetWidth;
    const height = el.offsetHeight;
    if (width !== host.size.width || height !== host.size.height) {
      host.size = { width, height };
    }
  });

  /* The popover takes focus, because it is a `role="dialog"` and a dialog
   * nobody is in announces nothing: Tab from an activated term went to the next
   * input in the row, leaving the popover open behind the cursor and its
   * `in the manual →` link reachable only by tabbing the whole app. Esc and a
   * second activation hand focus back to the term (`HelpHost.close`).
   *
   * `preventScroll` is load-bearing rather than tidy: a scroll closes the
   * popover, so a focus that scrolled anything would close what it just
   * opened. */
  $effect(() => {
    const el = host.el;
    const node = host.node;
    if (!el || !node) return;
    if (host.focusedFor === node) return;
    host.focusedFor = node;
    el.focus({ preventScroll: true });
  });

  // A resize or a scroll moves the anchor out from under the popover, and
  // there is nothing useful to do about it: re-measuring would chase a term
  // that may have left the screen entirely. Closing is honest and costs one
  // click.
  function resized() {
    viewport = { width: window.innerWidth, height: window.innerHeight };
    if (host.request) host.close();
  }

  // Only a scroll of a box that holds the term moves it. The console follows a
  // run by scrolling its own pane, and that scroll must not close an
  // explanation open elsewhere.
  function scrolled(event: Event) {
    if (!host.request) return;
    const box = event.target as Node | null;
    if (box && host.node && !box.contains(host.node)) return;
    host.close();
  }

  /** A click outside the popover and its own term closes it. */
  function clickAway(event: MouseEvent) {
    if (!host.request) return;
    const target = event.target as Node | null;
    if (target && (host.el?.contains(target) || host.node?.contains(target))) return;
    host.close();
  }
</script>

<svelte:window onclick={clickAway} onresize={resized} onscrollcapture={scrolled} />

{#if host.request}
  <!-- `data-flipped` is the only way to tell a flip from a clamp that landed on
       the same pixel — a popover taller than the viewport is clamped to the top
       margin, which is exactly where flipping it would also put it — so it is
       what a browser pass reads to check the rule (WP-1203). -->
  <div class="popover" bind:this={host.el} role="dialog" aria-label={title}
       tabindex="-1" data-flipped={placement.flipped}
       style="left: {placement.left}px; top: {placement.top}px">
    <h2>{title}</h2>
    {#if body}
      <p>{body}</p>
    {:else if !summary}
      <!-- a key that resolves to nothing. Saying so is the honest empty
           state: the corpus is where a description is owed, and inventing one
           here would put a wrong sentence under a real name. -->
      <p class="muted">Not described yet.</p>
    {/if}
    {#if entry && (entry.unit || entry.default || entry.typical || entry.modes?.length || code)}
      <dl>
        {#if code}<dt>Name</dt><dd class="mono">{code}</dd>{/if}
        {#if entry.unit}<dt>Unit</dt><dd>{entry.unit}</dd>{/if}
        {#if entry.default}<dt>Default</dt><dd class="mono">{entry.default}</dd>{/if}
        {#if entry.modes?.length}
          <dt>Modes</dt><dd class="mono">{entry.modes.join(", ")}</dd>
        {/if}
        {#if entry.typical}<dt>Typical</dt><dd>{entry.typical}</dd>{/if}
      </dl>
    {/if}
    {#if link}
      <a class="link" href={link} target="_blank" rel="noreferrer noopener"
        >in the manual →</a>
    {/if}
  </div>
{/if}
