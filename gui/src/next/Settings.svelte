<script lang="ts">
  /**
   * Settings (WP-2215), a modal dialog opened from the top bar's cog or ⌘,.
   *
   * The theme is three choices, Match system first and the default (the
   * maintainer, 2026-11-09). The version, which left the header with the
   * wordmark (WP-2214 rows 3 and 4), is the About line at the foot, as VS
   * Code's About is. Density and number format join when the pieces that draw
   * them land; a choice nothing reads is not offered.
   */
  import type { ThemeChoice } from "../lib/theme";

  let {
    choice,
    version = "",
    onchoose,
    onclose,
  }: {
    choice: ThemeChoice;
    version?: string;
    onchoose: (choice: ThemeChoice) => void;
    onclose: () => void;
  } = $props();

  const THEMES: Array<[ThemeChoice, string]> = [
    ["system", "Match system"],
    ["light", "Light"],
    ["dark", "Dark"],
  ];

  let done: HTMLButtonElement | undefined = $state();

  $effect(() => {
    done?.focus({ preventScroll: true });
  });

  function keydown(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    event.preventDefault();
    onclose();
  }
</script>

<svelte:window onkeydowncapture={keydown} />

<div class="scrim" role="presentation" onpointerdown={(e) => e.target === e.currentTarget && onclose()}>
  <div class="dlg" role="dialog" aria-modal="true" aria-labelledby="settings-title">
    <h2 id="settings-title">Settings</h2>
    <div class="row">
      <span class="label">Theme</span>
      <div class="segmented" role="radiogroup" aria-label="Theme">
        {#each THEMES as [value, label] (value)}
          <button class:on={choice === value} role="radio" aria-checked={choice === value}
            onclick={() => onchoose(value)}>{label}</button>
        {/each}
      </div>
    </div>
    <div class="foot">
      <span class="about">rietx <span class="num">{version}</span></span>
      <button class="ghost" bind:this={done} onclick={onclose}>Done</button>
    </div>
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 30;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 72px;
    background: color-mix(in srgb, var(--fg) 22%, transparent);
  }

  .dlg {
    min-width: 440px;
    padding: 18px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  h2 {
    margin: 0 0 14px;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .label {
    flex: 0 0 92px;
    color: var(--muted);
  }

  .foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 22px;
  }

  .about {
    color: var(--muted);
  }

  /* a number, so mono (`gui/STYLE.md` § Type) */
  .about .num {
    font-family: var(--mono-family);
  }
</style>
