<script lang="ts">
  /** The first-run checklist (WP-1017).
   *
   * **Non-modal, and never a wizard.** The onboarding argument this WP settled
   * is that a first-time user should be looking at the real interface from the
   * first second, so this is a strip above the tab strip that can be ignored
   * and dismissed — not a dialog over the app, and not a tour that moves the
   * pointer. It teaches the loop and then goes away.
   *
   * **Every step is derived, never stored.** A step is done because the
   * project says so — it has a phase, a result exists — so the strip cannot
   * disagree with the app, and a checkout that throws the curves away
   * correctly un-ticks `Run`. The one exception is `Read the report`, which is
   * about the person rather than the project and is therefore session-local:
   * persisting it would be storing that somebody looked at a tab.
   *
   * Only the dismissal is written (`ProjectDoc.ui.first_run`), on the verb like
   * every other `ui` key. There is no automatic write when the last step
   * completes: a strip that saved something the user never asked it to would
   * be a surprise write during what is meant to be the safest hour of using
   * the app.
   */
  interface Step {
    id: string;
    label: string;
    done: boolean;
    hint: string;
    tab?: string;
  }

  let {
    hasPhase,
    hasResult,
    reportSeen,
    busy,
    ongo,
    ondismiss,
  }: {
    hasPhase: boolean;
    hasResult: boolean;
    reportSeen: boolean;
    busy: boolean;
    ongo: (tab: string) => void;
    ondismiss: () => void;
  } = $props();

  const steps = $derived<Step[]>([
    {
      id: "project",
      label: "Open a project",
      done: true,
      hint: "the pattern, the structure and the instrument are in it",
    },
    {
      id: "phase",
      label: "Have a phase to refine",
      done: hasPhase,
      hint: hasPhase
        ? "the model the fit will move"
        : "no phase yet — pick peaks, index them, and adopt a cell",
      tab: hasPhase ? undefined : "peaks",
    },
    {
      id: "run",
      label: "Run the fit",
      done: hasResult,
      hint: hasResult
        ? "every stage left a node in the history"
        : "press Refine, or ⌘⏎",
    },
    {
      id: "report",
      label: "Read the report",
      done: reportSeen,
      hint: "what the package will and will not stand behind",
      tab: "report",
    },
  ]);

  const remaining = $derived(steps.filter((s) => !s.done).length);
</script>

<section class="checklist" aria-label="getting started">
  <div class="head">
    <strong>Getting started</strong>
    <span class="muted">
      {#if remaining === 0}
        edit, run, read, and go back to any state in History
      {:else}
        {remaining} left · this strip is only here until you dismiss it
      {/if}
    </span>
    <span class="spacer"></span>
    <button class="ghost" onclick={ondismiss} disabled={busy}
      title={busy ? "a run is in flight" : "hide this for this project"}
      >Dismiss</button>
  </div>
  <ol>
    {#each steps as step (step.id)}
      <li class:done={step.done}>
        <span class="mark" aria-hidden="true">{step.done ? "✓" : "○"}</span>
        <span class="what">
          {#if step.tab && !step.done}
            <button class="link" onclick={() => ongo(step.tab!)}>{step.label}</button>
          {:else}
            {step.label}
          {/if}
        </span>
        <span class="muted">{step.hint}</span>
      </li>
    {/each}
  </ol>
</section>

<style>
  .checklist {
    border: 1px solid var(--line);
    border-radius: var(--r-control);
    background: var(--panel);
    margin-bottom: 8px;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    font-size: var(--text-sm);
    padding: 6px 8px;
    border-bottom: 1px solid var(--line);
  }
  .spacer {
    flex: 1;
  }
  ol {
    margin: 0;
    padding: 6px 8px;
    list-style: none;
  }
  li {
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-size: var(--text-sm);
    padding: 2px 0;
  }
  li.done .what {
    color: var(--muted);
  }
  .mark {
    color: var(--muted);
    width: 1em;
  }
  li.done .mark {
    color: var(--ok);
  }
  .what {
    font-weight: 600;
  }
</style>
