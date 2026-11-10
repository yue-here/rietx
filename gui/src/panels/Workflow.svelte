<script lang="ts">
  /**
   * A workflow that is not built yet, in the model panel (WP-2204).
   *
   * The design round drew each placeholder as its steps across the top of the
   * panel and, for the step chosen, a heading over a dashed box saying what the
   * step will hold (round 4, 2026-11-07). The box opens with "Not built yet",
   * so the panel never reads as a feature with nothing in it. The step strip is
   * the Peaks tab's (WP-2202): the tab register, each word carrying its number.
   */
  import { workflow, type PlaceholderId } from "../lib/workflows";

  let { id }: { id: PlaceholderId } = $props();

  const steps = $derived(workflow(id).steps ?? []);
  let step = $state(0);
  // a different placeholder starts at its first step
  $effect.pre(() => {
    id;
    step = 0;
  });
  const shown = $derived(steps[Math.min(step, steps.length - 1)]);
</script>

<div class="wf">
  <nav class="steps" aria-label="Steps">
    {#each steps as entry, i (entry.name)}
      {#if i}<span class="arrow muted" aria-hidden="true">›</span>{/if}
      <button class="tab" class:on={step === i} aria-current={step === i ? "step" : undefined}
        onclick={() => (step = i)}><span class="n mono">{i + 1}</span> {entry.name}</button>
    {/each}
  </nav>
  {#if shown}
    <div class="body">
      <h3>{shown.heading}</h3>
      <div class="box muted">
        <p class="not-built">Not built yet.</p>
        <p>{shown.body}</p>
      </div>
    </div>
  {/if}
</div>

<style>
  .wf {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .steps {
    flex: 0 0 auto;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    border-bottom: 1px solid var(--line);
  }

  .steps .n {
    color: var(--muted);
    margin-right: var(--s1);
  }

  .arrow {
    padding: 0 var(--s1);
  }

  .body {
    padding: var(--s3);
  }

  /* sentence case, the maintainer's heading ruling of 2026-11-06 */
  h3 {
    margin: 0 0 var(--s2);
    font-size: var(--text);
    font-weight: 600;
    color: var(--fg);
    text-transform: none;
    letter-spacing: normal;
  }

  .box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 120px;
    padding: var(--s3);
    border: 1px dashed var(--line);
    border-radius: 8px;
    text-align: center;
  }

  .box p {
    margin: 0;
  }

  .box p.not-built {
    margin-bottom: var(--s1);
    color: var(--fg);
  }
</style>
