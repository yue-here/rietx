<script lang="ts">
  /**
   * The status bar along the window's foot (WP-2207).
   *
   * The maintainer's frame of 2026-11-07: a top bar with a collapse button at
   * each end, and a status bar along the foot with the console toggle at its
   * left. The bars never change shape, so no toggle in them moves. The bar is
   * drawn without a project too, its toggle disabled, so opening one moves
   * nothing here.
   *
   * It also carries the run's state, moved out of the header. A slot whose
   * words change sits between the toggle and `Cancel` and takes the room left
   * between them, so a stage name of any length moves nothing; a long one is
   * cut with an ellipsis. `Cancel` sits at the right end, beside the state it
   * acts on.
   */
  import { modifier, runWords, toggleTitle } from "../lib/statusbar";
  import type { RunState } from "../lib/stream";

  let {
    project = false,
    open = false,
    run = null,
    busy = false,
    ontoggle = () => {},
    oncancel = () => {},
  }: {
    project?: boolean;
    open?: boolean;
    run?: RunState | null;
    busy?: boolean;
    ontoggle?: () => void;
    oncancel?: () => void;
  } = $props();

  const mod = modifier(typeof navigator === "undefined" ? "" : navigator.platform ?? "");
  const words = $derived(project ? runWords(run) : "");
  /** Closing a project leaves the shell's `open` set, with no panel to show. */
  const shown = $derived(project && open);
  const tone = $derived(
    run?.state === "cancelling" ? "warn"
      : run?.state === "running" ? "live"
      : run?.run.status === "failed" ? "bad" : "rest");
</script>

<footer class="statusbar">
  <button class="ghost toggle" aria-pressed={shown} disabled={!project}
    onclick={ontoggle} aria-label={shown ? "Hide the console" : "Show the console"}
    title={toggleTitle(project, shown, mod)}>
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" />
      <rect class="fill" x="2" y="9.5" width="12" height="3.5" /><path d="M1.5 9h13" />
    </svg>
    Console
  </button>
  <!-- `title` holds the words a narrow window cuts with an ellipsis -->
  <span class="run mono" data-state={run?.state ?? "idle"} data-tone={tone}
    role="status" title={words}>{words}</span>
  <button class="ghost" onclick={oncancel} disabled={!busy}>Cancel</button>
</footer>

<style>
  .statusbar {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: var(--s3);
    padding: var(--s1) var(--s2);
    border-top: 1px solid var(--line);
    background: var(--panel);
    font-size: var(--text-sm);
    color: var(--muted);
  }

  .toggle {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    color: var(--muted);
  }

  .toggle svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.4;
  }

  .toggle svg .fill {
    fill: currentColor;
    stroke: none;
    opacity: 0;
  }

  .toggle[aria-pressed="true"] svg .fill {
    opacity: 0.55;
  }

  /* the room between the toggle and Cancel, so its words move nothing */
  .run {
    flex: 1 1 0;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .run[data-tone="live"] {
    color: var(--fg);
  }

  .run[data-tone="warn"] {
    color: var(--warn);
  }

  .run[data-tone="bad"] {
    color: var(--bad);
  }
</style>
